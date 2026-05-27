"""Business logic for Razbery (Doday Q&A) feature.

All state changes go through this module — HTTP layer (`router.py`) only
deserializes and calls these functions. Tests mock the database session, not
the service.

Error model: domain-specific `QAError` subclasses; the HTTP layer translates
them to status codes.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import and_, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.qa import rate_limits, reputation
from app.qa.models import (
    QAAnswer,
    QAQuestion,
    QAReport,
    QASubject,
    QAUserStats,
    QAVote,
)
from app.qa.rendering import excerpt, render_markdown, slugify
from app.qa.schemas import (
    VALID_REPORT_REASONS,
    AnswerCreate,
    AnswerUpdate,
    QuestionCreate,
    QuestionUpdate,
    ReportIn,
    UserStatsUpdate,
)

log = structlog.get_logger("doday.qa.service")


# ─── errors ────────────────────────────────────────────────────────────────


class QAError(Exception):
    """Base class for service-layer errors."""


class NotFound(QAError):
    """Resource does not exist."""


class Forbidden(QAError):
    """User is not allowed to perform this action."""


class ValidationError(QAError):
    """Input failed validation (e.g. anti-cheating keyword found)."""


class RateLimited(QAError):
    """Per-user rate limit exceeded."""


# ─── anti-cheating heuristic ───────────────────────────────────────────────


_CHEATING_PATTERNS = [
    re.compile(r"\bсдела(й|йте)\s+(за\s+меня|мне)\s+домашк", re.IGNORECASE),
    re.compile(r"\bреш(и|ите)\s+за\s+меня\b", re.IGNORECASE),
    re.compile(r"\bнапиш(и|ите)\s+за\s+деньги\b", re.IGNORECASE),
    re.compile(r"\bкуплю\s+(решение|ответ)\b", re.IGNORECASE),
    re.compile(r"\b\+?7[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b"),  # phone
    re.compile(r"\bтелеграм[мн]?[:\s]+@\w+", re.IGNORECASE),  # tg-handle drop
]


def _contains_cheating_signal(text: str) -> str | None:
    """Return matching pattern as string, or None if clean."""
    for pat in _CHEATING_PATTERNS:
        if pat.search(text):
            return pat.pattern
    return None


# ─── subjects ──────────────────────────────────────────────────────────────


async def list_subjects(session: AsyncSession) -> list[QASubject]:
    rows = (await session.execute(select(QASubject).order_by(QASubject.position))).scalars().all()
    return list(rows)


async def get_subject_by_slug(session: AsyncSession, slug: str) -> QASubject | None:
    return (
        await session.execute(select(QASubject).where(QASubject.slug == slug))
    ).scalar_one_or_none()


async def get_subject(session: AsyncSession, subject_id: int) -> QASubject | None:
    return await session.get(QASubject, subject_id)


# ─── user stats / display name ─────────────────────────────────────────────


def _slugify_display_name(name: str, user_id: UUID) -> str:
    base = slugify(name, max_len=40)
    if not base:
        base = "user"
    # Append last 6 hex chars of user_id for uniqueness
    suffix = user_id.hex[-6:]
    return f"{base}-{suffix}"


async def ensure_user_stats(session: AsyncSession, user: User) -> QAUserStats:
    stats = await session.get(QAUserStats, user.id)
    if stats is not None:
        return stats
    # First /qa action by this user — create lazily
    default_name = (user.email.split("@", 1)[0] or "ученик")[:50]
    stats = QAUserStats(
        user_id=user.id,
        display_name=default_name,
        display_slug=_slugify_display_name(default_name, user.id),
        avatar_emoji="📚",
        reputation=1,
    )
    session.add(stats)
    await session.flush()
    return stats


async def get_user_stats_by_slug(session: AsyncSession, display_slug: str) -> QAUserStats | None:
    return (
        await session.execute(select(QAUserStats).where(QAUserStats.display_slug == display_slug))
    ).scalar_one_or_none()


async def update_user_stats(
    session: AsyncSession, user: User, data: UserStatsUpdate
) -> QAUserStats:
    stats = await ensure_user_stats(session, user)
    if data.display_name is not None:
        stats.display_name = data.display_name
        stats.display_slug = _slugify_display_name(data.display_name, user.id)
    if data.bio is not None:
        stats.bio = data.bio
    if data.avatar_emoji is not None:
        stats.avatar_emoji = data.avatar_emoji
    stats.updated_at = datetime.now(UTC)
    await session.flush()
    return stats


async def _adjust_rep(session: AsyncSession, user_id: UUID | None, delta: int) -> None:
    if user_id is None or delta == 0:
        return
    stats = await session.get(QAUserStats, user_id)
    if stats is None:
        return  # user has no stats row yet — shouldn't happen for action-author paths
    stats.reputation = reputation.clamp_floor(stats.reputation + delta)
    stats.updated_at = datetime.now(UTC)


# ─── questions ─────────────────────────────────────────────────────────────


async def create_question(session: AsyncSession, author: User, data: QuestionCreate) -> QAQuestion:
    stats = await ensure_user_stats(session, author)

    if not rate_limits.hit(
        rate_limits.QAAction.ASK_QUESTION, str(author.id), user_rep=stats.reputation
    ):
        raise RateLimited("Слишком много вопросов за час. Подожди немного.")

    signal = _contains_cheating_signal(data.title + "\n" + data.body_md)
    if signal:
        log.info("qa.cheating_signal", user_id=str(author.id), pattern=signal[:50])
        raise ValidationError(
            "Похоже, ты просишь решить за тебя. Razbery помогает разобраться, "
            "а не списать. Переформулируй вопрос как «как это делается», и "
            "тебе помогут разобраться."
        )

    subject = await get_subject_by_slug(session, data.subject_slug)
    if subject is None:
        raise NotFound(f"Предмет «{data.subject_slug}» не найден")
    if data.grade is not None and not (subject.min_grade <= data.grade <= subject.max_grade):
        raise ValidationError(
            f"Класс {data.grade} не подходит для «{subject.name}» — допустимо "
            f"{subject.min_grade}–{subject.max_grade}."
        )

    slug = slugify(data.title)
    body_html = render_markdown(data.body_md)

    q = QAQuestion(
        author_id=author.id,
        subject_id=subject.id,
        grade=data.grade,
        title=data.title,
        slug=slug,
        body_md=data.body_md,
        body_html=body_html,
    )
    session.add(q)
    stats.q_count += 1
    await session.flush()
    return q


async def update_question(
    session: AsyncSession, user: User, qid: int, data: QuestionUpdate
) -> QAQuestion:
    q = await session.get(QAQuestion, qid)
    if q is None or q.is_hidden:
        raise NotFound("Вопрос не найден")
    stats = await ensure_user_stats(session, user)
    is_author = q.author_id == user.id
    can_edit = is_author or reputation.can(stats.reputation, reputation.Privilege.EDIT_OTHERS)
    if not can_edit:
        raise Forbidden("Только автор или модератор может редактировать вопрос")
    if data.title is not None:
        q.title = data.title
        q.slug = slugify(data.title)
    if data.body_md is not None:
        q.body_md = data.body_md
        q.body_html = render_markdown(data.body_md)
    if data.grade is not None:
        subject = await get_subject(session, q.subject_id)
        if subject and (subject.min_grade <= data.grade <= subject.max_grade):
            q.grade = data.grade
    q.updated_at = datetime.now(UTC)
    await session.flush()
    return q


async def get_question(session: AsyncSession, qid: int) -> QAQuestion | None:
    q = await session.get(QAQuestion, qid)
    if q is None or q.is_hidden:
        return None
    return q


async def increment_view_count(session: AsyncSession, qid: int) -> None:
    """Fire-and-forget view counter — failures swallowed (it's just a stat)."""
    try:
        await session.execute(
            update(QAQuestion)
            .where(QAQuestion.id == qid)
            .values(view_count=QAQuestion.view_count + 1)
        )
    except Exception as exc:
        log.warning("qa.view_count.fail", qid=qid, err=str(exc))


async def list_questions(
    session: AsyncSession,
    *,
    subject_id: int | None = None,
    grade: int | None = None,
    sort: str = "recent",
    only_unanswered: bool = False,
    offset: int = 0,
    limit: int = 20,
) -> list[QAQuestion]:
    stmt = select(QAQuestion).where(QAQuestion.is_hidden.is_(False))
    if subject_id is not None:
        stmt = stmt.where(QAQuestion.subject_id == subject_id)
    if grade is not None:
        stmt = stmt.where(QAQuestion.grade == grade)
    if only_unanswered:
        stmt = stmt.where(QAQuestion.answer_count == 0)
    if sort == "top":
        stmt = stmt.order_by(desc(QAQuestion.score), desc(QAQuestion.created_at))
    elif sort == "viewed":
        stmt = stmt.order_by(desc(QAQuestion.view_count), desc(QAQuestion.created_at))
    else:  # recent
        stmt = stmt.order_by(desc(QAQuestion.created_at))
    stmt = stmt.offset(offset).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)


