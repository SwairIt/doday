"""ORM model for time-tracking entries — one row per start/stop session."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class TimeEntry(Base):
    """A single start/stop tracking session attached to a task.

    `ended_at IS NULL` ⇒ entry is currently running (a started timer).
    """

    __tablename__ = "time_entries"
    __table_args__ = (
        Index("ix_time_entries_user", "user_id"),
        Index("ix_time_entries_task", "task_id"),
        Index("ix_time_entries_running", "user_id", "ended_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
