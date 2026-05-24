"""Telegram Stars payments — signing, pre-checkout, apply-payment idempotency.

The heavy I/O parts (Bot API calls) are not tested live here — we mock the
httpx layer or skip them. What we DO test:
- HMAC sign/verify round-trip
- Tampered payload is rejected
- Pre-checkout amount mismatch is rejected
- apply_successful_payment is idempotent (same charge_id twice → one row)
- pro_until extension math (renewal doesn't lose remaining days, lifetime
  sets far-future, expired user gets a fresh window)
- effective_tier honors pro_until expiration
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.billing.models import StarPayment
from app.billing.products import BY_CODE, PRODUCTS, get_product
from app.billing.service import effective_tier
from app.billing.stars import (
    PayloadError,
    apply_successful_payment,
    sign_payload,
    validate_pre_checkout,
    verify_payload,
)

# ---------------------------------------------------------------------------
# Payload signing
# ---------------------------------------------------------------------------


def test_sign_payload_roundtrip() -> None:
    user_id = uuid4()
    payload = sign_payload("pro_1m", user_id)
    code, parsed_uid, _nonce = verify_payload(payload)
    assert code == "pro_1m"
    assert parsed_uid == user_id


def test_sign_payload_unique_nonce() -> None:
    """Two calls with the same args produce different payloads (nonce is random)."""
    uid = uuid4()
    p1 = sign_payload("pro_1m", uid)
    p2 = sign_payload("pro_1m", uid)
    assert p1 != p2


def test_verify_payload_rejects_tampered_product() -> None:
    """Flip the product code → signature breaks."""
    uid = uuid4()
    good = sign_payload("pro_1m", uid)
    parts = good.split(":")
    parts[1] = "pro_forever"  # cheat: upgrade product without paying
    tampered = ":".join(parts)
    with pytest.raises(PayloadError):
        verify_payload(tampered)


def test_verify_payload_rejects_tampered_user() -> None:
    """Different user_id → signature breaks (can't pay for someone else)."""
    uid_a = uuid4()
    uid_b = uuid4()
    good = sign_payload("pro_1m", uid_a)
    parts = good.split(":")
    parts[2] = uid_b.hex
    tampered = ":".join(parts)
    with pytest.raises(PayloadError):
        verify_payload(tampered)


def test_verify_payload_rejects_malformed() -> None:
    with pytest.raises(PayloadError):
        verify_payload("not-a-payload")
    with pytest.raises(PayloadError):
        verify_payload("v1:pro_1m")  # too few parts
    with pytest.raises(PayloadError):
        verify_payload("v2:pro_1m:abc:def:ghi")  # wrong version


def test_payload_fits_in_telegram_limit() -> None:
    """Telegram caps invoice_payload at 128 bytes — we must stay well under."""
    uid = uuid4()
    p = sign_payload("pro_forever", uid)
    assert len(p) <= 128, f"payload too long: {len(p)} bytes"


# ---------------------------------------------------------------------------
# Pre-checkout validation
# ---------------------------------------------------------------------------


def test_validate_pre_checkout_happy_path() -> None:
    uid = uuid4()
    payload = sign_payload("pro_1m", uid)
    product = BY_CODE["pro_1m"]
    ok, reason, returned = validate_pre_checkout(payload, product.stars_amount)
    assert ok is True
    assert reason is None
    assert returned == product


def test_validate_pre_checkout_amount_mismatch() -> None:
    """Telegram declares less Stars than catalog price → rejected."""
    uid = uuid4()
    payload = sign_payload("pro_forever", uid)
    ok, reason, _ = validate_pre_checkout(payload, 100)  # not 12500
    assert ok is False
    assert reason is not None
    assert "Цена" in reason


def test_validate_pre_checkout_unsigned() -> None:
    """Random string in payload → rejected (signature check fails first)."""
    ok, reason, _ = validate_pre_checkout("v1:pro_1m:xyz:abc:fake", 250)
    assert ok is False
    assert reason is not None


# ---------------------------------------------------------------------------
# apply_successful_payment — idempotency + pro_until math
# ---------------------------------------------------------------------------


async def test_apply_creates_payment_and_extends_pro(logged_in_client: AsyncClient) -> None:
    """First payment: row inserted, tier=pro, pro_until ~30d away.

    Note: the fixture-created user starts with a 14-day trial → effective_tier
    is "pro" via trial. We're testing that PAID Pro takes over: user.tier
    becomes 'pro' (was 'free'), and user.pro_until gets populated. The trial
    is now irrelevant — paid takes priority in effective_tier."""
    me = (await logged_in_client.get("/api/billing/me")).json()
    user_id = me["user_id"]
    # User starts at tier='free' (trial gives temporary pro features but
    # the column stays 'free' until they pay).
    assert me["tier"] == "free"

    # Use the test client's DB session via a fixture helper would be nicer, but
    # we can just call the service directly through a fresh session.
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.config import get_settings

    engine = create_async_engine(get_settings().test_database_url)
    sm = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with sm() as session:
            from uuid import UUID

            uid = UUID(user_id)
            payload = sign_payload("pro_1m", uid)
            payment = await apply_successful_payment(
                session,
                telegram_payment_charge_id="charge_test_001",
                provider_payment_charge_id="prov_001",
                payload=payload,
                stars_amount=250,
            )
            await session.commit()
            assert payment is not None
            assert payment.product_code == "pro_1m"
            user = await session.get(User, uid)
            assert user is not None
            assert user.tier == "pro"
            assert user.pro_until is not None
            now = datetime.now(UTC)
            # 30 days * 1 month = 30 days exactly (we use 30-day months for simplicity)
            assert user.pro_until > now + timedelta(days=29)
            assert user.pro_until < now + timedelta(days=31)
    finally:
        await engine.dispose()


async def test_apply_is_idempotent(logged_in_client: AsyncClient) -> None:
    """Same charge_id twice → only one row, no double-extension of pro_until."""
    me = (await logged_in_client.get("/api/billing/me")).json()
    user_id = me["user_id"]

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.config import get_settings

    engine = create_async_engine(get_settings().test_database_url)
    sm = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with sm() as session:
            from uuid import UUID

            uid = UUID(user_id)
            payload = sign_payload("pro_1m", uid)
            # First delivery.
            p1 = await apply_successful_payment(
                session,
                telegram_payment_charge_id="charge_idem_001",
                provider_payment_charge_id="prov_a",
                payload=payload,
                stars_amount=250,
            )
            await session.commit()
            assert p1 is not None
            user = await session.get(User, uid)
            assert user is not None
            await session.refresh(user)
            first_pro_until = user.pro_until

            # Second delivery — same charge_id.
            p2 = await apply_successful_payment(
                session,
                telegram_payment_charge_id="charge_idem_001",
                provider_payment_charge_id="prov_a",
                payload=payload,
                stars_amount=250,
            )
            await session.commit()
            assert p2 is not None
            assert p2.id == p1.id
            # Pro_until must NOT have moved on second delivery.
            await session.refresh(user)
            assert user.pro_until == first_pro_until

            # And exactly one row in DB.
            count = (
                (
                    await session.execute(
                        select(StarPayment).where(
                            StarPayment.telegram_payment_charge_id == "charge_idem_001"
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert len(count) == 1
    finally:
        await engine.dispose()


async def test_renewal_extends_from_existing_expiry(logged_in_client: AsyncClient) -> None:
    """User with 10 days left buys another month → pro_until = old + 30 days, not now+30."""
    me = (await logged_in_client.get("/api/billing/me")).json()
    user_id = me["user_id"]

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.config import get_settings

    engine = create_async_engine(get_settings().test_database_url)
    sm = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with sm() as session:
            from uuid import UUID

            uid = UUID(user_id)
            # Seed user with pro_until 10 days in the future.
            user = await session.get(User, uid)
            assert user is not None
            user.tier = "pro"
            user.pro_until = datetime.now(UTC) + timedelta(days=10)
            await session.commit()
            expected_floor = user.pro_until + timedelta(days=29)

            payload = sign_payload("pro_1m", uid)
            await apply_successful_payment(
                session,
                telegram_payment_charge_id="charge_renew_001",
                provider_payment_charge_id="prov_r",
                payload=payload,
                stars_amount=250,
            )
            await session.commit()
            await session.refresh(user)
            # Should extend from the existing pro_until, not from now.
            assert user.pro_until >= expected_floor
    finally:
        await engine.dispose()


async def test_lifetime_purchase_sets_far_future(logged_in_client: AsyncClient) -> None:
    """pro_forever → user.pro_until is in year 2099 (effectively no expiry)."""
    me = (await logged_in_client.get("/api/billing/me")).json()
    user_id = me["user_id"]

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.config import get_settings

    engine = create_async_engine(get_settings().test_database_url)
    sm = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with sm() as session:
            from uuid import UUID

            uid = UUID(user_id)
            payload = sign_payload("pro_forever", uid)
            await apply_successful_payment(
                session,
                telegram_payment_charge_id="charge_life_001",
                provider_payment_charge_id="prov_l",
                payload=payload,
                stars_amount=12500,
            )
            await session.commit()
            user = await session.get(User, uid)
            assert user is not None
            assert user.tier == "pro"
            assert user.pro_until is not None
            assert user.pro_until.year >= 2099
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# effective_tier honors pro_until expiry
# ---------------------------------------------------------------------------


def test_effective_tier_expired_pro_falls_back_to_free() -> None:
    """User with tier=pro but pro_until in the past gets free."""
    u = User(
        email="x@x.x",
        password_hash="x",
        tier="pro",
        pro_until=datetime.now(UTC) - timedelta(days=1),
        trial_ends_at=None,
    )
    assert effective_tier(u) == "free"


def test_effective_tier_active_pro() -> None:
    u = User(
        email="x@x.x",
        password_hash="x",
        tier="pro",
        pro_until=datetime.now(UTC) + timedelta(days=15),
        trial_ends_at=None,
    )
    assert effective_tier(u) == "pro"


def test_effective_tier_family_active() -> None:
    u = User(
        email="x@x.x",
        password_hash="x",
        tier="family",
        pro_until=datetime.now(UTC) + timedelta(days=15),
        trial_ends_at=None,
    )
    assert effective_tier(u) == "family"


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------


async def test_list_products_endpoint(logged_in_client: AsyncClient) -> None:
    resp = await logged_in_client.get("/api/billing/products")
    assert resp.status_code == 200
    products = resp.json()
    codes = {p["code"] for p in products}
    assert codes == {p.code for p in PRODUCTS}
    for p in products:
        assert p["stars_amount"] > 0
        assert "title" in p and "description" in p


async def test_billing_me_includes_pro_until(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/api/billing/me")).json()
    assert "pro_until" in body  # may be None — what matters is the key exists


async def test_change_tier_blocks_self_upgrade(logged_in_client: AsyncClient) -> None:
    """Security fix: can't POST {'tier': 'pro'} to upgrade without paying."""
    resp = await logged_in_client.post("/api/billing/change-tier", json={"tier": "pro"})
    assert resp.status_code == 402
    assert "stars/invoice" in resp.json()["detail"]


async def test_change_tier_allows_downgrade(logged_in_client: AsyncClient) -> None:
    """Downgrading to free is always allowed (self-service cancellation)."""
    resp = await logged_in_client.post("/api/billing/change-tier", json={"tier": "free"})
    assert resp.status_code == 200
    assert resp.json()["tier"] == "free"


async def test_payments_history_empty_for_new_user(logged_in_client: AsyncClient) -> None:
    resp = await logged_in_client.get("/api/billing/stars/payments")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_invoice_unknown_product(logged_in_client: AsyncClient) -> None:
    resp = await logged_in_client.post("/api/billing/stars/invoice", json={"product_code": "bogus"})
    assert resp.status_code == 404


async def test_create_invoice_no_bot_token(
    logged_in_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In test env we don't have a real BOT_TOKEN → service surfaces 503."""
    from app.config import get_settings

    settings = get_settings()
    # Clear bot token for this test specifically; restore via monkeypatch.
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    resp = await logged_in_client.post(
        "/api/billing/stars/invoice", json={"product_code": "pro_1m"}
    )
    # Either 503 (our error) or another non-200 — what matters is it doesn't
    # crash or silently return a fake URL.
    assert resp.status_code in (503, 500)


def test_products_catalog_internal_consistency() -> None:
    """Sanity: titles non-empty, codes unique, stars > 0, grants_tier in known set."""
    seen_codes: set[str] = set()
    valid_tiers = {"pro", "family"}
    for p in PRODUCTS:
        assert p.code not in seen_codes, f"duplicate code {p.code}"
        seen_codes.add(p.code)
        assert p.title.strip()
        assert p.description.strip()
        assert p.stars_amount > 0
        assert p.grants_tier in valid_tiers
        assert p.duration_months is None or p.duration_months > 0
    # Year is cheaper-per-month than monthly (we promise this on landing).
    pro_year = get_product("pro_12m")
    pro_month = get_product("pro_1m")
    assert pro_year is not None and pro_month is not None
    assert pro_year.stars_amount < pro_month.stars_amount * 12
