"""Lessio module — landing waitlist + tutor/service/client/booking tables.

Префикс `lessio_*` чтобы соседствовать с Doday-таблицами в `public`-схеме
без конфликтов. В фазе валидации (с 2026-05-25) используется только
`lessio_waitlist_entries`. Остальные таблицы — заготовка для MVP-фазы,
создаются вперёд чтобы не плодить migration-файлы потом.

Revision ID: 0040
Revises: 0039
Create Date: 2026-05-25
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── lessio_waitlist_entries (used during validation phase) ────────────
    op.create_table(
        "lessio_waitlist_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("telegram_handle", sa.String(100), nullable=True),
        sa.Column("niche", sa.String(40), nullable=False, server_default="other"),
        sa.Column("pain_point", sa.String(500), nullable=True),
        sa.Column("source", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint("uq_lessio_waitlist_email", "lessio_waitlist_entries", ["email"])
    op.create_index("ix_lessio_waitlist_email", "lessio_waitlist_entries", ["email"])

    # ── lessio_tutor_profiles (MVP scaffold) ──────────────────────────────
    op.create_table(
        "lessio_tutor_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("niche", sa.String(40), nullable=False, server_default="other"),
        sa.Column("bio", sa.String(1000), nullable=True),
        sa.Column("avatar_emoji", sa.String(8), nullable=False, server_default="👨‍🏫"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Europe/Moscow"),
        sa.Column(
            "working_days",
            postgresql.JSONB,
            nullable=False,
            server_default="[1, 2, 3, 4, 5]",
        ),
        sa.Column("work_start_minute", sa.Integer, nullable=False, server_default="540"),
        sa.Column("work_end_minute", sa.Integer, nullable=False, server_default="1260"),
        sa.Column("buffer_minutes", sa.Integer, nullable=False, server_default="15"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint("uq_lessio_tutor_user", "lessio_tutor_profiles", ["user_id"])
    op.create_unique_constraint("uq_lessio_tutor_slug", "lessio_tutor_profiles", ["slug"])
    op.create_index("ix_lessio_tutor_slug", "lessio_tutor_profiles", ["slug"])

    # ── lessio_services ───────────────────────────────────────────────────
    op.create_table(
        "lessio_services",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tutor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lessio_tutor_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("duration_minutes", sa.Integer, nullable=False, server_default="60"),
        sa.Column("price_kopecks", sa.Integer, nullable=False),
        sa.Column("price_stars", sa.Integer, nullable=False),
        sa.Column("package_size", sa.Integer, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_lessio_services_tutor", "lessio_services", ["tutor_id"])

    # ── lessio_clients ────────────────────────────────────────────────────
    op.create_table(
        "lessio_clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tutor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lessio_tutor_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("telegram_user_id", sa.BigInteger, nullable=False),
        sa.Column("telegram_first_name", sa.String(100), nullable=True),
        sa.Column("telegram_username", sa.String(100), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        "uq_lessio_client_tutor_telegram",
        "lessio_clients",
        ["tutor_id", "telegram_user_id"],
    )
    op.create_index("ix_lessio_clients_tutor", "lessio_clients", ["tutor_id"])
    op.create_index("ix_lessio_clients_telegram_user_id", "lessio_clients", ["telegram_user_id"])

    # ── lessio_bookings ───────────────────────────────────────────────────
    op.create_table(
        "lessio_bookings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tutor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lessio_tutor_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lessio_clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "service_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lessio_services.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending_payment"),
        sa.Column("price_kopecks", sa.Integer, nullable=False),
        sa.Column("price_stars", sa.Integer, nullable=False),
        sa.Column(
            "star_payment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("star_payments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint(
        "uq_lessio_booking_slot", "lessio_bookings", ["tutor_id", "starts_at"]
    )
    op.create_index("ix_lessio_bookings_tutor", "lessio_bookings", ["tutor_id"])
    op.create_index("ix_lessio_bookings_client", "lessio_bookings", ["client_id"])
    op.create_index("ix_lessio_bookings_service", "lessio_bookings", ["service_id"])
    op.create_index("ix_lessio_bookings_starts_at", "lessio_bookings", ["starts_at"])


def downgrade() -> None:
    op.drop_table("lessio_bookings")
    op.drop_table("lessio_clients")
    op.drop_table("lessio_services")
    op.drop_table("lessio_tutor_profiles")
    op.drop_table("lessio_waitlist_entries")
