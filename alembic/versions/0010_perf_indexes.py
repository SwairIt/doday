"""perf indexes — partial index on tasks(user_id, completed_at) for stats queries

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Used by: stats (date(completed_at) for streaks/charts), done view, daily-goal counter.
    # Partial index — only rows where completed_at IS NOT NULL.
    op.create_index(
        "ix_tasks_user_completed_at",
        "tasks",
        ["user_id", "completed_at"],
        postgresql_where=sa.text("completed_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_user_completed_at", table_name="tasks")
