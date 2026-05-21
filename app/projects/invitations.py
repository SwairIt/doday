"""Project invitation logic — create / accept / revoke."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.projects.membership import add_member, is_member, is_owner
from app.projects.models import Project, ProjectInvitation

INVITE_TTL_DAYS = 7


class InvitationError(Exception):
    """Base for invitation problems."""


async def create_invitation(
    session: AsyncSession,
    *,
    project_id: UUID,
    inviter_id: UUID,
    invitee_email: str,
) -> ProjectInvitation:
    """Create a pending invitation. Raises InvitationError on bad input."""
    invitee_email = invitee_email.lower().strip()
    if not await is_owner(session, project_id, inviter_id):
        raise InvitationError("Только владелец проекта может приглашать")

    from app.auth.service import get_user_by_email

    existing_user = await get_user_by_email(session, invitee_email)
    if existing_user is not None and await is_member(session, project_id, existing_user.id):
        raise InvitationError("Этот юзер уже в проекте")

    prior = await session.execute(
        select(ProjectInvitation).where(
            ProjectInvitation.project_id == project_id,
            ProjectInvitation.invitee_email == invitee_email,
            ProjectInvitation.status == "pending",
        )
    )
    for inv in prior.scalars().all():
        inv.status = "revoked"

    invitation = ProjectInvitation(
        project_id=project_id,
        inviter_id=inviter_id,
        invitee_email=invitee_email,
        token=secrets.token_urlsafe(32),
        status="pending",
        expires_at=datetime.now(UTC) + timedelta(days=INVITE_TTL_DAYS),
    )
    session.add(invitation)
    await session.commit()
    await session.refresh(invitation)
    return invitation


async def accept_invitation(
    session: AsyncSession, *, token: str, user_id: UUID, user_email: str
) -> Project:
    """Accept an invitation. Returns the project. Raises InvitationError."""
    row = await session.execute(select(ProjectInvitation).where(ProjectInvitation.token == token))
    inv = row.scalar_one_or_none()
    if inv is None or inv.status != "pending":
        raise InvitationError("Приглашение не найдено или уже использовано")
    if inv.expires_at < datetime.now(UTC):
        inv.status = "revoked"
        await session.commit()
        raise InvitationError("Срок приглашения истёк")
    if inv.invitee_email != user_email.lower().strip():
        raise InvitationError("Приглашение выписано на другой email")

    await add_member(session, inv.project_id, user_id, role="member")
    inv.status = "accepted"
    inv.accepted_at = datetime.now(UTC)
    await session.commit()

    project = await session.get(Project, inv.project_id)
    if project is None:  # pragma: no cover — FK cascade prevents this
        raise InvitationError("Проект не найден")
    return project


async def revoke_invitation(
    session: AsyncSession, *, invitation_id: UUID, requester_id: UUID
) -> None:
    """Revoke a pending invitation. Raises InvitationError on bad input."""
    row = await session.execute(
        select(ProjectInvitation).where(ProjectInvitation.id == invitation_id)
    )
    inv = row.scalar_one_or_none()
    if inv is None:
        raise InvitationError("Приглашение не найдено")
    if not await is_owner(session, inv.project_id, requester_id):
        raise InvitationError("Только владелец может отзывать приглашения")
    inv.status = "revoked"
    await session.commit()


async def list_invitations_for_email(
    session: AsyncSession, email: str
) -> list[tuple[ProjectInvitation, str]]:
    """Pending, non-expired invitations addressed to an email, with project name.

    Powers the in-app "incoming invitations" banner. Returns [(invitation, project_name)].
    """
    email = email.lower().strip()
    now = datetime.now(UTC)
    rows = await session.execute(
        select(ProjectInvitation, Project.name)
        .join(Project, Project.id == ProjectInvitation.project_id)
        .where(
            ProjectInvitation.invitee_email == email,
            ProjectInvitation.status == "pending",
            ProjectInvitation.expires_at >= now,
        )
        .order_by(ProjectInvitation.created_at.desc())
    )
    return [(inv, name) for inv, name in rows.all()]


async def list_pending(session: AsyncSession, project_id: UUID) -> list[ProjectInvitation]:
    """Return all pending invitations for a project, newest first."""
    rows = await session.execute(
        select(ProjectInvitation)
        .where(
            ProjectInvitation.project_id == project_id,
            ProjectInvitation.status == "pending",
        )
        .order_by(ProjectInvitation.created_at.desc())
    )
    return list(rows.scalars().all())
