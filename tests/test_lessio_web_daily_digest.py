"""Daily morning digest cron — tutor получает email со списком сегодняшних встреч."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.cron import dispatch_daily_digests
from app.lessio.service import (
    auto_onboard_tutor,
    create_booking,
    create_services_from_template,
    create_tutor_profile,
)


async def _setup_with_booking_today(
    db_session: AsyncSession, *, tg_id: int, notification_email: str | None
) -> None:
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=tg_id)
    tutor = await create_tutor_profile(
        db_session, user=user, slug=f"dd_{tg_id}", display_name=f"T{tg_id}"
    )
    tutor.notification_email = notification_email
    services = await create_services_from_template(db_session, tutor=tutor, niche="english")
    await db_session.commit()

    msk = ZoneInfo("Europe/Moscow")
    today_msk = datetime.now(msk).replace(hour=14, minute=0, second=0, microsecond=0)
    slot = today_msk.astimezone(UTC)
    with patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock):
        await create_booking(
            db_session,
            tutor=tutor,
            service=services[0],
            slot=slot,
            client_email="digest@e.com",
            client_full_name="DigestClient",
            client_phone=None,
        )
        await db_session.commit()


@patch("app.lessio.cron.send_daily_digest_email", new_callable=AsyncMock, return_value=True)
async def test_digest_sent_to_tutor_with_notification_email(
    mock_send: AsyncMock, db_session: AsyncSession
) -> None:
    await _setup_with_booking_today(db_session, tg_id=97000001, notification_email="notif@e.com")
    result = await dispatch_daily_digests(db_session)
    await db_session.commit()
    assert result["sent"] >= 1
    mock_send.assert_awaited()
    # First call arg has correct recipient
    args = mock_send.await_args
    assert args.kwargs["to"] == "notif@e.com"


@patch("app.lessio.cron.send_daily_digest_email", new_callable=AsyncMock, return_value=True)
async def test_digest_skips_tutor_without_notification_email(
    mock_send: AsyncMock, db_session: AsyncSession
) -> None:
    await _setup_with_booking_today(db_session, tg_id=97000002, notification_email=None)
    result = await dispatch_daily_digests(db_session)
    assert result["sent"] == 0
    mock_send.assert_not_awaited()


@patch("app.lessio.cron.send_daily_digest_email", new_callable=AsyncMock, return_value=True)
async def test_digest_skips_tutor_with_no_bookings_today(
    mock_send: AsyncMock, db_session: AsyncSession
) -> None:
    # Tutor с notification_email но без бронирований сегодня
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=97000003)
    tutor = await create_tutor_profile(db_session, user=user, slug="dd_empty", display_name="E")
    tutor.notification_email = "empty@e.com"
    await db_session.commit()

    result = await dispatch_daily_digests(db_session)
    assert result["sent"] == 0
    mock_send.assert_not_awaited()


async def test_cron_endpoint_includes_digests(
    client, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "cron_token", "secret123")
    with patch(
        "app.lessio.cron.send_daily_digest_email", new_callable=AsyncMock, return_value=True
    ):
        r = await client.post(
            "/api/lessio/cron/dispatch-reminders",
            headers={"X-Cron-Token": "secret123"},
        )
    assert r.status_code == 200
    body = r.json()
    assert "digests" in body
