"""Service for managing the school weekly schedule (schedule_slots)."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.school.models import ScheduleSlot


async def list_slots(session: AsyncSession, user_id: UUID) -> list[ScheduleSlot]:
    result = await session.execute(
        select(ScheduleSlot)
        .where(ScheduleSlot.user_id == user_id)
        .order_by(ScheduleSlot.weekday, ScheduleSlot.period)
    )
    return list(result.scalars().all())


async def upsert_slot(
    session: AsyncSession,
    user_id: UUID,
    *,
    weekday: int,
    period: int,
    subject_code: str,
    room: str | None,
    teacher: str | None,
) -> ScheduleSlot:
    if not 0 <= weekday <= 6:
        raise ValueError("weekday must be in 0..6")
    if not 1 <= period <= 10:
        raise ValueError("period must be in 1..10")

    existing = (
        await session.execute(
            select(ScheduleSlot).where(
                ScheduleSlot.user_id == user_id,
                ScheduleSlot.weekday == weekday,
                ScheduleSlot.period == period,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        slot = ScheduleSlot(
            user_id=user_id,
            weekday=weekday,
            period=period,
            subject_code=subject_code,
            room=room,
            teacher=teacher,
        )
        session.add(slot)
    else:
        existing.subject_code = subject_code
        existing.room = room
        existing.teacher = teacher
        slot = existing
    await session.commit()
    await session.refresh(slot)
    return slot


async def delete_slot(session: AsyncSession, user_id: UUID, *, weekday: int, period: int) -> None:
    await session.execute(
        delete(ScheduleSlot).where(
            ScheduleSlot.user_id == user_id,
            ScheduleSlot.weekday == weekday,
            ScheduleSlot.period == period,
        )
    )
    await session.commit()


async def list_today(session: AsyncSession, user_id: UUID) -> list[ScheduleSlot]:
    weekday = datetime.now(UTC).weekday()
    result = await session.execute(
        select(ScheduleSlot)
        .where(ScheduleSlot.user_id == user_id, ScheduleSlot.weekday == weekday)
        .order_by(ScheduleSlot.period)
    )
    return list(result.scalars().all())
