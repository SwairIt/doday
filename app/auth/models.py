"""SQLAlchemy ORM models for the auth feature."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _trial_default() -> datetime:
    return datetime.now(UTC) + timedelta(days=14)


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    tier: Mapped[str] = mapped_column(String(20), nullable=False, default="free")
    trial_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=_trial_default
    )
    # Long-lived per-user token for unauthenticated calendar feeds (.ics). Lazy
    # — generated on first /api/calendar/feed request. Rotatable via /profile.
    ical_token: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    # Morning digest opt-in. False by default — explicit opt-in via /profile.
    # Cron worker shells `last_sent_at` after each successful send to dedupe.
    morning_digest_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    morning_digest_last_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # True for the operator account (yarik@doday.app on prod). Gives access to
    # /app/root admin panel, /api/admin/* endpoints, and complaint management.
    # Set via SQL/migration, never via UI — no risk of self-promotion.
    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # Per-user opt-in flags for experimental features (revived/in-progress).
    # Shape: {"graph": true, "habits": false, ...}. Defaults to empty dict so
    # experimental features stay OFF unless the user enables them in settings.
    experiments: Mapped[dict[str, bool]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    # When the user's paid Pro subscription expires (NULL = no paid sub, ever
    # or already lapsed long ago). effective_tier() returns "pro" while this
    # is in the future; otherwise falls back to trial / free. Payment via
    # Telegram Stars extends this — see app/billing/stars.py.
    pro_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
