"""Section service — CRUD and ordering within a project."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.projects.membership import is_member
from app.projects.service import get_project
from app.sections.models import Section


class SectionNotFound(Exception):
    """Section does not exist or does not belong to user."""


async def list_sections(session: AsyncSession, user_id: UUID, project_id: UUID) -> list[Section]:
    await get_project(session, user_id, project_id)
    result = await session.execute(
        select(Section)
        .where(Section.project_id == project_id, Section.user_id == user_id)
        .order_by(Section.position, Section.created_at)
    )
    return list(result.scalars().all())


async def get_section(session: AsyncSession, user_id: UUID, section_id: UUID) -> Section:
    section = await session.get(Section, section_id)
    if section is None:
        raise SectionNotFound(str(section_id))
    if not await is_member(session, section.project_id, user_id):
        raise SectionNotFound(str(section_id))
    return section


async def create_section(
    session: AsyncSession, user_id: UUID, *, project_id: UUID, name: str
) -> Section:
    await get_project(session, user_id, project_id)
    last = (
        await session.execute(
            select(Section)
            .where(Section.project_id == project_id)
            .order_by(Section.position.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    position = (last.position + 1) if last else 0

    section = Section(
        user_id=user_id,
        project_id=project_id,
        name=name,
        position=position,
    )
    session.add(section)
    await session.commit()
    await session.refresh(section)
    return section


async def update_section(
    session: AsyncSession,
    user_id: UUID,
    section_id: UUID,
    *,
    name: str | None = None,
) -> Section:
    section = await get_section(session, user_id, section_id)
    if name is not None:
        section.name = name
    await session.commit()
    await session.refresh(section)
    return section


async def delete_section(session: AsyncSession, user_id: UUID, section_id: UUID) -> None:
    section = await get_section(session, user_id, section_id)
    await session.delete(section)
    await session.commit()


async def reorder_sections(
    session: AsyncSession, user_id: UUID, project_id: UUID, ids: list[UUID]
) -> list[Section]:
    """Set new positions for sections within one project."""
    await get_project(session, user_id, project_id)
    rows = await session.execute(
        select(Section).where(
            Section.user_id == user_id,
            Section.project_id == project_id,
            Section.id.in_(ids),
        )
    )
    by_id = {s.id: s for s in rows.scalars().all()}
    if len(by_id) != len(set(ids)):
        raise SectionNotFound("one or more section ids do not belong to this project")
    for pos, sid in enumerate(ids):
        by_id[sid].position = pos
    await session.commit()
    return await list_sections(session, user_id, project_id)
