"""HTML view endpoints for the signed-in app shell."""

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.auth.deps import DbSession, RequiredUser
from app.projects.service import list_projects
from app.tasks.models import Task
from app.tasks.service import list_today, list_upcoming

router = APIRouter(prefix="/app", tags=["app"])
templates = Jinja2Templates(directory="app/templates")

_RU_WEEKDAYS = [
    "понедельник", "вторник", "среда", "четверг",
    "пятница", "суббота", "воскресенье",
]
_RU_MONTHS_GEN = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
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
async def today_view(
    request: Request, user: RequiredUser, session: DbSession
) -> HTMLResponse:
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


@router.get("/upcoming", response_class=HTMLResponse)
async def upcoming_view(
    request: Request, user: RequiredUser, session: DbSession
) -> HTMLResponse:
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
