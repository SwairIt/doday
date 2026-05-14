"""Task HTTP endpoints — JSON CRUD + complete/uncomplete + reorder + CSV export."""

import csv
import io
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from app.auth.deps import DbSession, RequiredUser
from app.projects.service import ProjectNotFound
from app.sections.service import SectionNotFound
from app.tasks.schemas import TaskBulkCreate, TaskCreate, TaskOut, TaskReorder, TaskUpdate
from app.tasks.service import (
    _SENTINEL,
    TaskNotFound,
    complete_task,
    create_task,
    delete_task,
    duplicate_task,
    get_task,
    list_tasks,
    list_today,
    list_trash,
    list_upcoming,
    pin_task,
    purge_task,
    reorder_tasks,
    restore_task,
    uncomplete_task,
    unpin_task,
    update_task,
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/export.csv", response_class=Response)
async def export_csv(
    user: RequiredUser, session: DbSession, include_completed: bool = False
) -> Response:
    """Stream all (or only active) tasks as CSV — for spreadsheet processing."""
    from sqlalchemy import select as sa_select

    from app.projects.models import Project as ProjectModel

    project_rows = (
        (await session.execute(sa_select(ProjectModel).where(ProjectModel.user_id == user.id)))
        .scalars()
        .all()
    )
    project_name: dict[UUID, str] = {p.id: p.name for p in project_rows}

    tasks = await list_tasks(session, user.id, include_completed=include_completed)

    buf = io.StringIO()
    writer = csv.writer(buf, dialect="excel")
    writer.writerow(
        [
            "id",
            "title",
            "project",
            "due_at",
            "priority",
            "is_completed",
            "completed_at",
            "recurrence",
            "labels",
            "description",
            "created_at",
        ]
    )
    for t in tasks:
        writer.writerow(
            [
                str(t.id),
                t.title,
                project_name.get(t.project_id, ""),
                t.due_at.isoformat() if t.due_at else "",
                t.priority.value,
                "1" if t.is_completed else "0",
                t.completed_at.isoformat() if t.completed_at else "",
                t.recurrence or "",
                " ".join(f"@{lab.name}" for lab in t.labels),
                (t.description or "").replace("\r", " ").replace("\n", " "),
                t.created_at.isoformat(),
            ]
        )

    body = "﻿" + buf.getvalue()  # BOM so Excel reads UTF-8 correctly
    return Response(
        content=body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="doday-tasks.csv"'},
    )


@router.get("", response_model=list[TaskOut])
async def list_endpoint(
    user: RequiredUser,
    session: DbSession,
    project_id: UUID | None = None,
    include_completed: bool = False,
) -> list[TaskOut]:
    tasks = await list_tasks(
        session, user.id, project_id=project_id, include_completed=include_completed
    )
    return [TaskOut.model_validate(t) for t in tasks]


@router.get("/today", response_model=list[TaskOut])
async def today_endpoint(user: RequiredUser, session: DbSession) -> list[TaskOut]:
    return [TaskOut.model_validate(t) for t in await list_today(session, user.id)]


@router.get("/upcoming", response_model=list[TaskOut])
async def upcoming_endpoint(user: RequiredUser, session: DbSession, days: int = 7) -> list[TaskOut]:
    return [TaskOut.model_validate(t) for t in await list_upcoming(session, user.id, days=days)]


@router.post("/bulk", response_model=list[TaskOut], status_code=status.HTTP_201_CREATED)
async def bulk_create_endpoint(
    payload: TaskBulkCreate, user: RequiredUser, session: DbSession
) -> list[TaskOut]:
    """Create many tasks in one go — used by quickadd's paste-multiple-lines flow.

    Empty / whitespace-only lines are silently dropped. Each surviving line
    becomes a top-level task in the chosen project (or Inbox if none).
    """
    from app.billing.service import can_create_task, can_paste_n_lines, limits_for

    cleaned = [t.strip() for t in payload.titles if t and t.strip()]
    if not cleaned:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "пустой список задач")

    if not can_paste_n_lines(user, len(cleaned)):
        cap = limits_for(user)["max_bulk_paste_lines"]
        raise HTTPException(
            402,
            {
                "code": "limit_reached",
                "feature": "bulk_paste",
                "limit": cap,
                "tier": "free",
                "message": f"Вставка более {cap} строк за раз — на Pro. Сейчас можно до {cap}.",
            },
        )
    allowed, reason = await can_create_task(session, user)
    if not allowed:
        raise HTTPException(
            402,
            {"code": "limit_reached", "feature": "tasks", "tier": "free", "message": reason},
        )

    out: list[TaskOut] = []
    try:
        for title in cleaned:
            task = await create_task(
                session,
                user.id,
                title=title[:500],
                project_id=payload.project_id,
                due_at=payload.common_due_at,
                priority=payload.common_priority,
            )
            out.append(TaskOut.model_validate(task))
    except ProjectNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "проект не найден") from e
    return out


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_endpoint(payload: TaskCreate, user: RequiredUser, session: DbSession) -> TaskOut:
    from app.billing.service import can_create_task

    # Subtasks don't count against the limit (they're sub-units of a parent task).
    if payload.parent_task_id is None:
        allowed, reason = await can_create_task(session, user)
        if not allowed:
            raise HTTPException(
                402,
                {
                    "code": "limit_reached",
                    "feature": "tasks",
                    "tier": "free",
                    "message": reason,
                },
            )

    try:
        task = await create_task(
            session,
            user.id,
            title=payload.title,
            project_id=payload.project_id,
            parent_task_id=payload.parent_task_id,
            section_id=payload.section_id,
            description=payload.description,
            due_at=payload.due_at,
            due_date_only=payload.due_date_only,
            priority=payload.priority,
            recurrence=payload.recurrence,
        )
    except ProjectNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "проект не найден") from e
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "родительская задача не найдена") from e
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return TaskOut.model_validate(task)


