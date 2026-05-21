"""Tests for in-app incoming invitations: service + /api/invites endpoints."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.projects.invitations import create_invitation, list_invitations_for_email
from app.projects.membership import is_member
from app.projects.service import create_project


async def _owner(db_session: AsyncSession) -> User:
    return (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()


async def test_list_invitations_for_email(
    logged_in_client: AsyncClient, db_session: AsyncSession, second_user: Any
) -> None:
    owner = await _owner(db_session)
    proj = await create_project(db_session, owner.id, name="Приглашаем")
    await create_invitation(
        db_session, project_id=proj.id, inviter_id=owner.id, invitee_email="second@example.com"
    )

    pairs = await list_invitations_for_email(db_session, "second@example.com")
    assert [name for _inv, name in pairs] == ["Приглашаем"]
    # not addressed to someone else
    assert await list_invitations_for_email(db_session, "nobody@example.com") == []


async def test_incoming_endpoint_and_accept(
    logged_in_client: AsyncClient,
    second_logged_in_client: AsyncClient,
    db_session: AsyncSession,
    second_user: Any,
) -> None:
    owner = await _owner(db_session)
    proj = await create_project(db_session, owner.id, name="Командный")
    await create_invitation(
        db_session, project_id=proj.id, inviter_id=owner.id, invitee_email="second@example.com"
    )

    # second_user sees the incoming invite
    resp = await second_logged_in_client.get("/api/invites/incoming")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    token = body[0]["token"]
    assert body[0]["project_name"] == "Командный"

    # second_user accepts → becomes a member
    acc = await second_logged_in_client.post(f"/api/invites/{token}/accept")
    assert acc.status_code == 204
    assert await is_member(db_session, proj.id, second_user.id)


async def test_incoming_anonymous_blocked(client: AsyncClient) -> None:
    assert (await client.get("/api/invites/incoming")).status_code == 401
    assert (await client.post("/api/invites/sometoken/accept")).status_code == 401
