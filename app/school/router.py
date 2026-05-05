"""HTTP routes for managing school portal integrations."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Form, HTTPException, status
from pydantic import ValidationError

from app.auth.deps import DbSession, RequiredUser
from app.school.holidays import current_holiday, next_holiday
from app.school.schedule_service import (
    delete_slot,
    list_slots,
    upsert_slot,
)
from app.school.schemas import IntegrationIn, IntegrationOut, Provider, SyncResult
from app.school.service import (
    IntegrationNotFound,
    delete_integration,
    import_pasted_payload,
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


@router.post("/integrations/{provider}/import", response_model=SyncResult)
async def import_endpoint(
    provider: Provider,
    user: RequiredUser,
    session: DbSession,
    payload: Annotated[object, Body(...)],
) -> SyncResult:
    """Manual paste-import: when the portal is unreachable from the server but
    visible from the user's browser. User pastes the raw API response JSON."""
    try:
        return await import_pasted_payload(session, user.id, provider, payload)
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


@router.get("/holiday")
async def holiday_endpoint(user: RequiredUser) -> dict[str, object]:
    """Return today's holiday window (if any) and the next upcoming one."""
    from app.school.holidays import HolidayWindow

    _ = user  # auth-gate only
    today = datetime.now(UTC).date()
    cur = current_holiday(today)
    nxt = next_holiday(today)

    def _serialize(h: HolidayWindow | None) -> dict[str, str] | None:
        if h is None:
            return None
        return {
            "name": h["name"],
            "start": h["start"].isoformat(),
            "end": h["end"].isoformat(),
        }

    days_until = (nxt["start"] - today).days if nxt else None
    days_left = (cur["end"] - today).days if cur else None
    return {
        "current": _serialize(cur),
        "next": _serialize(nxt),
        "days_until_next": days_until,
        "days_left_in_current": days_left,
    }
