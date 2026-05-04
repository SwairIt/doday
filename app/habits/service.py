"""Habit tracker business logic — CRUD, check-in toggle, streak math."""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.habits.models import Habit, HabitCheckin


class HabitNotFound(Exception):
    """Asked for a habit that doesn't exist for this user."""


async def list_habits(session: AsyncSession, user_id: UUID) -> list[Habit]:
    result = await session.execute(
        select(Habit)
        .where(Habit.user_id == user_id, Habit.archived_at.is_(None))
        .order_by(Habit.created_at)
    )
    return list(result.scalars().all())


async def create_habit(
    session: AsyncSession,
    user_id: UUID,
    *,
    name: str,
    emoji: str = "✅",
    color: str = "violet",
) -> Habit:
    habit = Habit(user_id=user_id, name=name, emoji=emoji, color=color)
    session.add(habit)
    await session.commit()
    await session.refresh(habit)
    return habit


async def get_habit(session: AsyncSession, user_id: UUID, habit_id: UUID) -> Habit:
    result = await session.execute(
        select(Habit).where(Habit.id == habit_id, Habit.user_id == user_id)
    )
    habit = result.scalar_one_or_none()
    if habit is None:
        raise HabitNotFound(habit_id)
    return habit


async def update_habit(
    session: AsyncSession,
    user_id: UUID,
    habit_id: UUID,
    *,
    name: str | None = None,
    emoji: str | None = None,
    color: str | None = None,
) -> Habit:
    habit = await get_habit(session, user_id, habit_id)
    if name is not None:
        habit.name = name
    if emoji is not None:
        habit.emoji = emoji
    if color is not None:
        habit.color = color
    await session.commit()
    await session.refresh(habit)
    return habit


async def archive_habit(session: AsyncSession, user_id: UUID, habit_id: UUID) -> None:
    habit = await get_habit(session, user_id, habit_id)
    habit.archived_at = datetime.now(UTC)
    await session.commit()


async def check_in(
    session: AsyncSession, user_id: UUID, habit_id: UUID, *, on_date: date | None = None
) -> HabitCheckin:
    """Idempotent — if a check-in for the date already exists, returns it."""
    habit = await get_habit(session, user_id, habit_id)
    target = on_date or datetime.now(UTC).date()
    existing = (
        await session.execute(
            select(HabitCheckin).where(
                HabitCheckin.habit_id == habit.id, HabitCheckin.checkin_date == target
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    row = HabitCheckin(habit_id=habit.id, user_id=user_id, checkin_date=target)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def uncheck(
    session: AsyncSession, user_id: UUID, habit_id: UUID, *, on_date: date | None = None
) -> None:
    habit = await get_habit(session, user_id, habit_id)
    target = on_date or datetime.now(UTC).date()
    await session.execute(
        delete(HabitCheckin).where(
            HabitCheckin.habit_id == habit.id, HabitCheckin.checkin_date == target
        )
    )
    await session.commit()


async def stats_for(session: AsyncSession, user_id: UUID, habit_id: UUID) -> dict[str, object]:
    """30-day window + current/longest streak for a habit."""
    habit = await get_habit(session, user_id, habit_id)
    today = datetime.now(UTC).date()
    horizon = today - timedelta(days=400)
    rows = await session.execute(
        select(HabitCheckin.checkin_date)
        .where(
            HabitCheckin.habit_id == habit.id,
            HabitCheckin.checkin_date >= horizon,
        )
        .order_by(HabitCheckin.checkin_date.desc())
    )
    days: set[date] = {r[0] for r in rows.all()}

    last_30 = [(today - timedelta(days=i)) in days for i in range(30)]

    current = 0
    if today in days:
        cursor = today
    elif (today - timedelta(days=1)) in days:
        cursor = today - timedelta(days=1)
    else:
        cursor = None
    if cursor is not None:
        while cursor in days:
            current += 1
            cursor -= timedelta(days=1)

    longest = 0
    sorted_days = sorted(days)
    if sorted_days:
        run = 1
        longest = 1
        for i in range(1, len(sorted_days)):
            if (sorted_days[i] - sorted_days[i - 1]).days == 1:
                run += 1
                longest = max(longest, run)
            else:
                run = 1

    return {
        "last_30": last_30,
        "current_streak": current,
        "longest_streak": max(longest, current),
        "today_done": today in days,
    }
