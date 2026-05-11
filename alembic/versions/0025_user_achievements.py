"""user_achievements — таблица unlocked-ачивок

Revision ID: 0025
Revises: 0024
Create Date: 2026-05-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_achievements",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("achievement_key", sa.String(length=64), primary_key=True),
        sa.Column(
            "unlocked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_user_achievements_unlocked_at",
        "user_achievements",
        ["unlocked_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_achievements_unlocked_at", table_name="user_achievements")
    op.drop_table("user_achievements")
