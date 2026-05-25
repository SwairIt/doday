"""Lessio: last_daily_digest_at для idempotency dispatch_daily_digests.

Revision ID: 0044
Revises: 0043
Create Date: 2026-05-26
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lessio_tutor_profiles",
        sa.Column("last_daily_digest_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lessio_tutor_profiles", "last_daily_digest_at")
