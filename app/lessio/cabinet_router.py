"""Lessio cabinet — endpoint'ы под /lessio/app/* для logged-in tutor'ов.

Один router содержит все cabinet-страницы: today / calendar / clients /
services / schedule / income / settings. Все требуют RequiredUser + наличие
LessioTutorProfile (иначе redirect на setup-profile).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import RequiredUser
from app.db import get_session
from app.lessio.models import LessioBooking, LessioTutorProfile

router = APIRouter(prefix="/lessio/app", tags=["lessio-cabinet"])
_templates = Jinja2Templates(directory="app/templates")


async def _require_profile(session: AsyncSession, user_id: UUID) -> LessioTutorProfile:
    profile = (
        await session.execute(
            select(LessioTutorProfile).where(LessioTutorProfile.user_id == user_id)
        )
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(303, headers={"Location": "/lessio/app/setup-profile"})
    return profile


# ── Today ─────────────────────────────────────────────────────────────


@router.get("/today", response_class=HTMLResponse, include_in_schema=False)
async def today(
    request: Request,
    user: RequiredUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    bookings = (
        (
            await session.execute(
                select(LessioBooking)
                .where(
                    LessioBooking.tutor_id == profile.id,
                    LessioBooking.starts_at >= today_start,
                    LessioBooking.starts_at < today_end,
                    LessioBooking.status == "confirmed",
                )
                .order_by(LessioBooking.starts_at)
            )
        )
        .scalars()
        .all()
    )
    return _templates.TemplateResponse(
        request,
        "lessio/app/today.html",
        {"profile": profile, "bookings": bookings, "active_nav": "today"},
    )


# ── Settings ──────────────────────────────────────────────────────────


@router.get("/settings", response_class=HTMLResponse, include_in_schema=False)
async def settings_page(
    request: Request,
    user: RequiredUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    return _templates.TemplateResponse(
        request,
        "lessio/app/settings.html",
        {"profile": profile, "active_nav": "settings"},
    )


@router.post("/settings", response_class=HTMLResponse, include_in_schema=False)
async def settings_submit(
    user: RequiredUser,
    bio: Annotated[str | None, Form()] = None,
    default_meeting_url_template: Annotated[str | None, Form()] = None,
    notification_email: Annotated[str | None, Form()] = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    profile.bio = ((bio or "").strip()[:1000]) or None
    profile.default_meeting_url_template = (
        ((default_meeting_url_template or "").strip()[:500]) or None
    )
    profile.notification_email = ((notification_email or "").strip()[:255]) or None
    await session.commit()
    return RedirectResponse("/lessio/app/settings?saved=1", status_code=303)
