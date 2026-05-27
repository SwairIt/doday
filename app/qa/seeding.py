"""Pipeline that loads agent-generated seed JSON into the database.

Usage:
    uv run python -m app.qa.seed_load            # ingests every *.json in seed_data/
    uv run python -m app.qa.seed_load --file=app/qa/seed_data/algebra.json

Idempotency:
- A system bot user is created or fetched by email.
- Each (subject_id, title) pair is treated as a natural key — re-running
  the loader skips already-imported questions.
- Subjects must already exist (seeded in the Alembic migration).
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import structlog
from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.db import get_session_maker
from app.qa.models import QAAnswer, QAQuestion, QASubject, QAUserStats
from app.qa.rendering import render_markdown, slugify
from app.qa.schemas import ANSWER_MIN, BODY_MIN, EXPLANATION_MIN, TITLE_MAX, TITLE_MIN
from app.qa.seed_topics import (
    BOT_USER_BIO,
    BOT_USER_DISPLAY_NAME,
    BOT_USER_DISPLAY_SLUG,
    BOT_USER_EMAIL,
)

log = structlog.get_logger("doday.qa.seed")


class SeedAnswer(BaseModel):
    answer_md: str = Field(min_length=ANSWER_MIN)
    explanation_md: str = Field(min_length=EXPLANATION_MIN)


class SeedQuestion(BaseModel):
    subject_slug: str
    grade: int | None = Field(default=None, ge=5, le=11)
    title: str = Field(min_length=TITLE_MIN, max_length=TITLE_MAX)
    body_md: str = Field(min_length=BODY_MIN)
    answers: list[SeedAnswer] = Field(min_length=1)


# ─── bot user ──────────────────────────────────────────────────────────────


async def get_or_create_bot_user(session: AsyncSession) -> User:
    user = (
        await session.execute(select(User).where(User.email == BOT_USER_EMAIL))
    ).scalar_one_or_none()
    if user is not None:
        return user
    user = User(
        email=BOT_USER_EMAIL,
        password_hash=None,
        email_verified_at=datetime.now(UTC),
        tier="free",
    )
    session.add(user)
    await session.flush()
    # Bot stats
    stats = QAUserStats(
        user_id=user.id,
        display_name=BOT_USER_DISPLAY_NAME,
        display_slug=BOT_USER_DISPLAY_SLUG,
        bio=BOT_USER_BIO,
        avatar_emoji="🤖",
        reputation=1000,
    )
    session.add(stats)
    await session.flush()
    log.info("qa.seed.bot_created", user_id=str(user.id))
    return user


# ─── loader ────────────────────────────────────────────────────────────────


async def _ingest_question(
    session: AsyncSession,
    bot: User,
    subject_map: dict[str, QASubject],
    item: SeedQuestion,
) -> bool:
    subject = subject_map.get(item.subject_slug)
    if subject is None:
        log.warning("qa.seed.subject_missing", slug=item.subject_slug, title=item.title[:60])
        return False
    # Idempotency: skip if (subject, title) already exists
    existing = (
        await session.execute(
            select(QAQuestion.id).where(
                and_(
                    QAQuestion.subject_id == subject.id,
                    QAQuestion.title == item.title,
                )
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return False
    item_grade: int | None
    if item.grade is not None and not (subject.min_grade <= item.grade <= subject.max_grade):
        # Clip to nearest valid grade
        item_grade = max(subject.min_grade, min(item.grade, subject.max_grade))
    else:
        item_grade = item.grade
    q = QAQuestion(
        author_id=bot.id,
        subject_id=subject.id,
        grade=item_grade,
        title=item.title,
        slug=slugify(item.title),
        body_md=item.body_md,
        body_html=render_markdown(item.body_md),
        is_seed=True,
        answer_count=len(item.answers),
    )
    session.add(q)
    await session.flush()
    for i, a in enumerate(item.answers):
        ans = QAAnswer(
            question_id=q.id,
            author_id=bot.id,
            answer_md=a.answer_md,
            answer_html=render_markdown(a.answer_md),
            explanation_md=a.explanation_md,
            explanation_html=render_markdown(a.explanation_md),
            is_seed=True,
            is_accepted=(i == 0),  # first answer accepted by default
        )
        session.add(ans)
        await session.flush()
        if i == 0:
            q.accepted_answer_id = ans.id
    return True


async def apply_seed_items(session: AsyncSession, items: list[SeedQuestion]) -> tuple[int, int]:
    """Ingest items. Returns (inserted, skipped)."""
    bot = await get_or_create_bot_user(session)
    subjects = (await session.execute(select(QASubject))).scalars().all()
    subject_map = {s.slug: s for s in subjects}
    inserted = 0
    skipped = 0
    for it in items:
        try:
            ok = await _ingest_question(session, bot, subject_map, it)
            if ok:
                inserted += 1
            else:
                skipped += 1
        except Exception as exc:
            log.warning(
                "qa.seed.ingest_error",
                title=it.title[:80],
                err=str(exc)[:200],
            )
            skipped += 1
    return inserted, skipped


def load_json_file(path: Path) -> list[SeedQuestion]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"{path}: expected top-level JSON array")
    out: list[SeedQuestion] = []
    for i, obj in enumerate(raw):
        try:
            out.append(SeedQuestion.model_validate(obj))
        except PydanticValidationError as exc:
            log.warning("qa.seed.invalid_row", file=str(path), idx=i, err=str(exc)[:300])
    return out


def load_dir(dir_path: Path) -> list[SeedQuestion]:
    items: list[SeedQuestion] = []
    for p in sorted(dir_path.glob("*.json")):
        items.extend(load_json_file(p))
    return items


async def run(file: Path | None = None) -> tuple[int, int]:
    if file is not None:
        items = load_json_file(file)
    else:
        items = load_dir(Path("app/qa/seed_data"))
    if not items:
        log.warning("qa.seed.no_items_loaded")
        return 0, 0
    Session = get_session_maker()
    async with Session() as session:
        inserted, skipped = await apply_seed_items(session, items)
        await session.commit()
    log.info("qa.seed.done", inserted=inserted, skipped=skipped, total=len(items))
    return inserted, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Load Razbery seed Q&A content")
    parser.add_argument("--file", type=Path, help="single JSON file")
    args = parser.parse_args()
    inserted, skipped = asyncio.run(run(file=args.file))
    print(f"inserted={inserted} skipped={skipped}")


if __name__ == "__main__":
    main()
