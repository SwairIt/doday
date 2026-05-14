"""Project service — CRUD and Inbox guarantee."""

import re
import secrets
import unicodedata
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.projects.membership import is_member, is_owner, member_project_ids
from app.projects.models import Project, ProjectMember
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


async def list_projects(
    session: AsyncSession, user_id: UUID, *, include_archived: bool = False
) -> list[Project]:
    ids = await member_project_ids(session, user_id)
    stmt = select(Project).where(Project.id.in_(ids))
    if not include_archived:
        stmt = stmt.where(Project.is_archived.is_(False))
    stmt = stmt.order_by(Project.position, Project.created_at)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_archived_projects(session: AsyncSession, user_id: UUID) -> list[Project]:
    ids = await member_project_ids(session, user_id)
    result = await session.execute(
        select(Project)
        .where(Project.id.in_(ids), Project.is_archived.is_(True))
        .order_by(Project.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_project(session: AsyncSession, user_id: UUID, project_id: UUID) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise ProjectNotFound(str(project_id))
    if not await is_member(session, project_id, user_id):
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
    await session.flush()
    session.add(ProjectMember(project_id=project.id, user_id=user_id, role="owner"))
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
    is_favorite: bool | None = None,
    description: str | None = None,
) -> Project:
    project = await get_project(session, user_id, project_id)
    if name is not None:
        project.name = name
    if color is not None:
        project.color = color
    if is_archived is not None:
        project.is_archived = is_archived
    if is_favorite is not None:
        project.is_favorite = is_favorite
    if description is not None:
        project.description = description
    await session.commit()
    await session.refresh(project)
    return project


async def export_project_to_markdown(session: AsyncSession, user_id: UUID, project_id: UUID) -> str:
    """Render a project + its sections + tasks as a Markdown checklist."""
    from sqlalchemy import select as sa_select

    from app.sections.models import Section
    from app.tasks.models import Task

    project = await get_project(session, user_id, project_id)
    sections = (
        (
            await session.execute(
                sa_select(Section)
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
                sa_select(Task)
                .where(Task.user_id == user_id, Task.project_id == project.id)
                .order_by(Task.position, Task.created_at)
            )
        )
        .scalars()
        .all()
    )

    by_parent: dict[UUID | None, list[Task]] = {}
    for t in tasks:
        by_parent.setdefault(t.parent_task_id, []).append(t)
    by_section: dict[UUID | None, list[Task]] = {}
    for t in by_parent.get(None, []):
        by_section.setdefault(t.section_id, []).append(t)

    def _render_task(t: Task, indent: int) -> list[str]:
        prefix = "  " * indent
        check = "x" if t.is_completed else " "
        bits: list[str] = []
        if t.priority.value != "p4":
            bits.append(f"!{t.priority.value[1:]}")
        if t.due_at:
            bits.append(t.due_at.strftime("%Y-%m-%d"))
        if t.recurrence:
            bits.append(f"↻ {t.recurrence}")
        meta = f" _({', '.join(bits)})_" if bits else ""
        lines = [f"{prefix}- [{check}] {t.title}{meta}"]
        if t.description:
            for line in t.description.splitlines():
                lines.append(f"{prefix}  > {line}")
        for child in by_parent.get(t.id, []):
            lines.extend(_render_task(child, indent + 1))
        return lines

    out: list[str] = [f"# {project.name}", ""]
    if project.description:
        out.extend([project.description, ""])

    no_sec = by_section.get(None, [])
    if no_sec:
        for t in no_sec:
            out.extend(_render_task(t, 0))
        out.append("")

    for s in sections:
        out.append(f"## {s.name}")
        out.append("")
        sec_tasks = by_section.get(s.id, [])
        if not sec_tasks:
            out.append("_Пусто_")
        for t in sec_tasks:
            out.extend(_render_task(t, 0))
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def _ics_escape(value: str) -> str:
    """Escape iCalendar text per RFC 5545 (backslashes, commas, semicolons, newlines)."""
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")


def _ics_fold(line: str) -> str:
    """Fold long lines at 75 octets per RFC 5545; continuation starts with a single space."""
    if len(line.encode("utf-8")) <= 75:
        return line
    out: list[str] = []
    buf = ""
    buf_len = 0
    for ch in line:
        ch_len = len(ch.encode("utf-8"))
        if buf_len + ch_len > 75:
            out.append(buf)
            buf = " " + ch
            buf_len = 1 + ch_len
        else:
            buf += ch
            buf_len += ch_len
    if buf:
        out.append(buf)
    return "\r\n".join(out)


async def export_project_to_ics(session: AsyncSession, user_id: UUID, project_id: UUID) -> str:
    """Render the project's tasks-with-dates as an iCalendar VCALENDAR string."""
    from sqlalchemy import select as sa_select

    from app.tasks.models import Task

    project = await get_project(session, user_id, project_id)
    tasks = (
        (
            await session.execute(
                sa_select(Task).where(
                    Task.user_id == user_id,
                    Task.project_id == project.id,
                    Task.due_at.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )

    now_stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Doday//Project Export//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_ics_escape(project.name)}",
    ]
    for t in tasks:
        if t.due_at is None:  # guarded by SQL filter, but mypy/ruff don't know that
            continue
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{t.id}@doday.app")
        lines.append(f"DTSTAMP:{now_stamp}")
        if t.due_date_only:
            d = t.due_at.date().strftime("%Y%m%d")
            lines.append(f"DTSTART;VALUE=DATE:{d}")
        else:
            lines.append(f"DTSTART:{t.due_at.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')}")
        prio_prefix = "" if t.priority.value == "p4" else f"[!{t.priority.value[1:]}] "
        done_prefix = "[✓] " if t.is_completed else ""
        lines.append(f"SUMMARY:{_ics_escape(done_prefix + prio_prefix + t.title)}")
        if t.description:
            lines.append(f"DESCRIPTION:{_ics_escape(t.description)}")
        if t.is_completed:
            lines.append("STATUS:COMPLETED")
        else:
            lines.append("STATUS:CONFIRMED")
        if t.recurrence:
            freq_map = {
                "daily": "DAILY",
                "weekly": "WEEKLY",
                "monthly": "MONTHLY",
                "yearly": "YEARLY",
            }
            freq = freq_map.get(t.recurrence)
            if freq:
                lines.append(f"RRULE:FREQ={freq}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_ics_fold(line) for line in lines) + "\r\n"


async def duplicate_project(
    session: AsyncSession, user_id: UUID, project_id: UUID, *, new_name: str | None = None
) -> Project:
    """Clone a project with its sections and active tasks (subtasks included)."""
    from sqlalchemy import select as sa_select

    from app.sections.models import Section
    from app.tasks.models import Task

    src = await get_project(session, user_id, project_id)
    new = await create_project(
        session, user_id, name=new_name or f"{src.name} (копия)", color=src.color
    )
    new.description = src.description
    await session.commit()
    await session.refresh(new)

    src_sections = (
        (
            await session.execute(
                sa_select(Section)
                .where(Section.user_id == user_id, Section.project_id == src.id)
                .order_by(Section.position)
            )
        )
        .scalars()
        .all()
    )
    section_id_map: dict[UUID, UUID] = {}
    for s in src_sections:
        new_s = Section(user_id=user_id, project_id=new.id, name=s.name, position=s.position)
        session.add(new_s)
        await session.flush()
        section_id_map[s.id] = new_s.id

    src_tasks = (
        (
            await session.execute(
                sa_select(Task)
                .where(Task.user_id == user_id, Task.project_id == src.id)
                .order_by(Task.position)
            )
        )
        .scalars()
        .all()
    )
    task_id_map: dict[UUID, UUID] = {}
    pending = list(src_tasks)
    while pending:
        progressed = False
        next_round = []
        for t in pending:
            new_parent_id: UUID | None = None
            if t.parent_task_id is not None:
                if t.parent_task_id not in task_id_map:
                    next_round.append(t)
                    continue
                new_parent_id = task_id_map[t.parent_task_id]
            new_t = Task(
                user_id=user_id,
                project_id=new.id,
                section_id=section_id_map.get(t.section_id) if t.section_id else None,
                parent_task_id=new_parent_id,
                title=t.title,
                description=t.description,
                due_at=t.due_at,
                due_date_only=t.due_date_only,
                priority=t.priority,
                position=t.position,
                recurrence=t.recurrence,
            )
            session.add(new_t)
            await session.flush()
            task_id_map[t.id] = new_t.id
            progressed = True
        if not progressed:
            break
        pending = next_round
    await session.commit()
    await session.refresh(new)
    return new


async def reorder_projects(session: AsyncSession, user_id: UUID, ids: list[UUID]) -> list[Project]:
    """Persist a new ordering. Inbox is pinned to position 0; other ids start at 1."""
    rows = await session.execute(
        select(Project).where(Project.user_id == user_id, Project.id.in_(ids))
    )
    by_id = {p.id: p for p in rows.scalars().all()}
    if len(by_id) != len(set(ids)):
        raise ProjectNotFound("one or more project ids do not belong to this user")
    pos = 1
    for pid in ids:
        proj = by_id[pid]
        if proj.is_inbox:
            proj.position = 0
            continue
        proj.position = pos
        pos += 1
    await session.commit()
    return await list_projects(session, user_id)


async def delete_project(session: AsyncSession, user_id: UUID, project_id: UUID) -> None:
    project = await get_project(session, user_id, project_id)
    if not await is_owner(session, project_id, user_id):
        raise ProjectNotFound(str(project_id))
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
    await session.flush()
    session.add(ProjectMember(project_id=inbox.id, user_id=user_id, role="owner"))
    await session.commit()
    await session.refresh(inbox)
    return inbox
