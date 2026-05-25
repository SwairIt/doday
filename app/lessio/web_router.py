"""Lessio web router — register/setup-profile + public profile /u/<slug>.

Отдельно от существующего `app.lessio.router` (он держит landing + waitlist +
Mini App endpoints). Этот модуль — для веб-кабинета через стандартный
Doday-auth (email+password) и публичных страниц с SEO.

`router` префикс `/lessio` (auth/cabinet — приватное, indexable=false).
`public_router` без префикса (`/u/<slug>` — публичное, indexable).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentUser, RequiredUser
from app.auth.schemas import RegisterIn
from app.auth.service import EmailAlreadyExists, register_user
from app.db import get_session
from app.lessio.models import LessioBooking, LessioService, LessioTutorProfile
from app.lessio.service import (
    BookingConflictError,
    OnboardError,
    cancel_booking,
    create_booking,
    create_services_from_template,
    create_tutor_profile,
    find_free_slots,
    reschedule_booking,
)

router = APIRouter(prefix="/lessio", tags=["lessio-web"])
_public_router = APIRouter(tags=["lessio-public"])
_templates = Jinja2Templates(directory="app/templates")


_ALLOWED_NICHES: frozenset[str] = frozenset(
    {"english", "ielts", "math", "school", "fitness", "psychology", "yoga", "other"}
)


# ── Auth ────────────────────────────────────────────────────────────


@router.get("/auth/register", response_class=HTMLResponse, include_in_schema=False)
async def lessio_register_page(request: Request, user: CurrentUser) -> Response:
    if user is not None:
        return RedirectResponse("/lessio/app/setup-profile", status_code=302)
    return _templates.TemplateResponse(request, "lessio/auth/lessio_register.html", {})


@router.post("/auth/register", response_class=HTMLResponse, include_in_schema=False)
async def lessio_register_submit(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    try:
        payload = RegisterIn(email=email.lower().strip(), password=password)
    except ValidationError:
        return _templates.TemplateResponse(
            request,
            "lessio/auth/lessio_register.html",
            {"error": "Проверьте email и пароль (от 8 символов)"},
            status_code=400,
        )
    try:
        user = await register_user(session, payload)
    except EmailAlreadyExists:
        return _templates.TemplateResponse(
            request,
            "lessio/auth/lessio_register.html",
            {"error": "Email уже зарегистрирован — войдите в существующий аккаунт"},
            status_code=400,
        )

    request.session["user_id"] = str(user.id)
    return RedirectResponse("/lessio/app/setup-profile", status_code=303)


# ── Setup-profile ─────────────────────────────────────────────────────


@router.get("/app/setup-profile", response_class=HTMLResponse, include_in_schema=False)
async def setup_profile_page(
    request: Request,
    user: RequiredUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    existing = (
        await session.execute(
            select(LessioTutorProfile).where(LessioTutorProfile.user_id == user.id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return RedirectResponse("/lessio/app/today", status_code=302)
    return _templates.TemplateResponse(request, "lessio/app/setup_profile.html", {})


@router.post("/app/setup-profile", response_class=HTMLResponse, include_in_schema=False)
async def setup_profile_submit(
    request: Request,
    user: RequiredUser,
    slug: Annotated[str, Form()],
    display_name: Annotated[str, Form()],
    niche: Annotated[str, Form()],
    bio: Annotated[str | None, Form()] = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    existing = (
        await session.execute(
            select(LessioTutorProfile).where(LessioTutorProfile.user_id == user.id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return RedirectResponse("/lessio/app/today", status_code=302)

    safe_niche = niche if niche in _ALLOWED_NICHES else "other"
    try:
        tutor = await create_tutor_profile(
            session,
            user=user,
            slug=slug,
            display_name=display_name,
            niche=safe_niche,
            bio=bio,
        )
    except OnboardError as exc:
        return _templates.TemplateResponse(
            request,
            "lessio/app/setup_profile.html",
            {
                "error": str(exc),
                "slug": slug,
                "display_name": display_name,
                "bio": bio,
            },
            status_code=400,
        )

    await create_services_from_template(session, tutor=tutor, niche=safe_niche)
    await session.commit()
    return RedirectResponse("/lessio/app/today", status_code=302)


# ── Placeholder cabinet endpoint (полный кабинет — wk3) ───────────────


@router.get("/app/today", response_class=HTMLResponse, include_in_schema=False)
async def lessio_today_placeholder(
    user: RequiredUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = (
        await session.execute(
            select(LessioTutorProfile).where(LessioTutorProfile.user_id == user.id)
        )
    ).scalar_one_or_none()
    if profile is None:
        return RedirectResponse("/lessio/app/setup-profile", status_code=302)
    return HTMLResponse(
        f'<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        f"<title>Lessio · {profile.display_name}</title>"
        '<meta name="robots" content="noindex,nofollow">'
        '<script src="https://cdn.tailwindcss.com"></script></head>'
        '<body style="background:linear-gradient(180deg,#0f0a1f,#2e1065);'
        'color:#f5f3ff;font-family:-apple-system,Segoe UI,sans-serif;min-height:100vh;">'
        '<main class="mx-auto max-w-2xl px-5 py-12">'
        f'<h1 class="text-4xl font-extrabold mb-4">Привет, {profile.display_name}!</h1>'
        '<p class="text-violet-200/80 mb-6">Профиль создан. Поделись ссылкой с клиентами:</p>'
        '<div class="bg-white/5 border border-white/10 rounded-2xl p-5 mb-6">'
        f'<a href="/u/{profile.slug}" class="text-violet-300 underline break-all">'
        f"getdoday.ru/u/{profile.slug}</a></div>"
        '<p class="text-violet-300/60 text-sm">Полный кабинет '
        "(календарь, клиенты, услуги, доход) — в разработке.</p>"
        "</main></body></html>"
    )


# ── Manage magic-link (anon client) ───────────────────────────────────


async def _load_booking_by_token(
    session: AsyncSession, token: str
) -> tuple[LessioBooking, LessioTutorProfile, LessioService]:
    booking = (
        await session.execute(select(LessioBooking).where(LessioBooking.manage_token == token))
    ).scalar_one_or_none()
    if booking is None:
        raise HTTPException(404, "Запись не найдена")
    tutor = await session.get(LessioTutorProfile, booking.tutor_id)
    service = await session.get(LessioService, booking.service_id)
    if tutor is None or service is None:
        raise HTTPException(404, "Запись не найдена")
    return booking, tutor, service


@router.get("/manage/{token}", response_class=HTMLResponse, include_in_schema=False)
async def manage_page(
    token: str,
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    booking, tutor, service = await _load_booking_by_token(session, token)
    siblings = (
        (
            await session.execute(
                select(LessioBooking)
                .where(
                    LessioBooking.tutor_id == tutor.id,
                    LessioBooking.client_email == booking.client_email,
                    LessioBooking.starts_at >= datetime.now(UTC),
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
        "lessio/manage/index.html",
        {
            "booking": booking,
            "tutor": tutor,
            "service": service,
            "siblings": siblings,
        },
    )


@router.post("/manage/{token}/cancel", response_class=HTMLResponse, include_in_schema=False)
async def manage_cancel(
    token: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    booking, _, _ = await _load_booking_by_token(session, token)
    await cancel_booking(session, booking=booking, by="client")
    await session.commit()
    return RedirectResponse(f"/lessio/manage/{token}", status_code=303)


@router.get("/manage/{token}/reschedule", response_class=HTMLResponse, include_in_schema=False)
async def manage_reschedule_page(
    token: str,
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    booking, tutor, service = await _load_booking_by_token(session, token)
    slots = await find_free_slots(
        session,
        tutor,
        date_from=datetime.now(UTC),
        date_to=datetime.now(UTC) + timedelta(days=14),
        service=service,
    )
    return _templates.TemplateResponse(
        request,
        "lessio/manage/reschedule.html",
        {
            "booking": booking,
            "tutor": tutor,
            "service": service,
            "slots": slots,
        },
    )


@router.post("/manage/{token}/reschedule", response_class=HTMLResponse, include_in_schema=False)
async def manage_reschedule_submit(
    token: str,
    slot_iso: Annotated[str, Form()],
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    booking, _, _ = await _load_booking_by_token(session, token)
    try:
        new_slot = datetime.fromisoformat(slot_iso)
    except ValueError as exc:
        raise HTTPException(400, "Некорректное время") from exc
    try:
        new = await reschedule_booking(session, booking=booking, new_slot=new_slot, by="client")
    except BookingConflictError as exc:
        raise HTTPException(400, str(exc)) from exc
    await session.commit()
    return RedirectResponse(f"/lessio/manage/{new.manage_token}", status_code=303)


# ── Public profile ────────────────────────────────────────────────────


@_public_router.get("/u/{slug}", response_class=HTMLResponse, include_in_schema=False)
async def public_profile(
    slug: str,
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = (
        await session.execute(
            select(LessioTutorProfile).where(LessioTutorProfile.slug == slug.lower())
        )
    ).scalar_one_or_none()
    if profile is None or not profile.is_active:
        raise HTTPException(404, "Репетитор не найден")

    services = (
        (
            await session.execute(
                select(LessioService)
                .where(
                    LessioService.tutor_id == profile.id,
                    LessioService.is_active.is_(True),
                )
                .order_by(LessioService.price_kopecks)
            )
        )
        .scalars()
        .all()
    )

    return _templates.TemplateResponse(
        request,
        "lessio/u/profile.html",
        {
            "tutor": profile,
            "services": services,
            "canonical_url": f"https://getdoday.ru/u/{profile.slug}",
        },
    )


# ── Public booking flow ───────────────────────────────────────────────


async def _load_tutor_and_service(
    session: AsyncSession, *, slug: str, service_id: UUID
) -> tuple[LessioTutorProfile, LessioService]:
    profile = (
        await session.execute(
            select(LessioTutorProfile).where(LessioTutorProfile.slug == slug.lower())
        )
    ).scalar_one_or_none()
    if profile is None or not profile.is_active:
        raise HTTPException(404, "Репетитор не найден")
    service = (
        await session.execute(
            select(LessioService).where(
                LessioService.id == service_id,
                LessioService.tutor_id == profile.id,
                LessioService.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if service is None:
        raise HTTPException(404, "Услуга не найдена")
    return profile, service


@_public_router.get(
    "/u/{slug}/book/{service_id}", response_class=HTMLResponse, include_in_schema=False
)
async def book_page(
    slug: str,
    service_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile, service = await _load_tutor_and_service(session, slug=slug, service_id=service_id)
    slots = await find_free_slots(
        session,
        profile,
        date_from=datetime.now(UTC),
        date_to=datetime.now(UTC) + timedelta(days=14),
        service=service,
    )
    return _templates.TemplateResponse(
        request,
        "lessio/u/book.html",
        {
            "tutor": profile,
            "service": service,
            "slots": slots,
            "canonical_url": f"https://getdoday.ru/u/{profile.slug}/book/{service.id}",
        },
    )


@_public_router.post(
    "/u/{slug}/book/{service_id}", response_class=HTMLResponse, include_in_schema=False
)
async def book_submit(
    slug: str,
    service_id: UUID,
    request: Request,
    slot_iso: Annotated[str, Form()],
    client_email: Annotated[str, Form()],
    client_full_name: Annotated[str, Form()],
    client_phone: Annotated[str | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile, service = await _load_tutor_and_service(session, slug=slug, service_id=service_id)
    try:
        slot = datetime.fromisoformat(slot_iso)
    except ValueError:
        return _templates.TemplateResponse(
            request,
            "lessio/u/book.html",
            {
                "tutor": profile,
                "service": service,
                "slots": [],
                "error": "Некорректный формат времени",
            },
            status_code=400,
        )

    try:
        booking = await create_booking(
            session,
            tutor=profile,
            service=service,
            slot=slot,
            client_email=client_email,
            client_full_name=client_full_name,
            client_phone=client_phone,
            notes=notes,
        )
    except BookingConflictError as exc:
        # Перезагрузить актуальные слоты — старые могли стать заняты
        slots = await find_free_slots(
            session,
            profile,
            date_from=datetime.now(UTC),
            date_to=datetime.now(UTC) + timedelta(days=14),
            service=service,
        )
        return _templates.TemplateResponse(
            request,
            "lessio/u/book.html",
            {
                "tutor": profile,
                "service": service,
                "slots": slots,
                "error": str(exc),
            },
            status_code=400,
        )
    await session.commit()
    return RedirectResponse(
        f"/u/{profile.slug}/booked?token={booking.manage_token}",
        status_code=303,
    )


@_public_router.get("/u/{slug}/booked", response_class=HTMLResponse, include_in_schema=False)
async def booked_page(
    slug: str,
    token: str,
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    booking = (
        await session.execute(select(LessioBooking).where(LessioBooking.manage_token == token))
    ).scalar_one_or_none()
    if booking is None:
        raise HTTPException(404, "Запись не найдена")
    tutor = await session.get(LessioTutorProfile, booking.tutor_id)
    if tutor is None or tutor.slug != slug.lower():
        raise HTTPException(404, "Запись не найдена")
    return _templates.TemplateResponse(
        request,
        "lessio/u/booked.html",
        {
            "tutor": tutor,
            "booking": booking,
            "manage_url": f"/lessio/manage/{booking.manage_token}",
        },
    )


public_router = _public_router
