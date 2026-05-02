"""Label HTTP endpoints — JSON CRUD plus attach/detach."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from app.auth.deps import DbSession, RequiredUser
from app.labels.schemas import LabelCreate, LabelOut, LabelUpdate
from app.labels.service import (
    LabelNotFound,
    attach_label,
    create_label,
    delete_label,
    detach_label,
    list_labels,
    list_task_labels,
    update_label,
)
from app.tasks.service import TaskNotFound

router = APIRouter(prefix="/api/labels", tags=["labels"])


@router.get("", response_model=list[LabelOut])
async def list_endpoint(user: RequiredUser, session: DbSession) -> list[LabelOut]:
    return [LabelOut.model_validate(lab) for lab in await list_labels(session, user.id)]


@router.post("", response_model=LabelOut, status_code=status.HTTP_201_CREATED)
async def create_endpoint(payload: LabelCreate, user: RequiredUser, session: DbSession) -> LabelOut:
    label = await create_label(session, user.id, name=payload.name, color=payload.color)
    return LabelOut.model_validate(label)


@router.patch("/{label_id}", response_model=LabelOut)
async def update_endpoint(
    label_id: UUID, payload: LabelUpdate, user: RequiredUser, session: DbSession
) -> LabelOut:
    try:
        label = await update_label(
            session, user.id, label_id, name=payload.name, color=payload.color
        )
    except LabelNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "лейбл не найден") from e
    return LabelOut.model_validate(label)


@router.delete("/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_endpoint(label_id: UUID, user: RequiredUser, session: DbSession) -> Response:
    try:
        await delete_label(session, user.id, label_id)
    except LabelNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "лейбл не найден") from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)


task_labels_router = APIRouter(prefix="/api/tasks/{task_id}/labels", tags=["labels"])


@task_labels_router.get("", response_model=list[LabelOut])
async def list_for_task(task_id: UUID, user: RequiredUser, session: DbSession) -> list[LabelOut]:
    try:
        labels = await list_task_labels(session, user.id, task_id)
    except TaskNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "задача не найдена") from e
    return [LabelOut.model_validate(lab) for lab in labels]


@task_labels_router.post("/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
async def attach_endpoint(
    task_id: UUID, label_id: UUID, user: RequiredUser, session: DbSession
) -> Response:
    try:
        await attach_label(session, user.id, task_id, label_id)
    except (TaskNotFound, LabelNotFound) as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "не найдено") from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@task_labels_router.delete("/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
async def detach_endpoint(
    task_id: UUID, label_id: UUID, user: RequiredUser, session: DbSession
) -> Response:
    try:
        await detach_label(session, user.id, task_id, label_id)
    except (TaskNotFound, LabelNotFound) as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "не найдено") from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)
