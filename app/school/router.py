"""HTTP routes for managing school portal integrations."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, status
from pydantic import ValidationError

from app.auth.deps import DbSession, RequiredUser
from app.school.schedule_service import (
    delete_slot,
    list_slots,
    upsert_slot,
)
from app.school.schemas import IntegrationIn, IntegrationOut, Provider, SyncResult
from app.school.service import (
    IntegrationNotFound,
    delete_integration,
    list_integrations,
    sync_now,
    upsert_integration,
)
from app.school.subjects import get_subject

router = APIRouter(prefix="/api/school", tags=["school"])


@router.get("/integrations", response_model=list[IntegrationOut])
async def list_endpoint(user: RequiredUser, session: DbSession) -> list[IntegrationOut]:
    integrations = await list_integrations(session, user.id)
    return [IntegrationOut.model_validate(i) for i in integrations]


@router.post("/integrations", response_model=IntegrationOut)
async def upsert_endpoint(
    user: RequiredUser,
    session: DbSession,
    provider: Annotated[str, Form()],
    auth_token: Annotated[str, Form()],
    target_project_id: Annotated[str | None, Form()] = None,
    enabled: Annotated[bool, Form()] = True,
) -> IntegrationOut:
    if provider not in ("school_mo", "mesh"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "неизвестный провайдер")
    target = UUID(target_project_id) if target_project_id else None
    try:
        payload = IntegrationIn(
            provider=provider,  # type: ignore[arg-type]
            auth_token=auth_token,
            target_project_id=target,
            enabled=enabled,
        )
    except ValidationError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e
    saved = await upsert_integration(session, user.id, payload)
    return IntegrationOut.model_validate(saved)


@router.delete("/integrations/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_endpoint(provider: Provider, user: RequiredUser, session: DbSession) -> None:
    try:
        await delete_integration(session, user.id, provider)
    except IntegrationNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "интеграция не найдена") from e


@router.post("/integrations/{provider}/sync", response_model=SyncResult)
async def sync_endpoint(provider: Provider, user: RequiredUser, session: DbSession) -> SyncResult:
    try:
        return await sync_now(session, user.id, provider)
    except IntegrationNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "интеграция не найдена") from e


@router.get("/schedule")
async def schedule_list(user: RequiredUser, session: DbSession) -> list[dict[str, object]]:
    slots = await list_slots(session, user.id)
    return [
        {
            "id": str(s.id),
            "weekday": s.weekday,
            "period": s.period,
            "subject_code": s.subject_code,
            "room": s.room,
            "teacher": s.teacher,
        }
        for s in slots
    ]


@router.post("/schedule")
async def schedule_upsert(
    user: RequiredUser,
    session: DbSession,
    weekday: Annotated[int, Form()],
    period: Annotated[int, Form()],
    subject_code: Annotated[str, Form()],
    room: Annotated[str | None, Form()] = None,
    teacher: Annotated[str | None, Form()] = None,
) -> dict[str, object]:
    if get_subject(subject_code) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "неизвестный предмет")
    try:
        slot = await upsert_slot(
            session,
            user.id,
            weekday=weekday,
            period=period,
            subject_code=subject_code,
            room=room or None,
            teacher=teacher or None,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e
    return {
        "id": str(slot.id),
        "weekday": slot.weekday,
        "period": slot.period,
        "subject_code": slot.subject_code,
        "room": slot.room,
        "teacher": slot.teacher,
    }


@router.delete("/schedule/{weekday}/{period}", status_code=status.HTTP_204_NO_CONTENT)
async def schedule_delete(
    weekday: int, period: int, user: RequiredUser, session: DbSession
) -> None:
    await delete_slot(session, user.id, weekday=weekday, period=period)