async def search_questions(
    session: AsyncSession,
    query: str,
    *,
    subject_id: int | None = None,
    grade: int | None = None,
    limit: int = 20,
) -> list[QAQuestion]:
    """Full-text search via Postgres tsvector (russian config).

    Falls back to ILIKE if the database lacks the tsv column populated (e.g.
    SQLite test fallback). Title is weight A, body weight B (see migration
    trigger).
    """
    query = query.strip()
    if not query:
        return []

    try:
        # plainto_tsquery is forgiving — handles stop words and stems.
        from sqlalchemy import func, literal

        ts_query = func.plainto_tsquery("russian", literal(query))
        stmt = (
            select(QAQuestion)
            .where(
                and_(
                    QAQuestion.is_hidden.is_(False),
                    QAQuestion.tsv.op("@@")(ts_query),
                )
            )
            .order_by(
                desc(func.ts_rank_cd(QAQuestion.tsv, ts_query)),
                desc(QAQuestion.score),
                desc(QAQuestion.created_at),
            )
        )
        if subject_id is not None:
            stmt = stmt.where(QAQuestion.subject_id == subject_id)
        if grade is not None:
            stmt = stmt.where(QAQuestion.grade == grade)
        stmt = stmt.limit(limit)
        rows = (await session.execute(stmt)).scalars().all()
        if rows:
            return list(rows)
    except Exception as exc:
        log.warning("qa.search.tsv_failed_fallback_ilike", err=str(exc)[:200])

    # Fallback for tests / when tsv is empty (no trigger run yet).
    pattern = f"%{query}%"
    stmt2 = select(QAQuestion).where(
        and_(
            QAQuestion.is_hidden.is_(False),
            or_(QAQuestion.title.ilike(pattern), QAQuestion.body_md.ilike(pattern)),
        )
    )
    if subject_id is not None:
        stmt2 = stmt2.where(QAQuestion.subject_id == subject_id)
    if grade is not None:
        stmt2 = stmt2.where(QAQuestion.grade == grade)
    stmt2 = stmt2.order_by(desc(QAQuestion.score), desc(QAQuestion.created_at)).limit(limit)
    rows2 = (await session.execute(stmt2)).scalars().all()
    return list(rows2)


