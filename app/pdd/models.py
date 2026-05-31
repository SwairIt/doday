"""SQLAlchemy ORM models for Doday PDD (driving-exam tickets).

Two groups of tables:

* **Content** (`pdd_topics`, `pdd_tickets`, `pdd_questions`, `pdd_options`) —
  immutable seed data from the official category A/B/M ticket set. Integer PKs;
  ``PddQuestion.public_slug`` is the stable SEO handle used in URLs.
* **User activity** (`pdd_attempts`, `pdd_exam_sessions`) — powers the Pro
  mistake trainer + statistics. Written only for logged-in users; anonymous
  practice persists nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ─── content ────────────────────────────────────────────────────────────────


class PddTopic(Base):
    """Official thematic grouping — drives `/pdd/tema/{slug}` SEO pages and the
    weak-topics analytics. Seeded from the dataset."""

    __tablename__ = "pdd_topics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Optional longer intro shown above the topic's question list (SEO copy).
    seo_intro: Mapped[str] = mapped_column(Text, nullable=False, default="")


class PddTicket(Base):
    """One of the 40 category A/B/M exam tickets (20 questions each)."""

    __tablename__ = "pdd_tickets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)


class PddQuestion(Base):
    """A single exam question. Belongs to exactly one ticket and one topic."""

    __tablename__ = "pdd_questions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Stable public handle for `/pdd/vopros/{public_slug}`, e.g. "bilet-1-vopros-3".
    public_slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("pdd_tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position_in_ticket: Mapped[int] = mapped_column(Integer, nullable=False)
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("pdd_topics.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Path under /static (e.g. "pdd/img/1_3.jpg"); NULL for text-only questions.
    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Official commentary shown after answering.
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 1-based index into the question's PddOption.position values.
    correct_position: Mapped[int] = mapped_column(Integer, nullable=False)

    # Eager (selectin) — async-safe and almost always needed alongside a question.
    options: Mapped[list[PddOption]] = relationship(
        "PddOption",
        order_by="PddOption.position",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    topic: Mapped[PddTopic] = relationship("PddTopic", lazy="selectin")
    ticket: Mapped[PddTicket] = relationship("PddTicket", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("ticket_id", "position_in_ticket", name="uq_pdd_question_ticket_pos"),
    )


class PddOption(Base):
    """One answer choice for a question (immutable seed content)."""

    __tablename__ = "pdd_options"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("pdd_questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("question_id", "position", name="uq_pdd_option_question_pos"),
    )


# ─── user activity ──────────────────────────────────────────────────────────


class PddAttempt(Base):
    """One answer event by a logged-in user — the log the trainer + stats read."""

    __tablename__ = "pdd_attempts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("pdd_questions.id", ondelete="CASCADE"), nullable=False
    )
    chosen_position: Mapped[int] = mapped_column(Integer, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # "practice" | "exam" | "trainer" — where the attempt happened.
    source: Mapped[str] = mapped_column(String(12), nullable=False, default="practice")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    __table_args__ = (
        Index("ix_pdd_attempt_user_question", "user_id", "question_id"),
        Index("ix_pdd_attempt_user_created", "user_id", "created_at"),
    )


class PddExamSession(Base):
    """One official-rules exam-simulator run. Persisted only for Pro users
    (free runs are scored client-side and not saved)."""

    __tablename__ = "pdd_exam_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Ordered question ids served this run.
    question_ids: Mapped[list[int]] = mapped_column(JSONB, nullable=False, default=list)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    mistakes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extra_added: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # "in_progress" | "passed" | "failed" | "abandoned"
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="in_progress")
