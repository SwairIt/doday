"""Lessio models — поля для web-flow: email/phone в Client, magic-token + denorm в Booking."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.models import (
    LessioBooking,
    LessioClient,
    LessioService,
    LessioTutorProfile,
)


async def test_client_supports_anon_email_phone_name(db_session: AsyncSession) -> None:
    """Web-клиент создаётся БЕЗ telegram_user_id, с email/phone/full_name."""
    from app.lessio.service import auto_onboard_tutor, create_tutor_profile

    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=10000001)
    tutor = await create_tutor_profile(db_session, user=user, slug="test_t1", display_name="T1")
    await db_session.commit()

    client = LessioClient(
        tutor_id=tutor.id,
        telegram_user_id=None,
        email="anon@example.com",
        phone="+79991234567",
        full_name="Anon Web",
    )
    db_session.add(client)
    await db_session.commit()

    fetched = (
        await db_session.execute(
            select(LessioClient).where(LessioClient.email == "anon@example.com")
        )
    ).scalar_one()
    assert fetched.telegram_user_id is None
    assert fetched.phone == "+79991234567"
    assert fetched.full_name == "Anon Web"


async def test_booking_has_manage_token_and_denorm(db_session: AsyncSession) -> None:
    from app.lessio.service import auto_onboard_tutor, create_tutor_profile

    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=10000002)
    tutor = await create_tutor_profile(db_session, user=user, slug="test_t2", display_name="T2")
    service = LessioService(
        tutor_id=tutor.id,
        title="Test",
        duration_minutes=60,
        price_kopecks=100000,
        price_stars=100,
    )
    client = LessioClient(
        tutor_id=tutor.id,
        email="c@e.com",
        full_name="C",
        telegram_user_id=None,
    )
    db_session.add_all([service, client])
    await db_session.commit()

    booking = LessioBooking(
        tutor_id=tutor.id,
        client_id=client.id,
        service_id=service.id,
        starts_at=datetime(2026, 6, 1, 14, 0, tzinfo=UTC),
        duration_minutes=60,
        price_kopecks=100000,
        price_stars=100,
        manage_token="a" * 64,
        payment_status="unpaid",
        client_email="c@e.com",
        client_full_name="C",
    )
    db_session.add(booking)
    await db_session.commit()

    fetched = (
        await db_session.execute(
            select(LessioBooking).where(LessioBooking.manage_token == "a" * 64)
        )
    ).scalar_one()
    assert fetched.payment_status == "unpaid"
    assert fetched.client_email == "c@e.com"
    assert fetched.reminder_24h_sent_at is None
    assert fetched.reminder_1h_sent_at is None


async def test_service_has_meeting_url_and_group_fields(db_session: AsyncSession) -> None:
    from app.lessio.service import auto_onboard_tutor, create_tutor_profile

    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=10000003)
    tutor = await create_tutor_profile(db_session, user=user, slug="test_t3", display_name="T3")
    service = LessioService(
        tutor_id=tutor.id,
        title="Group Yoga",
        duration_minutes=60,
        price_kopecks=80000,
        price_stars=80,
        meeting_url_template="https://meet.jit.si/lessio-yoga",
        is_group_session=True,
        max_attendees=8,
        location="онлайн",
    )
    db_session.add(service)
    await db_session.commit()

    fetched = (
        await db_session.execute(select(LessioService).where(LessioService.title == "Group Yoga"))
    ).scalar_one()
    assert fetched.is_group_session is True
    assert fetched.max_attendees == 8
    assert fetched.meeting_url_template is not None
    assert fetched.meeting_url_template.startswith("https://meet.jit.si")


async def test_tutor_profile_has_meeting_template_and_gc_token(db_session: AsyncSession) -> None:
    from app.lessio.service import auto_onboard_tutor, create_tutor_profile

    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=10000004)
    tutor = await create_tutor_profile(db_session, user=user, slug="test_t4", display_name="T4")
    tutor.default_meeting_url_template = "https://zoom.us/j/123"
    tutor.notification_email = "notify@example.com"
    tutor.google_calendar_refresh_token = "encrypted_token_blob"
    await db_session.commit()

    refetched = await db_session.get(LessioTutorProfile, tutor.id)
    assert refetched is not None
    assert refetched.default_meeting_url_template == "https://zoom.us/j/123"
    assert refetched.notification_email == "notify@example.com"
    assert refetched.google_calendar_refresh_token == "encrypted_token_blob"