async def find_similar(
    session: AsyncSession, title: str, *, subject_id: int | None = None, limit: int = 3
) -> list[QAQuestion]:
    """Suggest related questions for the ask-form (duplicate-avoidance)."""
    words = [w for w in re.split(r"\W+", title) if len(w) > 3]
    if not words:
        return []
    top = words[:4]
    stmt = select(QAQuestion).where(QAQuestion.is_hidden.is_(False))
    if subject_id is not None:
        stmt = stmt.where(QAQuestion.subject_id == subject_id)
    # OR of ilike per word
    or_conds = [QAQuestion.title.ilike(f"%{w}%") for w in top]
    stmt = stmt.where(or_(*or_conds))
    stmt = stmt.order_by(desc(QAQuestion.score), desc(QAQuestion.created_at)).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)


async def count_questions(
    session: AsyncSession,
    *,
    subject_id: int | None = None,
    grade: int | None = None,
) -> int:
    stmt = select(func.count(QAQuestion.id)).where(QAQuestion.is_hidden.is_(False))
    if subject_id is not None:
        stmt = stmt.where(QAQuestion.subject_id == subject_id)
    if grade is not None:
        stmt = stmt.where(QAQuestion.grade == grade)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


# ─── answers ───────────────────────────────────────────────────────────────


