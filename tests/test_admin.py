"""Tests for admin module — complaints + admin endpoints + token-secured access."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import Complaint
from app.admin.service import (
    admin_stats,
    create_complaint,
    delete_complaint,
    list_complaints,
    update_complaint,
)
from app.auth.models import User
from app.auth.schemas import RegisterIn
from app.auth.service import register_user


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> AsyncIterator[User]:
    user = await register_user(
        db_session, RegisterIn(email="admin@example.com", password="strongpass123")
    )
    user.email_verified_at = datetime.now(UTC)
    user.is_admin = True
    await db_session.commit()
    await db_session.refresh(user)
    yield user


@pytest.fixture
async def regular_user(db_session: AsyncSession) -> AsyncIterator[User]:
    user = await register_user(
        db_session, RegisterIn(email="reg@example.com", password="strongpass123")
    )
    user.email_verified_at = datetime.now(UTC)
    await db_session.commit()
    await db_session.refresh(user)
    yield user


# --- service-layer tests -----------------------------------------------------


async def test_create_complaint_persists(db_session: AsyncSession, regular_user: User) -> None:
    c = await create_complaint(
        db_session,
        user_id=regular_user.id,
        body="кнопка X не работает",
        page_url="/doday/app/today",
        viewport="375x800",
        user_agent="Mozilla/5.0",
    )
    assert c.id is not None
    assert c.body == "кнопка X не работает"
    assert c.status == "open"
    assert c.priority == "normal"


async def test_create_complaint_rejects_empty(db_session: AsyncSession, regular_user: User) -> None:
    with pytest.raises(ValueError):
        await create_complaint(
            db_session,
            user_id=regular_user.id,
            body="   ",
            page_url=None,
            viewport=None,
            user_agent=None,
        )


async def test_list_complaints_filters_by_status(
    db_session: AsyncSession, regular_user: User
) -> None:
    c1 = await create_complaint(
        db_session,
        user_id=regular_user.id,
        body="open one",
        page_url=None,
        viewport=None,
        user_agent=None,
    )
    c2 = await create_complaint(
        db_session,
        user_id=regular_user.id,
        body="resolved one",
        page_url=None,
        viewport=None,
        user_agent=None,
    )
    await update_complaint(db_session, c2.id, status="resolved")
    open_only = await list_complaints(db_session, status_filter="open")
    resolved_only = await list_complaints(db_session, status_filter="resolved")
    assert {c.id for c in open_only} == {c1.id}
    assert {c.id for c in resolved_only} == {c2.id}


async def test_update_complaint_sets_resolved_at(
    db_session: AsyncSession, regular_user: User
) -> None:
    c = await create_complaint(
        db_session,
        user_id=regular_user.id,
        body="x",
        page_url=None,
        viewport=None,
        user_agent=None,
    )
    assert c.resolved_at is None
    updated = await update_complaint(db_session, c.id, status="resolved")
    assert updated is not None
    assert updated.resolved_at is not None
    # Re-open clears resolved_at
    reopened = await update_complaint(db_session, c.id, status="open")
    assert reopened is not None
    assert reopened.resolved_at is None


async def test_delete_complaint(db_session: AsyncSession, regular_user: User) -> None:
    c = await create_complaint(
        db_session,
        user_id=regular_user.id,
        body="x",
        page_url=None,
        viewport=None,
        user_agent=None,
    )
    assert await delete_complaint(db_session, c.id) is True
    assert await delete_complaint(db_session, c.id) is False


async def test_admin_stats_returns_counts(db_session: AsyncSession, admin_user: User) -> None:
    stats = await admin_stats(db_session)
    assert stats["users_total"] >= 1
    assert "complaints_open" in stats
    assert "tasks_today" in stats


# --- HTTP endpoints ----------------------------------------------------------


async def test_submit_complaint_requires_login(client: AsyncClient) -> None:
    r = await client.post("/api/complaints", json={"body": "test"})
    assert r.status_code == 401


async def test_submit_complaint_logged_in(logged_in_client: AsyncClient) -> None:
    r = await logged_in_client.post(
        "/api/complaints",
        json={"body": "что-то сломалось", "page_url": "/doday/app/today", "viewport": "375x800"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["body"] == "что-то сломалось"
    assert body["status"] == "open"


async def test_admin_endpoints_require_admin(logged_in_client: AsyncClient) -> None:
    """Regular user gets 403 from admin endpoints."""
    r = await logged_in_client.get("/api/admin/complaints")
    assert r.status_code == 403


async def test_admin_lists_complaints(db_session: AsyncSession, client: AsyncClient) -> None:
    """Login as admin, fetch complaints list."""
    user = await register_user(
        db_session, RegisterIn(email="adm-list@example.com", password="strongpass123")
    )
    user.email_verified_at = datetime.now(UTC)
    user.is_admin = True
    await db_session.commit()
    await create_complaint(
        db_session,
        user_id=user.id,
        body="hello",
        page_url=None,
        viewport=None,
        user_agent=None,
    )
    login = await client.post(
        "/auth/login",
        data={"email": "adm-list@example.com", "password": "strongpass123"},
    )
    assert login.status_code == 303
    r = await client.get("/api/admin/complaints")
    assert r.status_code == 200
    assert len(r.json()) >= 1


async def test_admin_token_endpoint_without_token_503(client: AsyncClient) -> None:
    r = await client.get("/api/admin/complaints.json")
    # Settings.admin_token is empty in tests → 503.
    assert r.status_code in (403, 503)


# --- root view requires admin ----------------------------------------------


async def test_root_view_requires_admin(logged_in_client: AsyncClient) -> None:
    r = await logged_in_client.get("/doday/app/root")
    assert r.status_code == 403


async def test_root_view_loads_for_admin(db_session: AsyncSession, client: AsyncClient) -> None:
    user = await register_user(
        db_session, RegisterIn(email="adm-root@example.com", password="strongpass123")
    )
    user.email_verified_at = datetime.now(UTC)
    user.is_admin = True
    await db_session.commit()
    login = await client.post(
        "/auth/login",
        data={"email": "adm-root@example.com", "password": "strongpass123"},
    )
    assert login.status_code == 303
    r = await client.get("/doday/app/root")
    assert r.status_code == 200
    assert "Root" in r.text
    assert "Жалоб" in r.text


# --- Complaint model sanity --------------------------------------------------


async def test_complaint_table_exists(db_session: AsyncSession) -> None:
    """If migration didn't run, this select fails."""
    from sqlalchemy import select

    result = await db_session.execute(select(Complaint))
    rows = result.scalars().all()
    assert isinstance(rows, list)
