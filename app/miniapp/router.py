"""Mini App routes — auth + UI screens (5 bottom-nav tabs)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import func, select

from app.auth.deps import CurrentUser, DbSession
from app.config import get_settings
from app.miniapp.auth import get_telegram_user_id, validate_init_data
from app.miniapp.static import MINIAPP_JS
from app.projects.service import ensure_inbox, list_projects
from app.quickadd.parser import parse_quick_add
from app.tasks.models import Task
from app.tasks.service import create_task, list_completed_today, list_today
from app.telegram.models import TelegramLink

router = APIRouter(prefix="/miniapp", tags=["miniapp"])
templates = Jinja2Templates(directory="app/templates")


def _ctx(request: Request, current_user: object = None) -> dict[str, object]:
    """Common Jinja-context for miniapp pages (current_path для active-таба)."""
    return {"current_path": request.url.path, "current_user": current_user}


class AuthIn(BaseModel):
    init_data: str


@router.get("/assets/miniapp.js")
async def miniapp_js() -> Response:
    """Inline JS-bundle для Mini App. Cache на 1 час (короткий — пока итерируем
    дизайн), потом увеличим."""
    return Response(
        content=MINIAPP_JS,
        media_type="application/javascript; charset=utf-8",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.post("/auth")
async def auth(
    request: Request,
    payload: AuthIn,
    session: DbSession,
) -> JSONResponse:
    """Validate Telegram WebApp initData → set session cookie → return user info.

    Flow:
    1. Парсим initData, проверяем HMAC bot-token'ом
    2. Если невалидно → 401 {"error": "invalid_init_data"}
    3. Достаём Telegram user_id, ищем в telegram_links (chat_id == user_id)
    4. Если не привязан → 401 {"need_link": true, "telegram_user_id": ...}
    5. Если привязан → ставим session["user_id"] → 200 {"ok": true}
    """
    settings = get_settings()
    if not settings.telegram_bot_token:
        return JSONResponse(
            {"error": "bot_not_configured"},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    parsed = validate_init_data(payload.init_data, settings.telegram_bot_token)
    if parsed is None:
        return JSONResponse(
            {"error": "invalid_init_data"}, status_code=status.HTTP_401_UNAUTHORIZED
        )

    tg_user_id = get_telegram_user_id(parsed)
    if tg_user_id is None:
        return JSONResponse({"error": "no_user_field"}, status_code=status.HTTP_401_UNAUTHORIZED)

    # Telegram-личка = chat_id равен user_id; в групповых чатах было бы по-другому,
    # но Mini App открывается всегда в личке/инлайне.
    link = (
        await session.execute(select(TelegramLink).where(TelegramLink.chat_id == tg_user_id))
    ).scalar_one_or_none()
    if link is None or link.user_id is None:
        return JSONResponse(
            {"need_link": True, "telegram_user_id": tg_user_id},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    request.session["user_id"] = str(link.user_id)
    return JSONResponse({"ok": True, "user_id": str(link.user_id)})


# --- UI screens (5 bottom-nav tabs) -----------------------------------------
#
# Все требуют залогиненного юзера. Если session-cookie нет — редирект на
# /miniapp/link (там клиентский JS попытается auth через initData; если не
# Telegram — покажет инструкцию как привязать аккаунт).


def _require_user_or_redirect(user: object, telegram_user_id: int | None = None) -> Response | None:
    """Если user не залогинен — Response с редиректом на link-screen, иначе None."""
    if user is not None:
        return None
    url = "/miniapp/link"
    if telegram_user_id is not None:
        url += f"?telegram_user_id={telegram_user_id}"
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/", response_class=HTMLResponse)
async def today(request: Request, user: CurrentUser, session: DbSession) -> Response:
    redir = _require_user_or_redirect(user)
    if redir is not None:
        return redir
    if user is None:  # pragma: no cover — narrow для mypy
        return RedirectResponse(url="/miniapp/link", status_code=status.HTTP_303_SEE_OTHER)

    today_date = datetime.now(UTC).date()
    tasks = await list_today(session, user.id)
    overdue = [t for t in tasks if t.due_at and t.due_at.date() < today_date]
    today_tasks = [t for t in tasks if t.due_at and t.due_at.date() >= today_date]

    done_today_count = (
        await session.execute(
            select(func.count())
            .select_from(Task)
            .where(
                Task.user_id == user.id,
                Task.is_completed.is_(True),
                Task.completed_at.is_not(None),
                func.date(Task.completed_at) == today_date,
            )
        )
    ).scalar_one()

    completed_today = await list_completed_today(session, user.id, limit=10)

    ctx = _ctx(request, user)
    ctx.update(
        overdue=overdue,
        today=today_tasks,
        today_total=len(today_tasks) + len(overdue),
        done_today_count=done_today_count,
        completed_today=completed_today,
    )
    return templates.TemplateResponse(request, "miniapp/today.html", ctx)


@router.get("/inbox", response_class=HTMLResponse)
async def inbox(request: Request, user: CurrentUser, session: DbSession) -> Response:
    redir = _require_user_or_redirect(user)
    if redir is not None:
        return redir
    if user is None:  # pragma: no cover
        return RedirectResponse(url="/miniapp/link", status_code=status.HTTP_303_SEE_OTHER)
    inbox_proj = await ensure_inbox(session, user.id)
    rows = await session.execute(
        select(Task)
        .where(
            Task.user_id == user.id,
            Task.project_id == inbox_proj.id,
            Task.is_completed.is_(False),
            Task.deleted_at.is_(None),
        )
        .order_by(Task.position, Task.created_at)
        .limit(50)
    )
    tasks = list(rows.scalars().all())
    ctx = _ctx(request, user)
    ctx["tasks"] = tasks
    return templates.TemplateResponse(request, "miniapp/inbox.html", ctx)


@router.get("/calendar", response_class=HTMLResponse)
async def calendar(
    request: Request,
    user: CurrentUser,
    session: DbSession,
    date: str | None = None,
) -> Response:
    """Week-view calendar. Selected day defaults to today; navigation through
    ?date=YYYY-MM-DD links + horizontal swipe в miniapp.js."""
    redir = _require_user_or_redirect(user)
    if redir is not None:
        return redir
    if user is None:  # pragma: no cover
        return RedirectResponse(url="/miniapp/link", status_code=status.HTTP_303_SEE_OTHER)

    from datetime import date as date_cls
    from datetime import timedelta

    today_date = datetime.now(UTC).date()
    if date:
        try:
            selected_date = date_cls.fromisoformat(date)
        except ValueError:
            selected_date = today_date
    else:
        selected_date = today_date

    # Week starts on Monday — российская норма
    week_start = selected_date - timedelta(days=selected_date.weekday())
    week_dates = [week_start + timedelta(days=i) for i in range(7)]
    week_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

    # Tasks for selected day (and overdue if today is selected)
    day_start = datetime.combine(selected_date, datetime.min.time(), tzinfo=UTC)
    day_end = datetime.combine(selected_date, datetime.max.time(), tzinfo=UTC)
    tasks_q = await session.execute(
        select(Task)
        .where(
            Task.user_id == user.id,
            Task.is_completed.is_(False),
            Task.deleted_at.is_(None),
            Task.due_at.is_not(None),
            Task.due_at >= day_start,
            Task.due_at <= day_end,
        )
        .order_by(Task.due_at, Task.position)
        .limit(50)
    )
    day_tasks = list(tasks_q.scalars().all())

    # Counts per week-day for badges in chip-row
    week_counts_q = await session.execute(
        select(func.date(Task.due_at), func.count())
        .where(
            Task.user_id == user.id,
            Task.is_completed.is_(False),
            Task.deleted_at.is_(None),
            Task.due_at.is_not(None),
            func.date(Task.due_at) >= week_start,
            func.date(Task.due_at) <= week_dates[-1],
        )
        .group_by(func.date(Task.due_at))
    )
    counts_map = {row[0]: row[1] for row in week_counts_q.all()}

    week_chips = [
        {
            "date": d,
            "iso": d.isoformat(),
            "weekday_name": week_names[i],
            "is_today": d == today_date,
            "is_selected": d == selected_date,
            "count": counts_map.get(d, 0),
        }
        for i, d in enumerate(week_dates)
    ]

    prev_week_iso = (week_start - timedelta(days=7)).isoformat()
    next_week_iso = (week_start + timedelta(days=7)).isoformat()

    ctx = _ctx(request, user)
    ctx.update(
        selected_date=selected_date,
        week_chips=week_chips,
        day_tasks=day_tasks,
        prev_week_iso=prev_week_iso,
        next_week_iso=next_week_iso,
        today_iso=today_date.isoformat(),
    )
    return templates.TemplateResponse(request, "miniapp/calendar.html", ctx)


@router.get("/projects", response_class=HTMLResponse)
async def projects(request: Request, user: CurrentUser) -> Response:
    redir = _require_user_or_redirect(user)
    if redir is not None:
        return redir
    return templates.TemplateResponse(request, "miniapp/projects.html", _ctx(request, user))


class QuickAddIn(BaseModel):
    text: str


@router.post("/api/parse")
async def api_parse(payload: QuickAddIn, user: CurrentUser) -> JSONResponse:
    """Live-preview парсера для quick-add. Возвращает разбор (title, due_at,
    priority, labels) для Alpine'овых чипсов под полем."""
    if user is None:
        return JSONResponse({"error": "auth_required"}, status_code=401)
    parsed = parse_quick_add(payload.text or "")
    return JSONResponse(
        {
            "title": parsed.title,
            "due_at": parsed.due_at.isoformat() if parsed.due_at else None,
            "due_date_only": parsed.date_only,
            "priority": parsed.priority.value,
            "label_names": parsed.label_names,
            "project_name": parsed.project_name,
            "recurrence": parsed.recurrence,
        }
    )


