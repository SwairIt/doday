"""Stats service — aggregate completion counts and streak math."""

from collections import Counter
from datetime import UTC, date, datetime, timedelta
from typing import TypedDict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.models import Task

_RU_WEEKDAYS_NOM = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


class ChartCell(TypedDict):
    date: date
    label: str
    count: int


class UserStats(TypedDict):
    current_streak: int
    longest_streak: int
    done_today: int
    done_week: int
    done_month: int
    done_total: int
    chart: list[ChartCell]
    chart_max: int
    best_weekday: str
    avg_per_active_day: float
    active_days: int


async def _completed_dates(session: AsyncSession, user_id: UUID) -> list[date]:
    """All distinct UTC dates on which the user completed at least one task."""
    result = await session.execute(
        select(func.date(Task.completed_at))
        .where(
            Task.user_id == user_id,
            Task.is_completed.is_(True),
            Task.completed_at.is_not(None),
        )
        .distinct()
    )
    days_raw = {row[0] for row in result.all() if row[0] is not None}
    return sorted({d if isinstance(d, date) else date.fromisoformat(str(d)) for d in days_raw})


def _current_streak(days: list[date], today: date) -> int:
    """Consecutive completion days ending today (or yesterday — grace day)."""
    if not days:
        return 0
    days_set = set(days)
    streak = 0
    if today in days_set:
        cursor = today
    elif (today - timedelta(days=1)) in days_set:
        cursor = today - timedelta(days=1)
    else:
        return 0
    while cursor in days_set:
        streak += 1
        cursor = cursor - timedelta(days=1)
    return streak


def _longest_streak(days: list[date]) -> int:
    if not days:
        return 0
    days = sorted(days)
    longest = 1
    run = 1
    for i in range(1, len(days)):
        if (days[i] - days[i - 1]).days == 1:
            run += 1
            longest = max(longest, run)
        else:
            run = 1
    return longest


async def compute_user_stats(session: AsyncSession, user_id: UUID) -> UserStats:
    """One-shot dashboard payload for the stats page."""
    now = datetime.now(UTC)
    today = now.date()
    week_start = today - timedelta(days=today.weekday())  # Monday this week
    month_start = today.replace(day=1)
    last_14_start = today - timedelta(days=13)

    days = await _completed_dates(session, user_id)
    current = _current_streak(days, today)
    longest = _longest_streak(days)

    async def count_done(since: date | None = None, until: date | None = None) -> int:
        stmt = (
            select(func.count())
            .select_from(Task)
            .where(
                Task.user_id == user_id,
                Task.is_completed.is_(True),
                Task.completed_at.is_not(None),
            )
        )
        if since is not None:
            stmt = stmt.where(func.date(Task.completed_at) >= since)
        if until is not None:
            stmt = stmt.where(func.date(Task.completed_at) <= until)
        return (await session.execute(stmt)).scalar_one()

    done_today = await count_done(today, today)
    done_week = await count_done(week_start, today)
    done_month = await count_done(month_start, today)
    done_total = await count_done()

    # Per-day counts for last 14 days (for the bar chart)
    rows = await session.execute(
        select(func.date(Task.completed_at), func.count())
        .where(
            Task.user_id == user_id,
            Task.is_completed.is_(True),
            Task.completed_at.is_not(None),
            func.date(Task.completed_at) >= last_14_start,
        )
        .group_by(func.date(Task.completed_at))
    )
    by_day: dict[date, int] = {}
    for d, n in rows.all():
        if isinstance(d, date):
            by_day[d] = n
        elif d is not None:
            by_day[date.fromisoformat(str(d))] = n
    chart: list[ChartCell] = []
    for offset in range(14):
        d = last_14_start + timedelta(days=offset)
        chart.append({"date": d, "label": d.strftime("%d.%m"), "count": by_day.get(d, 0)})
    chart_max = max((c["count"] for c in chart), default=0)

    # Most productive weekday (across all-time history)
    weekday_counter: Counter[int] = Counter()
    for d in days:
        weekday_counter[d.weekday()] += 1
    if weekday_counter:
        best_wd, best_n = weekday_counter.most_common(1)[0]
        best_weekday = f"{_RU_WEEKDAYS_NOM[best_wd]} ({best_n})"
    else:
        best_weekday = "—"

    # Average per active day
    if days:
        avg_per_active_day = round(done_total / len(days), 1)
    else:
        avg_per_active_day = 0.0

    return {
        "current_streak": current,
        "longest_streak": longest,
        "done_today": done_today,
        "done_week": done_week,
        "done_month": done_month,
        "done_total": done_total,
        "chart": chart,
        "chart_max": chart_max,
        "best_weekday": best_weekday,
        "avg_per_active_day": avg_per_active_day,
        "active_days": len(days),
    }
