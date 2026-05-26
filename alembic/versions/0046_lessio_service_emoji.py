"""Lessio: lessio_services.icon_emoji — per-service visual icon.

Revision ID: 0046
Revises: 0045
Create Date: 2026-05-27
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lessio_services",
        sa.Column("icon_emoji", sa.String(8), nullable=False, server_default="💼"),
    )


def downgrade() -> None:
    op.drop_column("lessio_services", "icon_emoji")
