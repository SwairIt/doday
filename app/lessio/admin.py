"""Lessio admin — X-Admin-Token-secured endpoints for waitlist monitoring.

Validation-phase: only the waitlist is interesting. By 2026-06-01 we read these
endpoints + decide go/pivot/drop. Same auth pattern as app/admin/router.py's
token_router (X-Admin-Token header == settings.admin_token).
"""

from __future__ import annotations

import hmac
from collections import Counter
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select

from app.auth.deps import DbSession
from app.config import get_settings
from app.lessio.models import LessioWaitlistEntry

router = APIRouter(prefix="/api/admin/lessio", tags=["lessio-admin"])


class WaitlistEntryOut(BaseModel):
    email: str
    telegram_handle: str | None
    niche: str
    pain_point: str | None
    source: str | None
    created_at: str  # ISO-8601


class WaitlistStats(BaseModel):
    total: int
    by_niche: dict[str, int]
    with_pain_point: int
    decision_threshold: int = 100
    threshold_met: bool


def _check_admin_token(x_admin_token: str | None) -> None:
    """Validate X-Admin-Token header. Raise 403/503 on failure."""
    settings = get_settings()
    if not settings.admin_token:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "ADMIN_TOKEN не задан в окружении — endpoint отключён",
        )
    if not x_admin_token or not hmac.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid admin token")


@router.get("/waitlist.json", response_model=list[WaitlistEntryOut])
async def waitlist_list(
    session: DbSession,
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
    limit: int = 500,
) -> list[WaitlistEntryOut]:
    """All waitlist entries, newest first. For decision-day analysis."""
    _check_admin_token(x_admin_token)
    rows = (
        (
            await session.execute(
                select(LessioWaitlistEntry)
                .order_by(LessioWaitlistEntry.created_at.desc())
                .limit(min(max(limit, 1), 1000))
            )
        )
        .scalars()
        .all()
    )
    return [
        WaitlistEntryOut(
            email=r.email,
            telegram_handle=r.telegram_handle,
            niche=r.niche,
            pain_point=r.pain_point,
            source=r.source,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


@router.get("/waitlist/stats.json", response_model=WaitlistStats)
async def waitlist_stats(
    session: DbSession,
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
) -> WaitlistStats:
    """Aggregate counts. Single source of truth for go/pivot/drop decision."""
    _check_admin_token(x_admin_token)
    total = int(
        (await session.execute(select(func.count()).select_from(LessioWaitlistEntry))).scalar_one()
    )
    niches = (await session.execute(select(LessioWaitlistEntry.niche))).scalars().all()
    by_niche = dict(Counter(niches))
    with_pain = int(
        (
            await session.execute(
                select(func.count())
                .select_from(LessioWaitlistEntry)
                .where(LessioWaitlistEntry.pain_point.is_not(None))
            )
        ).scalar_one()
    )
    return WaitlistStats(
        total=total,
        by_niche=by_niche,
        with_pain_point=with_pain,
        threshold_met=total >= 100,
    )


@router.delete("/waitlist/by-email")
async def waitlist_delete_by_email(
    email: str,
    session: DbSession,
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
) -> Response:
    """Удалить запись по email — для cleanup тестовых submission'ов."""
    _check_admin_token(x_admin_token)
    await session.execute(delete(LessioWaitlistEntry).where(LessioWaitlistEntry.email == email))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
