"""HTML view endpoints for the signed-in app shell."""

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.auth.deps import DbSession, RequiredUser
from app.auth.models import User
from app.projects.service import (
    ProjectNotFound,
    get_project_by_slug,
    list_archived_projects,
    list_projects,
)
from app.tasks.models import Task
from app.tasks.service import (
    list_assigned_to_user,
    list_completed,
    list_completed_today,
    list_in_range,
    list_tasks,
    list_today,
    list_upcoming,
    subtask_counts_for,
)
from app.views.template_filters import due_state

router = APIRouter(prefix="/app", tags=["app"])
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["due_state"] = due_state

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
    from sqlalchemy import func
    from sqlalchemy import select as sa_select

    projects = await list_projects(session, user.id)
    project_color_map: dict[UUID, str] = {p.id: p.color for p in projects}

    tasks = await list_today(session, user.id)
    today_date = datetime.now(UTC).date()
    overdue = [t for t in tasks if t.due_at and t.due_at.date() < today_date]
    today = [t for t in tasks if t.due_at and t.due_at.date() >= today_date]

    done_today_count_row = await session.execute(
        sa_select(func.count())
        .select_from(Task)
        .where(
            Task.user_id == user.id,
            Task.is_completed.is_(True),
            Task.completed_at.is_not(None),
            func.date(Task.completed_at) == today_date,
        )
    )
    done_today_count = done_today_count_row.scalar_one()

    week_start = today_date - timedelta(days=today_date.weekday())
    done_week_count_row = await session.execute(
        sa_select(func.count())
        .select_from(Task)
        .where(
            Task.user_id == user.id,
            Task.is_completed.is_(True),
            Task.completed_at.is_not(None),
            func.date(Task.completed_at) >= week_start,
            func.date(Task.completed_at) <= today_date,
        )
    )
    done_week_count = done_week_count_row.scalar_one()

    completed_today = await list_completed_today(session, user.id, limit=10)

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
            "done_today_count": done_today_count,
            "done_week_count": done_week_count,
            "completed_today": completed_today,
        },
    )


@router.get("/calendar", response_class=HTMLResponse)
async def calendar_view(
    request: Request,
    user: RequiredUser,
    session: DbSession,
    month: str | None = None,
    view: str = "month",
    week: str | None = None,
) -> HTMLResponse:
    """Calendar in month-grid (default) or week-column layout (?view=week)."""
    today_date = datetime.now(UTC).date()
    projects = await list_projects(session, user.id)
    project_color_map: dict[UUID, str] = {p.id: p.color for p in projects}

    if view == "week":
        # Pick the Monday for the requested week. `week` is "YYYY-MM-DD" of any
        # day inside it, or absent → current week.
        anchor = today_date
        if week:
            try:
                anchor = datetime.strptime(week, "%Y-%m-%d").date()
            except ValueError:
                anchor = today_date
        monday = anchor - timedelta(days=anchor.weekday())
        sunday = monday + timedelta(days=7)
        range_start = datetime.combine(monday, datetime.min.time(), tzinfo=UTC)
        range_end = datetime.combine(sunday, datetime.min.time(), tzinfo=UTC)
        tasks = await list_in_range(session, user.id, start=range_start, end=range_end)
        by_day: dict[date, list[Task]] = defaultdict(list)
        for t in tasks:
            if t.due_at is not None:
                by_day[t.due_at.date()].append(t)
        days = []
        weekday_names = [
            "Понедельник",
            "Вторник",
            "Среда",
            "Четверг",
            "Пятница",
            "Суббота",
            "Воскресенье",
        ]
        for offset in range(7):
            d = monday + timedelta(days=offset)
            days.append(
                {
                    "date": d,
                    "weekday_name": weekday_names[offset],
                    "is_today": d == today_date,
                    "is_weekend": d.weekday() >= 5,
                    "tasks": by_day[d],
                }
            )
        prev_iso = (monday - timedelta(days=7)).isoformat()
        next_iso = (monday + timedelta(days=7)).isoformat()
        return templates.TemplateResponse(
            request,
            "app/calendar_week.html",
            {
                "current_user": user,
                "current_view": "calendar",
                "projects": projects,
                "project_color_map": project_color_map,
                "week_label": f"{monday.strftime('%d.%m')} – {(sunday - timedelta(days=1)).strftime('%d.%m.%Y')}",
                "days": days,
                "prev_week": prev_iso,
                "next_week": next_iso,
            },
        )

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

    by_day = defaultdict(list)
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
            "current_week_iso": today_date.isoformat(),
        },
    )


