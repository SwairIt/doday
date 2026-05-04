"""Tests for the company standup report endpoint + widget gating."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.security import hash_password


async def _make_user(session: AsyncSession, email: str, audience: str) -> None:
    user = User(
        email=email,
        password_hash=hash_password("strongpass123"),
        audience=audience,
        email_verified_at=datetime.now(UTC),
    )
    session.add(user)
    await session.commit()


async def test_standup_returns_three_buckets(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/api/company/standup")
    assert response.status_code == 200
    body = response.json()
    assert "yesterday" in body
    assert "today" in body
    assert "blockers" in body


async def test_today_task_appears_in_today_bucket(logged_in_client: AsyncClient) -> None:
    today_iso = datetime.now(UTC).date().isoformat() + "T15:00:00Z"
    await logged_in_client.post("/api/tasks", json={"title": "Stand up demo", "due_at": today_iso})
    body = (await logged_in_client.get("/api/company/standup")).json()
    titles = [t["title"] for t in body["today"]]
    assert "Stand up demo" in titles


async def test_overdue_appears_in_blockers(logged_in_client: AsyncClient) -> None:
    yesterday = (datetime.now(UTC).date() - timedelta(days=2)).isoformat() + "T10:00:00Z"
    await logged_in_client.post("/api/tasks", json={"title": "Overdue thing", "due_at": yesterday})
    body = (await logged_in_client.get("/api/company/standup")).json()
    titles = [t["title"] for t in body["blockers"]]
    assert "Overdue thing" in titles


async def test_p1_appears_in_blockers_even_without_due(logged_in_client: AsyncClient) -> None:
    await logged_in_client.post("/api/tasks", json={"title": "Critical bug", "priority": "p1"})
    body = (await logged_in_client.get("/api/company/standup")).json()
    titles = [t["title"] for t in body["blockers"]]
    assert "Critical bug" in titles


async def test_markdown_endpoint_renders_three_sections(logged_in_client: AsyncClient) -> None:
    today_iso = datetime.now(UTC).date().isoformat() + "T12:00:00Z"
    await logged_in_client.post("/api/tasks", json={"title": "Plan release", "due_at": today_iso})
    response = await logged_in_client.get("/api/company/standup.md")
    assert response.status_code == 200
    body = response.text
    assert "Вчера:" in body
    assert "Сегодня:" in body
    assert "Блокеры:" in body
    assert "Plan release" in body


async def test_today_widget_only_for_company(client: AsyncClient, db_session: AsyncSession) -> None:
    await _make_user(db_session, "schooler@x.test", "school")
    response = await client.post(
        "/auth/login", data={"email": "schooler@x.test", "password": "strongpass123"}
    )
    assert response.status_code == 303
    body = (await client.get("/app/today")).text
    # standup widget is gated on audience=='company'
    assert "Сборка стендапа" not in body
    # but school audience should see today's schedule widget
    assert "Расписание на сегодня" in body


async def test_today_widget_visible_for_company(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _make_user(db_session, "biz@x.test", "company")
    response = await client.post(
        "/auth/login", data={"email": "biz@x.test", "password": "strongpass123"}
    )
    assert response.status_code == 303
    body = (await client.get("/app/today")).text
    assert "Сборка стендапа" in body
    assert "/api/company/standup" in body
