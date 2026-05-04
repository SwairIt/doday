"""HTTP routes for habit tracking."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, status

from app.auth.deps import DbSession, RequiredUser
from app.habits.schemas import HabitCreate, HabitOut, HabitWithStats
from app.habits.service import (
    HabitNotFound,
    archive_habit,
    check_in,
    create_habit,
    list_habits,
    stats_for,
    uncheck,
    update_habit,
)

router = APIRouter(prefix="/api/habits", tags=["habits"])


@router.get("", response_model=list[HabitWithStats])
async def list_endpoint(user: RequiredUser, session: DbSession) -> list[HabitWithStats]:
    habits = await list_habits(session, user.id)
    out: list[HabitWithStats] = []
    for h in habits:
        stats = await stats_for(session, user.id, h.id)
        out.append(
            HabitWithStats(
                id=h.id,
                name=h.name,
                emoji=h.emoji,
                color=h.color,
                archived_at=h.archived_at,
                created_at=h.created_at,
                last_30=stats["last_30"],  # type: ignore[arg-type]
                current_streak=stats["current_streak"],  # type: ignore[arg-type]
                longest_streak=stats["longest_streak"],  # type: ignore[arg-type]
                today_done=stats["today_done"],  # type: ignore[arg-type]
            )
        )
    return out


@router.post("", response_model=HabitOut, status_code=status.HTTP_201_CREATED)
async def create_endpoint(user: RequiredUser, session: DbSession, payload: HabitCreate) -> HabitOut:
    habit = await create_habit(
        session, user.id, name=payload.name, emoji=payload.emoji, color=payload.color
    )
    return HabitOut.model_validate(habit)


@router.patch("/{habit_id}", response_model=HabitOut)
async def update_endpoint(
    habit_id: UUID,
    user: RequiredUser,
    session: DbSession,
    name: Annotated[str | None, Form()] = None,
    emoji: Annotated[str | None, Form()] = None,
    color: Annotated[str | None, Form()] = None,
) -> HabitOut:
    try:
        habit = await update_habit(session, user.id, habit_id, name=name, emoji=emoji, color=color)
    except HabitNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "habit not found") from e
    return HabitOut.model_validate(habit)


@router.delete("/{habit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_endpoint(habit_id: UUID, user: RequiredUser, session: DbSession) -> None:
    try:
        await archive_habit(session, user.id, habit_id)
    except HabitNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "habit not found") from e


@router.post("/{habit_id}/checkin")
async def checkin_endpoint(
    habit_id: UUID, user: RequiredUser, session: DbSession
) -> dict[str, object]:
    try:
        await check_in(session, user.id, habit_id)
    except HabitNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "habit not found") from e
    return await stats_for(session, user.id, habit_id)


@router.delete("/{habit_id}/checkin", status_code=status.HTTP_200_OK)
async def uncheck_endpoint(
    habit_id: UUID, user: RequiredUser, session: DbSession
) -> dict[str, object]:
    try:
        await uncheck(session, user.id, habit_id)
    except HabitNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "habit not found") from e
    return await stats_for(session, user.id, habit_id)
