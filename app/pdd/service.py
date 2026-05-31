"""Service layer for Doday PDD.

All reads/writes go through here; routers never touch the ORM directly (same rule
as `app/qa/service.py`). This module owns: content reads, attempt recording, the
adaptive trainer queue, weak-topic stats, exam scoring, and the `pdd_pro` gating
wrapper around the generic billing entitlement.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.pdd.models import PddQuestion, PddTicket, PddTopic

if TYPE_CHECKING:
    from app.auth.models import User

# The entitlement feature key sold via products pdd_pro_1m/3m/forever.
PDD_FEATURE = "pdd_pro"


class PddError(Exception):
    """Base for service-layer errors."""


class NotFound(PddError):
    """Requested content does not exist."""


# ─── content reads ──────────────────────────────────────────────────────────


async def list_tickets(session: AsyncSession) -> list[PddTicket]:
    """All 40 tickets ordered by number (cheap — no questions loaded)."""
    rows = await session.execute(select(PddTicket).order_by(PddTicket.number))
    return list(rows.scalars().all())


async def list_topics(session: AsyncSession) -> list[PddTopic]:
    """All topics ordered for the hub + topic index."""
    rows = await session.execute(select(PddTopic).order_by(PddTopic.position, PddTopic.title))
    return list(rows.scalars().all())


async def get_ticket(session: AsyncSession, number: int) -> PddTicket | None:
    return (
        await session.execute(select(PddTicket).where(PddTicket.number == number))
    ).scalar_one_or_none()


async def ticket_questions(session: AsyncSession, ticket_id: int) -> list[PddQuestion]:
    """A ticket's 20 questions in order (options eager-loaded via selectin)."""
    rows = await session.execute(
        select(PddQuestion)
        .where(PddQuestion.ticket_id == ticket_id)
        .order_by(PddQuestion.position_in_ticket)
    )
    return list(rows.scalars().all())


async def get_topic_by_slug(session: AsyncSession, slug: str) -> PddTopic | None:
    return (
        await session.execute(select(PddTopic).where(PddTopic.slug == slug))
    ).scalar_one_or_none()


async def topic_questions(session: AsyncSession, topic_id: int) -> list[PddQuestion]:
    """All questions of a topic, ordered by ticket then position."""
    rows = await session.execute(
        select(PddQuestion)
        .where(PddQuestion.topic_id == topic_id)
        .order_by(PddQuestion.ticket_id, PddQuestion.position_in_ticket)
    )
    return list(rows.scalars().all())


async def get_question_by_slug(session: AsyncSession, public_slug: str) -> PddQuestion | None:
    return (
        await session.execute(select(PddQuestion).where(PddQuestion.public_slug == public_slug))
    ).scalar_one_or_none()


async def question_count(session: AsyncSession) -> int:
    from sqlalchemy import func

    return (await session.execute(select(func.count()).select_from(PddQuestion))).scalar_one()


async def all_question_slugs(session: AsyncSession) -> list[str]:
    """Just the public slugs (no ORM objects) — for the sitemap. Capped at
    Google's 50k-URLs-per-file limit."""
    rows = await session.execute(
        select(PddQuestion.public_slug).order_by(PddQuestion.id).limit(50000)
    )
    return list(rows.scalars().all())


# ─── pdd_pro gating ─────────────────────────────────────────────────────────


async def is_pdd_pro(session: AsyncSession, user: User | None) -> bool:
    """True if the user holds an active `pdd_pro` entitlement (or beta override).

    Independent of the global Doday Pro tier — buying ПДД Pro must not unlock
    Doday Tasks, and vice versa.
    """
    if user is None:
        return False
    from app.billing.service import has_entitlement

    return await has_entitlement(session, user, PDD_FEATURE)


async def require_pdd_pro(session: AsyncSession, user: User | None) -> None:
    """Raise 402 if the user is not a ПДД Pro subscriber (frontend → upgrade)."""
    from fastapi import HTTPException, status

    if not await is_pdd_pro(session, user):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="ПДД Pro — оформи подписку, чтобы открыть тренажёр и статистику.",
        )
