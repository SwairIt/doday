"""Tests for stats service — streaks and aggregate counts."""

from datetime import UTC, date, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.stats.service import _current_streak, _longest_streak, compute_user_stats
from app.tasks.service import complete_task, create_task


async def _user(db_session: AsyncSession, email: str = "u@s.ru") -> User:
    u = User(email=email, password_hash="argon2-fake")
    db_session.add(u)
    await db_session.commit()
    return u


def test_current_streak_empty() -> None:
    assert _current_streak([], date(2026, 5, 3)) == 0


def test_current_streak_today_only() -> None:
    today = date(2026, 5, 3)
    assert _current_streak([today], today) == 1


def test_current_streak_three_in_a_row() -> None:
    today = date(2026, 5, 3)
    days = [today, today - timedelta(days=1), today - timedelta(days=2)]
    assert _current_streak(days, today) == 3


def test_current_streak_grace_yesterday() -> None:
    """If today is empty but yesterday had completion, streak still counts (grace)."""
    today = date(2026, 5, 3)
    yest = today - timedelta(days=1)
    days = [yest, yest - timedelta(days=1)]
    assert _current_streak(days, today) == 2


def test_current_streak_broken_after_two_day_gap() -> None:
    today = date(2026, 5, 3)
    # Last completion was 3 days ago — streak is 0
    days = [today - timedelta(days=3), today - timedelta(days=4)]
    assert _current_streak(days, today) == 0


def test_longest_streak() -> None:
    base = date(2026, 1, 1)
    days = [
        base,
        base + timedelta(days=1),
        base + timedelta(days=2),
        base + timedelta(days=10),
        base + timedelta(days=11),
    ]
    assert _longest_streak(days) == 3


def test_longest_streak_empty() -> None:
    assert _longest_streak([]) == 0


async def test_compute_user_stats_no_data(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    stats = await compute_user_stats(db_session, user.id)
    assert stats["current_streak"] == 0
    assert stats["longest_streak"] == 0
    assert stats["done_today"] == 0
    assert stats["done_total"] == 0
    assert stats["active_days"] == 0
    assert len(stats["chart"]) == 14


async def test_compute_user_stats_after_completion(
    db_session: AsyncSession,
) -> None:
    user = await _user(db_session)
    t1 = await create_task(db_session, user.id, title="A")
    t2 = await create_task(db_session, user.id, title="B")
    await complete_task(db_session, user.id, t1.id)
    await complete_task(db_session, user.id, t2.id)

    stats = await compute_user_stats(db_session, user.id)
    assert stats["done_today"] == 2
    assert stats["done_total"] == 2
    assert stats["current_streak"] == 1
    assert stats["active_days"] == 1
    today_str = datetime.now(UTC).date().strftime("%d.%m")
    today_cell = next(c for c in stats["chart"] if c["label"] == today_str)
    assert today_cell["count"] == 2


async def test_compute_user_stats_avg_completion_hours(
    db_session: AsyncSession,
) -> None:
    user = await _user(db_session)
    t = await create_task(db_session, user.id, title="X")
    await complete_task(db_session, user.id, t.id)
    stats = await compute_user_stats(db_session, user.id)
    assert "avg_completion_hours" in stats
    assert isinstance(stats["avg_completion_hours"], float)
    # Just-created and just-completed → near-zero hours
    assert stats["avg_completion_hours"] >= 0.0


async def test_stats_view_renders(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/doday/app/stats")
    assert response.status_code == 200
    assert "Статистика" in response.text
    assert "Стрик" in response.text


async def test_stats_view_anonymous_blocked(client: AsyncClient) -> None:
    response = await client.get("/doday/app/stats")
    assert response.status_code == 401
