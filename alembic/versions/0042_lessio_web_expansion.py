"""Lessio web expansion — alter clients/bookings/services/tutor_profiles for web-flow.

Backward-compatible: все новые колонки nullable либо с server_default.
Partial-unique constraint на bookings (tutor_id, starts_at) для НЕ-групповых
встреч добавлен через op.execute (alembic-autogen не поддерживает partial-unique).

Revision ID: 0042
Revises: 0041
Create Date: 2026-05-25
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── lessio_clients ────────────────────────────────────────────────────
    op.alter_column(
        "lessio_clients", "telegram_user_id", existing_type=sa.BigInteger, nullable=True
    )
    op.add_column("lessio_clients", sa.Column("email", sa.String(255), nullable=True))
    op.add_column("lessio_clients", sa.Column("phone", sa.String(50), nullable=True))
    op.add_column("lessio_clients", sa.Column("full_name", sa.String(120), nullable=True))
    # Backfill для legacy TG-only clients (если есть). На dev/prod на момент 2026-05-25
    # lessio_clients пуст — UPDATE no-op. Если строки появятся между миграциями —
    # placeholder email/full_name генерируются из telegram_user_id/first_name.
    op.execute(
        "UPDATE lessio_clients SET "
        "email = 'legacy_tg_' || telegram_user_id::text || '@placeholder.lessio', "
        "full_name = COALESCE(telegram_first_name, 'TG User') "
        "WHERE email IS NULL"
    )
    op.alter_column("lessio_clients", "email", existing_type=sa.String(255), nullable=False)
    op.alter_column("lessio_clients", "full_name", existing_type=sa.String(120), nullable=False)
    op.create_index("ix_lessio_clients_email", "lessio_clients", ["email"])
    op.drop_constraint("uq_lessio_client_tutor_telegram", "lessio_clients", type_="unique")
    op.create_unique_constraint(
        "uq_lessio_client_tutor_email", "lessio_clients", ["tutor_id", "email"]
    )

    # ── lessio_services ───────────────────────────────────────────────────
    op.add_column(
        "lessio_services", sa.Column("meeting_url_template", sa.String(500), nullable=True)
    )
    op.add_column(
        "lessio_services",
        sa.Column("is_group_session", sa.Boolean, nullable=False, server_default="false"),
    )
    op.add_column(
        "lessio_services",
        sa.Column("max_attendees", sa.Integer, nullable=False, server_default="1"),
    )
    op.add_column("lessio_services", sa.Column("location", sa.String(500), nullable=True))

    # ── lessio_bookings ────────────────────────────────────────────────────
    op.add_column("lessio_bookings", sa.Column("manage_token", sa.String(64), nullable=True))
    op.add_column("lessio_bookings", sa.Column("meeting_url", sa.String(500), nullable=True))
    op.add_column(
        "lessio_bookings",
        sa.Column("payment_status", sa.String(20), nullable=False, server_default="unpaid"),
    )
    op.add_column(
        "lessio_bookings", sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "lessio_bookings",
        sa.Column("reminder_24h_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "lessio_bookings",
        sa.Column("reminder_1h_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("lessio_bookings", sa.Column("client_email", sa.String(255), nullable=True))
    op.add_column("lessio_bookings", sa.Column("client_full_name", sa.String(120), nullable=True))
    # Backfill для существующих bookings (пусто на момент миграции; safe no-op).
    # `md5(random()::text || clock_timestamp()::text)` даёт 32-hex string без
    # зависимости от pgcrypto extension. Для production-collision-resistance
    # бы использовали uuid-ossp + concat — но в проде lessio_bookings пуст.
    op.execute(
        "UPDATE lessio_bookings b SET "
        "manage_token = md5(random()::text || clock_timestamp()::text) "
        "  || md5(random()::text || clock_timestamp()::text), "
        "client_email = COALESCE("
        "  (SELECT email FROM lessio_clients WHERE id = b.client_id), "
        "  'unknown@example.com'), "
        "client_full_name = COALESCE("
        "  (SELECT full_name FROM lessio_clients WHERE id = b.client_id), "
        "  'Unknown') "
        "WHERE manage_token IS NULL"
    )
    op.alter_column("lessio_bookings", "manage_token", existing_type=sa.String(64), nullable=False)
    op.alter_column("lessio_bookings", "client_email", existing_type=sa.String(255), nullable=False)
    op.alter_column(
        "lessio_bookings", "client_full_name", existing_type=sa.String(120), nullable=False
    )
    op.create_unique_constraint(
        "uq_lessio_booking_manage_token", "lessio_bookings", ["manage_token"]
    )
    op.create_index("ix_lessio_booking_manage_token", "lessio_bookings", ["manage_token"])
    # Drop старый full unique (tutor_id, starts_at) — блокировал бы групповые
    # сессии (несколько участников = несколько rows на одном starts_at).
    # Postgres не позволяет subquery в index predicate, поэтому partial-unique
    # на is_group_session нельзя выразить чисто DB. Защита от double-booking
    # реализована на app-level в lessio.service.create_booking (проверяет
    # find_free_slots перед INSERT). Race-condition acceptable для MVP-нагрузки;
    # в Phase 2 — добавить is_group_booking denorm column + partial unique.
    op.drop_constraint("uq_lessio_booking_slot", "lessio_bookings", type_="unique")

    # ── lessio_tutor_profiles ─────────────────────────────────────────────
    op.add_column(
        "lessio_tutor_profiles",
        sa.Column("default_meeting_url_template", sa.String(500), nullable=True),
    )
    op.add_column(
        "lessio_tutor_profiles", sa.Column("notification_email", sa.String(255), nullable=True)
    )
    op.add_column(
        "lessio_tutor_profiles",
        sa.Column("google_calendar_refresh_token", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lessio_tutor_profiles", "google_calendar_refresh_token")
    op.drop_column("lessio_tutor_profiles", "notification_email")
    op.drop_column("lessio_tutor_profiles", "default_meeting_url_template")
    op.create_unique_constraint(
        "uq_lessio_booking_slot", "lessio_bookings", ["tutor_id", "starts_at"]
    )
    op.drop_index("ix_lessio_booking_manage_token", "lessio_bookings")
    op.drop_constraint("uq_lessio_booking_manage_token", "lessio_bookings", type_="unique")
    op.drop_column("lessio_bookings", "client_full_name")
    op.drop_column("lessio_bookings", "client_email")
    op.drop_column("lessio_bookings", "reminder_1h_sent_at")
    op.drop_column("lessio_bookings", "reminder_24h_sent_at")
    op.drop_column("lessio_bookings", "paid_at")
    op.drop_column("lessio_bookings", "payment_status")
    op.drop_column("lessio_bookings", "meeting_url")
    op.drop_column("lessio_bookings", "manage_token")
    op.drop_column("lessio_services", "location")
    op.drop_column("lessio_services", "max_attendees")
    op.drop_column("lessio_services", "is_group_session")
    op.drop_column("lessio_services", "meeting_url_template")
    op.drop_constraint("uq_lessio_client_tutor_email", "lessio_clients", type_="unique")
    op.create_unique_constraint(
        "uq_lessio_client_tutor_telegram",
        "lessio_clients",
        ["tutor_id", "telegram_user_id"],
    )
    op.drop_index("ix_lessio_clients_email", "lessio_clients")
    op.drop_column("lessio_clients", "full_name")
    op.drop_column("lessio_clients", "phone")
    op.drop_column("lessio_clients", "email")
    op.alter_column(
        "lessio_clients", "telegram_user_id", existing_type=sa.BigInteger, nullable=False
    )
