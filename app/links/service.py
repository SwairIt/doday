"""Task-link service — create, list, delete + fetch with target task metadata."""

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.links.models import TaskLink
from app.links.schemas import LinkedTaskOut
from app.projects.models import Project
from app.tasks.models import Task


async def create_link(
    session: AsyncSession,
    user_id: UUID,
    source_task_id: UUID,
    target_task_id: UUID,
    note: str | None = None,
) -> TaskLink:
    """Create a directional link source→target. Idempotent on the (source,target) pair."""
    if source_task_id == target_task_id:
        raise ValueError("нельзя связать задачу саму с собой")

    # Both tasks must belong to this user (cross-project is fine; cross-user is not).
    rows = await session.execute(
        select(Task.id).where(
            Task.user_id == user_id, Task.id.in_([source_task_id, target_task_id])
        )
    )
    found = {row[0] for row in rows.all()}
    if source_task_id not in found or target_task_id not in found:
        raise PermissionError("задача не найдена")

    existing = await session.execute(
        select(TaskLink).where(
            TaskLink.source_task_id == source_task_id,
            TaskLink.target_task_id == target_task_id,
        )
    )
    found_link = existing.scalar_one_or_none()
    if found_link is not None:
        if note is not None and note != found_link.note:
            found_link.note = note
            await session.commit()
        return found_link

    link = TaskLink(
        user_id=user_id,
        source_task_id=source_task_id,
        target_task_id=target_task_id,
        note=note,
    )
    session.add(link)
    await session.commit()
    return link


async def delete_link(session: AsyncSession, user_id: UUID, link_id: UUID) -> bool:
    """Delete one link if it belongs to this user. Returns True if something was removed."""
    result = await session.execute(
        select(TaskLink).where(TaskLink.id == link_id, TaskLink.user_id == user_id)
    )
    link = result.scalar_one_or_none()
    if link is None:
        return False
    await session.delete(link)
    await session.commit()
    return True


async def list_links_for_task(
    session: AsyncSession, user_id: UUID, task_id: UUID
) -> list[LinkedTaskOut]:
    """All outgoing AND incoming links for a task — flat list with `direction`."""
    rows = await session.execute(
        select(TaskLink, Task, Project)
        .join(
            Task,
            ((TaskLink.source_task_id == task_id) & (TaskLink.target_task_id == Task.id))
            | ((TaskLink.target_task_id == task_id) & (TaskLink.source_task_id == Task.id)),
        )
        .join(Project, Project.id == Task.project_id)
        .where(
            TaskLink.user_id == user_id,
            or_(TaskLink.source_task_id == task_id, TaskLink.target_task_id == task_id),
            Task.deleted_at.is_(None),
        )
        .order_by(TaskLink.created_at.desc())
    )
    out: list[LinkedTaskOut] = []
    for link, task, project in rows.all():
        direction = "outgoing" if link.source_task_id == task_id else "incoming"
        out.append(
            LinkedTaskOut(
                link_id=link.id,
                task_id=task.id,
                title=task.title,
                project_id=project.id,
                project_name=project.name,
                is_completed=task.is_completed,
                direction=direction,
                note=link.note,
                created_at=link.created_at,
            )
        )
    return out


async def list_all_links_for_user(session: AsyncSession, user_id: UUID) -> list[tuple[UUID, UUID]]:
    """Return all (source_id, target_id) pairs the user owns — used by the graph view."""
    rows = await session.execute(
        select(TaskLink.source_task_id, TaskLink.target_task_id).where(TaskLink.user_id == user_id)
    )
    return [(row[0], row[1]) for row in rows.all()]


async def build_graph(session: AsyncSession, user_id: UUID) -> dict[str, list[dict[str, object]]]:
    """Aggregate active tasks + their links + parent-child + project-clustering edges
    into a node/edge JSON the /doday/app/graph view can render."""
    # Active tasks only (skip trash + completed older than a month).
    from datetime import UTC, datetime, timedelta

    cutoff = datetime.now(UTC) - timedelta(days=30)

    rows = await session.execute(
        select(
            Task.id,
            Task.title,
            Task.is_completed,
            Task.completed_at,
            Task.parent_task_id,
            Project.id,
            Project.name,
            Project.color,
        )
        .join(Project, Project.id == Task.project_id)
        .where(
            Task.user_id == user_id,
            Task.deleted_at.is_(None),
            ((Task.is_completed.is_(False)) | (Task.completed_at >= cutoff)),
        )
        .limit(800)
    )
    nodes: list[dict[str, object]] = []
    parent_pairs: list[tuple[UUID, UUID]] = []
    seen: set[UUID] = set()
    for tid, title, done, _comp_at, parent_id, pid, pname, pcolor in rows.all():
        seen.add(tid)
        nodes.append(
            {
                "id": str(tid),
                "title": title,
                "is_completed": bool(done),
                "project_id": str(pid),
                "project_name": pname,
                "project_color": pcolor,
            }
        )
        if parent_id is not None:
            parent_pairs.append((parent_id, tid))

    edges: list[dict[str, object]] = []
    for src, tgt in parent_pairs:
        if src in seen and tgt in seen:
            edges.append({"source": str(src), "target": str(tgt), "kind": "parent"})

    link_pairs = await list_all_links_for_user(session, user_id)
    for src, tgt in link_pairs:
        if src in seen and tgt in seen:
            edges.append({"source": str(src), "target": str(tgt), "kind": "link"})

    return {"nodes": nodes, "edges": edges}
