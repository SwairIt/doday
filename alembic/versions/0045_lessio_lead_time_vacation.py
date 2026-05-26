"""Lessio: booking_lead_hours + vacation_until для tutor profile.

booking_lead_hours: int, default 2 — клиент НЕ может забронировать раньше
чем за N часов до начала встречи (защита от last-minute booking).

vacation_until: timestamp nullable — пока > now(), все слоты до этого
момента скрыты (tutor в отпуске / болен / релокейтится).

Revision ID: 0045
Revises: 0044
Create Date: 2026-05-27
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lessio_tutor_profiles",
        sa.Column("booking_lead_hours", sa.Integer, nullable=False, server_default="2"),
    )
    op.add_column(
        "lessio_tutor_profiles",
        sa.Column("vacation_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lessio_tutor_profiles", "vacation_until")
    op.drop_column("lessio_tutor_profiles", "booking_lead_hours")
