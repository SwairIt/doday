"""Reminder CRUD + queries для cron-worker'а."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.reminders.models import Reminder


async def create(
    session: AsyncSession,
    user_id: UUID,
    task_id: UUID,
    remind_at: datetime,
    kind: str = "custom",
) -> Reminder:
    """Создать напоминание."""
    r = Reminder(user_id=user_id, task_id=task_id, remind_at=remind_at, kind=kind)
    session.add(r)
    await session.commit()
    await session.refresh(r)
    return r


async def list_for_task(session: AsyncSession, task_id: UUID) -> list[Reminder]:
    rows = await session.execute(
        select(Reminder).where(Reminder.task_id == task_id).order_by(Reminder.remind_at)
    )
    return list(rows.scalars().all())


async def delete_by_id(session: AsyncSession, user_id: UUID, reminder_id: UUID) -> bool:
    """Удалить напоминание (с ownership check)."""
    r = (
        await session.execute(
            select(Reminder).where(Reminder.id == reminder_id, Reminder.user_id == user_id)
        )
    ).scalar_one_or_none()
    if r is None:
        return False
    await session.delete(r)
    await session.commit()
    return True


async def list_due(session: AsyncSession) -> list[Reminder]:
    """Все pending reminders где remind_at <= now. Используется cron-worker."""
    rows = await session.execute(
        select(Reminder).where(
            Reminder.remind_at <= datetime.now(UTC),
            Reminder.sent_at.is_(None),
        )
    )
    return list(rows.scalars().all())


async def mark_sent(session: AsyncSession, reminder_id: UUID) -> None:
    """Пометить отправленным."""
    r = (
        await session.execute(select(Reminder).where(Reminder.id == reminder_id))
    ).scalar_one_or_none()
    if r is not None:
        r.sent_at = datetime.now(UTC)
        await session.commit()


async def cleanup_old_sent(session: AsyncSession, older_than_days: int = 30) -> int:
    """GC: удалить sent_at-reminders старше N дней. Возвращает count удалённых."""
    from datetime import timedelta

    cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
    result = await session.execute(
        delete(Reminder).where(
            Reminder.sent_at.is_not(None),
            Reminder.sent_at < cutoff,
        )
    )
    await session.commit()
    rowcount = getattr(result, "rowcount", 0) or 0
    return int(rowcount)