@router.get("/projects/{slug}", response_class=HTMLResponse)
async def project_view(
    slug: str,
    request: Request,
    user: RequiredUser,
    session: DbSession,
    view: str = "list",
) -> HTMLResponse:
    """Project list view + sections grouping. ?view=kanban switches to board layout."""
    from app.projects.membership import assignee_map_for_project, is_owner
    from app.sections.service import list_sections

    try:
        project = await get_project_by_slug(session, user.id, slug)
    except ProjectNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "проект не найден") from e

    tasks = await list_tasks(session, user.id, project_id=project.id, include_completed=True)
    sections = await list_sections(session, user.id, project.id)

    by_section: dict[UUID | None, list[Task]] = defaultdict(list)
    for t in tasks:
        if not t.is_completed:
            by_section[t.section_id].append(t)

    no_section_active = by_section.get(None, [])
    section_groups = [{"section": s, "tasks": by_section.get(s.id, [])} for s in sections]
    completed = [t for t in tasks if t.is_completed]

    projects = await list_projects(session, user.id)
    project_color_map: dict[UUID, str] = {p.id: p.color for p in projects}
    is_proj_owner = await is_owner(session, project.id, user.id)
    assignee_map = await assignee_map_for_project(session, project.id)

    active_ids = [t.id for tasks in by_section.values() for t in tasks]
    subtask_counts = await subtask_counts_for(session, user.id, active_ids)
    # String-keyed copy for JSON embedding (UUID keys aren't JSON-serializable).
    assignee_map_js = {str(uid): data for uid, data in assignee_map.items()}

    template_name = "app/kanban.html" if view == "kanban" else "app/project.html"
    return templates.TemplateResponse(
        request,
        template_name,
        {
            "current_user": user,
            "current_view": "project",
            "view_mode": "kanban" if view == "kanban" else "list",
            "project": project,
            "projects": projects,
            "project_color_map": project_color_map,
            "no_section_active": no_section_active,
            "section_groups": section_groups,
            "completed": completed,
            "is_owner": is_proj_owner,
            "assignee_map": assignee_map,
            "assignee_map_js": assignee_map_js,
            "subtask_counts": subtask_counts,
        },
    )


@router.get("/inbox", response_class=HTMLResponse, include_in_schema=False)
async def inbox_view(request: Request, user: RequiredUser, session: DbSession) -> Response:
    """Inbox is just a normal project under a known slug — redirect to it."""
    from app.projects.service import ensure_inbox

    inbox = await ensure_inbox(session, user.id)
    return RedirectResponse(url=f"/app/projects/{inbox.slug}", status_code=302)


@router.get("/filters/{slug}", response_class=HTMLResponse)
async def filter_view(
    slug: str, request: Request, user: RequiredUser, session: DbSession
) -> HTMLResponse:
    from app.filters.service import FILTERS, list_for_filter

    if slug not in FILTERS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "фильтр не найден")
    tasks = await list_for_filter(session, user.id, slug)
    projects = await list_projects(session, user.id)
    project_color_map: dict[UUID, str] = {p.id: p.color for p in projects}
    return templates.TemplateResponse(
        request,
        "app/filter.html",
        {
            "current_user": user,
            "current_view": f"filter:{slug}",
            "projects": projects,
            "project_color_map": project_color_map,
            "filter": FILTERS[slug],
            "tasks": tasks,
        },
    )


