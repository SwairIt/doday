"""ORM models for the habit tracker."""

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Habit(Base):
    """A named habit. archived_at hides it from the active list (soft-delete)."""

    __tablename__ = "habits"
    __table_args__ = (Index("ix_habits_user_id", "user_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    emoji: Mapped[str] = mapped_column(String(8), nullable=False, default="✅")
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="violet")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class HabitCheckin(Base):
    """One row per (habit, date). Date is UTC — same-day idempotency via uniq."""

    __tablename__ = "habit_checkins"
    __table_args__ = (
        UniqueConstraint("habit_id", "checkin_date", name="uq_habit_date"),
        Index("ix_checkins_habit", "habit_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    habit_id: Mapped[UUID] = mapped_column(
        ForeignKey("habits.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    checkin_date: Mapped[date] = mapped_column(Date(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
