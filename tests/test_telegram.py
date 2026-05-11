"""Tests for Telegram-link service + endpoint."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.schemas import RegisterIn
from app.auth.service import register_user
from app.telegram.models import TelegramLink
from app.telegram.service import (
    complete_link,
    get_link_for_user,
    get_user_by_chat,
    request_link_token,
    unlink,
)


@pytest.fixture
async def verified_user(db_session: AsyncSession) -> AsyncIterator[User]:
    user = await register_user(
        db_session, RegisterIn(email="tg@example.com", password="strongpass123")
    )
    user.email_verified_at = datetime.now(UTC)
    await db_session.commit()
    await db_session.refresh(user)
    yield user


# ---- service-layer tests ----


async def test_request_link_token_creates_row(
    db_session: AsyncSession, verified_user: User
) -> None:
    token, deeplink = await request_link_token(db_session, verified_user.id)
    assert len(token) >= 24
    assert deeplink.startswith("?start=") or deeplink.startswith("https://t.me/")
    link = await get_link_for_user(db_session, verified_user.id)
    assert link is not None
    assert link.link_token == token
    assert link.chat_id is None


async def test_request_link_token_idempotent(db_session: AsyncSession, verified_user: User) -> None:
    """Re-call generates new token, replaces old (one row per user)."""
    t1, _ = await request_link_token(db_session, verified_user.id)
    t2, _ = await request_link_token(db_session, verified_user.id)
    assert t1 != t2
    link = await get_link_for_user(db_session, verified_user.id)
    assert link is not None
    assert link.link_token == t2


async def test_complete_link_sets_chat_id(db_session: AsyncSession, verified_user: User) -> None:
    token, _ = await request_link_token(db_session, verified_user.id)
    chat_id = 123456789
    user = await complete_link(db_session, token, chat_id)
    assert user is not None
    assert user.id == verified_user.id
    link = await get_link_for_user(db_session, verified_user.id)
    assert link is not None
    assert link.chat_id == chat_id
    assert link.link_token is None  # cleared after use
    assert link.linked_at is not None


async def test_complete_link_invalid_token(db_session: AsyncSession) -> None:
    user = await complete_link(db_session, "nonexistent-token-123", 999)
    assert user is None


async def test_complete_link_chat_collision_returns_none(
    db_session: AsyncSession, verified_user: User
) -> None:
    """If chat_id already linked to ANOTHER user, refuse."""
    other = await register_user(
        db_session, RegisterIn(email="other@example.com", password="strongpass123")
    )
    other.email_verified_at = datetime.now(UTC)
    await db_session.commit()

    chat_id = 555
    # First user links chat 555
    token1, _ = await request_link_token(db_session, verified_user.id)
    u1 = await complete_link(db_session, token1, chat_id)
    assert u1 is not None
    # Second user tries to link same chat → refused
    token2, _ = await request_link_token(db_session, other.id)
    u2 = await complete_link(db_session, token2, chat_id)
    assert u2 is None


async def test_get_user_by_chat(db_session: AsyncSession, verified_user: User) -> None:
    token, _ = await request_link_token(db_session, verified_user.id)
    await complete_link(db_session, token, 42)
    found = await get_user_by_chat(db_session, 42)
    assert found is not None
    assert found.id == verified_user.id
    not_found = await get_user_by_chat(db_session, 99999)
    assert not_found is None


async def test_unlink(db_session: AsyncSession, verified_user: User) -> None:
    token, _ = await request_link_token(db_session, verified_user.id)
    await complete_link(db_session, token, 100)
    assert await unlink(db_session, verified_user.id) is True
    assert await unlink(db_session, verified_user.id) is False  # already gone
    assert await get_link_for_user(db_session, verified_user.id) is None


# ---- HTTP endpoint tests ----


async def test_endpoint_requires_auth(client: AsyncClient) -> None:
    r = await client.post("/api/profile/telegram-link")
    assert r.status_code == 401


async def test_endpoint_returns_token_and_deeplink(
    logged_in_client: AsyncClient,
) -> None:
    r = await logged_in_client.post("/api/profile/telegram-link")
    assert r.status_code == 200
    body = r.json()
    assert "token" in body
    assert "deeplink" in body


async def test_unlink_endpoint(db_session: AsyncSession, logged_in_client: AsyncClient) -> None:
    # Get token first
    r1 = await logged_in_client.post("/api/profile/telegram-link")
    assert r1.status_code == 200
    # Then unlink
    r2 = await logged_in_client.delete("/api/profile/telegram-link")
    assert r2.status_code == 204


# ---- Telegram link table sanity ----


async def test_telegram_links_table_exists(db_session: AsyncSession) -> None:
    from sqlalchemy import select

    result = await db_session.execute(select(TelegramLink))
    rows = result.scalars().all()
    assert isinstance(rows, list)


def test_force_ipv4_resolve_patches_socket() -> None:
    """Sanity: patch заменяет socket.getaddrinfo и закрывает family=AF_INET."""
    import socket

    from app.telegram.bot import _force_ipv4_resolve

    orig = socket.getaddrinfo
    try:
        _force_ipv4_resolve()
        # после патча — функция другая (closure), и при вызове передаст
        # family=AF_INET даже если caller не указал.
        assert socket.getaddrinfo is not orig
        # реальный resolve локалхоста, чтобы убедиться что AF_INET-ответ
        result = socket.getaddrinfo("127.0.0.1", 80)
        assert all(r[0] == socket.AF_INET for r in result)
    finally:
        socket.getaddrinfo = orig
