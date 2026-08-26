"""ORM ИИ-помощника: ключ провайдера, история чата, суточные лимиты."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AiCredential(Base):
    """Ключ доступа пользователя к LLM-провайдеру.

    Сам ключ лежит только в зашифрованном виде (app/ai/crypto.py). В
    интерфейс отдаётся key_last4, по которому владелец узнаёт свой ключ,
    но который бесполезен для постороннего.
    """

    __tablename__ = "ai_credentials"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    key_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    key_last4: Mapped[str] = mapped_column(String(8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class AiMessage(Base):
    """Одно сообщение диалога.

    Отдельной сущности «беседа» нет: диалог — это сообщения одного
    пользователя с одним task_id (или без него), упорядоченные по времени.
    Так проще и достаточно для нашего сценария.
    """

    __tablename__ = "ai_messages"
    __table_args__ = (Index("ix_ai_messages_thread", "user_id", "task_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, index=True
    )


class AiUsageDaily(Base):
    """Счётчик запросов за сутки.

    Живёт в БД, а не в памяти: деплой перезапускает процесс на каждый пуш,
    и счётчик в памяти обнулялся бы вместе с ним.
    """

    __tablename__ = "ai_usage_daily"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
