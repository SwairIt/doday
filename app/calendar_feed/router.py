"""HTTP routes exposing the account-wide iCalendar feed.

Two flavours:

- `/api/calendar/all.ics` — cookie-authenticated, used from the browser.
- `/api/calendar/feed/<token>.ics` — long-lived per-user token, what phones
  subscribe to (Apple/Google Calendar can't pass our session cookies).

`/api/profile/ical-token` issues a token (idempotent — returns the same one
on repeat calls) and `/api/profile/ical-token/rotate` invalidates the old.
"""

import secrets

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select

from app.auth.deps import DbSession, RequiredUser
from app.auth.models import User
from app.calendar_feed.service import export_all_to_ics

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


def _ical_response(body: str) -> Response:
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="doday-all.ics"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/all.ics", response_class=Response)
async def all_ics(user: RequiredUser, session: DbSession) -> Response:
    return _ical_response(await export_all_to_ics(session, user.id))


@router.get("/feed/{token}.ics", response_class=Response)
async def token_feed(token: str, session: DbSession) -> Response:
    """Public-by-token feed — no auth required. Token is treated as a secret."""
    if len(token) < 24 or len(token) > 64:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "feed not found")
    user = (
        await session.execute(select(User).where(User.ical_token == token))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "feed not found")
    return _ical_response(await export_all_to_ics(session, user.id))


def _generate_token() -> str:
    """43-char URL-safe random token (256 bits of entropy)."""
    return secrets.token_urlsafe(32)


token_router = APIRouter(prefix="/api/profile", tags=["profile"])


@token_router.get("/ical-token")
async def get_or_create_token(user: RequiredUser, session: DbSession) -> dict[str, str]:
    """Return the user's token, creating one on first call."""
    token = user.ical_token
    if not token:
        token = _generate_token()
        user.ical_token = token
        await session.commit()
    return {"token": token, "url": f"/api/calendar/feed/{token}.ics"}


@token_router.post("/ical-token/rotate")
async def rotate_token(user: RequiredUser, session: DbSession) -> dict[str, str]:
    """Generate a fresh token, invalidating the old one."""
    token = _generate_token()
    user.ical_token = token
    await session.commit()
    return {"token": token, "url": f"/api/calendar/feed/{token}.ics"}
