"""Label service — CRUD plus attach/detach to tasks."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.labels.models import Label, task_labels
from app.projects.service import slugify
from app.tasks.service import get_task


class LabelNotFound(Exception):
    """Label does not exist or belongs to another user."""


async def list_labels(session: AsyncSession, user_id: UUID) -> list[Label]:
    result = await session.execute(
        select(Label).where(Label.user_id == user_id).order_by(Label.created_at)
    )
    return list(result.scalars().all())


async def get_label(session: AsyncSession, user_id: UUID, label_id: UUID) -> Label:
    label = await session.get(Label, label_id)
    if label is None or label.user_id != user_id:
        raise LabelNotFound(str(label_id))
    return label


async def create_label(
    session: AsyncSession, user_id: UUID, *, name: str, color: str = "violet"
) -> Label:
    label = Label(user_id=user_id, name=name, slug=slugify(name), color=color)
    session.add(label)
    await session.commit()
    await session.refresh(label)
    return label


async def find_or_create_by_name(session: AsyncSession, user_id: UUID, name: str) -> Label:
    """For the @label syntax in quick-add: re-use existing label by name (case-insensitive)."""
    cleaned = name.strip()
    result = await session.execute(
        select(Label).where(Label.user_id == user_id, Label.name == cleaned)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing
    return await create_label(session, user_id, name=cleaned)


async def update_label(
    session: AsyncSession,
    user_id: UUID,
    label_id: UUID,
    *,
    name: str | None = None,
    color: str | None = None,
) -> Label:
    label = await get_label(session, user_id, label_id)
    if name is not None:
        label.name = name
    if color is not None:
        label.color = color
    await session.commit()
    await session.refresh(label)
    return label


async def delete_label(session: AsyncSession, user_id: UUID, label_id: UUID) -> None:
    label = await get_label(session, user_id, label_id)
    await session.delete(label)
    await session.commit()


async def attach_label(session: AsyncSession, user_id: UUID, task_id: UUID, label_id: UUID) -> None:
    """Attach a label to a task. Idempotent: re-attaching is a no-op."""
    await get_task(session, user_id, task_id)
    await get_label(session, user_id, label_id)

    existing = await session.execute(
        select(task_labels).where(
            task_labels.c.task_id == task_id, task_labels.c.label_id == label_id
        )
    )
    if existing.first() is not None:
        return
    await session.execute(task_labels.insert().values(task_id=task_id, label_id=label_id))
    await session.commit()


async def detach_label(session: AsyncSession, user_id: UUID, task_id: UUID, label_id: UUID) -> None:
    """Detach a label from a task. Idempotent."""
    await get_task(session, user_id, task_id)
    await get_label(session, user_id, label_id)
    await session.execute(
        task_labels.delete().where(
            task_labels.c.task_id == task_id, task_labels.c.label_id == label_id
        )
    )
    await session.commit()


async def list_task_labels(session: AsyncSession, user_id: UUID, task_id: UUID) -> list[Label]:
    """All labels currently attached to a task."""
    await get_task(session, user_id, task_id)
    result = await session.execute(
        select(Label)
        .join(task_labels, task_labels.c.label_id == Label.id)
        .where(task_labels.c.task_id == task_id)
        .order_by(Label.name)
    )
    return list(result.scalars().all())
