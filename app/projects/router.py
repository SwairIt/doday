"""Project HTTP endpoints — JSON CRUD."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from app.auth.deps import DbSession, RequiredUser
from app.projects.schemas import ProjectCreate, ProjectOut, ProjectUpdate
from app.projects.service import (
    CannotDeleteInbox,
    ProjectNotFound,
    create_project,
    delete_project,
    list_projects,
    update_project,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
async def list_endpoint(user: RequiredUser, session: DbSession) -> list[ProjectOut]:
    projects = await list_projects(session, user.id)
    return [ProjectOut.model_validate(p) for p in projects]


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_endpoint(
    payload: ProjectCreate, user: RequiredUser, session: DbSession
) -> ProjectOut:
    project = await create_project(session, user.id, name=payload.name, color=payload.color)
    return ProjectOut.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_endpoint(
    project_id: UUID,
    payload: ProjectUpdate,
    user: RequiredUser,
    session: DbSession,
) -> ProjectOut:
    try:
        project = await update_project(
            session,
            user.id,
            project_id,
            name=payload.name,
            color=payload.color,
            is_archived=payload.is_archived,
        )
    except ProjectNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "проект не найден") from e
    return ProjectOut.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_endpoint(project_id: UUID, user: RequiredUser, session: DbSession) -> Response:
    try:
        await delete_project(session, user.id, project_id)
    except ProjectNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "проект не найден") from e
    except CannotDeleteInbox as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Inbox удалить нельзя") from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)
