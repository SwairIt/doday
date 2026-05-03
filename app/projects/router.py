"""Project HTTP endpoints — JSON CRUD."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.auth.deps import DbSession, RequiredUser
from app.projects.schemas import ProjectCreate, ProjectOut, ProjectUpdate
from app.projects.service import (
    CannotDeleteInbox,
    ProjectNotFound,
    create_from_template,
    create_project,
    delete_project,
    list_projects,
    update_project,
)
from app.projects.templates_data import TEMPLATES, get_template


class ProjectTemplateOut(BaseModel):
    key: str
    name: str
    icon: str
    color: str
    description: str
    sections_count: int
    tasks_count: int


class FromTemplatePayload(BaseModel):
    template_key: str = Field(min_length=1)
    name: str | None = Field(default=None, max_length=120)


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


@router.get("/templates", response_model=list[ProjectTemplateOut])
async def list_templates(_: RequiredUser) -> list[ProjectTemplateOut]:
    return [
        ProjectTemplateOut(
            key=t["key"],
            name=t["name"],
            icon=t["icon"],
            color=t["color"],
            description=t["description"],
            sections_count=len(t["sections"]),
            tasks_count=sum(len(s["tasks"]) for s in t["sections"]) + len(t["loose_tasks"]),
        )
        for t in TEMPLATES
    ]


@router.post("/from-template", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_from_template_endpoint(
    payload: FromTemplatePayload, user: RequiredUser, session: DbSession
) -> ProjectOut:
    template = get_template(payload.template_key)
    if template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "шаблон не найден")
    project = await create_from_template(session, user.id, template, name=payload.name)
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
