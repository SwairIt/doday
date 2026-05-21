"""Project HTTP endpoints — JSON CRUD."""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.auth.deps import DbSession, RequiredUser
from app.auth.models import User
from app.projects.schemas import (
    InvitationOut,
    InviteCreate,
    MemberOut,
    ProjectCreate,
    ProjectOut,
    ProjectReorder,
    ProjectUpdate,
)
from app.projects.service import (
    CannotDeleteInbox,
    ProjectNotFound,
    create_from_template,
    create_project,
    delete_project,
    duplicate_project,
    export_project_to_ics,
    export_project_to_markdown,
    get_project,
    list_archived_projects,
    list_projects,
    reorder_projects,
    update_project,
)
from app.projects.templates_data import TEMPLATES, get_template

log = logging.getLogger(__name__)


class ProjectTemplateOut(BaseModel):
    key: str
    name: str
    icon: str
    color: str
    description: str
    sections_count: int
    tasks_count: int


class FromTemplatePayload(BaseModel):
    template_key: str = Field(min_length=1)
    name: str | None = Field(default=None, max_length=120)


router = APIRouter(prefix="/api/projects", tags=["projects"])
invites_router = APIRouter(prefix="/api/invites", tags=["invites"])


@router.get("", response_model=list[ProjectOut])
async def list_endpoint(
    user: RequiredUser, session: DbSession, include_archived: bool = False
) -> list[ProjectOut]:
    projects = await list_projects(session, user.id, include_archived=include_archived)
    return [ProjectOut.model_validate(p) for p in projects]


@router.get("/archived", response_model=list[ProjectOut])
async def list_archived_endpoint(user: RequiredUser, session: DbSession) -> list[ProjectOut]:
    projects = await list_archived_projects(session, user.id)
    return [ProjectOut.model_validate(p) for p in projects]


@router.get("/counts", response_model=dict[UUID, int])
async def counts_endpoint(user: RequiredUser, session: DbSession) -> dict[UUID, int]:
    """Return {project_id: active_top_level_task_count} for the sidebar badges."""
    from sqlalchemy import func, select

    from app.tasks.models import Task

    rows = await session.execute(
        select(Task.project_id, func.count(Task.id))
        .where(
            Task.user_id == user.id,
            Task.is_completed.is_(False),
            Task.parent_task_id.is_(None),
            Task.deleted_at.is_(None),
        )
        .group_by(Task.project_id)
    )
    return {pid: count for pid, count in rows.all()}


@router.get("/sidebar-counts")
async def sidebar_counts_endpoint(user: RequiredUser, session: DbSession) -> dict[str, int]:
    """One-shot counts for sidebar nav badges: inbox / today / upcoming / overdue / trash."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import func, select

    from app.projects.models import Project
    from app.projects.service import ensure_inbox
    from app.tasks.models import Task

    inbox = await ensure_inbox(session, user.id)
    now = datetime.now(UTC)
    today_end = datetime(now.year, now.month, now.day, 23, 59, 59, tzinfo=UTC)
    upcoming_end = datetime(now.year, now.month, now.day, tzinfo=UTC) + timedelta(days=8)

    base = (
        select(func.count())
        .select_from(Task)
        .where(
            Task.user_id == user.id,
            Task.deleted_at.is_(None),
            Task.parent_task_id.is_(None),
        )
    )

    inbox_count = int(
        (
            await session.execute(
                base.where(Task.project_id == inbox.id, Task.is_completed.is_(False))
            )
        ).scalar_one()
    )
    today_count = int(
        (
            await session.execute(
                base.where(
                    Task.is_completed.is_(False),
                    Task.due_at.is_not(None),
                    Task.due_at <= today_end,
                )
            )
        ).scalar_one()
    )
    upcoming_count = int(
        (
            await session.execute(
                base.where(
                    Task.is_completed.is_(False),
                    Task.due_at.is_not(None),
                    Task.due_at > today_end,
                    Task.due_at < upcoming_end,
                )
            )
        ).scalar_one()
    )
    overdue_count = int(
        (
            await session.execute(
                base.where(
                    Task.is_completed.is_(False),
                    Task.due_at.is_not(None),
                    Task.due_at < datetime(now.year, now.month, now.day, tzinfo=UTC),
                )
            )
        ).scalar_one()
    )
    trash_count_row = await session.execute(
        select(func.count())
        .select_from(Task)
        .where(Task.user_id == user.id, Task.deleted_at.is_not(None))
    )
    trash_count = int(trash_count_row.scalar_one())

    # Project archive count is also handy in sidebar.
    archive_count_row = await session.execute(
        select(func.count())
        .select_from(Project)
        .where(Project.user_id == user.id, Project.is_archived.is_(True))
    )
    archive_count = int(archive_count_row.scalar_one())

    from app.tasks.service import count_assigned_to_user

    assigned_count = await count_assigned_to_user(session, user.id)

    from app.filters.service import count_for_filter

    no_date_count = await count_for_filter(session, user.id, "no-date")
    high_priority_count = await count_for_filter(session, user.id, "high-priority")
    this_week_count = await count_for_filter(session, user.id, "this-week")

    return {
        "inbox": inbox_count,
        "today": today_count,
        "upcoming": upcoming_count,
        "overdue": overdue_count,
        "trash": trash_count,
        "archive": archive_count,
        "assigned": assigned_count,
        "no_date": no_date_count,
        "high_priority": high_priority_count,
        "this_week": this_week_count,
    }


@router.get("/calendar-markers")
async def calendar_markers_endpoint(
    user: RequiredUser, session: DbSession, month: str | None = None
) -> dict[str, list[str]]:
    """Return ISO dates within the requested month that have at least 1 task.

    Used by the sidebar mini-calendar to dot busy days.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import func, select

    from app.tasks.models import Task

    today = datetime.now(UTC).date()
    if month:
        try:
            target = datetime.strptime(month, "%Y-%m").date().replace(day=1)
        except ValueError:
            target = today.replace(day=1)
    else:
        target = today.replace(day=1)
    next_target = (target.replace(day=28) + timedelta(days=10)).replace(day=1)
    range_start = datetime(target.year, target.month, 1, tzinfo=UTC)
    range_end = datetime(next_target.year, next_target.month, 1, tzinfo=UTC)

    rows = await session.execute(
        select(func.date(Task.due_at))
        .where(
            Task.user_id == user.id,
            Task.deleted_at.is_(None),
            Task.due_at.is_not(None),
            Task.due_at >= range_start,
            Task.due_at < range_end,
        )
        .distinct()
    )
    dates: set[str] = set()
    for row in rows.all():
        d = row[0]
        if d is None:
            continue
        dates.add(d.isoformat() if hasattr(d, "isoformat") else str(d))
    return {"dates": sorted(dates)}


