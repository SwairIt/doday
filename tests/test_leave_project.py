"""Tests for «Покинуть проект» (member self-leave) — POST /api/projects/{id}/leave."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.projects.membership import add_member, get_role
from app.projects.service import create_project


async def _owner(db_session: AsyncSession) -> User:
    return (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()


async def test_member_can_leave(
    second_logged_in_client: AsyncClient,
    db_session: AsyncSession,
    second_user: Any,
) -> None:
    owner = User(email="leaveowner@example.com", password_hash="argon2-fake")
    db_session.add(owner)
    await db_session.commit()
    proj = await create_project(db_session, owner.id, name="Командный")
    await add_member(db_session, proj.id, second_user.id, role="member")
    assert await get_role(db_session, proj.id, second_user.id) == "member"

    resp = await second_logged_in_client.post(f"/api/projects/{proj.id}/leave")
    assert resp.status_code == 204
    assert await get_role(db_session, proj.id, second_user.id) is None


async def test_owner_cannot_leave(logged_in_client: AsyncClient, db_session: AsyncSession) -> None:
    owner = await _owner(db_session)
    proj = await create_project(db_session, owner.id, name="Мой")
    resp = await logged_in_client.post(f"/api/projects/{proj.id}/leave")
    assert resp.status_code == 400
    assert await get_role(db_session, proj.id, owner.id) == "owner"


async def test_leave_anonymous_blocked(client: AsyncClient) -> None:
    resp = await client.post("/api/projects/00000000-0000-0000-0000-000000000000/leave")
    assert resp.status_code == 401