@router.post("/api/tasks", status_code=status.HTTP_201_CREATED)
async def api_create_task(
    payload: QuickAddIn,
    user: CurrentUser,
    session: DbSession,
) -> JSONResponse:
    """Парсит и создаёт задачу. Без указания project — в Inbox."""
    if user is None:
        return JSONResponse({"error": "auth_required"}, status_code=401)
    text = (payload.text or "").strip()
    if not text:
        return JSONResponse({"error": "empty_text"}, status_code=400)
    parsed = parse_quick_add(text)
    inbox = await ensure_inbox(session, user.id)
    task = await create_task(
        session,
        user.id,
        title=parsed.title,
        project_id=inbox.id,
        due_at=parsed.due_at,
        due_date_only=parsed.date_only,
        priority=parsed.priority,
        recurrence=parsed.recurrence,
    )
    return JSONResponse(
        {
            "id": str(task.id),
            "title": task.title,
            "priority": task.priority.value,
            "due_at": task.due_at.isoformat() if task.due_at else None,
        },
        status_code=status.HTTP_201_CREATED,
    )


@router.post("/api/tasks/{task_id}/complete")
async def api_complete_task(
    task_id: str,
    user: CurrentUser,
    session: DbSession,
) -> JSONResponse:
    """Toggle complete. Используется в MB3 swipe-actions (свайп влево)."""
    if user is None:
        return JSONResponse({"error": "auth_required"}, status_code=401)
    from uuid import UUID

    try:
        tid = UUID(task_id)
    except ValueError:
        return JSONResponse({"error": "bad_id"}, status_code=400)
    task = (
        await session.execute(select(Task).where(Task.id == tid, Task.user_id == user.id))
    ).scalar_one_or_none()
    if task is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    if task.is_completed:
        task.is_completed = False
        task.completed_at = None
    else:
        task.is_completed = True
        task.completed_at = datetime.now(UTC)
    await session.commit()
    return JSONResponse({"id": str(task.id), "is_completed": task.is_completed})


