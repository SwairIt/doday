"""Custom filter HTTP endpoints — JSON CRUD."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from app.auth.deps import DbSession, RequiredUser
from app.custom_filters.schemas import (
    CustomFilterCreate,
    CustomFilterOut,
    CustomFilterUpdate,
)
from app.custom_filters.service import (
    CustomFilterNotFound,
    create_custom_filter,
    delete_custom_filter,
    list_custom_filters,
    update_custom_filter,
)

router = APIRouter(prefix="/api/custom-filters", tags=["custom-filters"])


@router.get("", response_model=list[CustomFilterOut])
async def list_endpoint(user: RequiredUser, session: DbSession) -> list[CustomFilterOut]:
    items = await list_custom_filters(session, user.id)
    return [CustomFilterOut.model_validate(i) for i in items]


@router.post("", response_model=CustomFilterOut, status_code=status.HTTP_201_CREATED)
async def create_endpoint(
    payload: CustomFilterCreate, user: RequiredUser, session: DbSession
) -> CustomFilterOut:
    obj = await create_custom_filter(
        session,
        user.id,
        name=payload.name,
        color=payload.color,
        query=payload.query.model_dump(mode="json", exclude_none=True),
    )
    return CustomFilterOut.model_validate(obj)


@router.patch("/{filter_id}", response_model=CustomFilterOut)
async def update_endpoint(
    filter_id: UUID,
    payload: CustomFilterUpdate,
    user: RequiredUser,
    session: DbSession,
) -> CustomFilterOut:
    try:
        obj = await update_custom_filter(
            session,
            user.id,
            filter_id,
            name=payload.name,
            color=payload.color,
            query=(
                payload.query.model_dump(mode="json", exclude_none=True)
                if payload.query is not None
                else None
            ),
        )
    except CustomFilterNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "фильтр не найден") from e
    return CustomFilterOut.model_validate(obj)


@router.delete("/{filter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_endpoint(filter_id: UUID, user: RequiredUser, session: DbSession) -> Response:
    try:
        await delete_custom_filter(session, user.id, filter_id)
    except CustomFilterNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "фильтр не найден") from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)
