"""Tests for the audience selector at registration (school/company/personal)."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rate_limit import reset_all
from app.auth.service import get_user_by_email


@pytest.fixture(autouse=True)
def _no_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests don't run a real SMTP — just record the call."""

    async def _stub(to: str, verification_url: str) -> None:
        return None

    monkeypatch.setattr("app.auth.router.send_verification_email", _stub)
    reset_all()


async def test_register_with_school_audience(client: AsyncClient, db_session: AsyncSession) -> None:
    response = await client.post(
        "/auth/register",
        data={
            "email": "pupil@school.example",
            "password": "verysecret123",
            "agree_privacy": "on",
            "audience": "school",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    user = await get_user_by_email(db_session, "pupil@school.example")
    assert user is not None
    assert user.audience == "school"


async def test_register_audience_optional(client: AsyncClient, db_session: AsyncSession) -> None:
    response = await client.post(
        "/auth/register",
        data={
            "email": "skip@example.com",
            "password": "verysecret123",
            "agree_privacy": "on",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    user = await get_user_by_email(db_session, "skip@example.com")
    assert user is not None
    assert user.audience is None


async def test_register_invalid_audience_treated_as_none(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post(
        "/auth/register",
        data={
            "email": "weird@example.com",
            "password": "verysecret123",
            "agree_privacy": "on",
            "audience": "alien",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    user = await get_user_by_email(db_session, "weird@example.com")
    assert user is not None
    assert user.audience is None


async def test_register_company_audience(client: AsyncClient, db_session: AsyncSession) -> None:
    response = await client.post(
        "/auth/register",
        data={
            "email": "biz@co.example",
            "password": "verysecret123",
            "agree_privacy": "on",
            "audience": "company",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    user = await get_user_by_email(db_session, "biz@co.example")
    assert user is not None
    assert user.audience == "company"


async def test_audience_picker_renders(client: AsyncClient) -> None:
    body = (await client.get("/auth/register")).text
    assert "Для чего туду-лист?" in body
    assert "🎓" in body and "💼" in body and "🌱" in body
    assert 'name="audience"' in body
    assert 'value="school"' in body
    assert 'value="company"' in body
    assert 'value="personal"' in body
