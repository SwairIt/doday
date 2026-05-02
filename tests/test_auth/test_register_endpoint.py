"""Integration tests for the /auth/register HTTP endpoint."""

from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User


@pytest.fixture(autouse=True)
def _no_smtp() -> Iterator[AsyncMock]:
    """Mock the SMTP call — no test should hit a real mail server."""
    with patch("app.auth.email.aiosmtplib.send", new=AsyncMock()) as m:
        yield m


async def test_register_creates_user_and_sends_email(
    client: AsyncClient,
    db_session: AsyncSession,
    _no_smtp: AsyncMock,
) -> None:
    response = await client.post(
        "/auth/register",
        data={
            "email": "kid@school.ru",
            "password": "strongpass123",
            "agree_privacy": "on",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/auth/verify-pending"

    result = await db_session.execute(select(User).where(User.email == "kid@school.ru"))
    user = result.scalar_one()
    assert user.email_verified_at is None

    _no_smtp.assert_awaited_once()


async def test_register_duplicate_email(
    client: AsyncClient,
    _no_smtp: AsyncMock,
) -> None:
    payload = {
        "email": "dup@school.ru",
        "password": "strongpass123",
        "agree_privacy": "on",
    }
    first = await client.post("/auth/register", data=payload)
    assert first.status_code == 303

    second = await client.post("/auth/register", data=payload)
    assert second.status_code == 400
    assert "уже зарегистрирован" in second.text


async def test_register_without_privacy_consent_blocked(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/register",
        data={
            "email": "kid@school.ru",
            "password": "strongpass123",
            # agree_privacy is missing — checkbox not checked
        },
    )
    assert response.status_code == 400
    assert "согласие" in response.text.lower()


async def test_register_short_password_returns_form_error(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/register",
        data={
            "email": "kid@school.ru",
            "password": "short",
            "agree_privacy": "on",
        },
    )
    assert response.status_code == 400


async def test_register_form_renders(client: AsyncClient) -> None:
    response = await client.get("/auth/register")
    assert response.status_code == 200
    assert "Регистрация" in response.text
    assert "agree_privacy" in response.text


async def test_verify_pending_renders(client: AsyncClient) -> None:
    response = await client.get("/auth/verify-pending")
    assert response.status_code == 200
    assert "Проверь почту" in response.text


async def test_privacy_renders(client: AsyncClient) -> None:
    response = await client.get("/privacy")
    assert response.status_code == 200
    assert "Политика" in response.text
