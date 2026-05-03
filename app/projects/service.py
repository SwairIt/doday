"""Project service — CRUD and Inbox guarantee."""

import re
import secrets
import unicodedata
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.projects.models import Project
from app.projects.templates_data import ProjectTemplate


def slugify(name: str) -> str:
    """Build a stable, unique slug. Cyrillic names degrade to 'p-XXXX'."""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-") or "p"
    return f"{base[:30]}-{secrets.token_urlsafe(4).lower()}"


class ProjectNotFound(Exception):
    """Project does not exist or belongs to another user."""


class CannotDeleteInbox(Exception):
    """Inbox is special-cased — never deletable."""


async def list_projects(session: AsyncSession, user_id: UUID) -> list[Project]:
    result = await session.execute(
        select(Project)
        .where(Project.user_id == user_id, Project.is_archived.is_(False))
        .order_by(Project.position, Project.created_at)
    )
    return list(result.scalars().all())


async def get_project(session: AsyncSession, user_id: UUID, project_id: UUID) -> Project:
    project = await session.get(Project, project_id)
    if project is None or project.user_id != user_id:
        raise ProjectNotFound(str(project_id))
    return project


async def get_project_by_slug(session: AsyncSession, user_id: UUID, slug: str) -> Project:
    result = await session.execute(
        select(Project).where(Project.user_id == user_id, Project.slug == slug)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise ProjectNotFound(slug)
    return project


async def create_project(
    session: AsyncSession, user_id: UUID, *, name: str, color: str = "violet"
) -> Project:
    last = (
        await session.execute(
            select(Project)
            .where(Project.user_id == user_id)
            .order_by(Project.position.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    position = (last.position + 1) if last else 0

    project = Project(
        user_id=user_id,
        name=name,
        slug=slugify(name),
        color=color,
        position=position,
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def update_project(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    *,
    name: str | None = None,
    color: str | None = None,
    is_archived: bool | None = None,
) -> Project:
    project = await get_project(session, user_id, project_id)
    if name is not None:
        project.name = name
    if color is not None:
        project.color = color
    if is_archived is not None:
        project.is_archived = is_archived
    await session.commit()
    await session.refresh(project)
    return project


async def delete_project(session: AsyncSession, user_id: UUID, project_id: UUID) -> None:
    project = await get_project(session, user_id, project_id)
    if project.is_inbox:
        raise CannotDeleteInbox(str(project_id))
    await session.delete(project)
    await session.commit()


async def create_from_template(
    session: AsyncSession, user_id: UUID, template: ProjectTemplate, *, name: str | None = None
) -> Project:
    """Materialize a project template — project + sections + tasks."""
    from app.sections.models import Section
    from app.tasks.models import Task, TaskPriority

    project = await create_project(
        session, user_id, name=name or template["name"], color=template["color"]
    )

    today = datetime.now(UTC)
    section_objs: list[Section] = []
    for idx, sec_def in enumerate(template["sections"]):
        section = Section(
            user_id=user_id,
            project_id=project.id,
            name=sec_def["name"],
            position=idx,
        )
        session.add(section)
        section_objs.append(section)
    await session.commit()
    for s in section_objs:
        await session.refresh(s)

    position = 0
    for sec_obj, sec_def in zip(section_objs, template["sections"], strict=True):
        for t_def in sec_def["tasks"]:
            due_at = None
            if "due_offset_days" in t_def:
                due_at = today + timedelta(days=t_def["due_offset_days"])
            session.add(
                Task(
                    user_id=user_id,
                    project_id=project.id,
                    section_id=sec_obj.id,
                    title=t_def["title"],
                    priority=TaskPriority(t_def.get("priority", "p4")),
                    due_at=due_at,
                    due_date_only=True,
                    position=position,
                )
            )
            position += 1
    for t_def in template["loose_tasks"]:
        due_at = None
        if "due_offset_days" in t_def:
            due_at = today + timedelta(days=t_def["due_offset_days"])
        session.add(
            Task(
                user_id=user_id,
                project_id=project.id,
                title=t_def["title"],
                priority=TaskPriority(t_def.get("priority", "p4")),
                due_at=due_at,
                due_date_only=True,
                position=position,
            )
        )
        position += 1
    await session.commit()
    await session.refresh(project)
    return project


async def ensure_inbox(session: AsyncSession, user_id: UUID) -> Project:
    """Return the user's Inbox project, creating it on first call."""
    inbox = (
        await session.execute(
            select(Project).where(Project.user_id == user_id, Project.is_inbox.is_(True))
        )
    ).scalar_one_or_none()
    if inbox is not None:
        return inbox

    inbox = Project(
        user_id=user_id,
        name="Inbox",
        slug="inbox",
        color="slate",
        position=0,
        is_inbox=True,
    )
    session.add(inbox)
    await session.commit()
    await session.refresh(inbox)
    return inbox
