"""HTTP route exposing achievement state for the current user."""

from fastapi import APIRouter

from app.achievements.service import ACHIEVEMENTS, compute_unlocked
from app.auth.deps import DbSession, RequiredUser

router = APIRouter(prefix="/api/achievements", tags=["achievements"])


@router.get("")
async def list_endpoint(user: RequiredUser, session: DbSession) -> dict[str, object]:
    unlocked = await compute_unlocked(session, user.id)
    items = [
        {
            "code": a["code"],
            "emoji": a["emoji"],
            "title": a["title"],
            "description": a["description"],
            "unlocked": a["code"] in unlocked,
        }
        for a in ACHIEVEMENTS
    ]
    return {
        "unlocked": len(unlocked),
        "total": len(ACHIEVEMENTS),
        "items": items,
    }
