"""reminders — отдельные от due_at напоминания, отправляются ботом

Revision ID: 0027
Revises: 0026
Create Date: 2026-05-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reminders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
        ),
        # Когда напомнить. Cron-worker берёт reminders WHERE remind_at <= now
        # AND sent_at IS NULL.
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        # 'before-due' (relative к due_at) | 'custom' (произвольное время)
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="custom"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_reminders_pending",
        "reminders",
        ["remind_at", "sent_at"],
    )
    op.create_index(
        "ix_reminders_task",
        "reminders",
        ["task_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_reminders_task", table_name="reminders")
    op.drop_index("ix_reminders_pending", table_name="reminders")
    op.drop_table("reminders")
