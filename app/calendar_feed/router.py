"""HTTP route exposing the account-wide iCalendar feed.

The endpoint is mounted under /api/calendar/all.ics and requires the user
to be logged in (cookie session). Calendar apps that don't speak cookies
should hit a token-based variant — TODO once we add long-lived tokens.
"""

from fastapi import APIRouter
from fastapi.responses import Response

from app.auth.deps import DbSession, RequiredUser
from app.calendar_feed.service import export_all_to_ics

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/all.ics", response_class=Response)
async def all_ics(user: RequiredUser, session: DbSession) -> Response:
    body = await export_all_to_ics(session, user.id)
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="doday-all.ics"',
            "Cache-Control": "no-store",
        },
    )
