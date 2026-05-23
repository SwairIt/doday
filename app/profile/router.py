"""Profile management — account deletion + password change."""

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


@router.post("/morning-digest")
async def update_morning_digest(
    user: RequiredUser,
    session: DbSession,
    enabled: Annotated[str, Form()],
) -> dict[str, bool]:
    """Toggle the morning digest opt-in. Pro+ only (TIERS["pro"]["email_digest"])."""
    from app.billing.service import require_pro

    new_value = enabled.lower() in ("1", "true", "on", "yes")
    if new_value:
        # Allow turning OFF without check (e.g., trial expired user wants to disable).
        require_pro(user, "Утренний email-дайджест")
        # Digest goes to email, so it needs a verified, deliverable address.
        if user.email_verified_at is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Сначала подтверди email — дайджест приходит на почту.",
            )
    user.morning_digest_enabled = new_value
    await session.commit()
    return {"enabled": new_value}


@router.post("/telegram-link")
async def request_telegram_link(user: RequiredUser, session: DbSession) -> dict[str, str]:
    """Сгенерировать одноразовый токен + deeplink на бот. Pro+ only."""
    from app.billing.service import require_pro
    from app.telegram.service import request_link_token

    require_pro(user, "Telegram-бот")
    token, deeplink = await request_link_token(session, user.id)
    return {"token": token, "deeplink": deeplink}


@router.delete("/telegram-link", status_code=204)
async def remove_telegram_link(user: RequiredUser, session: DbSession) -> None:
    """Отвязать Telegram-чат от аккаунта."""
    from app.telegram.service import unlink

    await unlink(session, user.id)


@router.post("/experiments/{key}")
async def toggle_experiment(
    key: str,
    user: RequiredUser,
    session: DbSession,
    enabled: Annotated[str, Form()],
) -> dict[str, bool]:
    """Toggle an experimental feature flag for the signed-in user.

    Unknown keys are rejected (422) so a typo in the UI doesn't silently store
    a dead flag in the JSONB."""
    from app.experiments.service import BY_KEY

    if key not in BY_KEY:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "неизвестный эксперимент")
    on = enabled.lower() in ("1", "true", "on", "yes")
    flags = dict(user.experiments or {})
    flags[key] = on
    user.experiments = flags
    await session.commit()
    return {"enabled": on}


@router.get("/share-link")
async def get_share_link(user: RequiredUser) -> dict[str, str]:
    """Return a public read-only progress link for the signed-in user (for parents)."""
    from app.config import get_settings
    from app.share.service import make_progress_token

    token = make_progress_token(user.id)
    base = get_settings().app_base_url.rstrip("/")
    return {"url": f"{base}/share/progress/{token}"}


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
