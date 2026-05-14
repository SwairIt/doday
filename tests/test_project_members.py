"""Phase δ — ProjectMember + ProjectInvitation model sanity."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.projects.models import ProjectInvitation, ProjectMember


async def test_project_members_table_exists(db_session: AsyncSession) -> None:
    rows = (await db_session.execute(select(ProjectMember))).scalars().all()
    assert isinstance(rows, list)


async def test_project_invitations_table_exists(db_session: AsyncSession) -> None:
    rows = (await db_session.execute(select(ProjectInvitation))).scalars().all()
    assert isinstance(rows, list)
