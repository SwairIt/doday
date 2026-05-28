"""ORM models for the Razbery (Doday Q&A) feature.

Tables: qa_subject, qa_question, qa_answer, qa_vote, qa_user_stats, qa_report.

PK choice — `BigInt autoincrement` for question/answer so URLs read as
`/qa/q/1234-slug` (short, shareable). Users use UUID (existing Doday users
table).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class QASubject(Base):
    """Fixed taxonomy — 16 RU school subjects, seeded at migration time."""

    __tablename__ = "qa_subject"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    min_grade: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    max_grade: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str] = mapped_column(String(20), nullable=False, default="📚")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class QAQuestion(Base):
    __tablename__ = "qa_question"
    __table_args__ = (
        Index("ix_qa_question_subject_created", "subject_id", "created_at"),
        Index("ix_qa_question_score", "score"),
        Index("ix_qa_question_author", "author_id"),
        Index("ix_qa_question_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_qa_question_subject_grade_score",
            "subject_id",
            "grade",
            "score",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    author_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("qa_subject.id", ondelete="RESTRICT"), nullable=False
    )
    grade: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    answer_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    accepted_answer_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )  # FK declared in migration 0047 (circular dep); conftest drops it pre-drop_all
    is_seed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_hidden: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
    tsv: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)


class QAAnswer(Base):
    __tablename__ = "qa_answer"
    __table_args__ = (
        Index("ix_qa_answer_question_score", "question_id", "score"),
        Index("ix_qa_answer_author", "author_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("qa_question.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    answer_md: Mapped[str] = mapped_column(Text, nullable=False)
    answer_html: Mapped[str] = mapped_column(Text, nullable=False)
    explanation_md: Mapped[str] = mapped_column(Text, nullable=False)
    explanation_html: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_accepted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_seed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_hidden: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    tips_total_stars: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )  # phase-2 Stars tips accumulator — wired here so we don't migrate later
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class QAVote(Base):
    __tablename__ = "qa_vote"
    __table_args__ = (
        UniqueConstraint("user_id", "target_type", "target_id", name="uq_qa_vote_target"),
        Index("ix_qa_vote_target", "target_type", "target_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(String(1), nullable=False)  # 'q' or 'a'
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    value: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # +1 or -1
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class QAUserStats(Base):
    """Per-user denormalized stats — keeps hot paths off `count()` queries.

    Created lazily on first /qa action by a user.
    """

    __tablename__ = "qa_user_stats"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    display_name: Mapped[str] = mapped_column(String(50), nullable=False)
    display_slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    bio: Mapped[str | None] = mapped_column(String(280), nullable=True)
    avatar_emoji: Mapped[str] = mapped_column(
        String(8), nullable=False, default="📚", server_default="📚"
    )
    reputation: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    q_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    a_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    accepted_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    pro_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # phase-2 Pro tier
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class QAReport(Base):
    __tablename__ = "qa_report"
    __table_args__ = (
        Index("ix_qa_report_status", "status"),
        Index("ix_qa_report_target", "target_type", "target_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    reporter_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(String(1), nullable=False)
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="open", server_default="open"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
