"""Achievement catalog + auto-unlock logic.

Каждая ачивка — `Achievement` dataclass с key/emoji/title/description +
async-функция `check(session, user_id) -> bool`.

Проверка после каждого complete_task: prosto перебираем все achievements
которые юзер ещё не unlocked, вызываем check() — если True, добавляем в
user_achievements. Возвращаем list of newly unlocked.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.gamification.models import UserAchievement, UserProgress
from app.projects.models import Project
from app.tasks.models import Task, TaskPriority

CheckFn = Callable[[AsyncSession, UUID], Awaitable[bool]]


@dataclass
class Achievement:
    key: str
    emoji: str
    title: str
    description: str
    check: CheckFn


# ---- check functions -------------------------------------------------------


async def _done_total(session: AsyncSession, user_id: UUID) -> int:
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(Task)
                .where(
                    Task.user_id == user_id,
                    Task.is_completed.is_(True),
                )
            )
        ).scalar_one()
    )


async def _has_done(session: AsyncSession, user_id: UUID, n: int) -> bool:
    return await _done_total(session, user_id) >= n


async def _check_seed(s: AsyncSession, u: UUID) -> bool:
    return await _has_done(s, u, 1)


async def _check_hundred(s: AsyncSession, u: UUID) -> bool:
    return await _has_done(s, u, 100)


async def _check_oak(s: AsyncSession, u: UUID) -> bool:
    return await _has_done(s, u, 1000)


async def _check_p1_sniper(s: AsyncSession, u: UUID) -> bool:
    n = int(
        (
            await s.execute(
                select(func.count())
                .select_from(Task)
                .where(
                    Task.user_id == u,
                    Task.is_completed.is_(True),
                    Task.priority == TaskPriority.P1,
                )
            )
        ).scalar_one()
    )
    return n >= 50


async def _check_lightning(s: AsyncSession, u: UUID) -> bool:
    """5 P1 closed за день."""
    today = datetime.now(UTC).date()
    n = int(
        (
            await s.execute(
                select(func.count())
                .select_from(Task)
                .where(
                    Task.user_id == u,
                    Task.is_completed.is_(True),
                    Task.priority == TaskPriority.P1,
                    Task.completed_at.is_not(None),
                    func.date(Task.completed_at) == today,
                )
            )
        ).scalar_one()
    )
    return n >= 5


async def _check_morning_bird(s: AsyncSession, u: UUID) -> bool:
    """10 задач закрыто до 9:00 (всё время)."""
    n = int(
        (
            await s.execute(
                select(func.count())
                .select_from(Task)
                .where(
                    Task.user_id == u,
                    Task.is_completed.is_(True),
                    Task.completed_at.is_not(None),
                    func.extract("hour", Task.completed_at) < 9,
                )
            )
        ).scalar_one()
    )
    return n >= 10


async def _check_night_owl(s: AsyncSession, u: UUID) -> bool:
    """10 задач закрыто после 22:00."""
    n = int(
        (
            await s.execute(
                select(func.count())
                .select_from(Task)
                .where(
                    Task.user_id == u,
                    Task.is_completed.is_(True),
                    Task.completed_at.is_not(None),
                    func.extract("hour", Task.completed_at) >= 22,
                )
            )
        ).scalar_one()
    )
    return n >= 10


async def _check_flood(s: AsyncSession, u: UUID) -> bool:
    """100 задач за неделю."""
    week_ago = (datetime.now(UTC) - timedelta(days=7)).date()
    n = int(
        (
            await s.execute(
                select(func.count())
                .select_from(Task)
                .where(
                    Task.user_id == u,
                    Task.is_completed.is_(True),
                    Task.completed_at.is_not(None),
                    func.date(Task.completed_at) >= week_ago,
                )
            )
        ).scalar_one()
    )
    return n >= 100


async def _check_builder(s: AsyncSession, u: UUID) -> bool:
    """10 проектов (не считая Inbox)."""
    n = int(
        (
            await s.execute(
                select(func.count())
                .select_from(Project)
                .where(Project.user_id == u, Project.is_inbox.is_(False))
            )
        ).scalar_one()
    )
    return n >= 10


async def _check_strategist(s: AsyncSession, u: UUID) -> bool:
    """50 завершённых повторяющихся задач."""
    n = int(
        (
            await s.execute(
                select(func.count())
                .select_from(Task)
                .where(
                    Task.user_id == u,
                    Task.is_completed.is_(True),
                    Task.recurrence.is_not(None),
                )
            )
        ).scalar_one()
    )
    return n >= 50


async def _check_streak_week(s: AsyncSession, u: UUID) -> bool:
    """Streak >= 7 (используем app.stats.service)."""
    from app.stats.service import compute_user_stats

    stats = await compute_user_stats(s, u)
    return int(stats["current_streak"]) >= 7


async def _check_streak_month(s: AsyncSession, u: UUID) -> bool:
    from app.stats.service import compute_user_stats

    stats = await compute_user_stats(s, u)
    return int(stats["current_streak"]) >= 30


async def _check_streak_100(s: AsyncSession, u: UUID) -> bool:
    from app.stats.service import compute_user_stats

    stats = await compute_user_stats(s, u)
    return int(stats["current_streak"]) >= 100


async def _check_level_5(s: AsyncSession, u: UUID) -> bool:
    progress = (
        await s.execute(select(UserProgress).where(UserProgress.user_id == u))
    ).scalar_one_or_none()
    return progress is not None and progress.level >= 5


async def _check_level_10(s: AsyncSession, u: UUID) -> bool:
    progress = (
        await s.execute(select(UserProgress).where(UserProgress.user_id == u))
    ).scalar_one_or_none()
    return progress is not None and progress.level >= 10


async def _check_perfectionist(s: AsyncSession, u: UUID) -> bool:
    """Все labels использованы (не пустой список)."""
    from app.labels.models import Label

    n = int(
        (
            await s.execute(select(func.count()).select_from(Label).where(Label.user_id == u))
        ).scalar_one()
    )
    return n >= 5


# ---- catalog ---------------------------------------------------------------


ACHIEVEMENTS: list[Achievement] = [
    Achievement("seed", "🌱", "Семечко", "Первая закрытая задача", _check_seed),
    Achievement("hundred", "💯", "Сотка", "100 задач закрыто", _check_hundred),
    Achievement("oak", "🌳", "Дуб", "1000 задач закрыто", _check_oak),
    Achievement("p1_sniper", "🎯", "Снайпер", "50 P1-задач закрыто", _check_p1_sniper),
    Achievement("lightning", "⚡", "Молния", "5 P1 за один день", _check_lightning),
    Achievement("morning_bird", "🌅", "Жаворонок", "10 задач закрыто до 9:00", _check_morning_bird),
    Achievement("night_owl", "🦉", "Сова", "10 задач закрыто после 22:00", _check_night_owl),
    Achievement("flood", "🌊", "Затопил", "100 задач за неделю", _check_flood),
    Achievement("builder", "🏗️", "Строитель", "10 своих проектов", _check_builder),
    Achievement("strategist", "🔮", "Стратег", "50 повторяющихся закрыто", _check_strategist),
    Achievement("streak_week", "🔥", "Неделя огня", "Стрик 7 дней", _check_streak_week),
    Achievement("streak_month", "🏆", "Месяц подряд", "Стрик 30 дней", _check_streak_month),
    Achievement("streak_100", "👑", "Сто дней", "Стрик 100 дней", _check_streak_100),
    Achievement("level_5", "⭐", "Уровень 5", "Достиг 5-го уровня", _check_level_5),
    Achievement("level_10", "🌟", "Уровень 10", "Достиг 10-го уровня", _check_level_10),
    Achievement("perfectionist", "🎨", "Палитра", "5+ лейблов созданы", _check_perfectionist),
]


async def list_unlocked_keys(session: AsyncSession, user_id: UUID) -> set[str]:
    rows = await session.execute(
        select(UserAchievement.achievement_key).where(UserAchievement.user_id == user_id)
    )
    return {r[0] for r in rows.all()}


async def check_and_unlock(session: AsyncSession, user_id: UUID) -> list[Achievement]:
    """Проверить все не-unlocked achievements, выдать те что check() == True.
    Возвращает list newly unlocked."""
    already = await list_unlocked_keys(session, user_id)
    newly: list[Achievement] = []
    for ach in ACHIEVEMENTS:
        if ach.key in already:
            continue
        try:
            if await ach.check(session, user_id):
                session.add(UserAchievement(user_id=user_id, achievement_key=ach.key))
                newly.append(ach)
        except Exception:  # noqa: S112 — broad catch by design: одна сломавшаяся ачивка не должна валить остальные
            continue
    if newly:
        await session.commit()
    return newly
