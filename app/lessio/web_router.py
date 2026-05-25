"""Lessio web router — register/setup-profile + public profile /u/<slug>.

Отдельно от существующего `app.lessio.router` (он держит landing + waitlist +
Mini App endpoints). Этот модуль — для веб-кабинета через стандартный
Doday-auth (email+password) и публичных страниц с SEO.

`router` префикс `/lessio` (auth/cabinet — приватное, indexable=false).
`public_router` без префикса (`/u/<slug>` — публичное, indexable).
"""

from __future__ import annotations

from typing import Annotated

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
from app.lessio.models import LessioService, LessioTutorProfile
from app.lessio.service import (
    OnboardError,
    create_services_from_template,
    create_tutor_profile,
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


public_router = _public_router
