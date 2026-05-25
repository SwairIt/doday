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
from app.lessio.models import LessioBooking, LessioClient, LessioService, LessioTutorProfile

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


# ── Services CRUD ─────────────────────────────────────────────────────


@router.get("/services", response_class=HTMLResponse, include_in_schema=False)
async def services_page(
    request: Request,
    user: RequiredUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    services = (
        (
            await session.execute(
                select(LessioService)
                .where(LessioService.tutor_id == profile.id)
                .order_by(LessioService.is_active.desc(), LessioService.price_kopecks)
            )
        )
        .scalars()
        .all()
    )
    return _templates.TemplateResponse(
        request,
        "lessio/app/services.html",
        {"profile": profile, "services": services, "active_nav": "services"},
    )


@router.post("/services", response_class=HTMLResponse, include_in_schema=False)
async def services_create(
    user: RequiredUser,
    title: Annotated[str, Form()],
    duration_minutes: Annotated[int, Form()],
    price_kopecks: Annotated[int, Form()],
    is_group_session: Annotated[bool, Form()] = False,
    max_attendees: Annotated[int, Form()] = 1,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    if duration_minutes < 5 or duration_minutes > 480:
        raise HTTPException(400, "Длительность от 5 до 480 минут")
    if price_kopecks < 0:
        raise HTTPException(400, "Цена не может быть отрицательной")
    # Stars = ₽ × 100 / 120 ≈ kopecks / 120. Round to nearest.
    price_stars = max(1, price_kopecks // 120)
    service = LessioService(
        tutor_id=profile.id,
        title=title[:120],
        duration_minutes=duration_minutes,
        price_kopecks=price_kopecks,
        price_stars=price_stars,
        is_group_session=bool(is_group_session),
        max_attendees=max(1, max_attendees) if is_group_session else 1,
    )
    session.add(service)
    await session.commit()
    return RedirectResponse("/lessio/app/services", status_code=303)


@router.post(
    "/services/{service_id}/toggle-active",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def services_toggle_active(
    service_id: UUID,
    user: RequiredUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    service = (
        await session.execute(
            select(LessioService).where(
                LessioService.id == service_id,
                LessioService.tutor_id == profile.id,
            )
        )
    ).scalar_one_or_none()
    if service is None:
        raise HTTPException(404, "Услуга не найдена")
    service.is_active = not service.is_active
    await session.commit()
    return RedirectResponse("/lessio/app/services", status_code=303)


@router.post(
    "/services/{service_id}/edit",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def services_edit(
    service_id: UUID,
    user: RequiredUser,
    title: Annotated[str, Form()],
    duration_minutes: Annotated[int, Form()],
    price_kopecks: Annotated[int, Form()],
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    service = (
        await session.execute(
            select(LessioService).where(
                LessioService.id == service_id,
                LessioService.tutor_id == profile.id,
            )
        )
    ).scalar_one_or_none()
    if service is None:
        raise HTTPException(404, "Услуга не найдена")
    if duration_minutes < 5 or duration_minutes > 480:
        raise HTTPException(400, "Длительность от 5 до 480 минут")
    if price_kopecks < 0:
        raise HTTPException(400, "Цена не может быть отрицательной")
    service.title = title[:120]
    service.duration_minutes = duration_minutes
    service.price_kopecks = price_kopecks
    service.price_stars = max(1, price_kopecks // 120)
    await session.commit()
    return RedirectResponse("/lessio/app/services", status_code=303)


# ── Clients ───────────────────────────────────────────────────────────


@router.get("/clients", response_class=HTMLResponse, include_in_schema=False)
async def clients_page(
    request: Request,
    user: RequiredUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    clients = (
        (
            await session.execute(
                select(LessioClient)
                .where(LessioClient.tutor_id == profile.id)
                .order_by(LessioClient.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return _templates.TemplateResponse(
        request,
        "lessio/app/clients.html",
        {"profile": profile, "clients": clients, "active_nav": "clients"},
    )


@router.get("/clients/{client_id}", response_class=HTMLResponse, include_in_schema=False)
async def client_detail(
    client_id: UUID,
    request: Request,
    user: RequiredUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    client = (
        await session.execute(
            select(LessioClient).where(
                LessioClient.id == client_id,
                LessioClient.tutor_id == profile.id,
            )
        )
    ).scalar_one_or_none()
    if client is None:
        raise HTTPException(404, "Клиент не найден")
    bookings = (
        (
            await session.execute(
                select(LessioBooking)
                .where(LessioBooking.client_id == client.id)
                .order_by(LessioBooking.starts_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return _templates.TemplateResponse(
        request,
        "lessio/app/client_detail.html",
        {
            "profile": profile,
            "client": client,
            "bookings": bookings,
            "active_nav": "clients",
        },
    )
