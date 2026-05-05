"""Tests for the mood tracker."""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.security import hash_password


async def _login_personal(client: AsyncClient, db_session: AsyncSession) -> None:
    user = User(
        email="mood-personal@x.test",
        password_hash=hash_password("strongpass123"),
        audience="personal",
        email_verified_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.commit()
    response = await client.post(
        "/auth/login",
        data={"email": "mood-personal@x.test", "password": "strongpass123"},
    )
    assert response.status_code == 303


async def test_today_initially_empty(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/api/mood/today")).json()
    assert body["recorded"] is False


async def test_upsert_today_with_score(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post("/api/mood/today", data={"score": "4"})
    assert response.status_code == 200
    body = response.json()
    assert body["score"] == 4


async def test_upsert_with_note(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/mood/today", data={"score": "5", "note": "продуктивный день"}
    )
    body = response.json()
    assert body["score"] == 5
    assert "продуктивный" in (body["note"] or "")


async def test_upsert_replaces_existing(logged_in_client: AsyncClient) -> None:
    await logged_in_client.post("/api/mood/today", data={"score": "2"})
    response = await logged_in_client.post("/api/mood/today", data={"score": "5"})
    body = response.json()
    assert body["score"] == 5


async def test_invalid_score_rejected(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post("/api/mood/today", data={"score": "9"})
    assert response.status_code == 422


async def test_history_returns_entries(logged_in_client: AsyncClient) -> None:
    await logged_in_client.post("/api/mood/today", data={"score": "3", "note": "ok"})
    history = (await logged_in_client.get("/api/mood/history")).json()
    assert len(history) == 1
    assert history[0]["score"] == 3


async def test_widget_visible_for_personal(client: AsyncClient, db_session: AsyncSession) -> None:
    await _login_personal(client, db_session)
    body = (await client.get("/app/today")).text
    assert "Настроение дня" in body
    assert "/api/mood/today" in body


async def test_widget_hidden_for_company(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/today")).text
    # logged_in_client has no audience set; widget is gated on 'personal'
    assert "Настроение дня" not in body
