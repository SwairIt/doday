"""drop lazy modules + audience column

Revision ID: 0028
Revises: 0027
Create Date: 2026-05-13
"""

from __future__ import annotations

from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # FK cascade — order matters. IF EXISTS guard makes it safe on freshly
    # provisioned test/dev databases where some tables may already be absent.
    op.execute("DROP TABLE IF EXISTS user_achievements CASCADE")
    op.execute("DROP TABLE IF EXISTS user_progress CASCADE")
    op.execute("DROP TABLE IF EXISTS xp_events CASCADE")
    op.execute("DROP TABLE IF EXISTS habit_completions CASCADE")
    op.execute("DROP TABLE IF EXISTS habits CASCADE")
    op.execute("DROP TABLE IF EXISTS mood_entries CASCADE")
    op.execute("DROP TABLE IF EXISTS time_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS user_templates CASCADE")
    op.execute("DROP TABLE IF EXISTS custom_filters CASCADE")
    op.execute("DROP TABLE IF EXISTS task_links CASCADE")
    # users.audience column (code-side removal happened in Task 10)
    op.drop_column("users", "audience")


def downgrade() -> None:
    raise NotImplementedError(
        "Aggressive cleanup is one-way; restore from pre-alpha-cleanup git tag "
        "or pg_dump backup (/tmp/doday-pre-alpha-cleanup.sql on prod) if needed."
    )
