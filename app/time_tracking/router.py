"""HTTP routes for time tracking — start/stop a per-task timer."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.auth.deps import DbSession, RequiredUser
from app.tasks.service import TaskNotFound
from app.time_tracking.service import (
    TimerNotRunning,
    get_running_for_user,
    start_timer,
    stop_timer,
    total_seconds_for_task,
    total_seconds_today,
)

router = APIRouter(prefix="/api/time", tags=["time"])


@router.post("/tasks/{task_id}/start")
async def start_endpoint(
    task_id: UUID, user: RequiredUser, session: DbSession
) -> dict[str, object]:
    try:
        entry = await start_timer(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    return {
        "id": str(entry.id),
        "task_id": str(entry.task_id),
        "started_at": entry.started_at.isoformat(),
    }


@router.post("/tasks/{task_id}/stop")
async def stop_endpoint(task_id: UUID, user: RequiredUser, session: DbSession) -> dict[str, object]:
    try:
        entry = await stop_timer(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    except TimerNotRunning as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "таймер не запущен") from e
    total = await total_seconds_for_task(session, user.id, task_id)
    return {
        "id": str(entry.id),
        "task_id": str(entry.task_id),
        "duration_seconds": entry.duration_seconds or 0,
        "task_total_seconds": total,
    }


@router.get("/tasks/{task_id}")
async def task_total_endpoint(
    task_id: UUID, user: RequiredUser, session: DbSession
) -> dict[str, object]:
    try:
        total = await total_seconds_for_task(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    running = await get_running_for_user(session, user.id)
    is_running_here = bool(running and running.task_id == task_id)
    return {
        "task_id": str(task_id),
        "total_seconds": total,
        "running": is_running_here,
        "running_started_at": (
            running.started_at.isoformat() if is_running_here and running else None
        ),
    }


@router.get("/today")
async def today_endpoint(user: RequiredUser, session: DbSession) -> dict[str, object]:
    seconds = await total_seconds_today(session, user.id)
    running = await get_running_for_user(session, user.id)
    return {
        "total_seconds": seconds,
        "running_task_id": str(running.task_id) if running else None,
        "running_started_at": running.started_at.isoformat() if running else None,
    }
