"""Jitsi auto-meeting URLs: если у tutor/service нет meeting_url_template,
автогенерируем https://meet.jit.si/lessio-<booking-uuid> при create_booking."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.models import LessioService
from app.lessio.service import (
    auto_onboard_tutor,
    create_booking,
    create_services_from_template,
    create_tutor_profile,
)


@patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock)
async def test_booking_gets_jitsi_url_when_no_template_set(
    mock_send: AsyncMock, db_session: AsyncSession
) -> None:
    """Tutor без default_meeting_url_template + service без meeting_url_template
    → booking.meeting_url автоматом https://meet.jit.si/lessio-<uuid>."""
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=100000001)
    tutor = await create_tutor_profile(db_session, user=user, slug="jitsi_t", display_name="J")
    # default_meeting_url_template = None (по умолчанию)
    services = await create_services_from_template(db_session, tutor=tutor, niche="english")
    # services[0].meeting_url_template — None по умолчанию
    await db_session.commit()

    booking = await create_booking(
        db_session,
        tutor=tutor,
        service=services[0],
        slot=datetime(2026, 7, 1, 14, 0, tzinfo=UTC),
        client_email="j@e.com",
        client_full_name="J Client",
        client_phone=None,
    )
    await db_session.commit()

    assert booking.meeting_url is not None
    assert booking.meeting_url.startswith("https://meet.jit.si/lessio-")
    # UUID-suffix содержит booking ID для уникальности
    assert str(booking.id) in booking.meeting_url


@patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock)
async def test_booking_respects_service_meeting_url_template(
    mock_send: AsyncMock, db_session: AsyncSession
) -> None:
    """Если у service есть meeting_url_template — Jitsi не подключается."""
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=100000002)
    tutor = await create_tutor_profile(db_session, user=user, slug="zoom_t", display_name="Z")
    svc = LessioService(
        tutor_id=tutor.id,
        title="Zoom session",
        duration_minutes=60,
        price_kopecks=100000,
        price_stars=100,
        meeting_url_template="https://zoom.us/j/123456789",
    )
    db_session.add(svc)
    await db_session.commit()

    booking = await create_booking(
        db_session,
        tutor=tutor,
        service=svc,
        slot=datetime(2026, 7, 1, 14, 0, tzinfo=UTC),
        client_email="z@e.com",
        client_full_name="Z Client",
        client_phone=None,
    )
    await db_session.commit()
    assert booking.meeting_url == "https://zoom.us/j/123456789"


@patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock)
async def test_booking_respects_tutor_default_template(
    mock_send: AsyncMock, db_session: AsyncSession
) -> None:
    """Если service.meeting_url_template пуст, но tutor.default_meeting_url_template
    есть — используем tutor's default (не Jitsi)."""
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=100000003)
    tutor = await create_tutor_profile(db_session, user=user, slug="default_t", display_name="D")
    tutor.default_meeting_url_template = "https://meet.google.com/abc-xyz-123"
    services = await create_services_from_template(db_session, tutor=tutor, niche="english")
    await db_session.commit()

    booking = await create_booking(
        db_session,
        tutor=tutor,
        service=services[0],
        slot=datetime(2026, 7, 1, 14, 0, tzinfo=UTC),
        client_email="d@e.com",
        client_full_name="D",
        client_phone=None,
    )
    await db_session.commit()
    assert booking.meeting_url == "https://meet.google.com/abc-xyz-123"
