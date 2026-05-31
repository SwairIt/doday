"""Idempotent loader for the official category A/B/M ticket dataset.

The model ships this loader + the dataset format doc (`docs/pdd-dataset-schema.md`);
the user prepares and runs the seed locally (DB-credential isolation). Re-running
updates existing questions by `public_slug` and rebuilds their options, so it is
safe to run repeatedly.

Each input item is a dict — see the dataset schema doc for the exact shape.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.pdd.models import PddOption, PddQuestion, PddTicket, PddTopic


def public_slug_for(category: str, ticket: int, position: int) -> str:
    """Stable SEO handle for a question — used in `/pdd/vopros/{slug}`.

    ABM keeps the bare ``bilet-N-vopros-M`` form (already indexed); other
    categories are prefixed (``cd-bilet-N-vopros-M``) to stay globally unique.
    """
    prefix = "" if category == "ABM" else f"{category.lower()}-"
    return f"{prefix}bilet-{ticket}-vopros-{position}"


async def _get_or_create_topic(
    session: AsyncSession, cache: dict[str, PddTopic], item: dict[str, Any]
) -> tuple[PddTopic, bool]:
    slug = item["topic_slug"]
    if slug in cache:
        return cache[slug], False
    topic = (
        await session.execute(select(PddTopic).where(PddTopic.slug == slug))
    ).scalar_one_or_none()
    created = False
    if topic is None:
        topic = PddTopic(
            slug=slug,
            title=item["topic_title"],
            position=int(item.get("topic_position", 0)),
            description=item.get("topic_description", ""),
            seo_intro=item.get("topic_seo_intro", ""),
        )
        session.add(topic)
        await session.flush()
        created = True
    cache[slug] = topic
    return topic, created


async def _get_or_create_ticket(
    session: AsyncSession, cache: dict[tuple[str, int], PddTicket], category: str, number: int
) -> tuple[PddTicket, bool]:
    key = (category, number)
    if key in cache:
        return cache[key], False
    ticket = (
        await session.execute(
            select(PddTicket).where(PddTicket.category == category, PddTicket.number == number)
        )
    ).scalar_one_or_none()
    created = False
    if ticket is None:
        ticket = PddTicket(category=category, number=number)
        session.add(ticket)
        await session.flush()
        created = True
    cache[key] = ticket
    return ticket, created


async def load_dataset(session: AsyncSession, data: list[dict[str, Any]]) -> dict[str, int]:
    """Upsert topics/tickets/questions/options from `data`. Returns row counts.

    Idempotent: a question is matched by its `public_slug`; its options are
    deleted and rebuilt from the item on every run.
    """
    counts = {"topics": 0, "tickets": 0, "questions": 0, "options": 0}
    topic_cache: dict[str, PddTopic] = {}
    ticket_cache: dict[tuple[str, int], PddTicket] = {}

    for item in data:
        category = str(item.get("category", "ABM"))
        topic, t_created = await _get_or_create_topic(session, topic_cache, item)
        counts["topics"] += int(t_created)
        ticket, k_created = await _get_or_create_ticket(
            session, ticket_cache, category, int(item["ticket"])
        )
        counts["tickets"] += int(k_created)

        slug = public_slug_for(category, int(item["ticket"]), int(item["position"]))
        question = (
            await session.execute(select(PddQuestion).where(PddQuestion.public_slug == slug))
        ).scalar_one_or_none()
        if question is None:
            question = PddQuestion(public_slug=slug)
            session.add(question)
            counts["questions"] += 1
        question.category = category
        question.ticket_id = ticket.id
        question.position_in_ticket = int(item["position"])
        question.topic_id = topic.id
        question.text = item["text"]
        question.image_path = item.get("image")
        question.explanation = item.get("explanation", "")
        question.correct_position = int(item["correct_position"])
        await session.flush()

        # Options are immutable content — rebuild them wholesale for idempotency.
        await session.execute(delete(PddOption).where(PddOption.question_id == question.id))
        for idx, option_text in enumerate(item["options"], start=1):
            session.add(PddOption(question_id=question.id, position=idx, text=option_text))
            counts["options"] += 1

    await session.commit()
    return counts
