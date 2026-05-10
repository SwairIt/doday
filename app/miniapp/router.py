"""Mini App routes — auth + UI screens (5 bottom-nav tabs)."""

from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select

from app.auth.deps import CurrentUser, DbSession
from app.config import get_settings
from app.miniapp.auth import get_telegram_user_id, validate_init_data
from app.miniapp.static import MINIAPP_JS
from app.telegram.models import TelegramLink

router = APIRouter(prefix="/miniapp", tags=["miniapp"])
templates = Jinja2Templates(directory="app/templates")


def _ctx(request: Request, current_user: object = None) -> dict[str, object]:
    """Common Jinja-context for miniapp pages (current_path для active-таба)."""
    return {"current_path": request.url.path, "current_user": current_user}


class AuthIn(BaseModel):
    init_data: str


@router.get("/assets/miniapp.js")
async def miniapp_js() -> Response:
    """Inline JS-bundle для Mini App. Cache на 1 час (короткий — пока итерируем
    дизайн), потом увеличим."""
    return Response(
        content=MINIAPP_JS,
        media_type="application/javascript; charset=utf-8",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.post("/auth")
async def auth(
    request: Request,
    payload: AuthIn,
    session: DbSession,
) -> JSONResponse:
    """Validate Telegram WebApp initData → set session cookie → return user info.

    Flow:
    1. Парсим initData, проверяем HMAC bot-token'ом
    2. Если невалидно → 401 {"error": "invalid_init_data"}
    3. Достаём Telegram user_id, ищем в telegram_links (chat_id == user_id)
    4. Если не привязан → 401 {"need_link": true, "telegram_user_id": ...}
    5. Если привязан → ставим session["user_id"] → 200 {"ok": true}
    """
    settings = get_settings()
    if not settings.telegram_bot_token:
        return JSONResponse(
            {"error": "bot_not_configured"},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    parsed = validate_init_data(payload.init_data, settings.telegram_bot_token)
    if parsed is None:
        return JSONResponse(
            {"error": "invalid_init_data"}, status_code=status.HTTP_401_UNAUTHORIZED
        )

    tg_user_id = get_telegram_user_id(parsed)
    if tg_user_id is None:
        return JSONResponse({"error": "no_user_field"}, status_code=status.HTTP_401_UNAUTHORIZED)

    # Telegram-личка = chat_id равен user_id; в групповых чатах было бы по-другому,
    # но Mini App открывается всегда в личке/инлайне.
    link = (
        await session.execute(select(TelegramLink).where(TelegramLink.chat_id == tg_user_id))
    ).scalar_one_or_none()
    if link is None or link.user_id is None:
        return JSONResponse(
            {"need_link": True, "telegram_user_id": tg_user_id},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    request.session["user_id"] = str(link.user_id)
    return JSONResponse({"ok": True, "user_id": str(link.user_id)})


# --- UI screens (5 bottom-nav tabs) -----------------------------------------
#
# Все требуют залогиненного юзера. Если session-cookie нет — редирект на
# /miniapp/link (там клиентский JS попытается auth через initData; если не
# Telegram — покажет инструкцию как привязать аккаунт).


def _require_user_or_redirect(user: object, telegram_user_id: int | None = None) -> Response | None:
    """Если user не залогинен — Response с редиректом на link-screen, иначе None."""
    if user is not None:
        return None
    url = "/miniapp/link"
    if telegram_user_id is not None:
        url += f"?telegram_user_id={telegram_user_id}"
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/", response_class=HTMLResponse)
async def today(request: Request, user: CurrentUser) -> Response:
    redir = _require_user_or_redirect(user)
    if redir is not None:
        return redir
    return templates.TemplateResponse(request, "miniapp/today.html", _ctx(request, user))


@router.get("/inbox", response_class=HTMLResponse)
async def inbox(request: Request, user: CurrentUser) -> Response:
    redir = _require_user_or_redirect(user)
    if redir is not None:
        return redir
    return templates.TemplateResponse(request, "miniapp/inbox.html", _ctx(request, user))


@router.get("/calendar", response_class=HTMLResponse)
async def calendar(request: Request, user: CurrentUser) -> Response:
    redir = _require_user_or_redirect(user)
    if redir is not None:
        return redir
    return templates.TemplateResponse(request, "miniapp/calendar.html", _ctx(request, user))


@router.get("/projects", response_class=HTMLResponse)
async def projects(request: Request, user: CurrentUser) -> Response:
    redir = _require_user_or_redirect(user)
    if redir is not None:
        return redir
    return templates.TemplateResponse(request, "miniapp/projects.html", _ctx(request, user))


@router.get("/me", response_class=HTMLResponse)
async def me(request: Request, user: CurrentUser) -> Response:
    redir = _require_user_or_redirect(user)
    if redir is not None:
        return redir
    return templates.TemplateResponse(request, "miniapp/me.html", _ctx(request, user))


@router.get("/link", response_class=HTMLResponse)
async def link_onboarding(
    request: Request,
    user: CurrentUser,
    telegram_user_id: int | None = None,
) -> Response:
    """Onboarding-экран. Если юзер УЖЕ залогинен — редирект на Today (не нужен
    onboarding). Иначе — рендерим инструкцию по привязке."""
    if user is not None:
        return RedirectResponse(url="/miniapp/", status_code=status.HTTP_303_SEE_OTHER)
    ctx = _ctx(request, user)
    ctx["telegram_user_id"] = telegram_user_id
    return templates.TemplateResponse(request, "miniapp/link.html", ctx)
