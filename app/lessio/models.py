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
    CheckConstraint,
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
    # Web-expansion (migration 0042, 2026-05-25)
    default_meeting_url_template: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notification_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_calendar_refresh_token: Mapped[str | None] = mapped_column(String(500), nullable=True)
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
    # Web-expansion (migration 0042, 2026-05-25)
    meeting_url_template: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_group_session: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    max_attendees: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class LessioClient(Base):
    """Client (person who books with one tutor). Scoped per-tutor — один Telegram
    юзер у двух репетиторов = две row'ы, isolates data.

    Web-expansion 2026-05-25 (migration 0042):
    - telegram_user_id → nullable (web-клиенты без TG)
    - email NOT NULL, phone nullable, full_name NOT NULL
    - UNIQUE per-tutor by email (новая стандартная identity)
    - старый UNIQUE (tutor_id, telegram_user_id) убран — TG-клиенты идентифицируются
      по email тоже (placeholder lessio_tg_<id>@auto.lessio для legacy)
    """

    __tablename__ = "lessio_clients"
    __table_args__ = (UniqueConstraint("tutor_id", "email", name="uq_lessio_client_tutor_email"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tutor_id: Mapped[UUID] = mapped_column(
        ForeignKey("lessio_tutor_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    telegram_first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    telegram_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class LessioBooking(Base):
    """Confirmed appointment between tutor and client.

    Web-expansion 2026-05-25 (migration 0042):
    - UNIQUE (tutor_id, starts_at) убран — заменён на **partial unique index** в БД
      (WHERE status IN ('confirmed','completed') AND service не-групповая).
    - + manage_token (UNIQUE) — magic-link для клиента
    - + payment_status (unpaid/paid/refunded) + paid_at
    - + reminder_24h_sent_at, reminder_1h_sent_at (idempotency для cron)
    - + client_email, client_full_name (denorm)
    - + meeting_url (per-booking override)
    """

    __tablename__ = "lessio_bookings"

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
    # confirmed | completed | cancelled | no_show
    # Web-flow: default 'confirmed' т.к. постоплата off-platform — слот фиксируется
    # сразу, payment_status отслеживается отдельно.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="confirmed")
    price_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    price_stars: Mapped[int] = mapped_column(Integer, nullable=False)
    star_payment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("star_payments.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Web-expansion 0042
    manage_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    meeting_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payment_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unpaid", server_default="unpaid"
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reminder_24h_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reminder_1h_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    client_email: Mapped[str] = mapped_column(String(255), nullable=False)
    client_full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LessioReview(Base):
    """Отзыв клиента после завершённой встречи (status='completed').

    Один review per booking (UNIQUE). Client_email/full_name денормализованы —
    если LessioClient удалят, review останется читаемым.

    Aggregate rating tutor'а — SELECT count(*), avg(rating) FROM lessio_reviews
    WHERE tutor_id = ?. На /u/<slug> показываем aggregateRating в JSON-LD
    schema.org для SEO + последние N reviews для social proof.
    """

    __tablename__ = "lessio_reviews"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_lessio_review_rating_1_5"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    booking_id: Mapped[UUID] = mapped_column(
        ForeignKey("lessio_bookings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    tutor_id: Mapped[UUID] = mapped_column(
        ForeignKey("lessio_tutor_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_email: Mapped[str] = mapped_column(String(255), nullable=False)
    client_full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
