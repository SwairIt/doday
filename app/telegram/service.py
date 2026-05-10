"""Сервис связи Doday-юзера с Telegram-чатом."""

import secrets
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.telegram.models import TelegramLink


async def request_link_token(session: AsyncSession, user_id: UUID) -> tuple[str, str]:
    """Generate fresh link-token for user. Идемпотентно — re-call → новый токен.

    Возвращает (token, deeplink_url). Deeplink требует TELEGRAM_BOT_USERNAME
    из env; если пустой — вернёт URL-заглушку без username.
    """
    from app.config import get_settings

    token = secrets.token_urlsafe(24)
    existing = (
        await session.execute(select(TelegramLink).where(TelegramLink.user_id == user_id))
    ).scalar_one_or_none()
    if existing is None:
        link = TelegramLink(user_id=user_id, chat_id=None, link_token=token)
        session.add(link)
    else:
        # Reset chat_id only if not yet linked. Otherwise keep current link
        # active and just refresh the token (юзер хочет перепривязать к новому чату).
        existing.link_token = token
        if existing.chat_id is None:
            existing.linked_at = None
    await session.commit()

    settings = get_settings()
    bot_username = settings.telegram_bot_username
    deeplink = f"https://t.me/{bot_username}?start={token}" if bot_username else f"?start={token}"
    return token, deeplink


async def complete_link(session: AsyncSession, link_token: str, chat_id: int) -> User | None:
    """Bot calls this when юзер пишет /start <token>.
    Заполняет chat_id, обнуляет link_token. Возвращает User или None."""
    link = (
        await session.execute(select(TelegramLink).where(TelegramLink.link_token == link_token))
    ).scalar_one_or_none()
    if link is None:
        return None
    # Если этот chat_id уже привязан к ДРУГОМУ юзеру — отказ (одновременно к
    # одному юзеру можно из одного чата).
    other = (
        await session.execute(
            select(TelegramLink).where(
                TelegramLink.chat_id == chat_id, TelegramLink.user_id != link.user_id
            )
        )
    ).scalar_one_or_none()
    if other is not None:
        return None
    link.chat_id = chat_id
    link.link_token = None
    link.linked_at = datetime.now(UTC)
    await session.commit()
    user = await session.get(User, link.user_id)
    return user


async def get_user_by_chat(session: AsyncSession, chat_id: int) -> User | None:
    """Используется ботом чтобы понять кто пишет."""
    link = (
        await session.execute(select(TelegramLink).where(TelegramLink.chat_id == chat_id))
    ).scalar_one_or_none()
    if link is None or link.chat_id is None:
        return None
    return await session.get(User, link.user_id)


async def get_link_for_user(session: AsyncSession, user_id: UUID) -> TelegramLink | None:
    return (
        await session.execute(select(TelegramLink).where(TelegramLink.user_id == user_id))
    ).scalar_one_or_none()


async def unlink(session: AsyncSession, user_id: UUID) -> bool:
    link = await get_link_for_user(session, user_id)
    if link is None:
        return False
    await session.delete(link)
    await session.commit()
    return True
