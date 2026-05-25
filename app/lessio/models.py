"""Lessio ORM — все таблицы префиксованы `lessio_*` чтобы соседствовать с
Doday-таблицами в одной БД (`public`-схема) без конфликтов.

В фазе валидации реально используется только `lessio_waitlist_entries`.
Остальные таблицы — заготовка для MVP (после go-решения), создаются миграцией
сразу чтобы потом не плодить пустых migration-файлов.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class LessioWaitlistEntry(Base):
    """Validation-phase signup. Email + niche + pain_point + source."""

    __tablename__ = "lessio_waitlist_entries"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    telegram_handle: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # english | ielts | math | school | fitness | psychology | yoga | other
    niche: Mapped[str] = mapped_column(String(40), nullable=False, default="other")
    # Free-text "что мешает в работе" — самое ценное поле, оно подскажет MVP-приоритеты.
    pain_point: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class LessioTutorProfile(Base):
    """Public-facing tutor profile. One row per Doday-user who acts as a tutor.

    FK to `users.id` — Lessio переиспользует Doday'shний User (через
    Telegram-link или email auth). После MVP появится role-флаг.
    """

    __tablename__ = "lessio_tutor_profiles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    # URL-safe handle — основа invite-ссылки t.me/DodayTaskBot?start=<slug>
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # english | ielts | math | school | fitness | psychology | yoga | other
    niche: Mapped[str] = mapped_column(String(40), nullable=False, default="other")
    bio: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    avatar_emoji: Mapped[str] = mapped_column(String(8), nullable=False, default="👨‍🏫")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Europe/Moscow")
    # JSONB list of weekday numbers 1..7 (Mon=1)
    working_days: Mapped[list[int]] = mapped_column(
        JSONB, nullable=False, default=lambda: [1, 2, 3, 4, 5], server_default="[1, 2, 3, 4, 5]"
    )
    work_start_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=9 * 60)
    work_end_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=21 * 60)
    buffer_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class LessioService(Base):
    """Service offered by a tutor — 1ч английский, пакет 8 занятий, и т.д."""

    __tablename__ = "lessio_services"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tutor_id: Mapped[UUID] = mapped_column(
        ForeignKey("lessio_tutor_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    # Price stored in kopecks (₽1500 → 150000) — avoid float.
    price_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    # Stars equivalent (~1 Star ≈ ₽1.2 gross). Tutor can override "for round number".
    price_stars: Mapped[int] = mapped_column(Integer, nullable=False)
    package_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class LessioClient(Base):
    """Client (person who books with one tutor). Scoped per-tutor — same Telegram
    user across two tutors = two rows, isolates data.
    """

    __tablename__ = "lessio_clients"
    __table_args__ = (
        UniqueConstraint("tutor_id", "telegram_user_id", name="uq_lessio_client_tutor_telegram"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tutor_id: Mapped[UUID] = mapped_column(
        ForeignKey("lessio_tutor_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    telegram_first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    telegram_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class LessioBooking(Base):
    """Confirmed appointment between tutor and client."""

    __tablename__ = "lessio_bookings"
    __table_args__ = (
        # No two bookings at the same starts_at for one tutor.
        UniqueConstraint("tutor_id", "starts_at", name="uq_lessio_booking_slot"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tutor_id: Mapped[UUID] = mapped_column(
        ForeignKey("lessio_tutor_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id: Mapped[UUID] = mapped_column(
        ForeignKey("lessio_clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_id: Mapped[UUID] = mapped_column(
        ForeignKey("lessio_services.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    # pending_payment | paid | completed | cancelled | no_show
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_payment")
    price_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    price_stars: Mapped[int] = mapped_column(Integer, nullable=False)
    star_payment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("star_payments.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
