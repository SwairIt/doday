"""HTTP routes for the mood tracker."""

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, status

from app.auth.deps import DbSession, RequiredUser
from app.mood.service import get_today, history, upsert_mood

router = APIRouter(prefix="/api/mood", tags=["mood"])


@router.get("/today")
async def today_endpoint(user: RequiredUser, session: DbSession) -> dict[str, object]:
    entry = await get_today(session, user.id)
    if entry is None:
        return {"recorded": False}
    return {
        "recorded": True,
        "score": entry.score,
        "note": entry.note,
        "mood_date": entry.mood_date.isoformat(),
    }


@router.post("/today")
async def upsert_today(
    user: RequiredUser,
    session: DbSession,
    score: Annotated[int, Form()],
    note: Annotated[str | None, Form()] = None,
) -> dict[str, object]:
    try:
        entry = await upsert_mood(session, user.id, score=score, note=note)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e
    return {
        "recorded": True,
        "score": entry.score,
        "note": entry.note,
        "mood_date": entry.mood_date.isoformat(),
    }


@router.get("/history")
async def history_endpoint(
    user: RequiredUser, session: DbSession, days: int = 30
) -> list[dict[str, object]]:
    rows = await history(session, user.id, days=max(7, min(days, 365)))
    return [{"mood_date": r.mood_date.isoformat(), "score": r.score, "note": r.note} for r in rows]
