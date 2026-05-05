"""Task ORM model — the unit of work the user checks off."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.labels.models import Label


def _utcnow() -> datetime:
    return datetime.now(UTC)


class TaskPriority(StrEnum):
    P1 = "p1"  # urgent
    P2 = "p2"
    P3 = "p3"
    P4 = "p4"  # none / default


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_user_id", "user_id"),
        Index("ix_tasks_project_id", "project_id"),
        Index("ix_tasks_user_due_at", "user_id", "due_at"),
        Index("ix_tasks_parent", "parent_task_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    parent_task_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True
    )
    section_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sections.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_date_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority, name="task_priority", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=TaskPriority.P4,
    )
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # User-pinned tasks float to the top of every list. Timestamp instead of bool
    # so consistent ordering when several pins exist (most-recent pin first).
    pinned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Recurrence: None | "daily" | "weekly" | "monthly" | "yearly". Validated in schemas.
    recurrence: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    labels: Mapped[list["Label"]] = relationship(
        "Label", secondary="task_labels", lazy="selectin", order_by="Label.name"
    )
