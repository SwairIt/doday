"""Публичная запись к репетитору: что принимает сервер, а что нет.

Форма записи анонимная. До этих проверок она принимала любое время, любой
адрес почты и любой статус брони — рабочие часы, отпуск и «не в прошлом»
были фильтрами только для интерфейса.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.models import LessioBooking, LessioService, LessioTutorProfile
from app.lessio.service import (
    BookingConflictError,
    auto_onboard_tutor,
    cancel_booking,
    create_booking,
    create_services_from_template,
    create_tutor_profile,
    ensure_slot_bookable,
    find_free_slots,
    reschedule_booking,
)


async def _setup(session: AsyncSession, *, tg_id: int) -> tuple[LessioTutorProfile, LessioService]:
    user, _ = await auto_onboard_tutor(session, telegram_user_id=tg_id)
    tutor = await create_tutor_profile(session, user=user, slug=f"hard_{tg_id}", display_name="T")
    services = await create_services_from_template(session, tutor=tutor, niche="english")
    await session.commit()
    return tutor, services[0]


async def _free_slot(session: AsyncSession, tutor: LessioTutorProfile, svc: LessioService) -> Any:
    slots = await find_free_slots(
        session,
        tutor,
        date_from=datetime.now(UTC),
        date_to=datetime.now(UTC) + timedelta(days=14),
        service=svc,
    )
    assert slots, "у дефолтного расписания должны быть свободные слоты"
    return slots[0]


# ── время записи ──────────────────────────────────────────────────────────


async def test_slot_in_the_past_rejected(db_session: AsyncSession) -> None:
    tutor, service = await _setup(db_session, tg_id=41000001)
    with pytest.raises(BookingConflictError):
        await ensure_slot_bookable(
            db_session,
            tutor=tutor,
            service=service,
            slot=datetime.now(UTC) - timedelta(days=3),
        )


async def test_slot_at_night_rejected(db_session: AsyncSession) -> None:
    """Три часа ночи не входит в рабочие часы — сетка его не предлагает."""
    tutor, service = await _setup(db_session, tg_id=41000002)
    night = (datetime.now(UTC) + timedelta(days=2)).replace(
        hour=3, minute=0, second=0, microsecond=0
    )
    with pytest.raises(BookingConflictError):
        await ensure_slot_bookable(db_session, tutor=tutor, service=service, slot=night)


async def test_slot_off_the_grid_rejected(db_session: AsyncSession) -> None:
    """Смещение на минуту от сетки — тоже отказ: иначе одно время можно
    забить сотней «почти одинаковых» записей."""
    tutor, service = await _setup(db_session, tg_id=41000003)
    slot = await _free_slot(db_session, tutor, service)
    with pytest.raises(BookingConflictError):
        await ensure_slot_bookable(
            db_session, tutor=tutor, service=service, slot=slot + timedelta(minutes=1)
        )


async def test_real_slot_accepted(db_session: AsyncSession) -> None:
    tutor, service = await _setup(db_session, tg_id=41000004)
    slot = await _free_slot(db_session, tutor, service)
    await ensure_slot_bookable(db_session, tutor=tutor, service=service, slot=slot)


@patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock)
async def test_public_form_rejects_arbitrary_time(
    mock_send: AsyncMock, client: AsyncClient, db_session: AsyncSession
) -> None:
    """Главный сценарий: POST мимо интерфейса, чтобы забить чужой календарь."""
    tutor, service = await _setup(db_session, tg_id=41000005)
    night = (datetime.now(UTC) + timedelta(days=1)).replace(hour=2, minute=0, second=0)

    resp = await client.post(
        f"/u/{tutor.slug}/book/{service.id}",
        data={
            "slot_iso": night.isoformat(),
            "client_email": "spam@e.com",
            "client_full_name": "Spam",
        },
    )
    assert resp.status_code == 400
    booked = (
        (await db_session.execute(select(LessioBooking).where(LessioBooking.tutor_id == tutor.id)))
        .scalars()
        .all()
    )
    assert booked == []
    mock_send.assert_not_awaited()


# ── адрес почты ───────────────────────────────────────────────────────────


@patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock)
async def test_public_form_rejects_broken_email(
    mock_send: AsyncMock, client: AsyncClient, db_session: AsyncSession
) -> None:
    """Поле было обычной строкой, то есть форма работала релеем на что угодно."""
    tutor, service = await _setup(db_session, tg_id=41000006)
    slot = await _free_slot(db_session, tutor, service)

    resp = await client.post(
        f"/u/{tutor.slug}/book/{service.id}",
        data={
            "slot_iso": slot.isoformat(),
            "client_email": "не почта вовсе",
            "client_full_name": "X",
        },
    )
    assert resp.status_code == 400
    mock_send.assert_not_awaited()


# ── статус брони ──────────────────────────────────────────────────────────


@patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock)
@patch("app.lessio.service.send_cancellation_email", new_callable=AsyncMock)
async def test_cancelled_booking_cannot_be_rescheduled(
    _mail: AsyncMock, _mail2: AsyncMock, db_session: AsyncSession
) -> None:
    """Ссылка управления не гаснет при отмене — значит статус обязан проверяться."""
    tutor, service = await _setup(db_session, tg_id=41000007)
    slot = await _free_slot(db_session, tutor, service)
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

    with pytest.raises(BookingConflictError):
        await reschedule_booking(
            db_session, booking=booking, new_slot=slot + timedelta(days=1), by="client"
        )
    with pytest.raises(BookingConflictError):
        await cancel_booking(db_session, booking=booking, by="client")
