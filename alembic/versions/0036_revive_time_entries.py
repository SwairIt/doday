"""Revive time_entries — per-task timer; dropped in phase α. Same schema as
the original `0018_time_entries`. Opt-in via `users.experiments['time_tracking']`.

Revision ID: 0036
Revises: 0035
Create Date: 2026-05-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "time_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            sa.Uuid(),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
    )
    op.create_index("ix_time_entries_user", "time_entries", ["user_id"])
    op.create_index("ix_time_entries_task", "time_entries", ["task_id"])
    op.create_index("ix_time_entries_running", "time_entries", ["user_id", "ended_at"])


def downgrade() -> None:
    op.drop_index("ix_time_entries_running", table_name="time_entries")
    op.drop_index("ix_time_entries_task", table_name="time_entries")
    op.drop_index("ix_time_entries_user", table_name="time_entries")
    op.drop_table("time_entries")
