"""Financial totals, callback isolation and public release pages."""

import asyncio
import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from itsdangerous import TimestampSigner
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.admin.billing import PaymentFilters, lifetime_summary, payment_page
from app.admin.models import Complaint
from app.admin.service import purge_unverified
from app.auth.models import User
from app.billing.models import ArchivedPayment, CardPayment, Entitlement, StarPayment
from app.billing.products import get_product
from app.billing.service import grant_product_access, subscription_days
from app.config import get_settings
from app.db import get_session
from app.main import app
from app.projects.models import Project
from app.tasks.models import Task


def sign_in(client: AsyncClient, user: User) -> None:
    client.cookies.clear()
    data = base64.b64encode(json.dumps({"user_id": str(user.id), "epoch": 0}).encode())
    client.cookies.set(
        "session", TimestampSigner(get_settings().app_secret_key).sign(data).decode()
    )


def card(user: User, number: int, **kwargs) -> CardPayment:
    values = dict(
        user_id=user.id,
        inv_id=number,
        provider="robokassa",
        provider_payment_id=str(number),
        product_code="pro_1m",
        amount_kopecks=19900,
        status="succeeded",
        paid_at=datetime.now(UTC),
    )
    values.update(kwargs)
    return CardPayment(**values)


async def test_ledger_filters_totals_pagination_csv_and_root(client, db_session):
    owner = User(email="owner@example.com", is_admin=True, timezone="Europe/Moscow")
    buyer = User(
        email="=buyer@example.com", tier="pro", pro_until=datetime.now(UTC) + timedelta(days=30)
    )
    db_session.add_all([owner, buyer])
    await db_session.flush()
    db_session.add_all([card(buyer, n) for n in range(1, 13)])
    db_session.add_all(
        [
            card(buyer, 20, status="refunded", refunded_at=datetime.now(UTC)),
            card(buyer, 21, is_test=True),
            card(buyer, 22, status="pending", paid_at=None),
            StarPayment(
                user_id=buyer.id,
                product_code="pro_1m",
                stars_amount=250,
                telegram_payment_charge_id="charge1",
                invoice_payload="test",
            ),
            StarPayment(
                user_id=buyer.id,
                product_code="pro_1m",
                stars_amount=250,
                telegram_payment_charge_id="charge2",
                invoice_payload="test",
                status="refunded",
            ),
            Complaint(
                user_id=buyer.id,
                body="A long complaint " * 20,
                admin_note="');window.injected=true;//",
            ),
        ]
    )
    await db_session.commit()
    summary = await lifetime_summary(db_session)
    assert (summary.buyers, summary.payments, summary.rub_gross, summary.rub_refunded) == (
        1,
        15,
        258700,
        19900,
    )
    assert (summary.stars_net, summary.pending, summary.active_subscriptions) == (250, 1, 1)
    result = await payment_page(db_session, PaymentFilters(per_page=10, page=99), "Europe/Moscow")
    assert (result.total, result.page, result.pages, len(result.items)) == (16, 2, 2, 6)
    assert (await payment_page(db_session, PaymentFilters(q="%"), None)).total == 0
    assert (await payment_page(db_session, PaymentFilters(mode="test"), None)).total == 1
    sign_in(client, owner)
    response = await client.get("/app/root?billing_provider=robokassa&billing_per_page=10")
    assert response.status_code == 200, response.text[:500]
    assert "Журнал платежей" in response.text and "billing_page=2" in response.text
    assert response.headers["cache-control"] == "no-store"
    export = await client.get("/api/admin/billing/transactions.csv?provider=robokassa&status=paid")
    assert export.status_code == 200
    assert "'=buyer@example.com" in export.text
    assert len(export.text.splitlines()) == 13  # header + 12 real paid cards
    assert (
        await client.get("/api/admin/billing/transactions?since=2026-10-29&until=2026-10-01")
    ).status_code == 422
    sign_in(client, buyer)
    for path in ["/app/root", "/api/admin/billing/overview", "/api/admin/billing/transactions.csv"]:
        assert (await client.get(path)).status_code == 403