@router.get("/stats", response_class=HTMLResponse)
async def stats_view(request: Request, user: RequiredUser, session: DbSession) -> HTMLResponse:
    from app.stats.service import compute_user_stats

    stats = await compute_user_stats(session, user.id)
    projects = await list_projects(session, user.id)
    return templates.TemplateResponse(
        request,
        "app/stats.html",
        {
            "current_user": user,
            "current_view": "stats",
            "projects": projects,
            "stats": stats,
        },
    )


@router.get("/assigned", response_class=HTMLResponse)
async def assigned_view(request: Request, user: RequiredUser, session: DbSession) -> HTMLResponse:
    """All open tasks assigned to the current user, grouped by project.

    Cross-project «Назначено мне» view — the team-collaboration counterpart to
    Today/Inbox: one place to see everything teammates put on your plate.
    """
    tasks = await list_assigned_to_user(session, user.id)
    projects = await list_projects(session, user.id)
    project_name_map: dict[UUID, str] = {p.id: p.name for p in projects}
    project_color_map: dict[UUID, str] = {p.id: p.color for p in projects}

    by_project: dict[UUID, list[Task]] = defaultdict(list)
    for t in tasks:
        by_project[t.project_id].append(t)
    groups = [
        {
            "project_id": pid,
            "name": project_name_map.get(pid, "Без проекта"),
            "color": project_color_map.get(pid, "violet"),
            "tasks": tlist,
        }
        for pid, tlist in by_project.items()
    ]

    return templates.TemplateResponse(
        request,
        "app/assigned.html",
        {
            "current_user": user,
            "current_view": "assigned",
            "projects": projects,
            "project_color_map": project_color_map,
            "groups": groups,
            "total": len(tasks),
        },
    )


@router.get("/activity", response_class=HTMLResponse)
async def activity_view(request: Request, user: RequiredUser, session: DbSession) -> HTMLResponse:
    """Derived activity feed — created/completed tasks + new comments, last 30 days."""
    from sqlalchemy import select as sa_select

    from app.comments.models import Comment

    cutoff = datetime.now(UTC) - timedelta(days=30)
    today_date = datetime.now(UTC).date()
    yesterday = today_date - timedelta(days=1)

    projects = await list_projects(session, user.id)
    project_color_map: dict[UUID, str] = {p.id: p.color for p in projects}
    project_name_map: dict[UUID, str] = {p.id: p.name for p in projects}

    created_rows = (
        (
            await session.execute(
                sa_select(Task).where(Task.user_id == user.id, Task.created_at >= cutoff)
            )
        )
        .scalars()
        .all()
    )
    completed_rows = (
        (
            await session.execute(
                sa_select(Task).where(
                    Task.user_id == user.id,
                    Task.is_completed.is_(True),
                    Task.completed_at.is_not(None),
                    Task.completed_at >= cutoff,
                )
            )
        )
        .scalars()
        .all()
    )
    comment_rows = (
        (
            await session.execute(
                sa_select(Comment).where(Comment.user_id == user.id, Comment.created_at >= cutoff)
            )
        )
        .scalars()
        .all()
    )
    task_lookup: dict[UUID, Task] = {t.id: t for t in created_rows}
    for t in completed_rows:
        task_lookup.setdefault(t.id, t)

    items: list[dict[str, object]] = []
    for t in created_rows:
        items.append(
            {
                "kind": "created",
                "ts": t.created_at,
                "title": t.title,
                "project": project_name_map.get(t.project_id, "?"),
                "color": project_color_map.get(t.project_id, "violet"),
                "task_id": t.id,
                "extra": "",
            }
        )
    for t in completed_rows:
        items.append(
            {
                "kind": "completed",
                "ts": t.completed_at,
                "title": t.title,
                "project": project_name_map.get(t.project_id, "?"),
                "color": project_color_map.get(t.project_id, "violet"),
                "task_id": t.id,
                "extra": "",
            }
        )
    for c in comment_rows:
        parent = task_lookup.get(c.task_id)
        if parent is None:
            parent = await session.get(Task, c.task_id)
        if parent is None:
            continue
        snippet = c.body if len(c.body) <= 80 else c.body[:77] + "…"
        items.append(
            {
                "kind": "commented",
                "ts": c.created_at,
                "title": parent.title,
                "project": project_name_map.get(parent.project_id, "?"),
                "color": project_color_map.get(parent.project_id, "violet"),
                "task_id": parent.id,
                "extra": snippet,
            }
        )

    items.sort(key=lambda x: x["ts"], reverse=True)  # type: ignore[arg-type,return-value]

    grouped: dict[date, list[dict[str, object]]] = defaultdict(list)
    for it in items:
        ts = it["ts"]
        when = ts.date() if isinstance(ts, datetime) else today_date
        grouped[when].append(it)

    days = []
    for d in sorted(grouped, reverse=True):
        if d == today_date:
            label = "Сегодня"
        elif d == yesterday:
            label = "Вчера"
        else:
            label = (
                f"{_RU_WEEKDAYS[d.weekday()].capitalize()}, {d.day} {_RU_MONTHS_GEN[d.month - 1]}"
            )
        days.append({"date": d, "label": label, "events": grouped[d]})

    return templates.TemplateResponse(
        request,
        "app/activity.html",
        {
            "current_user": user,
            "current_view": "activity",
            "projects": projects,
            "project_color_map": project_color_map,
            "days": days,
            "total": len(items),
        },
    )


