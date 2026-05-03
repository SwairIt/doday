"""HTML view endpoints for the signed-in app shell."""

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.auth.deps import DbSession, RequiredUser
from app.projects.service import ProjectNotFound, get_project_by_slug, list_projects
from app.tasks.models import Task
from app.tasks.service import list_in_range, list_tasks, list_today, list_upcoming

router = APIRouter(prefix="/app", tags=["app"])
templates = Jinja2Templates(directory="app/templates")

_RU_WEEKDAYS = [
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота",
    "воскресенье",
]
_RU_MONTHS_GEN = [
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
]

_RU_MONTHS_NOM = [
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]


def _today_label(today: date) -> str:
    return f"{_RU_WEEKDAYS[today.weekday()].capitalize()}, {today.day} {_RU_MONTHS_GEN[today.month - 1]}"


def _day_label(d: date, today: date) -> str:
    if d == today:
        return f"Сегодня · {d.day} {_RU_MONTHS_GEN[d.month - 1]}"
    if d == today + timedelta(days=1):
        return f"Завтра · {d.day} {_RU_MONTHS_GEN[d.month - 1]}"
    return f"{_RU_WEEKDAYS[d.weekday()].capitalize()} · {d.day} {_RU_MONTHS_GEN[d.month - 1]}"


@router.get("", include_in_schema=False)
async def app_root() -> Response:
    return RedirectResponse(url="/app/today", status_code=302)


@router.get("/today", response_class=HTMLResponse)
async def today_view(request: Request, user: RequiredUser, session: DbSession) -> HTMLResponse:
    projects = await list_projects(session, user.id)
    project_color_map: dict[UUID, str] = {p.id: p.color for p in projects}

    tasks = await list_today(session, user.id)
    today_date = datetime.now(UTC).date()
    overdue = [t for t in tasks if t.due_at and t.due_at.date() < today_date]
    today = [t for t in tasks if t.due_at and t.due_at.date() >= today_date]

    return templates.TemplateResponse(
        request,
        "app/today.html",
        {
            "current_user": user,
            "current_view": "today",
            "projects": projects,
            "project_color_map": project_color_map,
            "today_label": _today_label(today_date),
            "overdue": overdue,
            "today": today,
        },
    )


@router.get("/calendar", response_class=HTMLResponse)
async def calendar_view(
    request: Request,
    user: RequiredUser,
    session: DbSession,
    month: str | None = None,
) -> HTMLResponse:
    """Render a 7-by-6 month grid with up to 3 task chips per cell."""
    today_date = datetime.now(UTC).date()
    if month:
        try:
            target = datetime.strptime(month, "%Y-%m").date().replace(day=1)
        except ValueError:
            target = today_date.replace(day=1)
    else:
        target = today_date.replace(day=1)

    first_weekday = target.weekday()  # Mon=0
    grid_start = target - timedelta(days=first_weekday)
    grid_end = grid_start + timedelta(days=42)  # 6 weeks

    range_start = datetime.combine(grid_start, datetime.min.time(), tzinfo=UTC)
    range_end = datetime.combine(grid_end, datetime.min.time(), tzinfo=UTC)
    tasks = await list_in_range(session, user.id, start=range_start, end=range_end)

    by_day: dict[date, list[Task]] = defaultdict(list)
    for t in tasks:
        if t.due_at is not None:
            by_day[t.due_at.date()].append(t)

    cells = []
    for offset in range(42):
        d = grid_start + timedelta(days=offset)
        cells.append(
            {
                "day": d.day,
                "date": d,
                "in_month": d.month == target.month,
                "is_today": d == today_date,
                "is_weekend": d.weekday() >= 5,
                "tasks": by_day[d],
            }
        )

    projects = await list_projects(session, user.id)
    project_color_map: dict[UUID, str] = {p.id: p.color for p in projects}

    prev_target = (target.replace(day=1) - timedelta(days=1)).replace(day=1)
    next_target = (target.replace(day=28) + timedelta(days=10)).replace(day=1)

    return templates.TemplateResponse(
        request,
        "app/calendar.html",
        {
            "current_user": user,
            "current_view": "calendar",
            "projects": projects,
            "project_color_map": project_color_map,
            "month_label": f"{_RU_MONTHS_NOM[target.month - 1]} {target.year}",
            "cells": cells,
            "prev_month": prev_target.strftime("%Y-%m"),
            "next_month": next_target.strftime("%Y-%m"),
        },
    )


