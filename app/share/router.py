"""Public, read-only progress views. No auth — access is gated by a signed token.

This router exposes only GET endpoints and zero mutations, so it cannot affect
any existing data or authorization path.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select

from app.auth.deps import DbSession
from app.auth.models import User
from app.projects.membership import assignee_map_for_project
from app.projects.models import Project
from app.share.service import (
    InvalidShareToken,
    display_name_from_email,
    read_group_token,
    read_progress_token,
)
from app.tasks.models import Task
from app.tasks.service import list_completed_today, list_today
from app.views.router import templates  # reuse the env with due_label/due_state globals

router = APIRouter(prefix="/share", tags=["share"])


@router.get("/progress/{token}", response_class=HTMLResponse)
async def progress_view(request: Request, token: str, session: DbSession) -> HTMLResponse:
    """Render a read-only snapshot of one user's day for whoever holds the link."""
    try:
        user_id = read_progress_token(token)
    except InvalidShareToken as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ссылка недействительна") from exc

    child = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if child is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")

    tasks = await list_today(session, child.id)
    today_date = datetime.now(UTC).date()
    overdue = [t for t in tasks if t.due_at and t.due_at.date() < today_date]
    today = [t for t in tasks if t.due_at and t.due_at.date() >= today_date]

    done_today = (
        await session.execute(
            select(func.count())
            .select_from(Task)
            .where(
                Task.user_id == child.id,
                Task.is_completed.is_(True),
                Task.completed_at.is_not(None),
                func.date(Task.completed_at) == today_date,
            )
        )
    ).scalar_one()

    week_start = today_date - timedelta(days=today_date.weekday())
    done_week = (
        await session.execute(
            select(func.count())
            .select_from(Task)
            .where(
                Task.user_id == child.id,
                Task.is_completed.is_(True),
                Task.completed_at.is_not(None),
                func.date(Task.completed_at) >= week_start,
                func.date(Task.completed_at) <= today_date,
            )
        )
    ).scalar_one()

    completed_today = await list_completed_today(session, child.id, limit=10)

    return templates.TemplateResponse(
        request,
        "share/progress.html",
        {
            "child_name": display_name_from_email(child.email),
            "overdue": overdue,
            "today": today,
            "done_today_count": done_today,
            "done_week_count": done_week,
            "completed_today": completed_today,
        },
    )


@router.get("/group/{token}", response_class=HTMLResponse)
async def group_view(request: Request, token: str, session: DbSession) -> HTMLResponse:
    """Read-only per-member progress for one project (a class) for whoever holds the link."""
    try:
        project_id = read_group_token(token)
    except InvalidShareToken as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ссылка недействительна") from exc

    project = (
        await session.execute(select(Project).where(Project.id == project_id))
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Проект не найден")

    members = await assignee_map_for_project(session, project_id)
    today_date = datetime.now(UTC).date()

    tasks = (
        (
            await session.execute(
                select(Task).where(
                    Task.project_id == project_id,
                    Task.deleted_at.is_(None),
                    Task.assigned_to.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )

    stats: dict[UUID, dict[str, int]] = {
        uid: {"open": 0, "overdue": 0, "done_today": 0} for uid in members
    }
    for t in tasks:
        s = stats.get(t.assigned_to) if t.assigned_to else None
        if s is None:
            continue
        if t.is_completed:
            if t.completed_at and t.completed_at.date() == today_date:
                s["done_today"] += 1
        else:
            s["open"] += 1
            if t.due_at and t.due_at.date() < today_date:
                s["overdue"] += 1

    rows = sorted(
        (
            {
                "initial": m["initial"],
                "label": m["label"],
                "color": m["color"],
                "open": stats[uid]["open"],
                "overdue": stats[uid]["overdue"],
                "done_today": stats[uid]["done_today"],
            }
            for uid, m in members.items()
        ),
        key=lambda r: str(r["label"]),
    )

    return templates.TemplateResponse(
        request,
        "share/group.html",
        {"project_name": project.name, "rows": rows},
    )
