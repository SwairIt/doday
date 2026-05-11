"""XP + level calculations.

XP awarded по приоритету (P1=10, P2=5, P3=3, P4=2). Subtasks дают
половину (round-down). 100 XP = 1 level. Level-up event возвращается
из award_xp если случился.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.gamification.models import UserProgress
from app.tasks.models import Task, TaskPriority

XP_PER_PRIORITY = {
    TaskPriority.P1: 10,
    TaskPriority.P2: 5,
    TaskPriority.P3: 3,
    TaskPriority.P4: 2,
}
XP_PER_LEVEL = 100


def level_for_xp(xp: int) -> int:
    """XP → level. 0-99 = level 1, 100-199 = level 2, etc."""
    if xp < 0:
        return 1
    return 1 + xp // XP_PER_LEVEL


def xp_to_next_level(xp: int) -> int:
    current_level = level_for_xp(xp)
    return current_level * XP_PER_LEVEL - xp


def xp_in_current_level(xp: int) -> int:
    """Сколько XP набрано на текущем уровне (0 до XP_PER_LEVEL-1)."""
    return xp % XP_PER_LEVEL


def xp_for_task(task: Task) -> int:
    """Базовая XP за задачу. Subtask = 50% (но min 1)."""
    base = XP_PER_PRIORITY.get(task.priority, 2)
    if task.parent_task_id is not None:
        return max(1, base // 2)
    return base


async def get_progress(session: AsyncSession, user_id: UUID) -> UserProgress:
    """Получить или создать прогресс юзера."""
    row = (
        await session.execute(select(UserProgress).where(UserProgress.user_id == user_id))
    ).scalar_one_or_none()
    if row is None:
        row = UserProgress(user_id=user_id, xp_total=0, level=1)
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


async def award_xp(session: AsyncSession, user_id: UUID, amount: int) -> tuple[UserProgress, bool]:
    """Дать N XP. Возвращает (progress, level_up_just_happened)."""
    progress = await get_progress(session, user_id)
    old_level = progress.level
    progress.xp_total += amount
    progress.level = level_for_xp(progress.xp_total)
    leveled_up = progress.level > old_level
    if leveled_up:
        progress.last_level_up_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(progress)
    return progress, leveled_up
