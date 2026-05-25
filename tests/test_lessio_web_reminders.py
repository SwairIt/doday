"""Cron reminders: 24h + 1h batch dispatch с idempotency + X-Cron-Token guard."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.cron import dispatch_reminders
from app.lessio.models import LessioBooking
from app.lessio.service import (
    auto_onboard_tutor,
    create_booking,
    create_services_from_template,
    create_tutor_profile,
)


async def _book_at(db_session: AsyncSession, *, tg_id: int, slot: datetime) -> LessioBooking:
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=tg_id)
    tutor = await create_tutor_profile(db_session, user=user, slug=f"rem_{tg_id}", display_name="T")
    services = await create_services_from_template(db_session, tutor=tutor, niche="english")
    await db_session.commit()
    with patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock):
        booking = await create_booking(
            db_session,
            tutor=tutor,
            service=services[0],
            slot=slot,
            client_email="r@e.com",
            client_full_name="R",
            client_phone=None,
        )
        await db_session.commit()
    return booking


@patch("app.lessio.cron.send_reminder_email", new_callable=AsyncMock, return_value=True)
async def test_dispatch_24h_sends_for_bookings_in_window(
    mock_send: AsyncMock, db_session: AsyncSession
) -> None:
    target = (datetime.now(UTC) + timedelta(hours=24)).replace(microsecond=0)
    booking = await _book_at(db_session, tg_id=60000001, slot=target)

    result = await dispatch_reminders(db_session, hours=24)
    await db_session.commit()
    assert result["sent"] == 1
    refreshed = (
        await db_session.execute(select(LessioBooking).where(LessioBooking.id == booking.id))
    ).scalar_one()
    assert refreshed.reminder_24h_sent_at is not None


@patch("app.lessio.cron.send_reminder_email", new_callable=AsyncMock, return_value=True)
async def test_dispatch_1h_idempotent(mock_send: AsyncMock, db_session: AsyncSession) -> None:
    target = (datetime.now(UTC) + timedelta(minutes=60)).replace(microsecond=0)
    await _book_at(db_session, tg_id=60000002, slot=target)

    r1 = await dispatch_reminders(db_session, hours=1)
    await db_session.commit()
    r2 = await dispatch_reminders(db_session, hours=1)
    await db_session.commit()
    assert r1["sent"] == 1
    assert r2["sent"] == 0  # second run skips already-flagged


async def test_dispatch_outside_window_no_send(db_session: AsyncSession) -> None:
    target = (datetime.now(UTC) + timedelta(hours=5)).replace(microsecond=0)
    await _book_at(db_session, tg_id=60000003, slot=target)

    r24 = await dispatch_reminders(db_session, hours=24)
    r1 = await dispatch_reminders(db_session, hours=1)
    assert r24["sent"] == 0
    assert r1["sent"] == 0


async def test_cron_endpoint_token_guard(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "cron_token", "secret123")

    r = await client.post("/api/lessio/cron/dispatch-reminders")
    assert r.status_code == 403

    r = await client.post("/api/lessio/cron/dispatch-reminders", headers={"X-Cron-Token": "wrong"})
    assert r.status_code == 403

    r = await client.post(
        "/api/lessio/cron/dispatch-reminders", headers={"X-Cron-Token": "secret123"}
    )
    assert r.status_code == 200
    body = r.json()
    assert "24h" in body and "1h" in body


async def test_cron_endpoint_returns_503_when_no_token_configured(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "cron_token", "")
    r = await client.post(
        "/api/lessio/cron/dispatch-reminders", headers={"X-Cron-Token": "anything"}
    )
    assert r.status_code == 503
