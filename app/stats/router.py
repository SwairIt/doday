"""Lightweight JSON endpoints for stats badges shown across the UI."""

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter
from sqlalchemy import func, select

from app.auth.deps import DbSession, RequiredUser
from app.tasks.models import Task

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/streak")
async def streak(user: RequiredUser, session: DbSession) -> dict[str, int | bool]:
    """Return the current + longest completion streak. Used by the topbar chip."""
    today = datetime.now(UTC).date()
    horizon = today - timedelta(days=400)

    rows = await session.execute(
        select(func.date(Task.completed_at))
        .where(
            Task.user_id == user.id,
            Task.is_completed.is_(True),
            Task.completed_at.is_not(None),
            func.date(Task.completed_at) >= horizon,
        )
        .distinct()
    )
    days_set: set[date] = set()
    for row in rows.all():
        d = row[0]
        if isinstance(d, date):
            days_set.add(d)
        elif d is not None:
            days_set.add(date.fromisoformat(str(d)))

    if not days_set:
        return {"current": 0, "longest": 0, "today_done": False}

    if today in days_set:
        cursor = today
    elif (today - timedelta(days=1)) in days_set:
        cursor = today - timedelta(days=1)
    else:
        return {"current": 0, "longest": _longest(days_set), "today_done": False}

    current = 0
    while cursor in days_set:
        current += 1
        cursor -= timedelta(days=1)

    return {
        "current": current,
        "longest": max(current, _longest(days_set)),
        "today_done": today in days_set,
    }


def _longest(days: set[date]) -> int:
    if not days:
        return 0
    sorted_days = sorted(days)
    longest = 1
    run = 1
    for i in range(1, len(sorted_days)):
        if (sorted_days[i] - sorted_days[i - 1]).days == 1:
            run += 1
            longest = max(longest, run)
        else:
            run = 1
    return longest
