"""Task HTTP endpoints — JSON CRUD + complete/uncomplete + reorder."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from app.auth.deps import DbSession, RequiredUser
from app.projects.service import ProjectNotFound
from app.sections.service import SectionNotFound
from app.tasks.schemas import TaskCreate, TaskOut, TaskReorder, TaskUpdate
from app.tasks.service import (
    TaskNotFound,
    complete_task,
    create_task,
    delete_task,
    duplicate_task,
    get_task,
    list_tasks,
    list_today,
    list_upcoming,
    reorder_tasks,
    uncomplete_task,
    update_task,
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


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


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_endpoint(payload: TaskCreate, user: RequiredUser, session: DbSession) -> TaskOut:
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
            func.coalesce(
                func.sum(case((Task.is_completed.is_(True), 1), else_=0)), 0
            ).label("done"),
        )
        .select_from(Task)
        .where(Task.user_id == user.id, Task.parent_task_id == task_id)
    )
    r = row.first()
    return {"total": int(r.total or 0), "done": int(r.done or 0)}


@router.post("/{task_id}/duplicate", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def duplicate_endpoint(task_id: UUID, user: RequiredUser, session: DbSession) -> TaskOut:
    try:
        new = await duplicate_task(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    return TaskOut.model_validate(new)


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
