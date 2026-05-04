"""ORM models for school-specific features (integrations + class schedule)."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SchoolIntegration(Base):
    """One row per (user, provider). Stores token + sync metadata.

    The token is stored as plaintext for now — flagged in the spec; before
    going to prod this column should be encrypted at rest (KMS / pgcrypto).
    """

    __tablename__ = "school_integrations"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_user_provider"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    auth_token: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    target_project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class ScheduleSlot(Base):
    """One row per (user, weekday, period). Stores the chosen subject + room.

    weekday is 0=Mon..6=Sun (Python convention). period is 1..10 (school
    classes are typically 1..8, leaving headroom). subject_code matches
    `app.school.subjects.SUBJECTS[*].code`.
    """

    __tablename__ = "schedule_slots"
    __table_args__ = (UniqueConstraint("user_id", "weekday", "period", name="uq_user_slot"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    period: Mapped[int] = mapped_column(Integer, nullable=False)
    subject_code: Mapped[str] = mapped_column(String(20), nullable=False)
    room: Mapped[str | None] = mapped_column(String(40), nullable=True)
    teacher: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