@router.get("/api/tasks/{task_id}")
async def api_get_task(
    task_id: str,
    user: CurrentUser,
    session: DbSession,
) -> JSONResponse:
    """Получить задачу для bottom-sheet (MB4)."""
    if user is None:
        return JSONResponse({"error": "auth_required"}, status_code=401)
    from uuid import UUID

    try:
        tid = UUID(task_id)
    except ValueError:
        return JSONResponse({"error": "bad_id"}, status_code=400)
    task = (
        await session.execute(select(Task).where(Task.id == tid, Task.user_id == user.id))
    ).scalar_one_or_none()
    if task is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse(
        {
            "id": str(task.id),
            "title": task.title,
            "priority": task.priority.value,
            "due_at": task.due_at.isoformat() if task.due_at else None,
            "due_date_only": task.due_date_only,
            "is_completed": task.is_completed,
            "project_id": str(task.project_id),
            "recurrence": task.recurrence,
        }
    )


class TaskPatchIn(BaseModel):
    title: str | None = None
    priority: str | None = None  # 'p1'..'p4' or None
    due_at: str | None = None  # ISO 8601 or "" to clear
    due_date_only: bool | None = None
    project_id: str | None = None  # UUID — для move-to-project (MB5)


@router.patch("/api/tasks/{task_id}")
async def api_patch_task(
    task_id: str,
    payload: TaskPatchIn,
    user: CurrentUser,
    session: DbSession,
) -> JSONResponse:
    """Partial-update задачи из bottom-sheet (MB4)."""
    if user is None:
        return JSONResponse({"error": "auth_required"}, status_code=401)
    from uuid import UUID

    try:
        tid = UUID(task_id)
    except ValueError:
        return JSONResponse({"error": "bad_id"}, status_code=400)
    task = (
        await session.execute(select(Task).where(Task.id == tid, Task.user_id == user.id))
    ).scalar_one_or_none()
    if task is None:
        return JSONResponse({"error": "not_found"}, status_code=404)

    if payload.title is not None:
        title = payload.title.strip()
        if title:
            task.title = title[:500]
    if payload.priority is not None:
        from app.tasks.models import TaskPriority

        try:
            task.priority = TaskPriority(payload.priority)
        except ValueError:
            return JSONResponse({"error": "bad_priority"}, status_code=400)
    if payload.due_at is not None:
        if payload.due_at == "":
            task.due_at = None
        else:
            try:
                task.due_at = datetime.fromisoformat(payload.due_at.replace("Z", "+00:00"))
            except ValueError:
                return JSONResponse({"error": "bad_due_at"}, status_code=400)
    if payload.due_date_only is not None:
        task.due_date_only = payload.due_date_only
    if payload.project_id is not None:
        from uuid import UUID as _UUID

        try:
            new_project_id = _UUID(payload.project_id)
        except ValueError:
            return JSONResponse({"error": "bad_project_id"}, status_code=400)
        # Verify project ownership
        from app.projects.models import Project as _Project

        proj = (
            await session.execute(
                select(_Project).where(_Project.id == new_project_id, _Project.user_id == user.id)
            )
        ).scalar_one_or_none()
        if proj is None:
            return JSONResponse({"error": "project_not_found"}, status_code=404)
        task.project_id = new_project_id
    await session.commit()
    return JSONResponse(
        {
            "id": str(task.id),
            "title": task.title,
            "priority": task.priority.value,
            "due_at": task.due_at.isoformat() if task.due_at else None,
        }
    )


