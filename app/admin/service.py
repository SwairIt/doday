"""Complaint CRUD + admin stats."""

from datetime import UTC, datetime, time, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import Complaint, PageView
from app.auth.models import User
from app.tasks.models import Task

VALID_STATUSES = {"open", "in_progress", "resolved", "dismissed"}
VALID_PRIORITIES = {"low", "normal", "high"}


async def create_complaint(
    session: AsyncSession,
    *,
    user_id: UUID | None,
    body: str,
    contact_email: str | None = None,
    page_url: str | None,
    viewport: str | None,
    user_agent: str | None,
) -> Complaint:
    """Persist a new complaint. Trim body to ≤4000 chars."""
    body = body.strip()[:4000]
    if not body:
        raise ValueError("body не может быть пустым")
    complaint = Complaint(
        user_id=user_id,
        body=body,
        contact_email=(contact_email or "").strip()[:320] or None,
        page_url=(page_url or "")[:500] or None,
        viewport=(viewport or "")[:20] or None,
        user_agent=(user_agent or "")[:500] or None,
    )
    session.add(complaint)
    await session.commit()
    await session.refresh(complaint)
    return complaint


async def list_complaints(
    session: AsyncSession,
    *,
    status_filter: str | None = None,
    priority_filter: str | None = None,
    since: datetime | None = None,
    limit: int = 200,
) -> list[Complaint]:
    stmt = select(Complaint).order_by(desc(Complaint.created_at)).limit(limit)
    if status_filter and status_filter in VALID_STATUSES:
        stmt = stmt.where(Complaint.status == status_filter)
    if priority_filter and priority_filter in VALID_PRIORITIES:
        stmt = stmt.where(Complaint.priority == priority_filter)
    if since is not None:
        stmt = stmt.where(Complaint.created_at >= since)
    return list((await session.execute(stmt)).scalars().all())


async def get_complaint(session: AsyncSession, complaint_id: UUID) -> Complaint | None:
    return await session.get(Complaint, complaint_id)


async def update_complaint(
    session: AsyncSession,
    complaint_id: UUID,
    *,
    status: str | None = None,
    priority: str | None = None,
    admin_note: str | None = None,
) -> Complaint | None:
    c = await session.get(Complaint, complaint_id)
    if c is None:
        return None
    if status is not None and status in VALID_STATUSES:
        c.status = status
        if status in ("resolved", "dismissed"):
            c.resolved_at = datetime.now(UTC)
        elif status == "open":
            c.resolved_at = None
    if priority is not None and priority in VALID_PRIORITIES:
        c.priority = priority
    if admin_note is not None:
        c.admin_note = admin_note.strip()[:2000] or None
    await session.commit()
    await session.refresh(c)
    return c


async def delete_complaint(session: AsyncSession, complaint_id: UUID) -> bool:
    c = await session.get(Complaint, complaint_id)
    if c is None:
        return False
    await session.delete(c)
    await session.commit()
    return True


async def admin_stats(session: AsyncSession) -> dict[str, Any]:
    """Top-level numbers for the admin dashboard."""
    now = datetime.now(UTC)
    today_start = datetime.combine(now.date(), time.min, tzinfo=UTC)
    week_ago = now - timedelta(days=7)

    users_total = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    users_today = (
        await session.execute(
            select(func.count()).select_from(User).where(User.created_at >= today_start)
        )
    ).scalar_one()
    users_week = (
        await session.execute(
            select(func.count()).select_from(User).where(User.created_at >= week_ago)
        )
    ).scalar_one()
    users_verified = (
        await session.execute(
            select(func.count()).select_from(User).where(User.email_verified_at.is_not(None))
        )
    ).scalar_one()
    tasks_total = (await session.execute(select(func.count()).select_from(Task))).scalar_one()
    tasks_today = (
        await session.execute(
            select(func.count()).select_from(Task).where(Task.created_at >= today_start)
        )
    ).scalar_one()
    complaints_open = (
        await session.execute(
            select(func.count()).select_from(Complaint).where(Complaint.status == "open")
        )
    ).scalar_one()
    complaints_total = (
        await session.execute(select(func.count()).select_from(Complaint))
    ).scalar_one()
    views_today = (
        await session.execute(
            select(func.count()).select_from(PageView).where(PageView.created_at >= today_start)
        )
    ).scalar_one()
    views_week = (
        await session.execute(
            select(func.count()).select_from(PageView).where(PageView.created_at >= week_ago)
        )
    ).scalar_one()
    # Уникальные посетители за неделю: залогиненные считаем по user_id.
    visitors_week = (
        await session.execute(
            select(func.count(func.distinct(PageView.user_id))).where(
                PageView.created_at >= week_ago, PageView.user_id.is_not(None)
            )
        )
    ).scalar_one()

    return {
        "users_total": users_total,
        "users_today": users_today,
        "users_week": users_week,
        "users_verified": users_verified,
        "tasks_total": tasks_total,
        "tasks_today": tasks_today,
        "complaints_open": complaints_open,
        "complaints_total": complaints_total,
        "views_today": views_today,
        "views_week": views_week,
        "visitors_week": visitors_week,
    }


async def list_recent_users(session: AsyncSession, limit: int = 20) -> list[User]:
    """Last-N registered users — for «who's signing up» quick glance."""
    stmt = select(User).order_by(desc(User.created_at)).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def record_page_view(session: AsyncSession, *, path: str, user_id: UUID | None) -> None:
    """Пишет один просмотр страницы. Вызывается из middleware, ошибки глушит
    вызывающий код — аналитика не должна влиять на ответ пользователю."""
    session.add(PageView(path=path[:300], user_id=user_id))
    await session.commit()


async def top_pages(
    session: AsyncSession, *, days: int = 7, limit: int = 12
) -> list[dict[str, Any]]:
    """Самые посещаемые страницы за последние N дней: [{path, count}]."""
    since = datetime.now(UTC) - timedelta(days=days)
    rows = (
        await session.execute(
            select(PageView.path, func.count().label("n"))
            .where(PageView.created_at >= since)
            .group_by(PageView.path)
            .order_by(desc("n"))
            .limit(limit)
        )
    ).all()
    return [{"path": path, "count": n} for path, n in rows]


async def signups_by_day(session: AsyncSession, *, days: int = 14) -> list[dict[str, Any]]:
    """Регистрации по дням за последние N дней: [{day: 'дд.мм', count}].

    Заполняем и нулевые дни, чтобы график не «схлопывался» на пустых датах.
    """
    since_date = (datetime.now(UTC) - timedelta(days=days - 1)).date()
    rows = (
        await session.execute(
            select(func.date(User.created_at).label("d"), func.count().label("n"))
            .where(func.date(User.created_at) >= since_date)
            .group_by("d")
        )
    ).all()
    counts = {str(d): n for d, n in rows}
    out: list[dict[str, Any]] = []
    for i in range(days):
        day = since_date + timedelta(days=i)
        out.append({"day": day.strftime("%d.%m"), "count": counts.get(str(day), 0)})
    return out
