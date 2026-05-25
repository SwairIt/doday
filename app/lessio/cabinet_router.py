"""Lessio cabinet — endpoint'ы под /lessio/app/* для logged-in tutor'ов.

Один router содержит все cabinet-страницы: today / calendar / clients /
services / schedule / income / settings. Все требуют RequiredUser + наличие
LessioTutorProfile (иначе redirect на setup-profile).
"""

from __future__ import annotations

import calendar
from datetime import UTC, date, datetime, timedelta
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


# ── Schedule (working hours editor) ───────────────────────────────────


@router.get("/schedule", response_class=HTMLResponse, include_in_schema=False)
async def schedule_page(
    request: Request,
    user: RequiredUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    return _templates.TemplateResponse(
        request,
        "lessio/app/schedule.html",
        {
            "profile": profile,
            "active_nav": "schedule",
            "work_start_hour": profile.work_start_minute // 60,
            "work_end_hour": profile.work_end_minute // 60,
        },
    )


@router.post("/schedule", response_class=HTMLResponse, include_in_schema=False)
async def schedule_submit(
    user: RequiredUser,
    working_days: Annotated[list[str], Form()],
    work_start_hour: Annotated[int, Form()],
    work_end_hour: Annotated[int, Form()],
    buffer_minutes: Annotated[int, Form()],
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    if not (0 <= work_start_hour < work_end_hour <= 24):
        raise HTTPException(400, "Часы начала должны быть меньше часов окончания (0–24)")
    if buffer_minutes < 0 or buffer_minutes > 240:
        raise HTTPException(400, "Буфер от 0 до 240 минут")
    days_parsed = sorted({int(d) for d in working_days if d.isdigit() and 1 <= int(d) <= 7})
    if not days_parsed:
        raise HTTPException(400, "Выберите хотя бы один рабочий день")
    profile.working_days = days_parsed
    profile.work_start_minute = work_start_hour * 60
    profile.work_end_minute = work_end_hour * 60
    profile.buffer_minutes = buffer_minutes
    await session.commit()
    return RedirectResponse("/lessio/app/schedule?saved=1", status_code=303)


# ── Calendar (month view) ─────────────────────────────────────────────


def _parse_month(s: str | None) -> tuple[int, int]:
    if not s:
        today = datetime.now(UTC)
        return today.year, today.month
    try:
        y, m = s.split("-")
        year, month = int(y), int(m)
        if not (1 <= month <= 12 and 2020 <= year <= 2100):
            raise ValueError
        return year, month
    except (ValueError, AttributeError):
        today = datetime.now(UTC)
        return today.year, today.month


@router.get("/calendar", response_class=HTMLResponse, include_in_schema=False)
async def calendar_page(
    request: Request,
    user: RequiredUser,
    month: str | None = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    year, mo = _parse_month(month)
    first = datetime(year, mo, 1, tzinfo=UTC)
    last_day_num = calendar.monthrange(year, mo)[1]
    last = datetime(year, mo, last_day_num, 23, 59, 59, tzinfo=UTC)

    bookings = (
        (
            await session.execute(
                select(LessioBooking)
                .where(
                    LessioBooking.tutor_id == profile.id,
                    LessioBooking.starts_at >= first,
                    LessioBooking.starts_at <= last,
                )
                .order_by(LessioBooking.starts_at)
            )
        )
        .scalars()
        .all()
    )

    by_day: dict[int, list[LessioBooking]] = {}
    for b in bookings:
        by_day.setdefault(b.starts_at.day, []).append(b)

    first_weekday = first.isoweekday()
    leading_blanks = first_weekday - 1
    days_grid: list[date | None] = [None] * leading_blanks
    for d in range(1, last_day_num + 1):
        days_grid.append(date(year, mo, d))
    while len(days_grid) % 7 != 0:
        days_grid.append(None)

    prev_month = (mo - 1) or 12
    prev_year = year if mo > 1 else year - 1
    next_month = (mo % 12) + 1
    next_year = year if mo < 12 else year + 1
    month_label = f"{year}-{mo:02d}"
    return _templates.TemplateResponse(
        request,
        "lessio/app/calendar.html",
        {
            "profile": profile,
            "active_nav": "calendar",
            "year": year,
            "month": mo,
            "month_label": month_label,
            "prev_link": f"/lessio/app/calendar?month={prev_year}-{prev_month:02d}",
            "next_link": f"/lessio/app/calendar?month={next_year}-{next_month:02d}",
            "days_grid": days_grid,
            "by_day": by_day,
            "today": datetime.now(UTC).date(),
        },
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