@router.get("/labels", response_class=HTMLResponse)
async def labels_view(request: Request, user: RequiredUser, session: DbSession) -> HTMLResponse:
    from app.labels.service import list_labels_with_counts

    pairs = await list_labels_with_counts(session, user.id)
    projects = await list_projects(session, user.id)
    project_color_map: dict[UUID, str] = {p.id: p.color for p in projects}
    return templates.TemplateResponse(
        request,
        "app/labels.html",
        {
            "current_user": user,
            "current_view": "labels",
            "projects": projects,
            "project_color_map": project_color_map,
            "labels_with_counts": pairs,
        },
    )


@router.get("/labels/{label_id}", response_class=HTMLResponse)
async def label_tasks_view(
    label_id: UUID, request: Request, user: RequiredUser, session: DbSession
) -> HTMLResponse:
    """Open tasks carrying a single label. Reuses the generic filter template."""
    from app.labels.service import LabelNotFound, get_label, list_tasks_by_label

    try:
        label = await get_label(session, user.id, label_id)
    except LabelNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "лейбл не найден") from e

    tasks = await list_tasks_by_label(session, user.id, label_id)
    projects = await list_projects(session, user.id)
    project_color_map: dict[UUID, str] = {p.id: p.color for p in projects}
    return templates.TemplateResponse(
        request,
        "app/filter.html",
        {
            "current_user": user,
            "current_view": f"label:{label_id}",
            "projects": projects,
            "project_color_map": project_color_map,
            "filter": {
                "name": f"@{label.name}",
                "color": label.color,
                "icon_path": "M7 7h.01M3 5a2 2 0 012-2h5.586a1 1 0 01.707.293l8 "
                "8a2 2 0 010 2.828l-5.586 5.586a2 2 0 01-2.828 0l-8-8A1 1 0 013 "
                "10.586V5z",
                "description": "Задачи с этим лейблом",
            },
            "tasks": tasks,
        },
    )


@router.get("/done", response_class=HTMLResponse)
async def done_view(request: Request, user: RequiredUser, session: DbSession) -> HTMLResponse:
    """History of completed tasks, grouped by completion date (newest first)."""
    tasks = await list_completed(session, user.id, limit=300)
    today_date = datetime.now(UTC).date()
    yesterday = today_date - timedelta(days=1)

    grouped: dict[date, list[Task]] = defaultdict(list)
    for t in tasks:
        when = (t.completed_at or t.updated_at).date()
        grouped[when].append(t)

    days = []
    for d in sorted(grouped, reverse=True):
        if d == today_date:
            label = "Сегодня"
        elif d == yesterday:
            label = "Вчера"
        else:
            label = (
                f"{_RU_WEEKDAYS[d.weekday()].capitalize()}, {d.day} {_RU_MONTHS_GEN[d.month - 1]}"
            )
        days.append({"date": d, "label": label, "tasks": grouped[d]})

    projects = await list_projects(session, user.id)
    project_color_map: dict[UUID, str] = {p.id: p.color for p in projects}

    return templates.TemplateResponse(
        request,
        "app/done.html",
        {
            "current_user": user,
            "current_view": "done",
            "projects": projects,
            "project_color_map": project_color_map,
            "days": days,
            "total": len(tasks),
        },
    )


