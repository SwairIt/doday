"""Booking service: create_booking + cancel + reschedule + email side-effects."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.models import LessioBooking, LessioClient, LessioService, LessioTutorProfile
from app.lessio.service import (
    BookingConflictError,
    auto_onboard_tutor,
    cancel_booking,
    create_booking,
    create_services_from_template,
    create_tutor_profile,
)


async def _setup(session: AsyncSession, *, tg_id: int) -> tuple[LessioTutorProfile, LessioService]:
    user, _ = await auto_onboard_tutor(session, telegram_user_id=tg_id)
    tutor = await create_tutor_profile(session, user=user, slug=f"book_{tg_id}", display_name="T")
    services = await create_services_from_template(session, tutor=tutor, niche="english")
    await session.commit()
    return tutor, services[0]


@patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock)
async def test_create_booking_creates_client_booking_and_sends_emails(
    mock_send: AsyncMock, db_session: AsyncSession
) -> None:
    tutor, service = await _setup(db_session, tg_id=40000001)
    slot = datetime(2026, 6, 8, 14, 0, tzinfo=UTC)

    booking = await create_booking(
        db_session,
        tutor=tutor,
        service=service,
        slot=slot,
        client_email="kid@example.com",
        client_phone="+79991234567",
        client_full_name="Vasya",
    )
    await db_session.commit()

    assert booking.status == "confirmed"
    assert booking.payment_status == "unpaid"
    assert len(booking.manage_token) >= 32
    assert booking.client_email == "kid@example.com"
    assert booking.client_full_name == "Vasya"

    client = (
        await db_session.execute(
            select(LessioClient).where(LessioClient.email == "kid@example.com")
        )
    ).scalar_one()
    assert client.full_name == "Vasya"
    assert client.tutor_id == tutor.id

    mock_send.assert_awaited_once()
    kwargs = mock_send.await_args.kwargs
    assert kwargs["booking"].id == booking.id


@patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock)
async def test_repeat_booking_same_email_upserts_client(
    mock_send: AsyncMock, db_session: AsyncSession
) -> None:
    tutor, service = await _setup(db_session, tg_id=40000002)

    await create_booking(
        db_session,
        tutor=tutor,
        service=service,
        slot=datetime(2026, 6, 8, 14, 0, tzinfo=UTC),
        client_email="re@e.com",
        client_full_name="Old Name",
        client_phone=None,
    )
    await create_booking(
        db_session,
        tutor=tutor,
        service=service,
        slot=datetime(2026, 6, 9, 14, 0, tzinfo=UTC),
        client_email="re@e.com",
        client_full_name="New Name",
        client_phone="+79990000000",
    )
    await db_session.commit()

    clients = (
        (await db_session.execute(select(LessioClient).where(LessioClient.email == "re@e.com")))
        .scalars()
        .all()
    )
    assert len(clients) == 1
    assert clients[0].full_name == "New Name"
    assert clients[0].phone == "+79990000000"


@patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock)
async def test_booking_conflict_raises_for_individual(
    mock_send: AsyncMock, db_session: AsyncSession
) -> None:
    tutor, service = await _setup(db_session, tg_id=40000003)
    slot = datetime(2026, 6, 8, 14, 0, tzinfo=UTC)

    await create_booking(
        db_session,
        tutor=tutor,
        service=service,
        slot=slot,
        client_email="a@e.com",
        client_full_name="A",
        client_phone=None,
    )
    await db_session.commit()

    with pytest.raises(BookingConflictError):
        await create_booking(
            db_session,
            tutor=tutor,
            service=service,
            slot=slot,
            client_email="b@e.com",
            client_full_name="B",
            client_phone=None,
        )


@patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock)
async def test_group_session_allows_multiple_bookings(
    mock_send: AsyncMock, db_session: AsyncSession
) -> None:
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=40000004)
    tutor = await create_tutor_profile(db_session, user=user, slug="group_t", display_name="T")
    group = LessioService(
        tutor_id=tutor.id,
        title="Yoga",
        duration_minutes=60,
        price_kopecks=80000,
        price_stars=80,
        is_group_session=True,
        max_attendees=3,
    )
    db_session.add(group)
    await db_session.commit()

    slot = datetime(2026, 6, 8, 18, 0, tzinfo=UTC)
    for i in range(3):
        await create_booking(
            db_session,
            tutor=tutor,
            service=group,
            slot=slot,
            client_email=f"g{i}@e.com",
            client_full_name=f"G{i}",
            client_phone=None,
        )
        await db_session.commit()

    bookings = (
        (
            await db_session.execute(
                select(LessioBooking).where(LessioBooking.service_id == group.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(bookings) == 3


@patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock)
async def test_group_session_full_raises(mock_send: AsyncMock, db_session: AsyncSession) -> None:
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=40000005)
    tutor = await create_tutor_profile(db_session, user=user, slug="group_full_t", display_name="T")
    group = LessioService(
        tutor_id=tutor.id,
        title="Yoga",
        duration_minutes=60,
        price_kopecks=80000,
        price_stars=80,
        is_group_session=True,
        max_attendees=2,
    )
    db_session.add(group)
    await db_session.commit()

    slot = datetime(2026, 6, 8, 18, 0, tzinfo=UTC)
    for i in range(2):
        await create_booking(
            db_session,
            tutor=tutor,
            service=group,
            slot=slot,
            client_email=f"g{i}@e.com",
            client_full_name=f"G{i}",
            client_phone=None,
        )
        await db_session.commit()

    with pytest.raises(BookingConflictError):
        await create_booking(
            db_session,
            tutor=tutor,
            service=group,
            slot=slot,
            client_email="overflow@e.com",
            client_full_name="Overflow",
            client_phone=None,
        )


@patch("app.lessio.service.send_cancellation_email", new_callable=AsyncMock)
async def test_cancel_booking_marks_status_and_sends_email(
    mock_cancel: AsyncMock, db_session: AsyncSession
) -> None:
    with patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock):
        tutor, service = await _setup(db_session, tg_id=40000006)
        slot = datetime(2026, 6, 8, 14, 0, tzinfo=UTC)
        booking = await create_booking(
            db_session,
            tutor=tutor,
            service=service,
            slot=slot,
            client_email="c@e.com",
            client_full_name="C",
            client_phone=None,
        )
        await db_session.commit()

    await cancel_booking(db_session, booking=booking, by="client")
    await db_session.commit()

    assert booking.status == "cancelled"
    assert booking.cancelled_at is not None
    mock_cancel.assert_awaited_once()
