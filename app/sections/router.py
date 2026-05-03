"""Section HTTP endpoints — JSON CRUD."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from app.auth.deps import DbSession, RequiredUser
from app.projects.service import ProjectNotFound
from app.sections.schemas import SectionCreate, SectionOut, SectionReorder, SectionUpdate
from app.sections.service import (
    SectionNotFound,
    create_section,
    delete_section,
    list_sections,
    reorder_sections,
    update_section,
)

router = APIRouter(prefix="/api/sections", tags=["sections"])


@router.get("", response_model=list[SectionOut])
async def list_endpoint(
    project_id: UUID, user: RequiredUser, session: DbSession
) -> list[SectionOut]:
    try:
        sections = await list_sections(session, user.id, project_id)
    except ProjectNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "проект не найден") from e
    return [SectionOut.model_validate(s) for s in sections]


@router.post("", response_model=SectionOut, status_code=status.HTTP_201_CREATED)
async def create_endpoint(
    payload: SectionCreate, user: RequiredUser, session: DbSession
) -> SectionOut:
    try:
        section = await create_section(
            session, user.id, project_id=payload.project_id, name=payload.name
        )
    except ProjectNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "проект не найден") from e
    return SectionOut.model_validate(section)


@router.patch("/{section_id}", response_model=SectionOut)
async def update_endpoint(
    section_id: UUID,
    payload: SectionUpdate,
    user: RequiredUser,
    session: DbSession,
) -> SectionOut:
    try:
        section = await update_section(session, user.id, section_id, name=payload.name)
    except SectionNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "секция не найдена") from e
    return SectionOut.model_validate(section)


@router.delete("/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_endpoint(section_id: UUID, user: RequiredUser, session: DbSession) -> Response:
    try:
        await delete_section(session, user.id, section_id)
    except SectionNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "секция не найдена") from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reorder", response_model=list[SectionOut])
async def reorder_endpoint(
    payload: SectionReorder, user: RequiredUser, session: DbSession
) -> list[SectionOut]:
    try:
        sections = await reorder_sections(session, user.id, payload.project_id, payload.ids)
    except ProjectNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "проект не найден") from e
    except SectionNotFound as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return [SectionOut.model_validate(s) for s in sections]