@router.patch("/{task_id}", response_model=TaskOut)
async def update_endpoint(
    task_id: UUID, payload: TaskUpdate, user: RequiredUser, session: DbSession
) -> TaskOut:
    section_was_set = "section_id" in payload.model_fields_set
    assigned_to_was_set = "assigned_to" in payload.model_fields_set
    try:
        task = await update_task(
            session,
            user.id,
            task_id,
            title=payload.title,
            description=payload.description,
            due_at=payload.due_at,
            due_date_only=payload.due_date_only,
            priority=payload.priority,
            project_id=payload.project_id,
            parent_task_id=payload.parent_task_id,
            section_id=payload.section_id if section_was_set else None,
            clear_section=section_was_set and payload.section_id is None,
            assigned_to=payload.assigned_to if assigned_to_was_set else _SENTINEL,
        )
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    except ProjectNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "проект не найден") from e
    except SectionNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "секция не найдена") from e
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return TaskOut.model_validate(task)


@router.post("/{task_id}/complete", response_model=TaskOut)
async def complete_endpoint(task_id: UUID, user: RequiredUser, session: DbSession) -> TaskOut:
    try:
        task = await complete_task(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    return TaskOut.model_validate(task)


@router.get("/{task_id}/subtask-stats", response_model=dict[str, int])
async def subtask_stats_endpoint(
    task_id: UUID, user: RequiredUser, session: DbSession
) -> dict[str, int]:
    """{total, done} for direct children of this task — used by progress badges."""
    from sqlalchemy import case, func, select

    from app.tasks.models import Task

    try:
        await get_task(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    row = await session.execute(
        select(
            func.count().label("total"),
            func.coalesce(func.sum(case((Task.is_completed.is_(True), 1), else_=0)), 0).label(
                "done"
            ),
        )
        .select_from(Task)
        .where(Task.user_id == user.id, Task.parent_task_id == task_id)
    )
    r = row.first()
    if r is None:
        return {"total": 0, "done": 0}
    return {"total": int(r.total or 0), "done": int(r.done or 0)}


@router.post("/{task_id}/duplicate", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def duplicate_endpoint(task_id: UUID, user: RequiredUser, session: DbSession) -> TaskOut:
    try:
        new = await duplicate_task(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    return TaskOut.model_validate(new)


@router.post("/{task_id}/pin", response_model=TaskOut)
async def pin_endpoint(task_id: UUID, user: RequiredUser, session: DbSession) -> TaskOut:
    try:
        task = await pin_task(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    return TaskOut.model_validate(task)


@router.delete("/{task_id}/pin", response_model=TaskOut)
async def unpin_endpoint(task_id: UUID, user: RequiredUser, session: DbSession) -> TaskOut:
    try:
        task = await unpin_task(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    return TaskOut.model_validate(task)


@router.get("/trash", response_model=list[TaskOut])
async def trash_endpoint(user: RequiredUser, session: DbSession) -> list[TaskOut]:
    """Soft-deleted tasks newer than tier-specific window (Free: 14, Pro: 30).
    Older are purged on access."""
    from app.billing.service import limits_for

    rows = await list_trash(session, user.id, max_age_days=limits_for(user)["trash_retention_days"])
    return [TaskOut.model_validate(t) for t in rows]


@router.post("/{task_id}/restore", response_model=TaskOut)
async def restore_endpoint(task_id: UUID, user: RequiredUser, session: DbSession) -> TaskOut:
    try:
        task = await restore_task(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    return TaskOut.model_validate(task)


@router.delete("/{task_id}/purge", status_code=status.HTTP_204_NO_CONTENT)
async def purge_endpoint(task_id: UUID, user: RequiredUser, session: DbSession) -> None:
    """Hard-delete a task permanently (typically already in trash)."""
    try:
        await purge_task(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e


@router.post("/{task_id}/uncomplete", response_model=TaskOut)
async def uncomplete_endpoint(task_id: UUID, user: RequiredUser, session: DbSession) -> TaskOut:
    try:
        task = await uncomplete_task(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    return TaskOut.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_endpoint(task_id: UUID, user: RequiredUser, session: DbSession) -> Response:
    try:
        await delete_task(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)


reorder_router = APIRouter(prefix="/api/projects/{project_id}/tasks", tags=["tasks"])


@reorder_router.post("/reorder", response_model=list[TaskOut])
async def reorder_endpoint(
    project_id: UUID,
    payload: TaskReorder,
    user: RequiredUser,
    session: DbSession,
) -> list[TaskOut]:
    try:
        tasks = await reorder_tasks(session, user.id, project_id, payload.ids)
    except ProjectNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "проект не найден") from e
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return [TaskOut.model_validate(t) for t in tasks]
