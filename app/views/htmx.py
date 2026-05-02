"""HTMX-target endpoints — return HTML fragments rather than JSON."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from app.auth.deps import DbSession, RequiredUser
from app.tasks.service import (
    TaskNotFound,
    complete_task,
    get_task,
    uncomplete_task,
)

router = APIRouter(prefix="/htmx", tags=["htmx"])
templates = Jinja2Templates(directory="app/templates")


@router.post("/tasks/{task_id}/toggle", response_class=HTMLResponse)
async def toggle_task(
    request: Request, task_id: UUID, user: RequiredUser, session: DbSession
) -> Response:
    """Flip is_completed and re-render the row.

    On Today/Upcoming views the completed row should fall out — return
    an empty body for those views by checking HX-Trigger-Name; for now
    we always return the updated row, the caller decides via hx-swap.
    """
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