@router.get("/projects-archive", response_class=HTMLResponse)
async def projects_archive_view(
    request: Request, user: RequiredUser, session: DbSession
) -> HTMLResponse:
    projects = await list_projects(session, user.id)
    archived = await list_archived_projects(session, user.id)
    project_color_map: dict[UUID, str] = {p.id: p.color for p in projects}
    return templates.TemplateResponse(
        request,
        "app/projects_archive.html",
        {
            "current_user": user,
            "current_view": "archive",
            "projects": projects,
            "project_color_map": project_color_map,
            "archived": archived,
        },
    )


@router.get("/profile")
async def profile_redirect() -> RedirectResponse:
    return RedirectResponse("/app/settings", status_code=303)


@router.get("/settings", response_class=HTMLResponse)
async def settings_view(request: Request, user: RequiredUser, session: DbSession) -> HTMLResponse:
    from sqlalchemy import func
    from sqlalchemy import select as sa_select

    from app.billing.service import has_pro_features, trial_days_remaining
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
        "app/settings.html",
        {
            "current_user": user,
            "current_view": "settings",
            "projects": projects,
            "project_color_map": project_color_map,
            "stats": stats,
            "is_pro": has_pro_features(user),
            "trial_days_left": trial_days_remaining(user),
        },
    )


@router.get("/trash", response_class=HTMLResponse)
async def trash_view(request: Request, user: RequiredUser, session: DbSession) -> HTMLResponse:
    from app.billing.service import limits_for
    from app.tasks.service import list_trash

    projects = await list_projects(session, user.id)
    project_color_map: dict[UUID, str] = {p.id: p.color for p in projects}
    trashed = await list_trash(
        session, user.id, max_age_days=limits_for(user)["trash_retention_days"]
    )
    project_name: dict[UUID, str] = {p.id: p.name for p in projects}
    return templates.TemplateResponse(
        request,
        "app/trash.html",
        {
            "current_user": user,
            "current_view": "trash",
            "projects": projects,
            "project_color_map": project_color_map,
            "trashed": trashed,
            "project_name": project_name,
        },
    )


