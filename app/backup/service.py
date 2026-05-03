"""Backup/restore service — full user-data export and import as JSON."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.labels.models import Label, task_labels
from app.projects.models import Project
from app.projects.service import slugify
from app.sections.models import Section
from app.tasks.models import Task, TaskPriority

EXPORT_FORMAT_VERSION = 1


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


async def export_user_data(session: AsyncSession, user_id: UUID) -> dict[str, Any]:
    """Build a complete dump of one user's projects, sections, tasks, labels."""
    projects = (
        (await session.execute(select(Project).where(Project.user_id == user_id))).scalars().all()
    )
    sections = (
        (await session.execute(select(Section).where(Section.user_id == user_id))).scalars().all()
    )
    tasks = (await session.execute(select(Task).where(Task.user_id == user_id))).scalars().all()
    labels = (await session.execute(select(Label).where(Label.user_id == user_id))).scalars().all()
    task_label_rows = await session.execute(
        select(task_labels.c.task_id, task_labels.c.label_id)
        .join(Task, Task.id == task_labels.c.task_id)
        .where(Task.user_id == user_id)
    )
    task_label_pairs = [{"task_id": str(t), "label_id": str(lb)} for t, lb in task_label_rows.all()]

    return {
        "format_version": EXPORT_FORMAT_VERSION,
        "exported_at": datetime.now(UTC).isoformat(),
        "projects": [
            {
                "id": str(p.id),
                "name": p.name,
                "slug": p.slug,
                "color": p.color,
                "position": p.position,
                "is_inbox": p.is_inbox,
                "is_archived": p.is_archived,
                "is_favorite": p.is_favorite,
                "description": p.description,
            }
            for p in projects
        ],
        "sections": [
            {
                "id": str(s.id),
                "project_id": str(s.project_id),
                "name": s.name,
                "position": s.position,
            }
            for s in sections
        ],
        "tasks": [
            {
                "id": str(t.id),
                "project_id": str(t.project_id),
                "section_id": str(t.section_id) if t.section_id else None,
                "parent_task_id": str(t.parent_task_id) if t.parent_task_id else None,
                "title": t.title,
                "description": t.description,
                "due_at": _iso(t.due_at),
                "due_date_only": t.due_date_only,
                "priority": t.priority.value,
                "is_completed": t.is_completed,
                "completed_at": _iso(t.completed_at),
                "position": t.position,
                "recurrence": t.recurrence,
            }
            for t in tasks
        ],
        "labels": [{"id": str(lb.id), "name": lb.name, "color": lb.color} for lb in labels],
        "task_labels": task_label_pairs,
    }


class ImportError_(Exception):
    """Raised when an import payload is malformed or version-mismatched."""


async def import_user_data(
    session: AsyncSession, user_id: UUID, payload: dict[str, Any]
) -> dict[str, int]:
    """Import a backup payload. Skips Inbox (relies on existing one), remaps IDs."""
    if not isinstance(payload, dict) or payload.get("format_version") != EXPORT_FORMAT_VERSION:
        raise ImportError_(f"unsupported format_version (expected {EXPORT_FORMAT_VERSION})")

    project_id_map: dict[str, UUID] = {}
    section_id_map: dict[str, UUID] = {}
    task_id_map: dict[str, UUID] = {}
    label_id_map: dict[str, UUID] = {}

    inbox = (
        await session.execute(
            select(Project).where(Project.user_id == user_id, Project.is_inbox.is_(True))
        )
    ).scalar_one_or_none()

    project_count = 0
    for p in payload.get("projects", []):
        if p.get("is_inbox"):
            if inbox is not None:
                project_id_map[p["id"]] = inbox.id
            continue
        new_proj = Project(
            user_id=user_id,
            name=p["name"],
            slug=slugify(p["name"]),
            color=p.get("color", "violet"),
            position=p.get("position", 0),
            is_archived=p.get("is_archived", False),
            is_favorite=p.get("is_favorite", False),
            description=p.get("description"),
        )
        session.add(new_proj)
        await session.flush()
        project_id_map[p["id"]] = new_proj.id
        project_count += 1

    section_count = 0
    for s in payload.get("sections", []):
        new_proj_id = project_id_map.get(s["project_id"])
        if new_proj_id is None:
            continue
        new_sec = Section(
            user_id=user_id,
            project_id=new_proj_id,
            name=s["name"],
            position=s.get("position", 0),
        )
        session.add(new_sec)
        await session.flush()
        section_id_map[s["id"]] = new_sec.id
        section_count += 1

    label_count = 0
    for lb in payload.get("labels", []):
        new_lb = Label(
            user_id=user_id,
            name=lb["name"],
            slug=slugify(lb["name"]),
            color=lb.get("color", "violet"),
        )
        session.add(new_lb)
        await session.flush()
        label_id_map[lb["id"]] = new_lb.id
        label_count += 1

    raw_tasks = payload.get("tasks", [])
    pending = list(raw_tasks)
    task_count = 0
    while pending:
        progressed = False
        next_round: list[dict[str, Any]] = []
        for t in pending:
            new_proj_id = project_id_map.get(t["project_id"])
            if new_proj_id is None:
                continue  # orphan
            parent_id_in = t.get("parent_task_id")
            new_parent_id: UUID | None = None
            if parent_id_in:
                if parent_id_in not in task_id_map:
                    next_round.append(t)
                    continue
                new_parent_id = task_id_map[parent_id_in]
            sec_id_in = t.get("section_id")
            new_sec_id: UUID | None = None
            if sec_id_in:
                new_sec_id = section_id_map.get(sec_id_in)
            try:
                prio = TaskPriority(t.get("priority", "p4"))
            except ValueError:
                prio = TaskPriority.P4
            due_at = None
            if t.get("due_at"):
                try:
                    due_at = datetime.fromisoformat(t["due_at"].replace("Z", "+00:00"))
                except ValueError:
                    due_at = None
            completed_at = None
            if t.get("completed_at"):
                try:
                    completed_at = datetime.fromisoformat(t["completed_at"].replace("Z", "+00:00"))
                except ValueError:
                    completed_at = None
            new_task = Task(
                user_id=user_id,
                project_id=new_proj_id,
                section_id=new_sec_id,
                parent_task_id=new_parent_id,
                title=t.get("title", "(без названия)"),
                description=t.get("description"),
                due_at=due_at,
                due_date_only=t.get("due_date_only", True),
                priority=prio,
                is_completed=t.get("is_completed", False),
                completed_at=completed_at,
                position=t.get("position", 0),
                recurrence=t.get("recurrence"),
            )
            session.add(new_task)
            await session.flush()
            task_id_map[t["id"]] = new_task.id
            task_count += 1
            progressed = True
        if not progressed:
            break
        pending = next_round

    label_link_count = 0
    for tl in payload.get("task_labels", []):
        new_t = task_id_map.get(tl.get("task_id"))
        new_l = label_id_map.get(tl.get("label_id"))
        if new_t is None or new_l is None:
            continue
        await session.execute(task_labels.insert().values(task_id=new_t, label_id=new_l))
        label_link_count += 1

    await session.commit()
    return {
        "projects": project_count,
        "sections": section_count,
        "tasks": task_count,
        "labels": label_count,
        "task_labels": label_link_count,
    }
