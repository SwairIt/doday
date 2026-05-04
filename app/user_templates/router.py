"""User-template HTTP endpoints — list, save-from-project, instantiate, delete."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from app.auth.deps import DbSession, RequiredUser
from app.projects.schemas import ProjectOut
from app.projects.service import ProjectNotFound
from app.user_templates.service import (
    UserTemplateNotFound,
    delete_user_template,
    instantiate_user_template,
    list_user_templates,
    save_project_as_template,
)


class UserTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    color: str
    description: str | None
    payload: dict[str, object]
    created_at: datetime
    updated_at: datetime


class SaveAsTemplatePayload(BaseModel):
    name: str | None = Field(default=None, max_length=120)


class InstantiatePayload(BaseModel):
    name: str | None = Field(default=None, max_length=120)


router = APIRouter(prefix="/api/user-templates", tags=["user-templates"])


@router.get("", response_model=list[UserTemplateOut])
async def list_endpoint(user: RequiredUser, session: DbSession) -> list[UserTemplateOut]:
    items = await list_user_templates(session, user.id)
    return [UserTemplateOut.model_validate(t) for t in items]


@router.post(
    "/{template_id}/instantiate",
    response_model=ProjectOut,
    status_code=status.HTTP_201_CREATED,
)
async def instantiate_endpoint(
    template_id: UUID,
    payload: InstantiatePayload,
    user: RequiredUser,
    session: DbSession,
) -> ProjectOut:
    try:
        project = await instantiate_user_template(session, user.id, template_id, name=payload.name)
    except UserTemplateNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "шаблон не найден") from e
    return ProjectOut.model_validate(project)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_endpoint(template_id: UUID, user: RequiredUser, session: DbSession) -> Response:
    try:
        await delete_user_template(session, user.id, template_id)
    except UserTemplateNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "шаблон не найден") from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Save-as endpoint lives under /api/projects/{id}/save-as-template for discoverability,
# but the implementation is here to keep the user-template logic self-contained.
save_router = APIRouter(prefix="/api/projects", tags=["user-templates"])


@save_router.post(
    "/{project_id}/save-as-template",
    response_model=UserTemplateOut,
    status_code=status.HTTP_201_CREATED,
)
async def save_as_endpoint(
    project_id: UUID,
    payload: SaveAsTemplatePayload,
    user: RequiredUser,
    session: DbSession,
) -> UserTemplateOut:
    try:
        obj = await save_project_as_template(session, user.id, project_id, name=payload.name)
    except ProjectNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "проект не найден") from e
    return UserTemplateOut.model_validate(obj)