@router.get("/projects/{slug}", response_class=HTMLResponse)
async def project_view(
    slug: str, request: Request, user: RequiredUser, session: DbSession
) -> HTMLResponse:
    try:
        project = await get_project_by_slug(session, user.id, slug)
    except ProjectNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "проект не найден") from e

    tasks = await list_tasks(session, user.id, project_id=project.id, include_completed=True)
    active = [t for t in tasks if not t.is_completed]
    completed = [t for t in tasks if t.is_completed]

    projects = await list_projects(session, user.id)
    project_color_map: dict[UUID, str] = {p.id: p.color for p in projects}

    return templates.TemplateResponse(
        request,
        "app/project.html",
        {
            "current_user": user,
            "current_view": "project",
            "project": project,
            "projects": projects,
            "project_color_map": project_color_map,
            "active": active,
            "completed": completed,
        },
    )


@router.get("/inbox", response_class=HTMLResponse, include_in_schema=False)
async def inbox_view(request: Request, user: RequiredUser, session: DbSession) -> Response:
    """Inbox is just a normal project under a known slug — redirect to it."""
    from app.projects.service import ensure_inbox

    inbox = await ensure_inbox(session, user.id)
    return RedirectResponse(url=f"/app/projects/{inbox.slug}", status_code=302)


@router.get("/profile", response_class=HTMLResponse)
async def profile_view(request: Request, user: RequiredUser, session: DbSession) -> HTMLResponse:
    from sqlalchemy import func
    from sqlalchemy import select as sa_select

    from app.labels.models import Label
    from app.projects.models import Project as ProjectModel

    projects = await list_projects(session, user.id)
    project_color_map: dict[UUID, str] = {p.id: p.color for p in projects}

    project_count_row = await session.execute(
        sa_select(func.count()).select_from(ProjectModel).where(ProjectModel.user_id == user.id)
    )
    active_count_row = await session.execute(
        sa_select(func.count())
        .select_from(Task)
        .where(Task.user_id == user.id, Task.is_completed.is_(False))
    )
    completed_count_row = await session.execute(
        sa_select(func.count())
        .select_from(Task)
        .where(Task.user_id == user.id, Task.is_completed.is_(True))
    )
    label_count_row = await session.execute(
        sa_select(func.count()).select_from(Label).where(Label.user_id == user.id)
    )

    stats = {
        "projects": project_count_row.scalar_one(),
        "active": active_count_row.scalar_one(),
        "completed": completed_count_row.scalar_one(),
        "labels": label_count_row.scalar_one(),
    }

    return templates.TemplateResponse(
        request,
        "app/profile.html",
        {
            "current_user": user,
            "current_view": "profile",
            "projects": projects,
            "project_color_map": project_color_map,
            "stats": stats,
        },
    )


@router.get("/upcoming", response_class=HTMLResponse)
async def upcoming_view(request: Request, user: RequiredUser, session: DbSession) -> HTMLResponse:
    projects = await list_projects(session, user.id)
    project_color_map: dict[UUID, str] = {p.id: p.color for p in projects}

    tasks = await list_upcoming(session, user.id, days=7)
    today_date = datetime.now(UTC).date()

    grouped: dict[date, list[Task]] = defaultdict(list)
    for t in tasks:
        if t.due_at is not None:
            grouped[t.due_at.date()].append(t)

    days = [
        {
            "date": d,
            "label": _day_label(d, today_date),
            "is_today": d == today_date,
            "tasks": grouped[d],
        }
        for d in sorted(grouped)
    ]

    last = today_date + timedelta(days=7)
    range_label = (
        f"{today_date.day} {_RU_MONTHS_GEN[today_date.month - 1]} — "
        f"{last.day} {_RU_MONTHS_GEN[last.month - 1]}"
    )

    return templates.TemplateResponse(
        request,
        "app/upcoming.html",
        {
            "current_user": user,
            "current_view": "upcoming",
            "projects": projects,
            "project_color_map": project_color_map,
            "days": days,
            "range_label": range_label,
        },
    )