async def test_card_callback_modes_amounts_repeats_and_private_status(
    client, db_session, monkeypatch
):
    settings = get_settings()
    monkeypatch.setattr(settings, "robokassa_password2", "live-secret")
    monkeypatch.setattr(settings, "robokassa_test_password2", "test-secret")
    # The invoice remembers its original mode after configuration changes.
    monkeypatch.setattr(settings, "robokassa_test_mode", True)
    buyer = User(email="buyer@example.com")
    stranger = User(email="stranger@example.com")
    db_session.add_all([buyer, stranger])
    await db_session.flush()
    db_session.add_all(
        [
            card(buyer, 80, status="pending", paid_at=None),
            card(buyer, 81, status="pending", paid_at=None, is_test=True),
        ]
    )
    await db_session.commit()

    async def callback(number=80, amount="199.00", secret="live-secret", code="pro_1m"):  # noqa: S107
        signature = hashlib.md5(f"{amount}:{number}:{secret}:Shp_code={code}".encode()).hexdigest()  # noqa: S324
        return await client.post(
            "/api/billing/robokassa/result",
            data={
                "OutSum": amount,
                "InvId": str(number),
                "Shp_code": code,
                "SignatureValue": signature,
            },
        )

    assert (await callback(amount="1.00")).status_code == 400
    assert (await callback(amount="NaN")).status_code == 400
    assert (await callback(secret="wrong")).status_code == 400
    assert (await callback(code="family_1m")).status_code == 400
    assert (await callback(number=81, secret="test-secret")).text == "OK81"
    await db_session.refresh(buyer)
    assert buyer.pro_until is None
    assert (await callback()).text == "OK80"
    await db_session.refresh(buyer)
    expiry = buyer.pro_until
    assert expiry and 29 <= (expiry - datetime.now(UTC)).days <= 30
    assert (await callback()).text == "OK80"
    await db_session.refresh(buyer)
    assert buyer.pro_until == expiry
    sign_in(client, stranger)
    assert (await client.get("/api/billing/cards/80/status")).status_code == 404
    sign_in(client, buyer)
    result = await client.get("/api/billing/cards/80/status")
    assert result.json()["status"] == "succeeded"
    assert result.headers["cache-control"] == "no-store"
    redirect = await client.get("/api/billing/robokassa/success?InvId=80")
    assert redirect.headers["location"] == "/app/today?payment_invoice=80"


