"""find_free_slots алгоритм — granular cases.

Каждый кейс независим: свой tutor (уникальный tg_id), своя услуга. Базовый день —
понедельник в нескольких днях от "сегодня" (вычисляется динамически), чтобы
past-filter в find_free_slots не пожирал слоты теста. Раньше дата была захардкожена
(2026-06-01) и тесты "протухали", когда календарь проходил эту дату.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.models import LessioBooking, LessioClient, LessioService, LessioTutorProfile
from app.lessio.service import (
    auto_onboard_tutor,
    create_tutor_profile,
    find_free_slots,
)

# A Monday a handful of days in the future (4–10 days out) — always ahead of "now"
# so the past-filter keeps the slots, but close enough to fit any booking window.
_today = datetime.now(UTC).date()
_to_mon = (7 - _today.weekday()) % 7
_MONDAY = _today + timedelta(days=_to_mon if _to_mon >= 4 else _to_mon + 7)
_MON_Y, _MON_M, _MON_D = _MONDAY.year, _MONDAY.month, _MONDAY.day
_SATURDAY = _MONDAY + timedelta(days=5)
_SAT_Y, _SAT_M, _SAT_D = _SATURDAY.year, _SATURDAY.month, _SATURDAY.day


async def _setup_tutor(session: AsyncSession, *, tg_id: int) -> LessioTutorProfile:
    user, _ = await auto_onboard_tutor(session, telegram_user_id=tg_id)
    return await create_tutor_profile(session, user=user, slug=f"tutor_{tg_id}", display_name="T")


async def _add_service(
    session: AsyncSession,
    tutor: LessioTutorProfile,
    *,
    duration_minutes: int = 60,
    is_group_session: bool = False,
    max_attendees: int = 1,
) -> LessioService:
    service = LessioService(
        tutor_id=tutor.id,
        title="60min",
        duration_minutes=duration_minutes,
        price_kopecks=100000,
        price_stars=100,
        is_group_session=is_group_session,
        max_attendees=max_attendees,
    )
    session.add(service)
    await session.flush()
    return service


def _make_client(tutor: LessioTutorProfile, *, email: str = "c@e.com") -> LessioClient:
    return LessioClient(tutor_id=tutor.id, email=email, full_name="C", telegram_user_id=None)


async def test_no_bookings_returns_all_slots(db_session: AsyncSession) -> None:
    """Без booked-времён — все слоты в working_hours свободны."""
    tutor = await _setup_tutor(db_session, tg_id=20000001)
    service = await _add_service(db_session, tutor)
    await db_session.commit()

    monday = datetime(_MON_Y, _MON_M, _MON_D, 0, 0, tzinfo=UTC)
    slots = await find_free_slots(
        db_session,
        tutor,
        date_from=monday,
        date_to=monday + timedelta(days=1),
        service=service,
    )
    # Окно 9:00-21:00 = 720 мин, шаг (60+15)=75 мин → 9:00,10:15,11:30,...,19:30
    # фитнес: 9 слотов (последний 19:30 + 60 = 20:30 ≤ 21:00).
    assert len(slots) == 9
    assert slots[0] == datetime(_MON_Y, _MON_M, _MON_D, 9, 0, tzinfo=UTC)


async def test_weekend_returns_empty(db_session: AsyncSession) -> None:
    """working_days=[1..5] не включает Sat=6, Sun=7."""
    tutor = await _setup_tutor(db_session, tg_id=20000002)
    service = await _add_service(db_session, tutor)
    await db_session.commit()

    saturday = datetime(_SAT_Y, _SAT_M, _SAT_D, 0, 0, tzinfo=UTC)
    slots = await find_free_slots(
        db_session,
        tutor,
        date_from=saturday,
        date_to=saturday + timedelta(days=1),
        service=service,
    )
    assert slots == []


async def test_existing_booking_blocks_slot(db_session: AsyncSession) -> None:
    """confirmed booking исключает прямое попадание в этот слот."""
    tutor = await _setup_tutor(db_session, tg_id=20000003)
    service = await _add_service(db_session, tutor)
    client = _make_client(tutor)
    db_session.add(client)
    await db_session.flush()

    booked_slot = datetime(_MON_Y, _MON_M, _MON_D, 10, 15, tzinfo=UTC)
    booking = LessioBooking(
        tutor_id=tutor.id,
        client_id=client.id,
        service_id=service.id,
        starts_at=booked_slot,
        duration_minutes=60,
        status="confirmed",
        price_kopecks=100000,
        price_stars=100,
        manage_token="t" * 64,
        payment_status="unpaid",
        client_email="c@e.com",
        client_full_name="C",
    )
    db_session.add(booking)
    await db_session.commit()

    monday = datetime(_MON_Y, _MON_M, _MON_D, 0, 0, tzinfo=UTC)
    slots = await find_free_slots(
        db_session,
        tutor,
        date_from=monday,
        date_to=monday + timedelta(days=1),
        service=service,
    )
    assert booked_slot not in slots


async def test_cancelled_booking_does_not_block(db_session: AsyncSession) -> None:
    """status='cancelled' — слот снова свободен."""
    tutor = await _setup_tutor(db_session, tg_id=20000004)
    service = await _add_service(db_session, tutor)
    client = _make_client(tutor)
    db_session.add(client)
    await db_session.flush()

    cancelled_at = datetime(_MON_Y, _MON_M, _MON_D, 11, 30, tzinfo=UTC)
    cancelled = LessioBooking(
        tutor_id=tutor.id,
        client_id=client.id,
        service_id=service.id,
        starts_at=cancelled_at,
        duration_minutes=60,
        status="cancelled",
        price_kopecks=100000,
        price_stars=100,
        manage_token="x" * 64,
        payment_status="refunded",
        client_email="c@e.com",
        client_full_name="C",
    )
    db_session.add(cancelled)
    await db_session.commit()

    monday = datetime(_MON_Y, _MON_M, _MON_D, 0, 0, tzinfo=UTC)
    slots = await find_free_slots(
        db_session,
        tutor,
        date_from=monday,
        date_to=monday + timedelta(days=1),
        service=service,
    )
    assert cancelled_at in slots


async def test_buffer_respected(db_session: AsyncSession) -> None:
    """Buffer 15 мин: после booking 10:15-11:15 следующий допустимый старт ≥11:30."""
    tutor = await _setup_tutor(db_session, tg_id=20000005)
    service = await _add_service(db_session, tutor, duration_minutes=60)
    client = _make_client(tutor)
    db_session.add(client)
    await db_session.flush()

    booking = LessioBooking(
        tutor_id=tutor.id,
        client_id=client.id,
        service_id=service.id,
        starts_at=datetime(_MON_Y, _MON_M, _MON_D, 10, 15, tzinfo=UTC),
        duration_minutes=60,
        status="confirmed",
        price_kopecks=100000,
        price_stars=100,
        manage_token="b" * 64,
        payment_status="unpaid",
        client_email="c@e.com",
        client_full_name="C",
    )
    db_session.add(booking)
    await db_session.commit()

    monday = datetime(_MON_Y, _MON_M, _MON_D, 0, 0, tzinfo=UTC)
    slots = await find_free_slots(
        db_session,
        tutor,
        date_from=monday,
        date_to=monday + timedelta(days=1),
        service=service,
    )
    # 9:00 (before booking) и 11:30 (after booking+buffer) должны быть свободны.
    assert datetime(_MON_Y, _MON_M, _MON_D, 9, 0, tzinfo=UTC) in slots
    assert datetime(_MON_Y, _MON_M, _MON_D, 11, 30, tzinfo=UTC) in slots
    # 10:15 занят, 11:15 пересекается с buffer.
    assert datetime(_MON_Y, _MON_M, _MON_D, 10, 15, tzinfo=UTC) not in slots


async def test_past_slots_excluded(db_session: AsyncSession) -> None:
    """Слоты в прошлом не возвращаются даже если попадают в date_from."""
    tutor = await _setup_tutor(db_session, tg_id=20000006)
    service = await _add_service(db_session, tutor)
    await db_session.commit()

    now = datetime.now(UTC)
    yesterday = now - timedelta(days=1)
    slots = await find_free_slots(
        db_session,
        tutor,
        date_from=yesterday,
        date_to=now + timedelta(days=1),
        service=service,
    )
    for s in slots:
        assert s >= now


async def test_group_service_allows_multiple_at_same_slot(db_session: AsyncSession) -> None:
    """is_group_session=True: слот не блокируется одним booking'ом пока max_attendees > занято."""
    tutor = await _setup_tutor(db_session, tg_id=20000007)
    service = await _add_service(db_session, tutor, is_group_session=True, max_attendees=8)
    client = _make_client(tutor)
    db_session.add(client)
    await db_session.flush()

    starts_at = datetime(_MON_Y, _MON_M, _MON_D, 12, 0, tzinfo=UTC)
    for i in range(7):
        b = LessioBooking(
            tutor_id=tutor.id,
            client_id=client.id,
            service_id=service.id,
            starts_at=starts_at,
            duration_minutes=60,
            status="confirmed",
            price_kopecks=80000,
            price_stars=80,
            manage_token=f"g{i:>03}" + "z" * 60,
            payment_status="unpaid",
            client_email="c@e.com",
            client_full_name="C",
        )
        db_session.add(b)
    await db_session.commit()

    monday = datetime(_MON_Y, _MON_M, _MON_D, 0, 0, tzinfo=UTC)
    slots = await find_free_slots(
        db_session,
        tutor,
        date_from=monday,
        date_to=monday + timedelta(days=1),
        service=service,
    )
    assert starts_at in slots  # 7/8 — ещё свободен


async def test_returns_sorted_slots(db_session: AsyncSession) -> None:
    """Слоты возвращаются в хронологическом порядке."""
    tutor = await _setup_tutor(db_session, tg_id=20000008)
    service = await _add_service(db_session, tutor)
    await db_session.commit()

    monday = datetime(_MON_Y, _MON_M, _MON_D, 0, 0, tzinfo=UTC)
    slots = await find_free_slots(
        db_session,
        tutor,
        date_from=monday,
        date_to=monday + timedelta(days=7),
        service=service,
    )
    for i in range(len(slots) - 1):
        assert slots[i] < slots[i + 1]
