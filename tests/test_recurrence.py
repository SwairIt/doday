"""Tests for recurring tasks: complete spawns next instance with shifted date."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.tasks.models import Task
from app.tasks.service import _shift_date, complete_task, create_task


async def _user(db_session: AsyncSession, email: str = "u@s.ru") -> User:
    u = User(email=email, password_hash="argon2-fake")
    db_session.add(u)
    await db_session.commit()
    return u


def test_shift_date_daily() -> None:
    from datetime import date

    assert _shift_date(date(2026, 5, 3), "daily") == date(2026, 5, 4)


def test_shift_date_weekly() -> None:
    from datetime import date

    assert _shift_date(date(2026, 5, 3), "weekly") == date(2026, 5, 10)


def test_shift_date_monthly_normal() -> None:
    from datetime import date

    assert _shift_date(date(2026, 5, 15), "monthly") == date(2026, 6, 15)


def test_shift_date_monthly_clamps_to_last_day() -> None:
    """Jan 31 → Feb 28 (or 29 in leap year)."""
    from datetime import date

    # 2026 is not a leap year → Feb 28
    assert _shift_date(date(2026, 1, 31), "monthly") == date(2026, 2, 28)
    # December → January next year
    assert _shift_date(date(2026, 12, 15), "monthly") == date(2027, 1, 15)


def test_shift_date_yearly_feb_29() -> None:
    from datetime import date

    # 2024 is leap, 2025 is not → Feb 29 2024 → Feb 28 2025
    assert _shift_date(date(2024, 2, 29), "yearly") == date(2025, 2, 28)


def test_shift_date_invalid_raises() -> None:
    from datetime import date

    with pytest.raises(ValueError):
        _shift_date(date(2026, 1, 1), "bogus")


async def test_complete_recurring_spawns_next(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    today = datetime.now(UTC).replace(hour=10, minute=0, second=0, microsecond=0)

    task = await create_task(
        db_session,
        user.id,
        title="Daily standup",
        due_at=today,
        recurrence="daily",
    )

    completed = await complete_task(db_session, user.id, task.id)
    assert completed.is_completed is True
    assert completed.completed_at is not None

    # A new instance should exist with same title and due_at + 1 day
    rows = (
        (
            await db_session.execute(
                select(Task).where(
                    Task.user_id == user.id,
                    Task.title == "Daily standup",
                    Task.is_completed.is_(False),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    spawned = rows[0]
    assert spawned.recurrence == "daily"
    assert spawned.due_at is not None
    assert spawned.due_at.date() == (today + timedelta(days=1)).date()
    assert spawned.id != task.id


async def test_complete_non_recurring_does_not_spawn(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    task = await create_task(db_session, user.id, title="One-off")
    await complete_task(db_session, user.id, task.id)

    rows = (
        (
            await db_session.execute(
                select(Task).where(Task.user_id == user.id, Task.title == "One-off")
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1  # only the original


async def test_recurring_without_due_at_does_not_spawn(
    db_session: AsyncSession,
) -> None:
    """If recurrence is set but no due_at, complete shouldn't crash or spawn."""
    user = await _user(db_session)
    task = await create_task(db_session, user.id, title="Recur no date", recurrence="weekly")

    await complete_task(db_session, user.id, task.id)
    rows = (
        (
            await db_session.execute(
                select(Task).where(Task.user_id == user.id, Task.title == "Recur no date")
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1  # nothing spawned


async def test_create_task_with_recurrence_via_api(
    db_session: AsyncSession,
) -> None:
    user = await _user(db_session)
    task = await create_task(db_session, user.id, title="X", recurrence="weekly")
    assert task.recurrence == "weekly"
