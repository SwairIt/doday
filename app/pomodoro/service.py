"""Pomodoro service: start/stop sessions, time-on-task accumulator."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.pomodoro.models import PomodoroSession

DURATION_FOCUS_MIN = 25
DURATION_BREAK_SHORT_MIN = 5
DURATION_BREAK_LONG_MIN = 15
SESSIONS_BEFORE_LONG_BREAK = 4

VALID_KINDS = ("focus", "break-short", "break-long")


def _duration_for_kind(kind: str) -> int:
    if kind == "focus":
        return DURATION_FOCUS_MIN
    if kind == "break-short":
        return DURATION_BREAK_SHORT_MIN
    if kind == "break-long":
        return DURATION_BREAK_LONG_MIN
    raise ValueError(f"Unknown kind: {kind}")


async def get_active(session: AsyncSession, user_id: UUID) -> PomodoroSession | None:
    """Активная сессия (ended_at IS NULL). Должна быть только одна."""
    row = await session.execute(
        select(PomodoroSession)
        .where(PomodoroSession.user_id == user_id, PomodoroSession.ended_at.is_(None))
        .order_by(PomodoroSession.started_at.desc())
        .limit(1)
    )
    return row.scalar_one_or_none()


async def start(
    session: AsyncSession,
    user_id: UUID,
    task_id: UUID | None,
    kind: str = "focus",
) -> PomodoroSession:
    """Стартовать новую focus/break сессию. Если уже есть активная — её сначала
    стопим (force-stop, completed=False)."""
    if kind not in VALID_KINDS:
        raise ValueError(f"Unknown kind: {kind}")
    active = await get_active(session, user_id)
    if active is not None:
        active.ended_at = datetime.now(UTC)
        active.completed = False
        await session.commit()
    pomo = PomodoroSession(
        user_id=user_id,
        task_id=task_id,
        started_at=datetime.now(UTC),
        duration_min=_duration_for_kind(kind),
        kind=kind,
        completed=False,
    )
    session.add(pomo)
    await session.commit()
    await session.refresh(pomo)
    return pomo


async def stop(
    session: AsyncSession,
    user_id: UUID,
    session_id: UUID,
    completed: bool = False,
) -> PomodoroSession | None:
    """Остановить session. completed=True если timer истёк естественно,
    False если юзер нажал «стоп» досрочно."""
    pomo = (
        await session.execute(
            select(PomodoroSession).where(
                PomodoroSession.id == session_id,
                PomodoroSession.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if pomo is None:
        return None
    if pomo.ended_at is not None:
        return pomo  # уже остановлена, no-op
    pomo.ended_at = datetime.now(UTC)
    pomo.completed = completed
    await session.commit()
    await session.refresh(pomo)
    return pomo


async def time_on_task(session: AsyncSession, user_id: UUID, task_id: UUID) -> int:
    """Накопленное focus-время на задаче в минутах. Считаем фактические
    elapsed-минуты от started_at до ended_at (или now() если активна)."""
    rows = await session.execute(
        select(
            func.coalesce(
                func.sum(
                    func.extract(
                        "epoch",
                        func.coalesce(PomodoroSession.ended_at, func.now())
                        - PomodoroSession.started_at,
                    )
                ),
                0,
            )
        ).where(
            PomodoroSession.user_id == user_id,
            PomodoroSession.task_id == task_id,
            PomodoroSession.kind == "focus",
        )
    )
    seconds = float(rows.scalar_one() or 0)
    return int(seconds // 60)


async def count_focus_today(session: AsyncSession, user_id: UUID) -> int:
    """Сколько focus-сессий сегодня (для long-break suggestion после каждых 4)."""
    today = datetime.now(UTC).date()
    rows = await session.execute(
        select(func.count())
        .select_from(PomodoroSession)
        .where(
            PomodoroSession.user_id == user_id,
            PomodoroSession.kind == "focus",
            PomodoroSession.completed.is_(True),
            func.date(PomodoroSession.started_at) == today,
        )
    )
    return int(rows.scalar_one())


async def list_recent_for_task(
    session: AsyncSession, user_id: UUID, task_id: UUID, limit: int = 5
) -> list[PomodoroSession]:
    """Последние N сессий на задаче — для history-list в task-sheet."""
    rows = await session.execute(
        select(PomodoroSession)
        .where(
            PomodoroSession.user_id == user_id,
            PomodoroSession.task_id == task_id,
            PomodoroSession.kind == "focus",
        )
        .order_by(PomodoroSession.started_at.desc())
        .limit(limit)
    )
    return list(rows.scalars().all())