async def create_answer(
    session: AsyncSession, author: User, qid: int, data: AnswerCreate
) -> QAAnswer:
    stats = await ensure_user_stats(session, author)

    if not rate_limits.hit(rate_limits.QAAction.ANSWER, str(author.id), user_rep=stats.reputation):
        raise RateLimited("Слишком много ответов за час. Подожди немного.")

    q = await session.get(QAQuestion, qid)
    if q is None or q.is_hidden:
        raise NotFound("Вопрос не найден")

    signal = _contains_cheating_signal(data.answer_md + "\n" + data.explanation_md)
    if signal:
        raise ValidationError(
            "В тексте найдены контакты или предложение «решить за деньги» — "
            "Razbery бесплатная платформа, такие сообщения не публикуются."
        )

    a = QAAnswer(
        question_id=qid,
        author_id=author.id,
        answer_md=data.answer_md,
        answer_html=render_markdown(data.answer_md),
        explanation_md=data.explanation_md,
        explanation_html=render_markdown(data.explanation_md),
    )
    session.add(a)
    q.answer_count += 1
    q.updated_at = datetime.now(UTC)
    stats.a_count += 1
    await session.flush()
    return a


async def get_answers_for_question(session: AsyncSession, qid: int) -> list[QAAnswer]:
    stmt = (
        select(QAAnswer)
        .where(and_(QAAnswer.question_id == qid, QAAnswer.is_hidden.is_(False)))
        .order_by(desc(QAAnswer.is_accepted), desc(QAAnswer.score), QAAnswer.created_at)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)


async def update_answer(
    session: AsyncSession, user: User, aid: int, data: AnswerUpdate
) -> QAAnswer:
    a = await session.get(QAAnswer, aid)
    if a is None or a.is_hidden:
        raise NotFound("Ответ не найден")
    stats = await ensure_user_stats(session, user)
    is_author = a.author_id == user.id
    can_edit = is_author or reputation.can(stats.reputation, reputation.Privilege.EDIT_OTHERS)
    if not can_edit:
        raise Forbidden("Только автор или модератор может редактировать ответ")
    if data.answer_md is not None:
        a.answer_md = data.answer_md
        a.answer_html = render_markdown(data.answer_md)
    if data.explanation_md is not None:
        a.explanation_md = data.explanation_md
        a.explanation_html = render_markdown(data.explanation_md)
    a.updated_at = datetime.now(UTC)
    await session.flush()
    return a


# ─── voting ────────────────────────────────────────────────────────────────


async def vote(
    session: AsyncSession,
    voter: User,
    target_type: str,
    target_id: int,
    value: int,
) -> int:
    """Set/update/remove voter's vote on target. Returns new target score.

    value ∈ {-1, 0, +1}. Zero means un-vote (idempotent if no vote exists).
    """
    if target_type not in ("q", "a"):
        raise ValidationError("invalid target_type")
    if value not in (-1, 0, 1):
        raise ValidationError("invalid value")

    stats = await ensure_user_stats(session, voter)
    if not rate_limits.hit(rate_limits.QAAction.VOTE, str(voter.id), user_rep=stats.reputation):
        raise RateLimited("Слишком много голосов за час.")

    # Downvotes require rep
    if value == -1 and not reputation.can(stats.reputation, reputation.Privilege.DOWNVOTE):
        raise Forbidden(
            f"Голосовать против можно с репутации {int(reputation.Privilege.DOWNVOTE)}. "
            f"Твоя — {stats.reputation}."
        )

    # Load target
    target: QAQuestion | QAAnswer | None
    if target_type == "q":
        target = await session.get(QAQuestion, target_id)
    else:
        target = await session.get(QAAnswer, target_id)
    if target is None or getattr(target, "is_hidden", False):
        raise NotFound("Цель голоса не найдена")
    if target.author_id == voter.id:
        raise Forbidden("Нельзя голосовать за свой контент")

    # Find existing vote
    existing = (
        await session.execute(
            select(QAVote).where(
                and_(
                    QAVote.user_id == voter.id,
                    QAVote.target_type == target_type,
                    QAVote.target_id == target_id,
                )
            )
        )
    ).scalar_one_or_none()

    old_value = existing.value if existing else 0
    new_value = value

    # No-op
    if old_value == new_value:
        if new_value == 0 and existing is not None:
            await session.delete(existing)
        return target.score

    # Compute score delta and reputation deltas
    score_delta = new_value - old_value

    # Reputation deltas to target author
    rep_delta_author = _author_rep_delta(target_type, old_value, new_value)
    # Reputation cost for the voter (downvote casting)
    rep_delta_voter = _voter_rep_delta(old_value, new_value)

    # Update or insert/delete vote row
    if new_value == 0:
        if existing is not None:
            await session.delete(existing)
    elif existing is not None:
        existing.value = new_value
    else:
        session.add(
            QAVote(
                user_id=voter.id,
                target_type=target_type,
                target_id=target_id,
                value=new_value,
            )
        )

    # Apply score delta to target
    target.score += score_delta
    # Auto-hide threshold
    if target.score <= -5 and not target.is_hidden:
        target.is_hidden = True
        await _adjust_rep(
            session,
            target.author_id,
            reputation.ReputationDelta.Q_HIDDEN
            if target_type == "q"
            else reputation.ReputationDelta.A_HIDDEN,
        )

    await _adjust_rep(session, target.author_id, rep_delta_author)
    await _adjust_rep(session, voter.id, rep_delta_voter)

    await session.flush()
    return target.score


