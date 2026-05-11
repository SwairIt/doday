"""pomodoro_sessions — focus/break time tracking

Revision ID: 0026
Revises: 0025
Create Date: 2026-05-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pomodoro_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        # task_id NULL = free-form focus без привязки к задаче
        sa.Column(
            "task_id",
            sa.Uuid(),
            sa.ForeignKey("tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        # ended_at NULL = session активна. Когда юзер останавливает/timer истекает → set.
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        # Плановая длительность в минутах (25/5/15)
        sa.Column("duration_min", sa.Integer(), nullable=False),
        # 'focus' | 'break-short' | 'break-long'
        sa.Column("kind", sa.String(length=20), nullable=False),
        # True = session завершилась естественно (доработала до конца).
        # False = юзер остановил вручную.
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_pomodoro_user_active",
        "pomodoro_sessions",
        ["user_id", "ended_at"],
    )
    op.create_index(
        "ix_pomodoro_task",
        "pomodoro_sessions",
        ["task_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_pomodoro_task", table_name="pomodoro_sessions")
    op.drop_index("ix_pomodoro_user_active", table_name="pomodoro_sessions")
    op.drop_table("pomodoro_sessions")
