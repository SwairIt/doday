"""Lessio web router — register/setup-profile + public profile /u/<slug>.

Отдельно от существующего `app.lessio.router` (он держит landing + waitlist +
Mini App endpoints). Этот модуль — для веб-кабинета через стандартный
Doday-auth (email+password) и публичных страниц с SEO.

`router` префикс `/lessio` (auth/cabinet — приватное, indexable=false).
`public_router` без префикса (`/u/<slug>` — публичное, indexable).
"""

from __future__ import annotations

import hmac
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Request
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
_cron_router = APIRouter(prefix="/api/lessio", tags=["lessio-cron"])
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


# ── Login (Lessio-scoped — отдельно от Doday /auth/login) ────────────


@router.get("/auth/login", response_class=HTMLResponse, include_in_schema=False)
async def lessio_login_page(request: Request, user: CurrentUser) -> Response:
    """Если уже залогинен — сразу в Lessio cabinet."""
    if user is not None:
        return RedirectResponse("/lessio/app/today", status_code=302)
    return _templates.TemplateResponse(request, "lessio/auth/lessio_login.html", {})


@router.post("/auth/login", response_class=HTMLResponse, include_in_schema=False)
async def lessio_login_submit(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    from app.auth.service import InvalidCredentials, authenticate

    try:
        user = await authenticate(session, email, password)
    except InvalidCredentials:
        return _templates.TemplateResponse(
            request,
            "lessio/auth/lessio_login.html",
            {"error": "Неверный email или пароль"},
            status_code=401,
        )
    request.session.clear()
    request.session["user_id"] = str(user.id)
    # Если у user'а ещё нет LessioTutorProfile — _require_profile отправит на setup-profile
    return RedirectResponse("/lessio/app/today", status_code=303)


@router.post("/auth/logout", response_class=HTMLResponse, include_in_schema=False)
async def lessio_logout(request: Request) -> Response:
    """Lessio-scoped logout — возврат в /lessio landing, не в Doday hub."""
    request.session.clear()
    return RedirectResponse("/lessio", status_code=303)


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

    # Fire-and-forget IndexNow ping — Yandex/Bing должны узнать о новой /u/<slug>
    from app.config import get_settings as _gs
    from app.lessio.email import send_welcome_email
    from app.lessio.indexnow import ping_indexnow

    base = _gs().app_base_url.rstrip("/")
    await ping_indexnow(urls=[f"{base}/u/{tutor.slug}"])

    # Welcome email — onboarding tutorial. Fail-safe (SMTP-fail логируется).
    await send_welcome_email(to=user.email, tutor=tutor)

    return RedirectResponse("/lessio/app/today", status_code=302)


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


# ── Review submit (after completed booking) ───────────────────────────


@router.get("/review/{token}", response_class=HTMLResponse, include_in_schema=False)
async def review_page(
    token: str,
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    booking, tutor, service = await _load_booking_by_token(session, token)
    return _templates.TemplateResponse(
        request,
        "lessio/review/submit.html",
        {"booking": booking, "tutor": tutor, "service": service},
    )


@router.post("/review/{token}", response_class=HTMLResponse, include_in_schema=False)
async def review_submit(
    token: str,
    request: Request,
    rating: Annotated[int, Form()],
    text: Annotated[str | None, Form()] = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    from app.lessio.reviews import ReviewError, create_review

    booking, tutor, service = await _load_booking_by_token(session, token)
    try:
        await create_review(session, booking=booking, rating=rating, text=text)
    except ReviewError as exc:
        return _templates.TemplateResponse(
            request,
            "lessio/review/submit.html",
            {
                "booking": booking,
                "tutor": tutor,
                "service": service,
                "error": str(exc),
            },
            status_code=400,
        )
    await session.commit()
    return RedirectResponse(f"/u/{tutor.slug}?thanks=1", status_code=303)


# ── Public profile ────────────────────────────────────────────────────


@_public_router.get("/u/{slug}", response_class=HTMLResponse, include_in_schema=False)
async def public_profile(
    slug: str,
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    from app.lessio.reviews import get_tutor_aggregate, get_tutor_recent_reviews

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

    aggregate = await get_tutor_aggregate(session, tutor_id=profile.id)
    recent_reviews = await get_tutor_recent_reviews(session, tutor_id=profile.id, limit=5)

    return _templates.TemplateResponse(
        request,
        "lessio/u/profile.html",
        {
            "tutor": profile,
            "services": services,
            "aggregate": aggregate,
            "recent_reviews": recent_reviews,
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


# ── Cron: dispatch reminders 24h+1h ───────────────────────────────────


@_cron_router.post("/cron/dispatch-reminders", include_in_schema=False)
async def cron_dispatch_reminders(
    x_cron_token: Annotated[str | None, Header(alias="X-Cron-Token")] = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, Any]:
    from app.config import get_settings
    from app.lessio.cron import (
        dispatch_daily_digests,
        dispatch_reminders,
        mark_completed_bookings,
    )

    settings = get_settings()
    if not settings.cron_token:
        raise HTTPException(503, "cron не настроен на этом сервере")
    if not x_cron_token or not hmac.compare_digest(x_cron_token, settings.cron_token):
        raise HTTPException(403, "Неверный X-Cron-Token")
    r24 = await dispatch_reminders(session, hours=24)
    r1 = await dispatch_reminders(session, hours=1)
    completed = await mark_completed_bookings(session)
    digests = await dispatch_daily_digests(session)
    await session.commit()
    return {"24h": r24, "1h": r1, "completed": completed, "digests": digests}


# ── Google Calendar OAuth (Phase 2 optional) ──────────────────────────


@router.get("/oauth/google/connect", include_in_schema=False)
async def oauth_google_connect(
    user: RequiredUser,
) -> Response:
    """Redirect tutor'а на Google OAuth consent. Возврат → /oauth/google/callback."""
    from urllib.parse import urlencode

    from app.config import get_settings as _gs
    from app.lessio.google_calendar import GOOGLE_OAUTH_AUTH_URL, GOOGLE_OAUTH_SCOPES

    settings = _gs()
    if not settings.google_oauth_client_id:
        raise HTTPException(503, "Google OAuth не настроен на сервере")
    redirect_uri = f"{settings.app_base_url.rstrip('/')}/lessio/oauth/google/callback"
    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GOOGLE_OAUTH_SCOPES,
        "access_type": "offline",  # gives refresh_token
        "prompt": "consent",  # forces refresh_token even on re-auth
        "state": str(user.id),  # tutor-id для callback идентификации
    }
    return RedirectResponse(f"{GOOGLE_OAUTH_AUTH_URL}?{urlencode(params)}", status_code=302)


@router.get("/oauth/google/callback", include_in_schema=False)
async def oauth_google_callback(
    user: RequiredUser,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    """Google OAuth callback: code → refresh_token → encrypt + save."""
    import httpx as _httpx

    from app.config import get_settings as _gs
    from app.lessio.google_calendar import GOOGLE_OAUTH_TOKEN_URL, encrypt_refresh_token

    if error:
        return RedirectResponse(f"/lessio/app/settings?gcal_error={error}", status_code=303)
    if not code:
        raise HTTPException(400, "OAuth callback missing 'code' parameter")
    if state != str(user.id):
        raise HTTPException(400, "OAuth state mismatch — повторите попытку")

    settings = _gs()
    redirect_uri = f"{settings.app_base_url.rstrip('/')}/lessio/oauth/google/callback"
    async with _httpx.AsyncClient(timeout=10.0) as http_client:
        token_resp = await http_client.post(
            GOOGLE_OAUTH_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            return RedirectResponse(
                "/lessio/app/settings?gcal_error=token_exchange_failed", status_code=303
            )
        refresh_token = token_resp.json().get("refresh_token")
        if not refresh_token:
            return RedirectResponse(
                "/lessio/app/settings?gcal_error=no_refresh_token", status_code=303
            )

    profile = (
        await session.execute(
            select(LessioTutorProfile).where(LessioTutorProfile.user_id == user.id)
        )
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(404, "Tutor profile not found")
    profile.google_calendar_refresh_token = encrypt_refresh_token(refresh_token)
    await session.commit()
    return RedirectResponse("/lessio/app/settings?toast=gcal_connected", status_code=303)


@router.post("/oauth/google/disconnect", include_in_schema=False)
async def oauth_google_disconnect(
    user: RequiredUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    """Удалить refresh_token — отключить GCal sync."""
    profile = (
        await session.execute(
            select(LessioTutorProfile).where(LessioTutorProfile.user_id == user.id)
        )
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(404, "Tutor profile not found")
    profile.google_calendar_refresh_token = None
    await session.commit()
    return RedirectResponse("/lessio/app/settings?toast=gcal_disconnected", status_code=303)


@_public_router.get("/u/{slug}/og.svg", include_in_schema=False)
async def public_profile_og(
    slug: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    from app.lessio.og_image import render_tutor_og_svg

    profile = (
        await session.execute(
            select(LessioTutorProfile).where(LessioTutorProfile.slug == slug.lower())
        )
    ).scalar_one_or_none()
    if profile is None or not profile.is_active:
        raise HTTPException(404, "Репетитор не найден")
    svg = render_tutor_og_svg(profile)
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


public_router = _public_router
cron_router = _cron_router