@router.post("/reorder", response_model=list[ProjectOut])
async def reorder_endpoint(
    payload: ProjectReorder, user: RequiredUser, session: DbSession
) -> list[ProjectOut]:
    try:
        projects = await reorder_projects(session, user.id, payload.ids)
    except ProjectNotFound as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return [ProjectOut.model_validate(p) for p in projects]


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_endpoint(
    payload: ProjectCreate, user: RequiredUser, session: DbSession
) -> ProjectOut:
    from app.billing.service import can_create_project

    allowed, reason = await can_create_project(session, user)
    if not allowed:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            {
                "code": "limit_reached",
                "feature": "projects",
                "tier": "free",
                "message": reason or "Достигнут лимит активных проектов",
            },
        )
    project = await create_project(session, user.id, name=payload.name, color=payload.color)
    return ProjectOut.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_endpoint(
    project_id: UUID,
    payload: ProjectUpdate,
    user: RequiredUser,
    session: DbSession,
) -> ProjectOut:
    try:
        project = await update_project(
            session,
            user.id,
            project_id,
            name=payload.name,
            color=payload.color,
            is_archived=payload.is_archived,
            is_favorite=payload.is_favorite,
            description=payload.description,
        )
    except ProjectNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "проект не найден") from e
    return ProjectOut.model_validate(project)


@router.get("/templates", response_model=list[ProjectTemplateOut])
async def list_templates(_: RequiredUser) -> list[ProjectTemplateOut]:
    return [
        ProjectTemplateOut(
            key=t["key"],
            name=t["name"],
            icon=t["icon"],
            color=t["color"],
            description=t["description"],
            sections_count=len(t["sections"]),
            tasks_count=sum(len(s["tasks"]) for s in t["sections"]) + len(t["loose_tasks"]),
        )
        for t in TEMPLATES
    ]


@router.post("/from-template", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_from_template_endpoint(
    payload: FromTemplatePayload, user: RequiredUser, session: DbSession
) -> ProjectOut:
    template = get_template(payload.template_key)
    if template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "шаблон не найден")
    project = await create_from_template(session, user.id, template, name=payload.name)
    return ProjectOut.model_validate(project)


@router.post(
    "/{project_id}/duplicate", response_model=ProjectOut, status_code=status.HTTP_201_CREATED
)
async def duplicate_endpoint(
    project_id: UUID, user: RequiredUser, session: DbSession
) -> ProjectOut:
    try:
        new = await duplicate_project(session, user.id, project_id)
    except ProjectNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "проект не найден") from e
    return ProjectOut.model_validate(new)


@router.get("/{project_id}/export.md", response_class=Response)
async def export_md_endpoint(project_id: UUID, user: RequiredUser, session: DbSession) -> Response:
    try:
        md = await export_project_to_markdown(session, user.id, project_id)
    except ProjectNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "проект не найден") from e
    return Response(
        content=md,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="project-{project_id}.md"'},
    )


