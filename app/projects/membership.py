"""Service layer for project membership — who can access a shared project."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.projects.models import ProjectMember

# Stable palette for assignee avatars — Tailwind color names (full palette is
# available via the CDN). Picked deterministically from the user id so the same
# person always gets the same colour across sessions.
_AVATAR_PALETTE = (
    "rose",
    "amber",
    "sky",
    "violet",
    "emerald",
    "fuchsia",
    "cyan",
    "orange",
    "teal",
    "indigo",
)


async def is_member(session: AsyncSession, project_id: UUID, user_id: UUID) -> bool:
    """True if user has any role in the project."""
    row = await session.execute(
        select(ProjectMember.id).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    return row.first() is not None


async def get_role(session: AsyncSession, project_id: UUID, user_id: UUID) -> str | None:
    """'owner' | 'member' | None."""
    row = await session.execute(
        select(ProjectMember.role).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    return row.scalar_one_or_none()


async def is_owner(session: AsyncSession, project_id: UUID, user_id: UUID) -> bool:
    return (await get_role(session, project_id, user_id)) == "owner"


async def list_members(session: AsyncSession, project_id: UUID) -> list[ProjectMember]:
    rows = await session.execute(
        select(ProjectMember)
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.joined_at)
    )
    return list(rows.scalars().all())


def _avatar_data(user_id: UUID, email: str) -> dict[str, str]:
    """Display data for one assignee avatar: stable colour from the user id."""
    initial = email[0].upper() if email else "?"
    color = _AVATAR_PALETTE[int(user_id.hex, 16) % len(_AVATAR_PALETTE)]
    return {"initial": initial, "label": email, "color": color}


async def assignee_map_for_project(
    session: AsyncSession, project_id: UUID
) -> dict[UUID, dict[str, str]]:
    """Map every member's user id to display data for the assignee avatar.

    Returns `{user_id: {"initial": "A", "label": "a@b.com", "color": "rose"}}`.
    Used by the project list/kanban views to render a small avatar on each task
    that has an `assigned_to`. Single-user (personal) projects just return their
    one member; the template only renders the avatar when `assigned_to` is set.
    """
    rows = await session.execute(
        select(User.id, User.email)
        .join(ProjectMember, ProjectMember.user_id == User.id)
        .where(ProjectMember.project_id == project_id)
    )
    return {user_id: _avatar_data(user_id, email) for user_id, email in rows.all()}


async def assignee_map_for_projects(
    session: AsyncSession, project_ids: Iterable[UUID]
) -> dict[UUID, dict[str, str]]:
    """Merged assignee map across several projects (one query, deduped by user).

    Used by cross-project views (Today / Upcoming) so a task from a shared
    project still shows its assignee avatar. Empty input → empty map.
    """
    ids = list(project_ids)
    if not ids:
        return {}
    rows = await session.execute(
        select(User.id, User.email)
        .join(ProjectMember, ProjectMember.user_id == User.id)
        .where(ProjectMember.project_id.in_(ids))
        .distinct()
    )
    return {user_id: _avatar_data(user_id, email) for user_id, email in rows.all()}


async def add_member(
    session: AsyncSession, project_id: UUID, user_id: UUID, role: str = "member"
) -> ProjectMember:
    """Idempotent — if already a member, returns existing row (role unchanged)."""
    existing = await session.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    found = existing.scalar_one_or_none()
    if found is not None:
        return found
    member = ProjectMember(project_id=project_id, user_id=user_id, role=role)
    session.add(member)
    await session.commit()
    await session.refresh(member)
    return member


async def set_role(session: AsyncSession, project_id: UUID, user_id: UUID, role: str) -> None:
    """Update a member's role (e.g. transfer ownership). Idempotent if unchanged."""
    await session.execute(
        update(ProjectMember)
        .where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        .values(role=role)
    )
    await session.commit()


async def remove_member(session: AsyncSession, project_id: UUID, user_id: UUID) -> None:
    """Remove a member. Caller must ensure not removing the last owner."""
    await session.execute(
        delete(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    await session.commit()


async def member_project_ids(session: AsyncSession, user_id: UUID) -> list[UUID]:
    """All project ids the user is a member of (any role)."""
    rows = await session.execute(
        select(ProjectMember.project_id).where(ProjectMember.user_id == user_id)
    )
    return list(rows.scalars().all())


async def shared_project_ids(session: AsyncSession, user_id: UUID) -> list[UUID]:
    """Project ids the user belongs to that have more than one member.

    These are the "team" projects — the ones worth showing on the cross-project
    «Команда» view. Single-member (personal) projects are excluded.
    """
    pids = await member_project_ids(session, user_id)
    if not pids:
        return []
    rows = await session.execute(
        select(ProjectMember.project_id)
        .where(ProjectMember.project_id.in_(pids))
        .group_by(ProjectMember.project_id)
        .having(func.count() > 1)
    )
    return list(rows.scalars().all())
