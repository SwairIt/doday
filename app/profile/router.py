"""Profile management — account deletion + audience switching + password change."""

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import delete

from app.auth.deps import DbSession, RequiredUser
from app.auth.models import User
from app.auth.security import hash_password, verify_password

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.post("/delete")
async def delete_account(request: Request, user: RequiredUser, session: DbSession) -> Response:
    """Cascade-delete the user. Tasks/projects/labels go with them via ON DELETE CASCADE."""
    await session.execute(delete(User).where(User.id == user.id))
    await session.commit()
    request.session.clear()
    return RedirectResponse(url="/?deleted=1", status_code=303)


@router.post("/audience")
async def update_audience(
    user: RequiredUser,
    session: DbSession,
    audience: Annotated[str, Form()],
) -> dict[str, str | None]:
    """Switch the user's audience (school / company / personal / clear).

    Empty string clears the choice; the audience-specific widgets revert to
    the generic experience until a new value is picked.
    """
    if audience == "":
        new_value: str | None = None
    elif audience in ("school", "company", "personal"):
        new_value = audience
    else:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "неизвестная аудитория")
    user.audience = new_value
    await session.commit()
    return {"audience": new_value}


@router.post("/morning-digest")
async def update_morning_digest(
    user: RequiredUser,
    session: DbSession,
    enabled: Annotated[str, Form()],
) -> dict[str, bool]:
    """Toggle the morning digest opt-in for the signed-in user."""
    new_value = enabled.lower() in ("1", "true", "on", "yes")
    user.morning_digest_enabled = new_value
    await session.commit()
    return {"enabled": new_value}


@router.post("/telegram-link")
async def request_telegram_link(user: RequiredUser, session: DbSession) -> dict[str, str]:
    """Сгенерировать одноразовый токен + deeplink на бот для привязки чата."""
    from app.telegram.service import request_link_token

    token, deeplink = await request_link_token(session, user.id)
    return {"token": token, "deeplink": deeplink}


@router.delete("/telegram-link", status_code=204)
async def remove_telegram_link(user: RequiredUser, session: DbSession) -> None:
    """Отвязать Telegram-чат от аккаунта."""
    from app.telegram.service import unlink

    await unlink(session, user.id)


@router.post("/password")
async def change_password(
    user: RequiredUser,
    session: DbSession,
    current_password: Annotated[str, Form()],
    new_password: Annotated[str, Form()],
) -> dict[str, str]:
    """Change the signed-in user's password (requires current password)."""
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Текущий пароль неверный")
    if len(new_password) < 8:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Минимум 8 символов")
    if new_password == current_password:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Новый пароль совпадает с текущим"
        )
    user.password_hash = hash_password(new_password)
    await session.commit()
    return {"status": "ok"}
