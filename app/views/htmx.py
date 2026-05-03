"""HTMX-target endpoints — return HTML fragments rather than JSON."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.auth.deps import DbSession, RequiredUser
from app.labels.service import attach_label, find_or_create_by_name
from app.projects.models import Project
from app.quickadd.parser import parse_quick_add
from app.tasks.service import (
    TaskNotFound,
    complete_task,
    create_task,
    get_task,
    uncomplete_task,
)

router = APIRouter(prefix="/htmx", tags=["htmx"])
templates = Jinja2Templates(directory="app/templates")


@router.post("/tasks/{task_id}/toggle", response_class=HTMLResponse)
async def toggle_task(
    request: Request, task_id: UUID, user: RequiredUser, session: DbSession
) -> Response:
    try:
        task = await get_task(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e

    if task.is_completed:
        task = await uncomplete_task(session, user.id, task_id)
    else:
        task = await complete_task(session, user.id, task_id)

    return templates.TemplateResponse(
        request,
        "_partials/task_row.html",
        {"task": task, "project_color_map": {}},
    )


@router.delete("/tasks/{task_id}", response_class=HTMLResponse)
async def delete_task_endpoint(task_id: UUID, user: RequiredUser, session: DbSession) -> Response:
    from app.tasks.service import delete_task

    try:
        await delete_task(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    return HTMLResponse("", status_code=200)


@router.post("/quickadd", response_class=HTMLResponse)
async def quickadd_endpoint(
    request: Request,
    user: RequiredUser,
    session: DbSession,
    text: Annotated[str, Form()],
    project_id: Annotated[UUID | None, Form()] = None,
) -> Response:
    """Parse a free-form quick-add string, create the task, attach labels."""
    parsed = parse_quick_add(text)

    target_project_id = project_id
    if parsed.project_name and target_project_id is None:
        result = await session.execute(
            select(Project).where(
                Project.user_id == user.id,
                (
                    (Project.slug == parsed.project_name.lower())
                    | (Project.name == parsed.project_name)
                ),
            )
        )
        match = result.scalar_one_or_none()
        if match is not None:
            target_project_id = match.id

    task = await create_task(
        session,
        user.id,
        title=parsed.title,
        project_id=target_project_id,
        due_at=parsed.due_at,
        priority=parsed.priority,
    )

    for label_name in parsed.label_names:
        label = await find_or_create_by_name(session, user.id, label_name)
        await attach_label(session, user.id, task.id, label.id)

    color_result = await session.execute(
        select(Project.id, Project.color).where(Project.user_id == user.id)
    )
    project_color_map: dict[UUID, str] = {pid: color for pid, color in color_result.all()}

    return templates.TemplateResponse(
        request,
        "_partials/task_row.html",
        {"task": task, "project_color_map": project_color_map},
    )
