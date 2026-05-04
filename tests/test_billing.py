"""Tests for tier model + trial logic + project limit enforcement."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User


async def test_billing_me_returns_trial(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/api/billing/me")
    assert response.status_code == 200
    body = response.json()
    assert body["tier"] == "free"
    assert body["effective_tier"] == "pro"  # trial defaults to pro features
    assert body["trial_active"] is True
    assert body["trial_days_remaining"] >= 1
    assert body["limits"]["max_active_projects"] is None  # pro = unlimited


async def test_change_tier_to_pro(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post("/api/billing/change-tier", json={"tier": "pro"})
    assert response.status_code == 200
    assert response.json()["tier"] == "pro"
    assert response.json()["effective_tier"] == "pro"


async def test_tier_catalog_listed(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/api/billing/tiers")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"free", "pro", "team"}
    assert body["free"]["max_active_projects"] == 5
    assert body["pro"]["max_active_projects"] is None


async def _expire_trial(db_session: AsyncSession) -> None:
    await db_session.execute(
        update(User).values(trial_ends_at=datetime.now(UTC) - timedelta(days=1))
    )
    await db_session.commit()


async def test_project_limit_blocks_after_trial_expires(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    await _expire_trial(db_session)

    for i in range(5):
        r = await logged_in_client.post("/api/projects", json={"name": f"P{i}"})
        assert r.status_code == 201, r.text

    r = await logged_in_client.post("/api/projects", json={"name": "P6"})
    assert r.status_code == 402
    assert "Free" in r.json()["detail"]


async def test_project_limit_does_not_count_archived_or_inbox(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    await _expire_trial(db_session)

    proj_ids = []
    for i in range(5):
        proj = (await logged_in_client.post("/api/projects", json={"name": f"P{i}"})).json()
        proj_ids.append(proj["id"])

    await logged_in_client.patch(f"/api/projects/{proj_ids[0]}", json={"is_archived": True})
    r = await logged_in_client.post("/api/projects", json={"name": "Replacement"})
    assert r.status_code == 201


async def test_pro_tier_has_no_project_limit(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    await _expire_trial(db_session)
    await logged_in_client.post("/api/billing/change-tier", json={"tier": "pro"})

    for i in range(8):
        r = await logged_in_client.post("/api/projects", json={"name": f"Many{i}"})
        assert r.status_code == 201, f"failed at {i}: {r.text}"