def _author_rep_delta(target_type: str, old: int, new: int) -> int:
    """How much the target's author's rep changes for this vote transition."""
    if target_type == "q":
        up = int(reputation.ReputationDelta.Q_UPVOTE)
        down = int(reputation.ReputationDelta.Q_DOWNVOTE)
    else:
        up = int(reputation.ReputationDelta.A_UPVOTE)
        down = int(reputation.ReputationDelta.A_DOWNVOTE)
    # Map (old, new) → delta
    # Reverse old first, then apply new.
    delta = 0
    if old == 1:
        delta -= up
    elif old == -1:
        delta -= down
    if new == 1:
        delta += up
    elif new == -1:
        delta += down
    return delta


def _voter_rep_delta(old: int, new: int) -> int:
    """How much the voter pays for casting/changing a downvote."""
    cost = int(reputation.ReputationDelta.DOWNVOTER_COST)
    delta = 0
    if old == -1:
        delta -= cost  # refund
    if new == -1:
        delta += cost  # charge
    return delta


# ─── accept / unaccept ─────────────────────────────────────────────────────


async def accept_answer(session: AsyncSession, asker: User, aid: int) -> None:
    a = await session.get(QAAnswer, aid)
    if a is None or a.is_hidden:
        raise NotFound("Ответ не найден")
    q = await session.get(QAQuestion, a.question_id)
    if q is None or q.is_hidden:
        raise NotFound("Вопрос не найден")
    if q.author_id != asker.id:
        raise Forbidden("Только автор вопроса может принять ответ")

    if not rate_limits.hit(rate_limits.QAAction.ACCEPT, str(asker.id)):
        raise RateLimited("Слишком много действий accept.")

    # Un-accept previous if any
    if q.accepted_answer_id is not None and q.accepted_answer_id != aid:
        prev = await session.get(QAAnswer, q.accepted_answer_id)
        if prev is not None:
            prev.is_accepted = False
            await _adjust_rep(
                session, prev.author_id, -int(reputation.ReputationDelta.A_ACCEPTED_AUTHOR)
            )

    if not a.is_accepted:
        a.is_accepted = True
        q.accepted_answer_id = a.id
        await _adjust_rep(session, a.author_id, reputation.ReputationDelta.A_ACCEPTED_AUTHOR)
        await _adjust_rep(session, asker.id, reputation.ReputationDelta.A_ACCEPTED_ASKER)
        # Increment answerer's accepted_count
        if a.author_id is not None:
            answerer_stats = await session.get(QAUserStats, a.author_id)
            if answerer_stats is not None:
                answerer_stats.accepted_count += 1

    await session.flush()