async def test_simultaneous_callbacks_extend_once(client, db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "robokassa_password2", "concurrent-secret")
    buyer = User(email="race@example.com")
    db_session.add(buyer)
    await db_session.flush()
    db_session.add(card(buyer, 90, status="pending", paid_at=None))
    await db_session.commit()
    engine = create_async_engine(get_settings().test_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def independent_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = independent_session
    signature = hashlib.md5(b"199.00:90:concurrent-secret:Shp_code=pro_1m").hexdigest()  # noqa: S324
    try:
        results = await asyncio.gather(
            *[
                client.post(
                    "/api/billing/robokassa/result",
                    data={
                        "OutSum": "199.00",
                        "InvId": "90",
                        "Shp_code": "pro_1m",
                        "SignatureValue": signature,
                    },
                )
                for _ in range(2)
            ]
        )
        assert [r.text for r in results] == ["OK90", "OK90"]
        await db_session.refresh(buyer)
        assert buyer.pro_until and (buyer.pro_until - datetime.now(UTC)).days == 29
    finally:
        await engine.dispose()


async def test_cleanup_keeps_buyers_entitlements_and_activity(db_session):
    old = datetime.now(UTC) - timedelta(days=50)
    users = [
        User(email=f"empty-{i}@example.com", created_at=old, trial_ends_at=old) for i in range(4)
    ]
    db_session.add_all(users)
    await db_session.flush()
    db_session.add_all(
        [
            card(users[0], 100),
            Entitlement(user_id=users[1].id, feature="pdd_pro", source_code="pdd_pro_3m"),
            Project(user_id=users[2].id, name="Keep my project", slug="keep"),
        ]
    )
    await db_session.commit()
    assert await purge_unverified(db_session, older_than_days=30) == 1
    remaining = set((await db_session.scalars(select(User.email))).all())
    assert remaining == {u.email for u in users[:3]}


async def test_account_deletion_preserves_revenue_without_contact_data(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(get_settings(), "robokassa_password2", "archive-secret")
    user = User(email="delete-buyer@example.com")
    db_session.add(user)
    await db_session.flush()
    user_id = user.id
    db_session.add_all(
        [
            card(user, 110),
            card(user, 111, status="pending", paid_at=None),
            StarPayment(
                user_id=user.id,
                product_code="pro_1m",
                stars_amount=250,
                telegram_payment_charge_id="archive-star",
                invoice_payload="secret-payload",
            ),
        ]
    )
    await db_session.commit()
    before = await lifetime_summary(db_session)
    sign_in(client, user)
    response = await client.post("/api/profile/delete")
    assert response.status_code == 303
    assert await db_session.scalar(select(User.id).where(User.id == user_id)) is None
    assert not (await db_session.scalars(select(CardPayment))).all()
    archived = (await db_session.scalars(select(ArchivedPayment))).all()
    assert len(archived) == 3
    assert not hasattr(archived[0], "email") and not hasattr(archived[0], "invoice_payload")
    after = await lifetime_summary(db_session)
    assert after.rub_gross == before.rub_gross and after.stars_gross == before.stars_gross
    assert after.buyers == before.buyers == 1
    rows = await payment_page(db_session, PaymentFilters(), None)
    assert {row.email for row in rows.items} == {"Удалённый аккаунт"}
    for number in [110, 111, 111]:
        signature = hashlib.md5(  # noqa: S324 - provider protocol
            f"199.00:{number}:archive-secret:Shp_code=pro_1m".encode()
        ).hexdigest()
        result = await client.post(
            "/api/billing/robokassa/result",
            data={
                "OutSum": "199.00",
                "InvId": str(number),
                "Shp_code": "pro_1m",
                "SignatureValue": signature,
            },
        )
        assert result.text == f"OK{number}"
    assert (await lifetime_summary(db_session)).rub_gross == 39800
    from app.billing.stars import apply_successful_payment, sign_payload

    for charge in ["archive-star", "late-star", "late-star"]:
        await apply_successful_payment(
            db_session,
            telegram_payment_charge_id=charge,
            provider_payment_charge_id=None,
            payload=sign_payload("pro_1m", user_id),
            stars_amount=250,
        )
        await db_session.commit()
    assert (await lifetime_summary(db_session)).stars_gross == 500


async def test_annual_grant_and_lifetime_preservation(db_session):
    user = User(email="year@example.com")
    db_session.add(user)
    await db_session.flush()
    product = get_product("pro_12m")
    assert product and subscription_days(12) == 365
    now = datetime.now(UTC)
    await grant_product_access(db_session, user.id, product)
    assert user.pro_until and 364 <= (user.pro_until - now).days <= 365
    lifetime = get_product("pro_forever")
    assert lifetime
    await grant_product_access(db_session, user.id, lifetime)
    await grant_product_access(db_session, user.id, product)
    assert user.pro_until.year == 2099
    user.tier = "family"
    await grant_product_access(db_session, user.id, product)
    assert user.tier == "family"


async def test_annual_refund_reverses_full_year_once(db_session, monkeypatch):
    import httpx

    from app.billing import stars
    from app.telegram.models import TelegramLink

    monkeypatch.setattr(get_settings(), "telegram_bot_token", "fake-bot-token")
    now = datetime.now(UTC)
    user = User(email="refund@example.com", tier="pro", pro_until=now + timedelta(days=395))
    db_session.add(user)
    await db_session.flush()
    payment = StarPayment(
        user_id=user.id,
        product_code="pro_12m",
        stars_amount=2500,
        telegram_payment_charge_id="refund-year",
        invoice_payload="test",
    )
    db_session.add_all([payment, TelegramLink(user_id=user.id, chat_id=999)])
    await db_session.commit()
    calls = []

    async def fake_post(self, url, **kwargs):
        calls.append(url)
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    assert await stars.refund_payment(db_session, payment)
    await db_session.commit()
    assert user.pro_until == now + timedelta(days=30)
    assert await stars.refund_payment(db_session, payment)
    assert len(calls) == 1


async def test_updates_link_article_legacy_and_unknown(client):
    landing = await client.get("/")
    slug = "/changelog/subscriptions-owner-dashboard-and-mobile"
    assert slug in landing.text
    article = await client.get(slug)
    assert article.status_code == 200 and "Что изменилось" in article.text
    assert (await client.get("/changelog/2026-05-11")).status_code == 200
    assert (await client.get("/changelog/not-a-release")).status_code == 404
    sitemap = await client.get("/sitemap.xml")
    assert slug in sitemap.text


async def test_miniapp_cannot_bypass_task_and_project_limits(client, db_session):
    user = User(email="limits@example.com", trial_ends_at=datetime.now(UTC) - timedelta(days=1))
    db_session.add(user)
    await db_session.flush()
    projects = [Project(user_id=user.id, name=f"P{i}", slug=f"p{i}") for i in range(10)]
    db_session.add_all(projects)
    await db_session.flush()
    tasks = [Task(user_id=user.id, project_id=projects[0].id, title=f"T{i}") for i in range(500)]
    db_session.add_all(tasks)
    await db_session.commit()
    sign_in(client, user)
    stale = await client.post(
        "/miniapp/api/projects",
        json={"name": "Wrong account"},
        headers={"X-Doday-User": "another-account"},
    )
    assert stale.status_code == 409
    for path, payload in [
        ("/miniapp/api/projects", {"name": "Extra"}),
        ("/miniapp/api/tasks", {"text": "Extra"}),
        (f"/miniapp/api/tasks/{tasks[0].id}/subtasks", {"title": "Extra"}),
        (f"/miniapp/api/tasks/{tasks[0].id}/duplicate", {}),
    ]:
        response = await client.post(path, json=payload)
        assert response.status_code == 402, response.text
