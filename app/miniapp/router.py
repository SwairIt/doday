"""Mini App routes — auth + (later) UI screens."""

from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.auth.deps import DbSession
from app.config import get_settings
from app.miniapp.auth import get_telegram_user_id, validate_init_data
from app.telegram.models import TelegramLink

router = APIRouter(prefix="/miniapp", tags=["miniapp"])


class AuthIn(BaseModel):
    init_data: str


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
