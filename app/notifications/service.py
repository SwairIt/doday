"""CRUD уведомлений: создать, список, счётчик непрочитанных, отметить прочитанным."""

from uuid import UUID

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.models import Notification


async def create_notification(
    session: AsyncSession,
    *,
    user_id: UUID,
    kind: str,
    title: str,
    body: str | None = None,
    link: str | None = None,
) -> Notification:
    """Создаёт уведомление пользователю и коммитит."""
    n = Notification(
        user_id=user_id,
        kind=kind[:30],
        title=title.strip()[:200],
        body=(body or "").strip()[:4000] or None,
        link=(link or "")[:300] or None,
    )
    session.add(n)
    await session.commit()
    await session.refresh(n)
    return n


async def list_notifications(
    session: AsyncSession, user_id: UUID, *, limit: int = 20
) -> list[Notification]:
    rows = await session.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(desc(Notification.created_at))
        .limit(limit)
    )
    return list(rows.scalars().all())


async def unread_count(session: AsyncSession, user_id: UUID) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        )
    ).scalar_one()


async def mark_all_read(session: AsyncSession, user_id: UUID) -> None:
    """Отмечает все непрочитанные уведомления пользователя прочитанными."""
    from datetime import UTC, datetime

    await session.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    await session.commit()
