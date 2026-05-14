"""Phase δ — invitation create/accept/revoke logic."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def _project_owned_by(
    db_session: AsyncSession, email: str, name: str
) -> tuple[object, object]:
    from app.auth.models import User
    from app.projects.service import create_project

    user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    project = await create_project(db_session, user.id, name=name, color="violet")
    await db_session.commit()
    return user, project


async def test_create_invitation_by_owner(
    db_session: AsyncSession, logged_in_client: object
) -> None:
    from app.projects.invitations import create_invitation

    owner, project = await _project_owned_by(db_session, "logged-in@example.com", "Inv1")
    inv = await create_invitation(
        db_session,
        project_id=project.id,  # type: ignore[attr-defined]
        inviter_id=owner.id,  # type: ignore[attr-defined]
        invitee_email="newperson@example.com",
    )
    assert inv.status == "pending"
    assert inv.token
    assert inv.invitee_email == "newperson@example.com"


async def test_create_invitation_non_owner_rejected(
    db_session: AsyncSession, logged_in_client: object, second_user: object
) -> None:
    from app.projects.invitations import InvitationError, create_invitation

    _owner, project = await _project_owned_by(db_session, "logged-in@example.com", "Inv2")
    with pytest.raises(InvitationError):
        await create_invitation(
            db_session,
            project_id=project.id,  # type: ignore[attr-defined]
            inviter_id=second_user.id,  # type: ignore[attr-defined]
            invitee_email="x@example.com",
        )


async def test_accept_invitation_adds_member(
    db_session: AsyncSession, logged_in_client: object, second_user: object
) -> None:
    from app.projects.invitations import accept_invitation, create_invitation
    from app.projects.membership import is_member

    owner, project = await _project_owned_by(db_session, "logged-in@example.com", "Inv3")
    inv = await create_invitation(
        db_session,
        project_id=project.id,  # type: ignore[attr-defined]
        inviter_id=owner.id,  # type: ignore[attr-defined]
        invitee_email=second_user.email,  # type: ignore[attr-defined]
    )
    accepted = await accept_invitation(
        db_session,
        token=inv.token,
        user_id=second_user.id,  # type: ignore[attr-defined]
        user_email=second_user.email,  # type: ignore[attr-defined]
    )
    assert accepted.id == project.id  # type: ignore[attr-defined]
    assert await is_member(db_session, project.id, second_user.id) is True  # type: ignore[attr-defined]


async def test_accept_wrong_email_rejected(
    db_session: AsyncSession, logged_in_client: object, second_user: object
) -> None:
    from app.projects.invitations import InvitationError, accept_invitation, create_invitation

    owner, project = await _project_owned_by(db_session, "logged-in@example.com", "Inv4")
    inv = await create_invitation(
        db_session,
        project_id=project.id,  # type: ignore[attr-defined]
        inviter_id=owner.id,  # type: ignore[attr-defined]
        invitee_email="someone-else@example.com",
    )
    with pytest.raises(InvitationError):
        await accept_invitation(
            db_session,
            token=inv.token,
            user_id=second_user.id,  # type: ignore[attr-defined]
            user_email=second_user.email,  # type: ignore[attr-defined]
        )


async def test_accept_expired_rejected(
    db_session: AsyncSession, logged_in_client: object, second_user: object
) -> None:
    from app.projects.invitations import InvitationError, accept_invitation, create_invitation

    owner, project = await _project_owned_by(db_session, "logged-in@example.com", "Inv5")
    inv = await create_invitation(
        db_session,
        project_id=project.id,  # type: ignore[attr-defined]
        inviter_id=owner.id,  # type: ignore[attr-defined]
        invitee_email=second_user.email,  # type: ignore[attr-defined]
    )
    inv.expires_at = datetime.now(UTC) - timedelta(days=1)
    await db_session.commit()
    with pytest.raises(InvitationError):
        await accept_invitation(
            db_session,
            token=inv.token,
            user_id=second_user.id,  # type: ignore[attr-defined]
            user_email=second_user.email,  # type: ignore[attr-defined]
        )


async def test_revoke_invitation(
    db_session: AsyncSession, logged_in_client: object, second_user: object
) -> None:
    from app.projects.invitations import (
        InvitationError,
        accept_invitation,
        create_invitation,
        revoke_invitation,
    )

    owner, project = await _project_owned_by(db_session, "logged-in@example.com", "Inv6")
    inv = await create_invitation(
        db_session,
        project_id=project.id,  # type: ignore[attr-defined]
        inviter_id=owner.id,  # type: ignore[attr-defined]
        invitee_email=second_user.email,  # type: ignore[attr-defined]
    )
    await revoke_invitation(
        db_session,
        invitation_id=inv.id,
        requester_id=owner.id,  # type: ignore[attr-defined]
    )
    with pytest.raises(InvitationError):
        await accept_invitation(
            db_session,
            token=inv.token,
            user_id=second_user.id,  # type: ignore[attr-defined]
            user_email=second_user.email,  # type: ignore[attr-defined]
        )


# ─── Endpoint-level tests ─────────────────────────────────────────────────────


async def test_list_members_endpoint(db_session: AsyncSession, logged_in_client: "object") -> None:
    """Owner is listed as a member via GET /api/projects/{id}/members."""
    from httpx import AsyncClient

    _owner, project = await _project_owned_by(db_session, "logged-in@example.com", "Ep1")
    client = logged_in_client  # type: ignore[assignment]
    assert isinstance(client, AsyncClient)

    r = await client.get(f"/api/projects/{project.id}/members")  # type: ignore[attr-defined]
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["role"] == "owner"
    assert data[0]["email"] == "logged-in@example.com"


async def test_post_invite_endpoint_owner(
    db_session: AsyncSession, logged_in_client: "object"
) -> None:
    """Owner can POST an invite; response includes invitee_email."""
    from httpx import AsyncClient

    _owner, project = await _project_owned_by(db_session, "logged-in@example.com", "Ep2")
    client = logged_in_client  # type: ignore[assignment]
    assert isinstance(client, AsyncClient)

    r = await client.post(
        f"/api/projects/{project.id}/invites",  # type: ignore[attr-defined]
        json={"invitee_email": "guest@example.com"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["invitee_email"] == "guest@example.com"
    assert data["status"] == "pending"
    assert "id" in data
    assert "expires_at" in data


async def test_post_invite_endpoint_non_member_404(
    db_session: AsyncSession,
    logged_in_client: "object",
    second_logged_in_client: "object",
) -> None:
    """Non-member POSTing invite gets 404 (get_project gate)."""
    from httpx import AsyncClient

    _owner, project = await _project_owned_by(db_session, "logged-in@example.com", "Ep3")
    client2 = second_logged_in_client  # type: ignore[assignment]
    assert isinstance(client2, AsyncClient)

    r = await client2.post(
        f"/api/projects/{project.id}/invites",  # type: ignore[attr-defined]
        json={"invitee_email": "attacker@example.com"},
    )
    assert r.status_code == 404


async def test_get_invites_endpoint_owner(
    db_session: AsyncSession, logged_in_client: "object"
) -> None:
    """Owner can list pending invitations."""
    from httpx import AsyncClient

    from app.projects.invitations import create_invitation

    owner, project = await _project_owned_by(db_session, "logged-in@example.com", "Ep4")
    await create_invitation(
        db_session,
        project_id=project.id,  # type: ignore[attr-defined]
        inviter_id=owner.id,  # type: ignore[attr-defined]
        invitee_email="pending@example.com",
    )
    client = logged_in_client  # type: ignore[assignment]
    assert isinstance(client, AsyncClient)

    r = await client.get(f"/api/projects/{project.id}/invites")  # type: ignore[attr-defined]
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["invitee_email"] == "pending@example.com"
    assert data[0]["status"] == "pending"


async def test_revoke_invite_endpoint(db_session: AsyncSession, logged_in_client: "object") -> None:
    """Owner can DELETE (revoke) an invitation via /api/invites/{id}."""
    from httpx import AsyncClient

    from app.projects.invitations import create_invitation

    owner, project = await _project_owned_by(db_session, "logged-in@example.com", "Ep5")
    inv = await create_invitation(
        db_session,
        project_id=project.id,  # type: ignore[attr-defined]
        inviter_id=owner.id,  # type: ignore[attr-defined]
        invitee_email="todelete@example.com",
    )
    client = logged_in_client  # type: ignore[assignment]
    assert isinstance(client, AsyncClient)

    r = await client.delete(f"/api/invites/{inv.id}")
    assert r.status_code == 204


async def test_get_invite_page_renders(
    db_session: AsyncSession, logged_in_client: "object"
) -> None:
    """GET /invite/{token} renders the project name for a valid invitation."""
    from httpx import AsyncClient

    from app.projects.invitations import create_invitation

    owner, project = await _project_owned_by(db_session, "logged-in@example.com", "Ep6-Page")
    inv = await create_invitation(
        db_session,
        project_id=project.id,  # type: ignore[attr-defined]
        inviter_id=owner.id,  # type: ignore[attr-defined]
        invitee_email="viewer@example.com",
    )
    client = logged_in_client  # type: ignore[assignment]
    assert isinstance(client, AsyncClient)

    r = await client.get(f"/invite/{inv.token}")
    assert r.status_code == 200
    assert "Ep6-Page" in r.text


async def test_accept_via_post_endpoint(
    db_session: AsyncSession,
    logged_in_client: "object",
    second_logged_in_client: "object",
    second_user: "object",
) -> None:
    """second_user POSTs /invite/{token} and becomes a project member."""
    from httpx import AsyncClient

    from app.projects.invitations import create_invitation
    from app.projects.membership import is_member

    owner, project = await _project_owned_by(db_session, "logged-in@example.com", "Ep7")
    inv = await create_invitation(
        db_session,
        project_id=project.id,  # type: ignore[attr-defined]
        inviter_id=owner.id,  # type: ignore[attr-defined]
        invitee_email=second_user.email,  # type: ignore[attr-defined]
    )
    client2 = second_logged_in_client  # type: ignore[assignment]
    assert isinstance(client2, AsyncClient)

    r = await client2.post(f"/invite/{inv.token}", follow_redirects=False)
    assert r.status_code == 303

    # Verify second_user is now a member
    assert await is_member(
        db_session,
        project.id,
        second_user.id,  # type: ignore[attr-defined]
    )