@router.get("/{project_id}/export.ics", response_class=Response)
async def export_ics_endpoint(project_id: UUID, user: RequiredUser, session: DbSession) -> Response:
    try:
        ics = await export_project_to_ics(session, user.id, project_id)
    except ProjectNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "проект не найден") from e
    return Response(
        content=ics,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="project-{project_id}.ics"'},
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_endpoint(project_id: UUID, user: RequiredUser, session: DbSession) -> Response:
    try:
        await delete_project(session, user.id, project_id)
    except ProjectNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "проект не найден") from e
    except CannotDeleteInbox as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Inbox удалить нельзя") from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── Members & Invitations ────────────────────────────────────────────────────


@router.get("/{project_id}/members", response_model=list[MemberOut])
async def list_members_endpoint(
    project_id: UUID, user: RequiredUser, session: DbSession
) -> list[MemberOut]:
    """List all members of a project. Any member may call this."""
    from app.projects.membership import list_members

    try:
        await get_project(session, user.id, project_id)
    except ProjectNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "проект не найден") from e

    members = await list_members(session, project_id)

    # Fetch emails in one query
    user_ids = [m.user_id for m in members]
    if user_ids:
        rows = await session.execute(select(User).where(User.id.in_(user_ids)))
        email_map: dict[UUID, str] = {u.id: u.email for u in rows.scalars().all()}
    else:
        email_map = {}

    return [
        MemberOut(
            user_id=m.user_id,
            email=email_map.get(m.user_id, ""),
            role=m.role,
            joined_at=m.joined_at,
        )
        for m in members
    ]


@router.post(
    "/{project_id}/invites",
    response_model=InvitationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_invite_endpoint(
    project_id: UUID, payload: InviteCreate, user: RequiredUser, session: DbSession
) -> InvitationOut:
    """Create an invitation (owner-only) and send an email."""
    from app.auth.email import send_invitation_email
    from app.config import get_settings
    from app.projects.invitations import InvitationError, create_invitation

    try:
        project = await get_project(session, user.id, project_id)
    except ProjectNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "проект не найден") from e

    try:
        invitation = await create_invitation(
            session,
            project_id=project_id,
            inviter_id=user.id,
            invitee_email=payload.invitee_email,
        )
    except InvitationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e

    invite_url = get_settings().app_base_url.rstrip("/") + "/invite/" + invitation.token
    try:
        await send_invitation_email(
            to=payload.invitee_email,
            invite_url=invite_url,
            project_name=project.name,
            inviter_email=user.email,
        )
    except Exception:
        log.warning(
            "invite_email_failed: invitation_id=%s invitee=%s",
            invitation.id,
            payload.invitee_email,
            exc_info=True,
        )

    return InvitationOut(
        id=invitation.id,
        invitee_email=invitation.invitee_email,
        status=invitation.status,
        expires_at=invitation.expires_at,
    )


@router.get("/{project_id}/invites", response_model=list[InvitationOut])
async def list_invites_endpoint(
    project_id: UUID, user: RequiredUser, session: DbSession
) -> list[InvitationOut]:
    """List pending invitations (owner-only)."""
    from app.projects.invitations import list_pending
    from app.projects.membership import is_owner

    try:
        await get_project(session, user.id, project_id)
    except ProjectNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "проект не найден") from e

    if not await is_owner(session, project_id, user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "только для владельца проекта")

    pending = await list_pending(session, project_id)
    return [
        InvitationOut(
            id=inv.id,
            invitee_email=inv.invitee_email,
            status=inv.status,
            expires_at=inv.expires_at,
        )
        for inv in pending
    ]


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member_endpoint(
    project_id: UUID, user_id: UUID, user: RequiredUser, session: DbSession
) -> Response:
    """Remove a member (owner-only). Cannot remove the last owner."""
    from app.projects.membership import is_owner, list_members, remove_member

    try:
        await get_project(session, user.id, project_id)
    except ProjectNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "проект не найден") from e

    if not await is_owner(session, project_id, user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "только для владельца проекта")

    members = await list_members(session, project_id)
    target_role = next((m.role for m in members if m.user_id == user_id), None)
    if target_role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "участник не найден")

    if target_role == "owner":
        owners = [m for m in members if m.role == "owner"]
        if len(owners) == 1:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Нельзя удалить последнего владельца")

    await remove_member(session, project_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── /api/invites/{invitation_id} ────────────────────────────────────────────


@invites_router.delete("/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invite_endpoint(
    invitation_id: UUID, user: RequiredUser, session: DbSession
) -> Response:
    """Revoke an invitation (owner-only)."""
    from app.projects.invitations import InvitationError, revoke_invitation

    try:
        await revoke_invitation(session, invitation_id=invitation_id, requester_id=user.id)
    except InvitationError as e:
        msg = str(e)
        if "не найдено" in msg:
            raise HTTPException(status.HTTP_404_NOT_FOUND, msg) from e
        raise HTTPException(status.HTTP_400_BAD_REQUEST, msg) from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)
