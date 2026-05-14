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