async def unaccept_answer(session: AsyncSession, asker: User, qid: int) -> None:
    q = await session.get(QAQuestion, qid)
    if q is None:
        raise NotFound("Вопрос не найден")
    if q.author_id != asker.id:
        raise Forbidden("Только автор вопроса может отменить принятие")
    if q.accepted_answer_id is None:
        return
    a = await session.get(QAAnswer, q.accepted_answer_id)
    if a is not None:
        a.is_accepted = False
        await _adjust_rep(session, a.author_id, -int(reputation.ReputationDelta.A_ACCEPTED_AUTHOR))
        if a.author_id is not None:
            answerer_stats = await session.get(QAUserStats, a.author_id)
            if answerer_stats is not None and answerer_stats.accepted_count > 0:
                answerer_stats.accepted_count -= 1
    q.accepted_answer_id = None
    await session.flush()


# ─── reports ───────────────────────────────────────────────────────────────


async def report(session: AsyncSession, reporter: User, data: ReportIn) -> QAReport:
    if data.reason not in VALID_REPORT_REASONS:
        raise ValidationError(
            f"Неизвестная причина «{data.reason}». Допустимо: {sorted(VALID_REPORT_REASONS)}"
        )
    if not rate_limits.hit(rate_limits.QAAction.REPORT, str(reporter.id)):
        raise RateLimited("Слишком много жалоб за час.")
    # Verify target exists
    target: QAQuestion | QAAnswer | None
    if data.target_type == "q":
        target = await session.get(QAQuestion, data.target_id)
    else:
        target = await session.get(QAAnswer, data.target_id)
    if target is None:
        raise NotFound("Цель жалобы не найдена")
    r = QAReport(
        reporter_id=reporter.id,
        target_type=data.target_type,
        target_id=data.target_id,
        reason=data.reason,
        comment=data.comment,
    )
    session.add(r)
    await session.flush()
    return r


async def list_open_reports(session: AsyncSession, limit: int = 50) -> list[QAReport]:
    stmt = (
        select(QAReport).where(QAReport.status == "open").order_by(QAReport.created_at).limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)


async def resolve_report(session: AsyncSession, rid: int, *, hide_target: bool) -> QAReport:
    r = await session.get(QAReport, rid)
    if r is None:
        raise NotFound("Жалоба не найдена")
    if r.status != "open":
        return r
    if hide_target:
        if r.target_type == "q":
            q = await session.get(QAQuestion, r.target_id)
            if q is not None:
                q.is_hidden = True
        else:
            a = await session.get(QAAnswer, r.target_id)
            if a is not None:
                a.is_hidden = True
        r.status = "resolved"
    else:
        r.status = "rejected"
    await session.flush()
    return r


# ─── user listings ─────────────────────────────────────────────────────────


async def list_user_questions(
    session: AsyncSession, user_id: UUID, *, limit: int = 50
) -> list[QAQuestion]:
    stmt = (
        select(QAQuestion)
        .where(and_(QAQuestion.author_id == user_id, QAQuestion.is_hidden.is_(False)))
        .order_by(desc(QAQuestion.created_at))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)


async def list_user_answers(
    session: AsyncSession, user_id: UUID, *, limit: int = 50
) -> list[QAAnswer]:
    stmt = (
        select(QAAnswer)
        .where(and_(QAAnswer.author_id == user_id, QAAnswer.is_hidden.is_(False)))
        .order_by(desc(QAAnswer.score), desc(QAAnswer.created_at))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)


# ─── user vote state (for rendering "you upvoted this" UI) ─────────────────


async def get_user_votes(
    session: AsyncSession,
    user_id: UUID,
    target_type: str,
    target_ids: list[int],
) -> dict[int, int]:
    """Return {target_id: value} for votes the user has cast on these targets."""
    if not target_ids:
        return {}
    stmt = select(QAVote.target_id, QAVote.value).where(
        and_(
            QAVote.user_id == user_id,
            QAVote.target_type == target_type,
            QAVote.target_id.in_(target_ids),
        )
    )
    result = await session.execute(stmt)
    return {row.target_id: row.value for row in result}


def question_url(q: QAQuestion) -> str:
    return f"/qa/q/{q.id}-{q.slug}"


def make_meta_description(body_md: str) -> str:
    return excerpt(body_md, limit=160)
