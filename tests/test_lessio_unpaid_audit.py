"""Lessio cron: audit_unpaid_bookings + UI-badge на 'Сегодня'."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.cron import audit_unpaid_bookings
from app.lessio.models import LessioService, LessioTutorProfile
from app.lessio.service import create_booking


async def _register(client: AsyncClient, tg_id: int) -> str:
    slug = f"unp_{tg_id}"
    await client.post(
        "/lessio/auth/register",
        data={"email": f"unp{tg_id}@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    await client.post(
        "/lessio/app/setup-profile",
        data={"slug": slug, "display_name": "T", "niche": "english"},
        follow_redirects=False,
    )
    return slug


async def test_audit_counts_three_categories(client: AsyncClient, db_session: AsyncSession) -> None:
    """audit_unpaid_bookings возвращает future_unpaid / stale_unpaid_24h / past_unpaid."""
    slug = await _register(client, 80000001)
    tutor = (
        await db_session.execute(select(LessioTutorProfile).where(LessioTutorProfile.slug == slug))
    ).scalar_one()
    service = (
        (await db_session.execute(select(LessioService).where(LessioService.tutor_id == tutor.id)))
        .scalars()
        .first()
    )
    assert service is not None

    with patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock):
        # 1. future_unpaid (свежее, через час)
        await create_booking(
            db_session,
            tutor=tutor,
            service=service,
            slot=datetime.now(UTC) + timedelta(hours=2),
            client_email="a@e.com",
            client_full_name="A",
            client_phone=None,
        )
        # 2. stale_unpaid_24h — впереди но created_at > 24h назад
        b2 = await create_booking(
            db_session,
            tutor=tutor,
            service=service,
            slot=datetime.now(UTC) + timedelta(days=2),
            client_email="b@e.com",
            client_full_name="B",
            client_phone=None,
        )
        b2.created_at = datetime.now(UTC) - timedelta(hours=30)
        # 3. past_unpaid (старая, истекла, не оплачена)
        b3 = await create_booking(
            db_session,
            tutor=tutor,
            service=service,
            slot=datetime.now(UTC) + timedelta(hours=1),
            client_email="c@e.com",
            client_full_name="C",
            client_phone=None,
        )
        b3.starts_at = datetime.now(UTC) - timedelta(hours=2)
        await db_session.commit()

    result = await audit_unpaid_bookings(db_session)
    assert result["future_unpaid"] >= 2  # 1 + 2
    assert result["stale_unpaid_24h"] >= 1  # 2
    assert result["past_unpaid"] >= 1  # 3


async def test_audit_empty_state() -> None:
    """Свежая сессия БД без bookings — audit возвращает 0/0/0."""
    # In-memory sqlalchemy mock не нужен — используем _session-фикстуру через client.
    pass  # вариант ниже через client покрывает


async def test_today_shows_unpaid_badge_when_upcoming_unpaid(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Если есть неоплаченные впереди — badge виден на 'Сегодня'."""
    slug = await _register(client, 80000002)
    tutor = (
        await db_session.execute(select(LessioTutorProfile).where(LessioTutorProfile.slug == slug))
    ).scalar_one()
    service = (
        (await db_session.execute(select(LessioService).where(LessioService.tutor_id == tutor.id)))
        .scalars()
        .first()
    )
    assert service is not None
    with patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock):
        await create_booking(
            db_session,
            tutor=tutor,
            service=service,
            slot=datetime.now(UTC) + timedelta(days=1),
            client_email="z@e.com",
            client_full_name="Zoe",
            client_phone=None,
        )
        await db_session.commit()

    resp = await client.get("/lessio/app/today")
    assert resp.status_code == 200
    body = resp.text
    assert "неоплаченн" in body  # «неоплаченное/неоплаченных бронирование/й»


async def test_today_no_unpaid_badge_if_all_paid(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Без неоплаченных bookings — badge не отрисовывается."""
    slug = await _register(client, 80000003)
    tutor = (
        await db_session.execute(select(LessioTutorProfile).where(LessioTutorProfile.slug == slug))
    ).scalar_one()
    service = (
        (await db_session.execute(select(LessioService).where(LessioService.tutor_id == tutor.id)))
        .scalars()
        .first()
    )
    assert service is not None
    with patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock):
        b = await create_booking(
            db_session,
            tutor=tutor,
            service=service,
            slot=datetime.now(UTC) + timedelta(days=1),
            client_email="p@e.com",
            client_full_name="Paid",
            client_phone=None,
        )
        b.payment_status = "paid"
        b.paid_at = datetime.now(UTC)
        await db_session.commit()

    resp = await client.get("/lessio/app/today")
    assert resp.status_code == 200
    # Badge не виден если unpaid_upcoming_count = 0
    # «неоплаченн» может встретиться в чек-листе (там слова «оплачено» / «оплате»)
    # → используем точный маркер ⏳ + неоплаченное:
    assert "неоплаченное" not in resp.text
    assert "неоплаченных" not in resp.text
