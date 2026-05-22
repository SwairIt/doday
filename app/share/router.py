"""Public, read-only progress view. No auth — access is gated by a signed token.

This router exposes exactly one GET endpoint and zero mutations, so it cannot
affect any existing data or authorization path.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select

from app.auth.deps import DbSession
from app.auth.models import User
from app.share.service import (
    InvalidShareToken,
    display_name_from_email,
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
