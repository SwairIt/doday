"""HTMX-target endpoints — return HTML fragments rather than JSON."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select

from app.auth.deps import DbSession, RequiredUser
from app.labels.service import attach_label, find_or_create_by_name
from app.projects.models import Project
from app.quickadd.parser import parse_quick_add
from app.tasks.models import Task, TaskPriority
from app.tasks.service import (
    TaskNotFound,
    complete_task,
    create_task,
    get_task,
    list_subtasks,
    uncomplete_task,
    update_task,
)

router = APIRouter(prefix="/htmx", tags=["htmx"])
templates = Jinja2Templates(directory="app/templates")


async def _project_color_map(session: DbSession, user_id: UUID) -> dict[UUID, str]:
    rows = await session.execute(
        select(Project.id, Project.color).where(Project.user_id == user_id)
    )
    return {pid: color for pid, color in rows.all()}


def _row_response(request: Request, task: Task, project_color_map: dict[UUID, str]) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "_partials/task_row.html",
        {"task": task, "project_color_map": project_color_map},
    )


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

    return _row_response(request, task, await _project_color_map(session, user.id))


@router.delete("/tasks/{task_id}", response_class=HTMLResponse)
async def delete_task_endpoint(task_id: UUID, user: RequiredUser, session: DbSession) -> Response:
    from app.tasks.service import delete_task

    try:
        await delete_task(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    return HTMLResponse("", status_code=200)


@router.get("/tasks/{task_id}/row", response_class=HTMLResponse)
async def get_row(
    request: Request, task_id: UUID, user: RequiredUser, session: DbSession
) -> Response:
    """Return the read-only row HTML — used to cancel an inline edit."""
    try:
        task = await get_task(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    return _row_response(request, task, await _project_color_map(session, user.id))


@router.get("/tasks/{task_id}/edit", response_class=HTMLResponse)
async def edit_form(
    request: Request, task_id: UUID, user: RequiredUser, session: DbSession
) -> Response:
    try:
        task = await get_task(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    return templates.TemplateResponse(request, "_partials/task_row_edit.html", {"task": task})


@router.patch("/tasks/{task_id}", response_class=HTMLResponse)
async def edit_save(
    request: Request,
    task_id: UUID,
    user: RequiredUser,
    session: DbSession,
    title: Annotated[str, Form()],
    description: Annotated[str, Form()] = "",
    recurrence: Annotated[str, Form()] = "",
) -> Response:
    try:
        task = await get_task(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    task.title = title
    task.description = description if description else None
    task.recurrence = recurrence if recurrence in ("daily", "weekly", "monthly", "yearly") else None
    await session.commit()
    await session.refresh(task)
    return _row_response(request, task, await _project_color_map(session, user.id))


@router.post("/tasks/{task_id}/priority", response_class=HTMLResponse)
async def set_priority(
    request: Request,
    task_id: UUID,
    user: RequiredUser,
    session: DbSession,
    priority: Annotated[str, Form()],
) -> Response:
    """Inline-edit task priority. Form: priority=p1|p2|p3|p4."""
    try:
        prio = TaskPriority(priority)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "неизвестный приоритет") from e
    try:
        task = await update_task(session, user.id, task_id, priority=prio)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    return _row_response(request, task, await _project_color_map(session, user.id))


@router.post("/tasks/{task_id}/due", response_class=HTMLResponse)
async def set_due(
    request: Request,
    task_id: UUID,
    user: RequiredUser,
    session: DbSession,
    due: Annotated[str, Form()] = "",
) -> Response:
    """Inline-edit due date. Form: due=YYYY-MM-DD or empty to clear."""
    try:
        task = await get_task(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e

    if due:
        try:
            d = datetime.strptime(due, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "неверный формат даты") from e
        task.due_at = d
        task.due_date_only = True
    else:
        task.due_at = None
    await session.commit()
    await session.refresh(task)
    return _row_response(request, task, await _project_color_map(session, user.id))


@router.get("/tasks/{task_id}/subtasks", response_class=HTMLResponse)
async def subtasks_list(
    request: Request, task_id: UUID, user: RequiredUser, session: DbSession
) -> Response:
    """Return the subtasks block (rows + 'add subtask' inline form)."""
    try:
        await get_task(session, user.id, task_id)  # ownership check
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    subs = await list_subtasks(session, user.id, task_id)
    color_map = await _project_color_map(session, user.id)
    return templates.TemplateResponse(
        request,
        "_partials/subtasks.html",
        {"parent_id": task_id, "subtasks": subs, "project_color_map": color_map},
    )


@router.post("/tasks/{task_id}/subtasks", response_class=HTMLResponse)
async def create_subtask(
    request: Request,
    task_id: UUID,
    user: RequiredUser,
    session: DbSession,
    title: Annotated[str, Form()],
) -> Response:
    """Create a child task under task_id and return the new subtask row."""
    try:
        parent = await get_task(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    sub = await create_task(
        session,
        user.id,
        title=title.strip() or "(без названия)",
        project_id=parent.project_id,
        parent_task_id=parent.id,
    )
    color_map = await _project_color_map(session, user.id)
    return _row_response(request, sub, color_map)


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

    return _row_response(request, task, await _project_color_map(session, user.id))


@router.post("/bulk", response_class=HTMLResponse)
async def bulk_action(
    request: Request,
    user: RequiredUser,
    session: DbSession,
    action: Annotated[str, Form()],
    ids: Annotated[list[UUID], Form()],
) -> Response:
    """Apply an action to many tasks at once. action ∈ {complete, delete}."""
    from app.tasks.service import delete_task

    if not ids:
        return HTMLResponse("", status_code=200)

    if action == "complete":
        for tid in ids:
            try:
                await complete_task(session, user.id, tid)
            except TaskNotFound:
                pass  # silently skip — IDs from selection may include stale ones
    elif action == "delete":
        for tid in ids:
            try:
                await delete_task(session, user.id, tid)
            except TaskNotFound:
                pass
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown action: {action}")

    return HTMLResponse("", status_code=200, headers={"HX-Refresh": "true"})


@router.post("/sections", response_class=HTMLResponse)
async def create_section_inline(
    request: Request,
    user: RequiredUser,
    session: DbSession,
    project_id: Annotated[UUID, Form()],
    name: Annotated[str, Form()],
) -> Response:
    """Create a section inline from project view. Returns confirmation HTML."""
    from app.projects.service import ProjectNotFound
    from app.sections.service import create_section

    try:
        section = await create_section(session, user.id, project_id=project_id, name=name.strip())
    except ProjectNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "проект не найден") from e
    return HTMLResponse(
        f'<div class="text-xs text-emerald-400 px-3 py-1">Секция «{section.name}» создана</div>'
    )


@router.get("/tasks/{task_id}/labels-popover", response_class=HTMLResponse)
async def labels_popover(
    request: Request, task_id: UUID, user: RequiredUser, session: DbSession
) -> Response:
    """Return the label-picker popover: all user labels with checkboxes for current task."""
    from app.labels.service import list_labels, list_task_labels

    try:
        attached = await list_task_labels(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    all_labels = await list_labels(session, user.id)
    attached_ids = {lab.id for lab in attached}
    return templates.TemplateResponse(
        request,
        "_partials/labels_popover.html",
        {"task_id": task_id, "labels": all_labels, "attached_ids": attached_ids},
    )


@router.post("/tasks/{task_id}/labels/{label_id}/toggle", response_class=HTMLResponse)
async def toggle_label(
    request: Request,
    task_id: UUID,
    label_id: UUID,
    user: RequiredUser,
    session: DbSession,
) -> Response:
    """Attach or detach a label and return the refreshed task row."""
    from app.labels.service import (
        LabelNotFound,
        attach_label,
        detach_label,
        list_task_labels,
    )

    try:
        attached = await list_task_labels(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    is_attached = any(lab.id == label_id for lab in attached)
    try:
        if is_attached:
            await detach_label(session, user.id, task_id, label_id)
        else:
            await attach_label(session, user.id, task_id, label_id)
    except LabelNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "лейбл не найден") from e
    task = await get_task(session, user.id, task_id)
    return _row_response(request, task, await _project_color_map(session, user.id))


@router.post("/tasks/{task_id}/labels/new", response_class=HTMLResponse)
async def create_and_attach_label(
    request: Request,
    task_id: UUID,
    user: RequiredUser,
    session: DbSession,
    name: Annotated[str, Form()],
) -> Response:
    """Create a new label by name and attach it to the task."""
    from app.labels.service import attach_label, find_or_create_by_name

    try:
        label = await find_or_create_by_name(session, user.id, name.strip())
        await attach_label(session, user.id, task_id, label.id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    task = await get_task(session, user.id, task_id)
    return _row_response(request, task, await _project_color_map(session, user.id))


@router.get("/tasks/{task_id}/comments", response_class=HTMLResponse)
async def comments_block(
    request: Request, task_id: UUID, user: RequiredUser, session: DbSession
) -> Response:
    """Return the comments block (rows + add-comment form) for inline display."""
    from app.comments.service import list_comments

    try:
        comments = await list_comments(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    return templates.TemplateResponse(
        request,
        "_partials/comments_block.html",
        {"task_id": task_id, "comments": comments},
    )


@router.post("/tasks/{task_id}/comments", response_class=HTMLResponse)
async def comment_create(
    request: Request,
    task_id: UUID,
    user: RequiredUser,
    session: DbSession,
    body: Annotated[str, Form()],
) -> Response:
    """Add a comment and return the refreshed comments block."""
    from app.comments.service import create_comment, list_comments

    try:
        await create_comment(session, user.id, task_id=task_id, body=body.strip())
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    comments = await list_comments(session, user.id, task_id)
    return templates.TemplateResponse(
        request,
        "_partials/comments_block.html",
        {"task_id": task_id, "comments": comments},
    )


@router.delete("/comments/{comment_id}", response_class=HTMLResponse)
async def comment_delete(comment_id: UUID, user: RequiredUser, session: DbSession) -> Response:
    from app.comments.service import CommentNotFound, delete_comment

    try:
        await delete_comment(session, user.id, comment_id)
    except CommentNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "комментарий не найден") from e
    return HTMLResponse("", status_code=200)


@router.get("/search", response_class=HTMLResponse)
async def search_endpoint(
    request: Request, user: RequiredUser, session: DbSession, q: str = ""
) -> Response:
    """Live search across task titles + descriptions + project names. Case-insensitive ILIKE."""
    q = q.strip()
    if len(q) < 2:
        return templates.TemplateResponse(
            request, "_partials/search_results.html", {"q": q, "tasks": [], "projects": []}
        )

    # Use lower() on both sides — Postgres ILIKE only lowercases ASCII in C locale,
    # which breaks Cyrillic case-insensitive matching.
    pattern = f"%{q.lower()}%"
    task_rows = await session.execute(
        select(Task)
        .where(
            Task.user_id == user.id,
            or_(
                func.lower(Task.title).like(pattern),
                func.lower(Task.description).like(pattern),
            ),
        )
        .order_by(Task.is_completed, Task.created_at.desc())
        .limit(15)
    )
    tasks = list(task_rows.scalars().all())

    project_rows = await session.execute(
        select(Project)
        .where(Project.user_id == user.id, func.lower(Project.name).like(pattern))
        .order_by(Project.position)
        .limit(8)
    )
    projects = list(project_rows.scalars().all())

    color_map = await _project_color_map(session, user.id)

    return templates.TemplateResponse(
        request,
        "_partials/search_results.html",
        {"q": q, "tasks": tasks, "projects": projects, "project_color_map": color_map},
    )
