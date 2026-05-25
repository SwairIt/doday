"""Lessio cabinet: /lessio/app/income — toggle paid + CSV export + month aggregate."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.models import LessioBooking, LessioService, LessioTutorProfile
from app.lessio.service import create_booking


async def _setup_with_booking(
    client: AsyncClient,
    db_session: AsyncSession,
    *,
    tg_id: int,
    slot: datetime,
    price_kopecks: int = 150000,
) -> tuple[LessioTutorProfile, LessioBooking]:
    slug = f"inc_{tg_id}"
    await client.post(
        "/lessio/auth/register",
        data={"email": f"in{tg_id}@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    await client.post(
        "/lessio/app/setup-profile",
        data={"slug": slug, "display_name": "T", "niche": "english"},
        follow_redirects=False,
    )
    profile = (
        await db_session.execute(select(LessioTutorProfile).where(LessioTutorProfile.slug == slug))
    ).scalar_one()
    service = (
        (
            await db_session.execute(
                select(LessioService).where(LessioService.tutor_id == profile.id)
            )
        )
        .scalars()
        .first()
    )
    assert service is not None
    service.price_kopecks = price_kopecks
    await db_session.commit()
    with patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock):
        booking = await create_booking(
            db_session,
            tutor=profile,
            service=service,
            slot=slot,
            client_email="payer@e.com",
            client_full_name="Payer",
            client_phone=None,
        )
        await db_session.commit()
    return profile, booking


async def test_income_page_renders(client: AsyncClient, db_session: AsyncSession) -> None:
    slot = datetime(2026, 6, 15, 14, 0, tzinfo=UTC)
    _, _ = await _setup_with_booking(client, db_session, tg_id=76000001, slot=slot)
    resp = await client.get("/lessio/app/income?month=2026-06")
    assert resp.status_code == 200
    body = resp.text
    assert "Payer" in body
    assert "доход" in body.lower() or "Доход" in body


async def test_toggle_paid_flips_status(client: AsyncClient, db_session: AsyncSession) -> None:
    slot = datetime(2026, 6, 15, 14, 0, tzinfo=UTC)
    _, booking = await _setup_with_booking(client, db_session, tg_id=76000002, slot=slot)
    assert booking.payment_status == "unpaid"

    resp = await client.post(
        f"/lessio/app/bookings/{booking.id}/toggle-paid", follow_redirects=False
    )
    assert resp.status_code in (302, 303)

    await db_session.refresh(booking)
    assert booking.payment_status == "paid"
    assert booking.paid_at is not None

    # Toggle back
    await client.post(f"/lessio/app/bookings/{booking.id}/toggle-paid", follow_redirects=False)
    await db_session.refresh(booking)
    assert booking.payment_status == "unpaid"
    assert booking.paid_at is None


async def test_income_csv_export(client: AsyncClient, db_session: AsyncSession) -> None:
    slot = datetime(2026, 6, 15, 14, 0, tzinfo=UTC)
    _, booking = await _setup_with_booking(
        client, db_session, tg_id=76000003, slot=slot, price_kopecks=200000
    )
    booking.payment_status = "paid"
    booking.paid_at = datetime.now(UTC)
    await db_session.commit()

    resp = await client.get("/lessio/app/income/export.csv?year=2026&month=6")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    body = resp.text
    assert "Payer" in body
    assert "payer@e.com" in body
    assert "2000" in body  # 200000 kopecks = 2000 rub
    assert "paid" in body


async def test_income_month_filter(client: AsyncClient, db_session: AsyncSession) -> None:
    # Создаём booking в июне, фильтруем календарём июль — booking не должен попасть
    slot = datetime(2026, 6, 15, 14, 0, tzinfo=UTC)
    _, _ = await _setup_with_booking(client, db_session, tg_id=76000004, slot=slot)
    resp = await client.get("/lessio/app/income?month=2026-07")
    assert resp.status_code == 200
    # Payer is from June booking, July page should NOT show "Payer"
    assert "Payer" not in resp.text or "0 ₽" in resp.text
