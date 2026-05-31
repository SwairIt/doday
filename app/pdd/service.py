"""Service layer for Doday PDD.

All reads/writes go through here; routers never touch the ORM directly (same rule
as `app/qa/service.py`). This module owns: content reads, attempt recording, the
adaptive trainer queue, weak-topic stats, exam scoring, and the `pdd_pro` gating
wrapper around the generic billing entitlement.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.pdd.models import PddAttempt, PddExamSession, PddQuestion, PddTicket, PddTopic
from app.pdd.schemas import AttemptIn, AttemptOut, ExamAnswerIn

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
    return (await session.execute(select(func.count()).select_from(PddQuestion))).scalar_one()


async def all_question_slugs(session: AsyncSession) -> list[str]:
    """Just the public slugs (no ORM objects) — for the sitemap. Capped at
    Google's 50k-URLs-per-file limit."""
    rows = await session.execute(
        select(PddQuestion.public_slug).order_by(PddQuestion.id).limit(50000)
    )
    return list(rows.scalars().all())


# ─── attempts (logged-in) ───────────────────────────────────────────────────


async def record_attempt(session: AsyncSession, user: User, data: AttemptIn) -> AttemptOut:
    """Persist one answer for a logged-in user and report correctness.

    Anonymous practice never reaches here (the endpoint requires auth); it stays
    purely client-side.
    """
    question = await session.get(PddQuestion, data.question_id)
    if question is None:
        raise NotFound("вопрос не найден")
    is_correct = data.chosen_position == question.correct_position
    session.add(
        PddAttempt(
            user_id=user.id,
            question_id=question.id,
            chosen_position=data.chosen_position,
            is_correct=is_correct,
            source=data.source,
        )
    )
    await session.commit()
    return AttemptOut(
        is_correct=is_correct,
        correct_position=question.correct_position,
        explanation=question.explanation,
    )


def _latest_attempt_subquery(user_id: object):  # type: ignore[no-untyped-def]
    """Subquery flagging, per question, the user's most recent attempt (rn == 1)."""
    rn = (
        func.row_number()
        .over(
            partition_by=PddAttempt.question_id,
            order_by=PddAttempt.created_at.desc(),
        )
        .label("rn")
    )
    return (
        select(PddAttempt.question_id, PddAttempt.is_correct, rn)
        .where(PddAttempt.user_id == user_id)
        .subquery()
    )


async def recent_mistakes(session: AsyncSession, user: User, limit: int = 50) -> list[PddQuestion]:
    """Questions whose latest attempt by this user was wrong (the basic free
    mistakes list on /pdd/my)."""
    latest = _latest_attempt_subquery(user.id)
    wrong_ids = select(latest.c.question_id).where(latest.c.rn == 1, latest.c.is_correct.is_(False))
    rows = await session.execute(
        select(PddQuestion).where(PddQuestion.id.in_(wrong_ids)).limit(limit)
    )
    return list(rows.scalars().all())


async def attempt_stats(session: AsyncSession, user: User) -> dict[str, int]:
    """Quick counters for the /pdd/my header: answered / correct distinct."""
    total = (
        await session.execute(
            select(func.count()).select_from(PddAttempt).where(PddAttempt.user_id == user.id)
        )
    ).scalar_one()
    distinct_q = (
        await session.execute(
            select(func.count(func.distinct(PddAttempt.question_id))).where(
                PddAttempt.user_id == user.id
            )
        )
    ).scalar_one()
    return {"attempts": total, "questions_touched": distinct_q}


# ─── trainer + stats (Pro) ──────────────────────────────────────────────────


async def trainer_queue(session: AsyncSession, user: User, limit: int = 20) -> list[PddQuestion]:
    """Adaptive queue: questions whose latest attempt is wrong, hardest first
    (most wrong attempts). Spaced-repetition-lite over the user's mistakes."""
    latest = _latest_attempt_subquery(user.id)
    wrong_ids = (
        select(latest.c.question_id)
        .where(latest.c.rn == 1, latest.c.is_correct.is_(False))
        .scalar_subquery()
    )
    wrong_counts = (
        select(
            PddAttempt.question_id.label("qid"),
            func.count().label("wc"),
        )
        .where(PddAttempt.user_id == user.id, PddAttempt.is_correct.is_(False))
        .group_by(PddAttempt.question_id)
        .subquery()
    )
    stmt = (
        select(PddQuestion)
        .where(PddQuestion.id.in_(wrong_ids))
        .join(wrong_counts, wrong_counts.c.qid == PddQuestion.id)
        .order_by(wrong_counts.c.wc.desc(), PddQuestion.id)
        .limit(limit)
    )
    rows = await session.execute(stmt)
    return list(rows.scalars().all())


