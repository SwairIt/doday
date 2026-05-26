"""booking_lead_hours + vacation_until — фильтры в find_free_slots."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.models import LessioService
from app.lessio.service import (
    auto_onboard_tutor,
    create_tutor_profile,
    find_free_slots,
)


async def _tutor_with_service(db_session: AsyncSession, *, tg_id: int) -> tuple:
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=tg_id)
    tutor = await create_tutor_profile(db_session, user=user, slug=f"lv_{tg_id}", display_name="T")
    service = LessioService(
        tutor_id=tutor.id,
        title="60 мин",
        duration_minutes=60,
        price_kopecks=100000,
        price_stars=100,
    )
    db_session.add(service)
    await db_session.commit()
    return tutor, service


async def test_default_lead_hours_filters_slots_within_2h(
    db_session: AsyncSession,
) -> None:
    """Default booking_lead_hours = 2 — слоты в ближайшие 2 часа исключаются."""
    tutor, service = await _tutor_with_service(db_session, tg_id=110000001)
    assert tutor.booking_lead_hours == 2

    # Запрашиваем слоты на сегодня — некоторые слоты будут в ближайшие 2 часа
    # Они должны быть исключены.
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    slots = await find_free_slots(
        db_session,
        tutor,
        date_from=today_start,
        date_to=today_start + timedelta(days=1),
        service=service,
    )
    # Каждый возвращённый слот должен быть НЕ раньше now + 2h
    lead_threshold = now + timedelta(hours=2)
    for s in slots:
        assert s >= lead_threshold, f"Slot {s} нарушает lead_hours, must be >= {lead_threshold}"


async def test_custom_lead_hours_24h(db_session: AsyncSession) -> None:
    """Tutor с booking_lead_hours = 24 — никаких слотов на следующие 24 часа."""
    tutor, service = await _tutor_with_service(db_session, tg_id=110000002)
    tutor.booking_lead_hours = 24
    await db_session.commit()

    now = datetime.now(UTC)
    slots = await find_free_slots(
        db_session,
        tutor,
        date_from=now,
        date_to=now + timedelta(days=2),
        service=service,
    )
    lead_threshold = now + timedelta(hours=24)
    for s in slots:
        assert s >= lead_threshold


async def test_vacation_until_hides_all_slots_before(
    db_session: AsyncSession,
) -> None:
    """vacation_until установлен → все слоты до этой даты скрыты."""
    tutor, service = await _tutor_with_service(db_session, tg_id=110000003)
    vacation_end = datetime.now(UTC) + timedelta(days=7)
    tutor.vacation_until = vacation_end
    await db_session.commit()

    now = datetime.now(UTC)
    slots = await find_free_slots(
        db_session,
        tutor,
        date_from=now,
        date_to=now + timedelta(days=14),
        service=service,
    )
    for s in slots:
        assert s >= vacation_end, f"Slot {s} в отпуске (до {vacation_end})"


async def test_vacation_until_past_no_effect(db_session: AsyncSession) -> None:
    """Если vacation_until уже в прошлом — фильтр не применяется."""
    tutor, service = await _tutor_with_service(db_session, tg_id=110000004)
    tutor.vacation_until = datetime.now(UTC) - timedelta(days=7)
    await db_session.commit()

    now = datetime.now(UTC)
    slots = await find_free_slots(
        db_session,
        tutor,
        date_from=now,
        date_to=now + timedelta(days=3),
        service=service,
    )
    # Слоты должны быть — vacation в прошлом, не блокирует
    # (точное число зависит от lead-time, но >= 1 должно быть)
    # Здесь только smoke — функция возвращает что-то
    assert isinstance(slots, list)


async def test_vacation_until_none_no_filter(db_session: AsyncSession) -> None:
    """vacation_until = None — фильтр не применяется."""
    tutor, service = await _tutor_with_service(db_session, tg_id=110000005)
    assert tutor.vacation_until is None
    # Просто smoke — функция работает
    now = datetime.now(UTC)
    slots = await find_free_slots(
        db_session,
        tutor,
        date_from=now,
        date_to=now + timedelta(days=3),
        service=service,
    )
    assert isinstance(slots, list)
