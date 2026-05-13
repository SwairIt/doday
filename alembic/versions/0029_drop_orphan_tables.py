"""drop orphan tables left by 0028 (wrong names)

Revision ID: 0029
Revises: 0028
Create Date: 2026-05-13
"""

from __future__ import annotations

from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS time_entries CASCADE")
    op.execute("DROP TABLE IF EXISTS habit_checkins CASCADE")


def downgrade() -> None:
    raise NotImplementedError(
        "Aggressive cleanup is one-way; restore from pre-alpha-cleanup tag or "
        "pg_dump backup if needed."
    )