@router.get("/schedule", response_class=HTMLResponse)
async def schedule_view(request: Request, user: RequiredUser, session: DbSession) -> HTMLResponse:
    from app.school.schedule_service import list_slots
    from app.school.subjects import SUBJECTS, WEEKDAY_FULL_RU, WEEKDAY_SHORT_RU

    projects = await list_projects(session, user.id)
    project_color_map: dict[UUID, str] = {p.id: p.color for p in projects}
    slots = await list_slots(session, user.id)
    grid: dict[tuple[int, int], dict[str, object]] = {}
    for s in slots:
        grid[(s.weekday, s.period)] = {
            "subject_code": s.subject_code,
            "room": s.room,
            "teacher": s.teacher,
        }
    return templates.TemplateResponse(
        request,
        "app/schedule.html",
        {
            "current_user": user,
            "current_view": "schedule",
            "projects": projects,
            "project_color_map": project_color_map,
            "subjects": SUBJECTS,
            "weekdays_short": WEEKDAY_SHORT_RU,
            "weekdays_full": WEEKDAY_FULL_RU,
            "periods": list(range(1, 9)),
            "grid": grid,
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


@router.get("/root", response_class=HTMLResponse)
async def admin_root_view(request: Request, session: DbSession) -> HTMLResponse:
    """Admin panel — total control: complaints, users, stats. Requires is_admin."""
    from app.admin.service import admin_stats, list_complaints, list_recent_users
    from app.auth.deps import get_current_user, require_admin, require_user

    user = await require_user(await get_current_user(request, session))
    user = await require_admin(user)

    complaints = await list_complaints(session, limit=200)
    stats = await admin_stats(session)
    recent_users = await list_recent_users(session, limit=20)

    # Map complaint.user_id → user.email for display
    user_emails: dict[UUID, str] = {}
    for c in complaints:
        if c.user_id and c.user_id not in user_emails:
            u = await session.get(User, c.user_id)
            if u:
                user_emails[c.user_id] = u.email

    return templates.TemplateResponse(
        request,
        "app/root.html",
        {
            "current_user": user,
            "current_view": "root",
            "projects": [],
            "complaints": complaints,
            "stats": stats,
            "recent_users": recent_users,
            "user_emails": user_emails,
        },
    )


@router.get("/simple/today", response_class=HTMLResponse)
async def simple_today_view(
    request: Request, user: RequiredUser, session: DbSession
) -> HTMLResponse:
    from app.tasks.service import list_today as _list_today_simple

    tasks = await _list_today_simple(session, user.id)
    today_date = datetime.now(UTC).date()
    return templates.TemplateResponse(
        request,
        "simple/today.html",
        {
            "current_user": user,
            "tasks": tasks,
            "today_label": _today_label(today_date),
        },
    )


@router.get("/simple/inbox", response_class=HTMLResponse)
async def simple_inbox_view(
    request: Request, user: RequiredUser, session: DbSession
) -> HTMLResponse:
    from app.projects.service import ensure_inbox
    from app.tasks.service import list_tasks as _list_tasks_simple

    inbox = await ensure_inbox(session, user.id)
    tasks = await _list_tasks_simple(session, user.id, project_id=inbox.id, include_completed=False)
    return templates.TemplateResponse(
        request,
        "simple/inbox.html",
        {"current_user": user, "tasks": tasks},
    )


@router.get("/simple/add", response_class=HTMLResponse)
async def simple_add_form(request: Request, user: RequiredUser) -> HTMLResponse:
    return templates.TemplateResponse(request, "simple/add.html", {"current_user": user})


@router.post("/simple/add", response_class=RedirectResponse)
async def simple_add_submit(
    request: Request,
    user: RequiredUser,
    session: DbSession,
) -> RedirectResponse:

    from app.tasks.service import create_task as _create_task_simple

    form = await request.form()
    title_value = form.get("title", "")
    title = str(title_value).strip() if title_value else ""
    due_date_value = form.get("due_date", "")
    due_date = str(due_date_value).strip() if due_date_value else ""
    if not title:
        return RedirectResponse(url="/app/simple/add", status_code=status.HTTP_303_SEE_OTHER)

    due_at: datetime | None = None
    if due_date:
        try:
            d = date.fromisoformat(due_date)
            due_at = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=UTC)
        except ValueError:
            due_at = None

    await _create_task_simple(session, user.id, title=title, due_at=due_at)

    redirect = "/app/simple/today" if due_at else "/app/simple/inbox"
    return RedirectResponse(url=redirect, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/simple/task/{task_id}/toggle", response_class=HTMLResponse)
async def simple_toggle_task(
    request: Request, user: RequiredUser, session: DbSession, task_id: UUID
) -> HTMLResponse:
    from app.tasks.service import (
        complete_task,
        get_task,
        uncomplete_task,
    )

    task = await get_task(session, user.id, task_id)
    if task.is_completed:
        task = await uncomplete_task(session, user.id, task_id)
    else:
        task = await complete_task(session, user.id, task_id)
    return templates.TemplateResponse(
        request,
        "simple/_partials/task_row.html",
        {"task": task},
    )


@router.post("/simple/task/{task_id}/delete", response_class=HTMLResponse)
async def simple_delete_task(user: RequiredUser, session: DbSession, task_id: UUID) -> HTMLResponse:
    from app.tasks.service import delete_task as _delete_task_simple

    await _delete_task_simple(session, user.id, task_id)
    return HTMLResponse(content="", status_code=200)


@router.get("/simple/settings", response_class=HTMLResponse)
async def simple_settings_view(request: Request, user: RequiredUser) -> HTMLResponse:
    return templates.TemplateResponse(request, "simple/settings.html", {"current_user": user})
