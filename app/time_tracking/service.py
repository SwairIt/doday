"""Time-tracking business logic — start/stop, totals, today summary."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.service import get_task
from app.time_tracking.models import TimeEntry


class TimerNotRunning(Exception):
    """Tried to stop a timer when nothing was running."""


async def start_timer(session: AsyncSession, user_id: UUID, task_id: UUID) -> TimeEntry:
    """Start a timer on a task. Stops any other running timers for this user
    so only one timer is active at a time (the user expectation)."""
    await get_task(session, user_id, task_id)
    # Close any other open timers first.
    open_rows = (
        (
            await session.execute(
                select(TimeEntry).where(TimeEntry.user_id == user_id, TimeEntry.ended_at.is_(None))
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    for row in open_rows:
        row.ended_at = now
        row.duration_seconds = max(0, int((now - row.started_at).total_seconds()))

    entry = TimeEntry(user_id=user_id, task_id=task_id, started_at=now)
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


async def stop_timer(session: AsyncSession, user_id: UUID, task_id: UUID) -> TimeEntry:
    open_row = (
        await session.execute(
            select(TimeEntry)
            .where(
                TimeEntry.user_id == user_id,
                TimeEntry.task_id == task_id,
                TimeEntry.ended_at.is_(None),
            )
            .order_by(TimeEntry.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if open_row is None:
        raise TimerNotRunning(str(task_id))
    now = datetime.now(UTC)
    open_row.ended_at = now
    open_row.duration_seconds = max(0, int((now - open_row.started_at).total_seconds()))
    await session.commit()
    await session.refresh(open_row)
    return open_row


async def total_seconds_for_task(session: AsyncSession, user_id: UUID, task_id: UUID) -> int:
    """Sum of completed entries + the running entry (if any) computed live."""
    row = (
        await session.execute(
            select(
                func.coalesce(func.sum(TimeEntry.duration_seconds), 0),
            ).where(
                TimeEntry.user_id == user_id,
                TimeEntry.task_id == task_id,
                TimeEntry.ended_at.is_not(None),
            )
        )
    ).first()
    completed = int(row[0] if row else 0)

    running = (
        await session.execute(
            select(TimeEntry)
            .where(
                TimeEntry.user_id == user_id,
                TimeEntry.task_id == task_id,
                TimeEntry.ended_at.is_(None),
            )
            .order_by(TimeEntry.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    live_extra = (
        max(0, int((datetime.now(UTC) - running.started_at).total_seconds())) if running else 0
    )
    return completed + live_extra


async def total_seconds_today(session: AsyncSession, user_id: UUID) -> int:
    """Across all tasks: how much time the user logged today (UTC)."""
    today = datetime.now(UTC).date()
    completed_row = (
        await session.execute(
            select(func.coalesce(func.sum(TimeEntry.duration_seconds), 0)).where(
                TimeEntry.user_id == user_id,
                TimeEntry.ended_at.is_not(None),
                func.date(TimeEntry.started_at) == today,
            )
        )
    ).first()
    completed = int(completed_row[0] if completed_row else 0)
    running = (
        await session.execute(
            select(TimeEntry).where(
                TimeEntry.user_id == user_id,
                TimeEntry.ended_at.is_(None),
                func.date(TimeEntry.started_at) == today,
            )
        )
    ).scalar_one_or_none()
    live_extra = (
        max(0, int((datetime.now(UTC) - running.started_at).total_seconds())) if running else 0
    )
    return completed + live_extra


async def get_running_for_user(session: AsyncSession, user_id: UUID) -> TimeEntry | None:
    return (
        await session.execute(
            select(TimeEntry)
            .where(TimeEntry.user_id == user_id, TimeEntry.ended_at.is_(None))
            .order_by(TimeEntry.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
