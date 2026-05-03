"""Comment HTTP endpoints — JSON CRUD attached to tasks."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from app.auth.deps import DbSession, RequiredUser
from app.comments.schemas import CommentCreate, CommentOut, CommentUpdate
from app.comments.service import (
    CommentNotFound,
    create_comment,
    delete_comment,
    list_comments,
    update_comment,
)
from app.tasks.service import TaskNotFound

task_comments_router = APIRouter(prefix="/api/tasks/{task_id}/comments", tags=["comments"])


@task_comments_router.get("", response_model=list[CommentOut])
async def list_endpoint(task_id: UUID, user: RequiredUser, session: DbSession) -> list[CommentOut]:
    try:
        comments = await list_comments(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    return [CommentOut.model_validate(c) for c in comments]


@task_comments_router.post("", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
async def create_endpoint(
    task_id: UUID, payload: CommentCreate, user: RequiredUser, session: DbSession
) -> CommentOut:
    try:
        comment = await create_comment(session, user.id, task_id=task_id, body=payload.body)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    return CommentOut.model_validate(comment)


comments_router = APIRouter(prefix="/api/comments", tags=["comments"])


@comments_router.patch("/{comment_id}", response_model=CommentOut)
async def update_endpoint(
    comment_id: UUID, payload: CommentUpdate, user: RequiredUser, session: DbSession
) -> CommentOut:
    try:
        comment = await update_comment(session, user.id, comment_id, body=payload.body)
    except CommentNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "комментарий не найден") from e
    return CommentOut.model_validate(comment)


@comments_router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_endpoint(comment_id: UUID, user: RequiredUser, session: DbSession) -> Response:
    try:
        await delete_comment(session, user.id, comment_id)
    except CommentNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "комментарий не найден") from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)