@router.get("/api/projects")
async def api_list_projects(user: CurrentUser, session: DbSession) -> JSONResponse:
    """Список проектов юзера для project-picker в task-sheet (MB5)."""
    if user is None:
        return JSONResponse({"error": "auth_required"}, status_code=401)
    projects = await list_projects(session, user.id)
    return JSONResponse(
        {
            "projects": [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "color": p.color,
                    "is_inbox": p.is_inbox,
                }
                for p in projects
            ]
        }
    )


@router.delete("/api/tasks/{task_id}")
async def api_delete_task(
    task_id: str,
    user: CurrentUser,
    session: DbSession,
) -> JSONResponse:
    """Soft-delete задачи через deleted_at (попадает в корзину)."""
    if user is None:
        return JSONResponse({"error": "auth_required"}, status_code=401)
    from uuid import UUID

    try:
        tid = UUID(task_id)
    except ValueError:
        return JSONResponse({"error": "bad_id"}, status_code=400)
    task = (
        await session.execute(select(Task).where(Task.id == tid, Task.user_id == user.id))
    ).scalar_one_or_none()
    if task is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    task.deleted_at = datetime.now(UTC)
    await session.commit()
    return JSONResponse({"ok": True})


@router.post("/api/tasks/{task_id}/snooze")
async def api_snooze_task(
    task_id: str,
    user: CurrentUser,
    session: DbSession,
) -> JSONResponse:
    """Снуз на завтра. Используется в MB3 swipe-actions (свайп вправо).

    Логика: due_at = завтра 23:59 UTC, due_date_only=True. Если due_at не было
    — ставим завтра. Так задача гарантированно «уходит» из Today.
    """
    if user is None:
        return JSONResponse({"error": "auth_required"}, status_code=401)
    from datetime import timedelta
    from uuid import UUID

    try:
        tid = UUID(task_id)
    except ValueError:
        return JSONResponse({"error": "bad_id"}, status_code=400)
    task = (
        await session.execute(select(Task).where(Task.id == tid, Task.user_id == user.id))
    ).scalar_one_or_none()
    if task is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).date()
    task.due_at = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 23, 59, tzinfo=UTC)
    task.due_date_only = True
    await session.commit()
    return JSONResponse({"id": str(task.id), "due_at": task.due_at.isoformat()})


@router.get("/me", response_class=HTMLResponse)
async def me(request: Request, user: CurrentUser) -> Response:
    redir = _require_user_or_redirect(user)
    if redir is not None:
        return redir
    return templates.TemplateResponse(request, "miniapp/me.html", _ctx(request, user))


@router.get("/link", response_class=HTMLResponse)
async def link_onboarding(
    request: Request,
    user: CurrentUser,
    telegram_user_id: int | None = None,
) -> Response:
    """Onboarding-экран. Если юзер УЖЕ залогинен — редирект на Today (не нужен
    onboarding). Иначе — рендерим инструкцию по привязке."""
    if user is not None:
        return RedirectResponse(url="/miniapp/", status_code=status.HTTP_303_SEE_OTHER)
    ctx = _ctx(request, user)
    ctx["telegram_user_id"] = telegram_user_id
    return templates.TemplateResponse(request, "miniapp/link.html", ctx)
