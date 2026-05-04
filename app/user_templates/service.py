"""User-template service — snapshot a project + instantiate from snapshot."""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.projects.models import Project
from app.projects.service import ProjectNotFound, create_project, get_project
from app.sections.models import Section
from app.tasks.models import Task, TaskPriority
from app.user_templates.models import UserTemplate


class UserTemplateNotFound(Exception):
    """Template does not exist or does not belong to user."""


def _snapshot_payload(
    project: Project, sections: list[Section], tasks: list[Task]
) -> dict[str, Any]:
    """Convert ORM rows into a portable JSON structure (no IDs, only relative refs)."""
    sec_index = {s.id: i for i, s in enumerate(sections)}
    sec_data = [{"name": s.name, "position": s.position} for s in sections]
    task_index = {t.id: i for i, t in enumerate(tasks)}
    task_data = []
    for t in tasks:
        task_data.append(
            {
                "title": t.title,
                "description": t.description,
                "priority": t.priority.value,
                "section_idx": sec_index.get(t.section_id) if t.section_id else None,
                "parent_idx": task_index.get(t.parent_task_id) if t.parent_task_id else None,
                "position": t.position,
                "recurrence": t.recurrence,
            }
        )
    return {
        "color": project.color,
        "description": project.description,
        "sections": sec_data,
        "tasks": task_data,
    }


async def list_user_templates(session: AsyncSession, user_id: UUID) -> list[UserTemplate]:
    result = await session.execute(
        select(UserTemplate)
        .where(UserTemplate.user_id == user_id)
        .order_by(UserTemplate.created_at.desc())
    )
    return list(result.scalars().all())


async def get_user_template(
    session: AsyncSession, user_id: UUID, template_id: UUID
) -> UserTemplate:
    obj = await session.get(UserTemplate, template_id)
    if obj is None or obj.user_id != user_id:
        raise UserTemplateNotFound(str(template_id))
    return obj


async def save_project_as_template(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    *,
    name: str | None = None,
) -> UserTemplate:
    """Snapshot the active state of a project into a reusable user template."""
    project = await get_project(session, user_id, project_id)
    sections = (
        (
            await session.execute(
                select(Section)
                .where(Section.user_id == user_id, Section.project_id == project.id)
                .order_by(Section.position)
            )
        )
        .scalars()
        .all()
    )
    tasks = (
        (
            await session.execute(
                select(Task)
                .where(
                    Task.user_id == user_id,
                    Task.project_id == project.id,
                    Task.is_completed.is_(False),
                )
                .order_by(Task.position)
            )
        )
        .scalars()
        .all()
    )
    payload = _snapshot_payload(project, list(sections), list(tasks))
    obj = UserTemplate(
        user_id=user_id,
        name=name or f"Шаблон: {project.name}",
        color=project.color,
        description=project.description,
        payload=payload,
    )
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def instantiate_user_template(
    session: AsyncSession,
    user_id: UUID,
    template_id: UUID,
    *,
    name: str | None = None,
) -> Project:
    """Materialize a saved template back into a fresh project."""
    template = await get_user_template(session, user_id, template_id)
    payload = template.payload or {}
    color = payload.get("color") or template.color or "violet"
    project = await create_project(session, user_id, name=name or template.name, color=color)
    if template.description:
        project.description = template.description
    await session.commit()
    await session.refresh(project)

    sec_objs: list[Section] = []
    for sd in payload.get("sections", []):
        sec = Section(
            user_id=user_id,
            project_id=project.id,
            name=sd.get("name", "?"),
            position=sd.get("position", len(sec_objs)),
        )
        session.add(sec)
        sec_objs.append(sec)
    await session.commit()
    for s in sec_objs:
        await session.refresh(s)

    raw_tasks = payload.get("tasks", [])
    task_objs: list[Task] = [None for _ in raw_tasks]  # type: ignore[misc]
    pending = list(enumerate(raw_tasks))
    while pending:
        progressed = False
        next_round: list[tuple[int, dict[str, Any]]] = []
        for idx, td in pending:
            parent_idx = td.get("parent_idx")
            new_parent_id: UUID | None = None
            if parent_idx is not None:
                if parent_idx >= len(task_objs) or task_objs[parent_idx] is None:
                    next_round.append((idx, td))
                    continue
                new_parent_id = task_objs[parent_idx].id
            sec_idx = td.get("section_idx")
            new_section_id: UUID | None = None
            if sec_idx is not None and 0 <= sec_idx < len(sec_objs):
                new_section_id = sec_objs[sec_idx].id
            try:
                prio = TaskPriority(td.get("priority", "p4"))
            except ValueError:
                prio = TaskPriority.P4
            new_t = Task(
                user_id=user_id,
                project_id=project.id,
                section_id=new_section_id,
                parent_task_id=new_parent_id,
                title=td.get("title", "?"),
                description=td.get("description"),
                priority=prio,
                position=td.get("position", idx),
                recurrence=td.get("recurrence"),
            )
            session.add(new_t)
            await session.flush()
            task_objs[idx] = new_t
            progressed = True
        if not progressed:
            break
        pending = next_round
    await session.commit()
    await session.refresh(project)
    return project


async def delete_user_template(session: AsyncSession, user_id: UUID, template_id: UUID) -> None:
    obj = await get_user_template(session, user_id, template_id)
    await session.delete(obj)
    await session.commit()


__all__ = [
    "ProjectNotFound",
    "UserTemplateNotFound",
    "delete_user_template",
    "get_user_template",
    "instantiate_user_template",
    "list_user_templates",
    "save_project_as_template",
]
