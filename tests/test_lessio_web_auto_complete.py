"""Auto-complete cron: confirmed → completed после starts_at + duration, шлёт review email."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.cron import dispatch_review_requests, mark_completed_bookings
from app.lessio.models import LessioBooking
from app.lessio.service import (
    auto_onboard_tutor,
    create_booking,
    create_services_from_template,
    create_tutor_profile,
)


async def _booking_at(
    db_session: AsyncSession, *, tg_id: int, starts_at: datetime, duration: int = 60
) -> LessioBooking:
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=tg_id)
    tutor = await create_tutor_profile(db_session, user=user, slug=f"ac_{tg_id}", display_name="T")
    services = await create_services_from_template(db_session, tutor=tutor, niche="english")
    await db_session.commit()
    with patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock):
        booking = await create_booking(
            db_session,
            tutor=tutor,
            service=services[0],
            slot=starts_at,
            client_email="ac@e.com",
            client_full_name="AC",
            client_phone=None,
        )
        await db_session.commit()
    booking.duration_minutes = duration
    await db_session.commit()
    return booking


@patch("app.lessio.cron.send_review_request_email", new_callable=AsyncMock, return_value=True)
async def test_mark_completed_for_past_booking(
    mock_send: AsyncMock, db_session: AsyncSession
) -> None:
    past_start = datetime.now(UTC) - timedelta(hours=2)
    booking = await _booking_at(db_session, tg_id=96000001, starts_at=past_start)

    result = await mark_completed_bookings(db_session)
    await db_session.commit()
    assert result["completed"] == 1

    refreshed = (
        await db_session.execute(select(LessioBooking).where(LessioBooking.id == booking.id))
    ).scalar_one()
    assert refreshed.status == "completed"
    assert refreshed.completed_at is not None
    mock_send.assert_awaited_once()


@patch("app.lessio.cron.send_review_request_email", new_callable=AsyncMock, return_value=True)
async def test_mark_completed_skips_future(mock_send: AsyncMock, db_session: AsyncSession) -> None:
    future = datetime.now(UTC) + timedelta(days=1)
    booking = await _booking_at(db_session, tg_id=96000002, starts_at=future)
    result = await mark_completed_bookings(db_session)
    assert result["completed"] == 0
    refreshed = (
        await db_session.execute(select(LessioBooking).where(LessioBooking.id == booking.id))
    ).scalar_one()
    assert refreshed.status == "confirmed"
    mock_send.assert_not_awaited()


@patch("app.lessio.cron.send_review_request_email", new_callable=AsyncMock, return_value=True)
async def test_mark_completed_idempotent_second_run(
    mock_send: AsyncMock, db_session: AsyncSession
) -> None:
    past_start = datetime.now(UTC) - timedelta(hours=2)
    await _booking_at(db_session, tg_id=96000003, starts_at=past_start)
    r1 = await mark_completed_bookings(db_session)
    await db_session.commit()
    r2 = await mark_completed_bookings(db_session)
    await db_session.commit()
    assert r1["completed"] == 1
    assert r2["completed"] == 0  # already done
    assert mock_send.await_count == 1


@patch("app.lessio.cron.send_review_request_email", new_callable=AsyncMock)
async def test_mark_completed_skips_cancelled(
    mock_send: AsyncMock, db_session: AsyncSession
) -> None:
    past_start = datetime.now(UTC) - timedelta(hours=2)
    booking = await _booking_at(db_session, tg_id=96000004, starts_at=past_start)
    booking.status = "cancelled"
    booking.cancelled_at = datetime.now(UTC)
    await db_session.commit()
    result = await mark_completed_bookings(db_session)
    assert result["completed"] == 0
    mock_send.assert_not_awaited()


@patch("app.lessio.cron.send_review_request_email", new_callable=AsyncMock, return_value=True)
async def test_cron_endpoint_runs_mark_completed_too(
    mock_send: AsyncMock,
    client,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "cron_token", "secret123")
    past_start = datetime.now(UTC) - timedelta(hours=2)
    await _booking_at(db_session, tg_id=96000005, starts_at=past_start)
    r = await client.post(
        "/api/lessio/cron/dispatch-reminders",
        headers={"X-Cron-Token": "secret123"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "completed" in body
    assert body["completed"]["completed"] >= 1


async def test_dispatch_review_requests_alias_works(db_session: AsyncSession) -> None:
    """dispatch_review_requests — backwards-compat alias на mark_completed_bookings."""
    past = datetime.now(UTC) - timedelta(hours=2)
    await _booking_at(db_session, tg_id=96000006, starts_at=past)
    with patch(
        "app.lessio.cron.send_review_request_email", new_callable=AsyncMock, return_value=True
    ):
        result = await dispatch_review_requests(db_session)
    assert result["completed"] >= 1
