"""Lessio router — landing + waitlist + tutor onboarding (Mini App).

URLs (validation phase + onboarding):
- GET /lessio                           — лендинг + waitlist форма (anon)
- POST /lessio/waitlist                 — submit waitlist (anon, idempotent by email)
- GET /lessio/miniapp/cabinet           — кабинет репетитора (требует TG initData)
- GET /lessio/miniapp/onboard           — форма онбординга (slug + display_name + niche)
- POST /lessio/miniapp/onboard          — создать LessioTutorProfile (idempotent по user_id)
- GET /lessio/miniapp/check-slug        — JSON {"available": bool} для live-validation

Booking endpoints (MVP-phase, заглушки на 503):
- GET /lessio/miniapp/book/<slug>       — публичная страница записи к репетитору
- POST /lessio/miniapp/book/<slug>/confirm  — создать Stars-invoice
- GET /lessio/miniapp/booking/<id>/status   — poll-статус для UX
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.lessio.models import LessioWaitlistEntry
from app.lessio.service import (
    OnboardError,
    auto_onboard_tutor,
    create_tutor_profile,
    is_slug_available,
)
from app.miniapp.auth import get_telegram_user_id, validate_init_data

router = APIRouter(prefix="/lessio", tags=["lessio"])

_templates = Jinja2Templates(directory="app/templates")


async def _require_telegram_user(
    init_data: str | None,
    session: AsyncSession,
) -> tuple[int, str | None, str | None]:
    """Извлечь Telegram user_id из initData. Raise 401 если невалидно.

    Возвращает (telegram_user_id, first_name, username) — данные для auto-onboard.
    """
    if not init_data:
        raise HTTPException(401, "Telegram WebApp initData отсутствует")
    settings = get_settings()
    if not settings.lessio_bot_token:
        # На dev без LESSIO_BOT_TOKEN валидировать нечем — отказ.
        raise HTTPException(503, "Lessio bot не настроен на этом сервере")
    parsed = validate_init_data(init_data, settings.lessio_bot_token)
    if parsed is None:
        raise HTTPException(401, "Telegram initData не прошёл HMAC-проверку")
    telegram_user_id = get_telegram_user_id(parsed)
    if telegram_user_id is None:
        raise HTTPException(401, "В initData нет user.id")
    user_obj = parsed.get("user", {})
    first_name = user_obj.get("first_name") if isinstance(user_obj, dict) else None
    username = user_obj.get("username") if isinstance(user_obj, dict) else None
    # Touch session чтобы dependency mypy-чистый.
    _ = session
    return telegram_user_id, first_name, username


# Niches allowed in landing dropdown. Bad values fall back to "other".
_ALLOWED_NICHES: frozenset[str] = frozenset(
    {"english", "ielts", "math", "school", "fitness", "psychology", "yoga", "other"}
)


@router.get("", response_class=HTMLResponse, include_in_schema=False)
@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def lessio_landing(
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008 — FastAPI Depends pattern
) -> HTMLResponse:
    """Landing page + waitlist signup form."""
    count_row = await session.execute(select(func.count()).select_from(LessioWaitlistEntry))
    count = int(count_row.scalar_one())
    # Show social proof only after a threshold — empty list signals "no traction"
    show_count = count >= 20
    return _templates.TemplateResponse(
        request,
        "lessio/index.html",
        {
            "waitlist_count": count,
            "show_count": show_count,
        },
    )


@router.post("/waitlist", response_class=HTMLResponse, include_in_schema=False)
async def lessio_submit_waitlist(
    email: Annotated[EmailStr, Form()],
    niche: Annotated[str, Form()],
    pain_point: Annotated[str | None, Form()] = None,
    telegram_handle: Annotated[str | None, Form()] = None,
    source: Annotated[str | None, Form()] = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008 — FastAPI Depends pattern
) -> HTMLResponse:
    """Accept signup. Idempotent by email — second submit updates the row."""
    safe_niche = niche if niche in _ALLOWED_NICHES else "other"

    existing = (
        await session.execute(select(LessioWaitlistEntry).where(LessioWaitlistEntry.email == email))
    ).scalar_one_or_none()

    if existing is not None:
        if pain_point:
            existing.pain_point = pain_point[:500]
        if telegram_handle:
            existing.telegram_handle = telegram_handle.lstrip("@")[:100]
        existing.niche = safe_niche
        if source:
            existing.source = source[:80]
        await session.commit()
    else:
        entry = LessioWaitlistEntry(
            email=str(email),
            niche=safe_niche,
            pain_point=(pain_point or "")[:500] or None,
            telegram_handle=(telegram_handle or "").lstrip("@")[:100] or None,
            source=(source or "")[:80] or None,
        )
        session.add(entry)
        try:
            await session.commit()
        except Exception as exc:
            await session.rollback()
            raise HTTPException(status_code=500, detail="Не удалось сохранить заявку") from exc

    return HTMLResponse(
        '<div class="rounded-xl bg-emerald-500/15 px-5 py-4 text-emerald-300">'
        "✅ Вы в листе ожидания. Напишу лично в Telegram когда будет первая версия."
        "</div>"
    )


# ── Mini App: cabinet / onboarding ───────────────────────────────────────────
#
# Точка входа — GET /lessio/miniapp/cabinet. Telegram передаёт initData в URL
# через `?tgWebAppData=<…>` или мы читаем из заголовка `X-Telegram-Init-Data`
# (тот же паттерн что Doday's /miniapp). Auto-onboarding: валидация HMAC →
# find/create User by telegram_user_id → find LessioTutorProfile → если нет,
# редирект на /lessio/miniapp/onboard.


@router.get("/miniapp/cabinet", response_class=HTMLResponse, include_in_schema=False)
async def miniapp_cabinet(
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    x_telegram_init_data: Annotated[str | None, Header(alias="X-Telegram-Init-Data")] = None,
) -> Response:
    """Кабинет репетитора. Auto-onboard на лету, редирект на /onboard если нет профиля."""
    init_data = x_telegram_init_data or request.query_params.get("tgWebAppData")
    tg_id, first_name, username = await _require_telegram_user(init_data, session)

    user, profile = await auto_onboard_tutor(
        session,
        telegram_user_id=tg_id,
        telegram_first_name=first_name,
        telegram_username=username,
    )
    await session.commit()

    if profile is None:
        # Профиля нет — редирект на онбординг.
        return RedirectResponse(
            url=f"/lessio/miniapp/onboard?tgWebAppData={init_data or ''}", status_code=302
        )

    # MVP: cabinet.html будет в следующем chunk'e. Сейчас — placeholder.
    return HTMLResponse(
        f'<!doctype html><meta charset="utf-8"><title>{profile.display_name}</title>'
        "<style>body{font-family:sans-serif;background:#0f0a1f;color:#f5f3ff;padding:2em;}</style>"
        f"<h1>Привет, {profile.display_name}!</h1>"
        f"<p>Slug: <code>{profile.slug}</code> · ниша: {profile.niche}</p>"
        '<p style="color:#a78bfa">Кабинет (booking, услуги, статистика) — '
        "в разработке. Появится после фазы валидации.</p>"
        f"<p>User id: {user.id}</p>"
    )


@router.get("/miniapp/onboard", response_class=HTMLResponse, include_in_schema=False)
async def miniapp_onboard_form(
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    x_telegram_init_data: Annotated[str | None, Header(alias="X-Telegram-Init-Data")] = None,
) -> Response:
    """Форма онбординга. Auto-onboard внутри (создаёт user если нет), показывает форму."""
    init_data = x_telegram_init_data or request.query_params.get("tgWebAppData")
    tg_id, first_name, username = await _require_telegram_user(init_data, session)

    user, profile = await auto_onboard_tutor(
        session,
        telegram_user_id=tg_id,
        telegram_first_name=first_name,
        telegram_username=username,
    )
    await session.commit()

    if profile is not None:
        # Профиль уже есть — редирект в кабинет.
        return RedirectResponse(
            url=f"/lessio/miniapp/cabinet?tgWebAppData={init_data or ''}", status_code=302
        )

    return _templates.TemplateResponse(
        request,
        "lessio/miniapp/onboard.html",
        {
            "telegram_first_name": first_name or "Репетитор",
            "user_id": str(user.id),
        },
    )


@router.post("/miniapp/onboard", response_class=HTMLResponse, include_in_schema=False)
async def miniapp_onboard_submit(
    request: Request,
    slug: Annotated[str, Form()],
    display_name: Annotated[str, Form()],
    niche: Annotated[str, Form()],
    bio: Annotated[str | None, Form()] = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    x_telegram_init_data: Annotated[str | None, Header(alias="X-Telegram-Init-Data")] = None,
) -> Response:
    """Создать LessioTutorProfile. Auto-onboard ensures user exists первым делом."""
    init_data = x_telegram_init_data or request.query_params.get("tgWebAppData")
    tg_id, first_name, username = await _require_telegram_user(init_data, session)

    user, existing_profile = await auto_onboard_tutor(
        session,
        telegram_user_id=tg_id,
        telegram_first_name=first_name,
        telegram_username=username,
    )

    if existing_profile is not None:
        await session.commit()
        return RedirectResponse(
            url=f"/lessio/miniapp/cabinet?tgWebAppData={init_data or ''}", status_code=302
        )

    safe_niche = niche if niche in _ALLOWED_NICHES else "other"
    try:
        await create_tutor_profile(
            session,
            user=user,
            slug=slug,
            display_name=display_name,
            niche=safe_niche,
            bio=bio,
        )
    except OnboardError as exc:
        return HTMLResponse(
            f'<div class="rounded-xl bg-rose-500/15 px-5 py-4 text-rose-300">❌ {exc}</div>',
            status_code=400,
        )
    await session.commit()
    return RedirectResponse(
        url=f"/lessio/miniapp/cabinet?tgWebAppData={init_data or ''}", status_code=302
    )


@router.get("/miniapp/check-slug", include_in_schema=False)
async def miniapp_check_slug(
    slug: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> JSONResponse:
    """Live-validation для onboard формы. Возвращает `{available: bool, reason: str?}`."""
    if not slug:
        return JSONResponse({"available": False, "reason": "пусто"})
    available = await is_slug_available(session, slug)
    if not available:
        # Можно разделить «формат неверный» vs «занят», но для UX достаточно одного.
        return JSONResponse(
            {
                "available": False,
                "reason": (
                    "формат: 3-50 символов, латиница+цифры+- и _, начинается с буквы/цифры"
                    if not _slug_format_ok(slug)
                    else f"«{slug}» занят, выберите другой"
                ),
            }
        )
    return JSONResponse({"available": True})


def _slug_format_ok(slug: str) -> bool:
    """Шорткат вокруг validate_slug — не делаем DB-запрос если формат не подходит."""
    from app.lessio.service import validate_slug

    return validate_slug(slug)


# ── Booking endpoints — заглушки на 503 (MVP-фаза) ───────────────────────────


@router.get("/miniapp/book/{slug}", include_in_schema=False)
async def miniapp_book_page(slug: str) -> Response:
    """Публичная booking-страница. MVP — заглушка."""
    raise HTTPException(503, "Booking откроется после фазы валидации (≥100 waitlist).")


@router.post("/miniapp/book/{slug}/confirm", include_in_schema=False)
async def miniapp_book_confirm(slug: str) -> Response:
    """Создать Stars-invoice для booking'а. MVP — заглушка."""
    raise HTTPException(503, "Booking откроется после фазы валидации.")


@router.get("/miniapp/booking/{booking_id}/status", include_in_schema=False)
async def miniapp_booking_status(booking_id: str) -> Response:
    """Polling-статус booking'а. MVP — заглушка."""
    raise HTTPException(503, "Booking откроется после фазы валидации.")