async def weak_topics(session: AsyncSession, user: User) -> list[dict[str, object]]:
    """Per-topic error rate over the user's latest attempts — the Pro stats
    dashboard. Only topics with at least one current mistake, weakest first."""
    latest = _latest_attempt_subquery(user.id)
    wrong_expr = func.sum(case((latest.c.is_correct.is_(False), 1), else_=0))
    stmt = (
        select(
            PddTopic.id,
            PddTopic.title,
            PddTopic.slug,
            func.count().label("total"),
            wrong_expr.label("wrong"),
        )
        .select_from(latest)
        .join(PddQuestion, PddQuestion.id == latest.c.question_id)
        .join(PddTopic, PddTopic.id == PddQuestion.topic_id)
        .where(latest.c.rn == 1)
        .group_by(PddTopic.id, PddTopic.title, PddTopic.slug)
        .having(wrong_expr > 0)
    )
    rows = (await session.execute(stmt)).all()
    # Sort typed tuples (rate, wrong) before shaping into dicts — keeps the sort
    # key numeric so the type checker is happy.
    ranked: list[tuple[float, int, str, str, int]] = []
    for row in rows:
        wrong = int(row.wrong or 0)
        total = int(row.total or 0)
        rate = (wrong / total) if total else 0.0
        ranked.append((rate, wrong, row.title, row.slug, total))
    ranked.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [
        {"title": title, "slug": slug, "wrong": wrong, "total": total, "rate": rate}
        for rate, wrong, title, slug, total in ranked
    ]


# ─── exam simulator ─────────────────────────────────────────────────────────

EXAM_SIZE = 20
EXAM_MISTAKE_LIMIT = 2
PENALTY_PER_MISTAKE = 5


def score_exam(answers: dict[int, int], correct: dict[int, int]) -> tuple[bool, int, int]:
    """Score one exam run. Pure (no DB) so it is trivially testable.

    Official-rules simplification: 20 questions, an unanswered or wrong question
    is a mistake; ``EXAM_MISTAKE_LIMIT`` (2) mistakes are allowed; each mistake
    nominally adds ``PENALTY_PER_MISTAKE`` (5) extra questions. Returns
    ``(passed, mistakes, extra_added)``.
    """
    mistakes = sum(1 for qid, right in correct.items() if answers.get(qid) != right)
    extra_added = mistakes * PENALTY_PER_MISTAKE
    passed = mistakes <= EXAM_MISTAKE_LIMIT
    return passed, mistakes, extra_added


async def random_exam_questions(session: AsyncSession, n: int = EXAM_SIZE) -> list[PddQuestion]:
    """A random `n`-question ticket for the simulator (options eager-loaded)."""
    rows = await session.execute(select(PddQuestion).order_by(func.random()).limit(n))
    return list(rows.scalars().all())


def exam_payload(questions: list[PddQuestion]) -> list[dict[str, object]]:
    """Shape questions for the client-side exam component (JSON-embedded)."""
    return [
        {
            "id": q.id,
            "text": q.text,
            "image_path": q.image_path,
            "options": [{"position": o.position, "text": o.text} for o in q.options],
            "correct_position": q.correct_position,
            "explanation": q.explanation,
        }
        for q in questions
    ]


async def save_exam_session(
    session: AsyncSession, user: User, answers: list[ExamAnswerIn]
) -> PddExamSession:
    """Persist a finished run (Pro only — caller gates) and record each answer as
    an exam-source attempt so it feeds the trainer + stats. Server re-scores from
    the DB; the client result is not trusted."""
    qids = [a.question_id for a in answers]
    rows = (
        await session.execute(
            select(PddQuestion.id, PddQuestion.correct_position).where(PddQuestion.id.in_(qids))
        )
    ).all()
    correct = {row.id: row.correct_position for row in rows}
    answer_map = {a.question_id: a.chosen_position for a in answers}
    passed, mistakes, extra = score_exam(answer_map, correct)

    for a in answers:
        session.add(
            PddAttempt(
                user_id=user.id,
                question_id=a.question_id,
                chosen_position=a.chosen_position,
                is_correct=correct.get(a.question_id) == a.chosen_position,
                source="exam",
            )
        )
    exam = PddExamSession(
        user_id=user.id,
        question_ids=qids,
        total=len(qids),
        mistakes=mistakes,
        extra_added=extra,
        status="passed" if passed else "failed",
        finished_at=datetime.now(UTC),
    )
    session.add(exam)
    await session.commit()
    return exam


async def list_exam_sessions(
    session: AsyncSession, user: User, limit: int = 10
) -> list[PddExamSession]:
    rows = await session.execute(
        select(PddExamSession)
        .where(PddExamSession.user_id == user.id)
        .order_by(PddExamSession.started_at.desc())
        .limit(limit)
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
