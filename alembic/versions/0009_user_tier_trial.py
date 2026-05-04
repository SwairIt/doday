"""add tier + trial_ends_at to users

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("tier", sa.String(length=20), nullable=False, server_default="free"),
    )
    op.add_column(
        "users",
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Bootstrap trial for existing users — 14 days from now.
    op.execute(
        "UPDATE users SET trial_ends_at = NOW() + INTERVAL '14 days' WHERE trial_ends_at IS NULL"
    )


def downgrade() -> None:
    op.drop_column("users", "trial_ends_at")
    op.drop_column("users", "tier")
