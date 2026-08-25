"""Notification model — колокольчик в топбаре для всех пользователей.

Пока источник один: реакции админа на обращения в поддержку («взял в работу»,
«ответил»). Модель сделана общей (kind/title/body/link), чтобы позже под неё
легко завести другие события без изменения схемы.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Тип события: support_in_progress | support_reply | ... — под будущие источники.
    kind: Mapped[str] = mapped_column(String(30), nullable=False, default="generic")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Куда ведёт клик по уведомлению (например /support или /app/today). NULL — никуда.
    link: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # NULL — не прочитано. Проставляем время при открытии колокольчика.
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )
