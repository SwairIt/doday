"""Complaint model — user-submitted feedback shown in /app/root admin panel."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    page_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    viewport: Mapped[str | None] = mapped_column(String(20), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # open / in_progress / resolved / dismissed
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="open", server_default="open"
    )
    # low / normal / high
    priority: Mapped[str] = mapped_column(
        String(10), nullable=False, default="normal", server_default="normal"
    )
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
