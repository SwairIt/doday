"""create habits + habit_checkins tables

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "habits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("emoji", sa.String(length=8), nullable=False, server_default="✅"),
        sa.Column("color", sa.String(length=20), nullable=False, server_default="violet"),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_habits_user_id", "habits", ["user_id"])

    op.create_table(
        "habit_checkins",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "habit_id",
            sa.Uuid(),
            sa.ForeignKey("habits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("checkin_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("habit_id", "checkin_date", name="uq_habit_date"),
    )
    op.create_index("ix_checkins_habit", "habit_checkins", ["habit_id"])


def downgrade() -> None:
    op.drop_index("ix_checkins_habit", table_name="habit_checkins")
    op.drop_table("habit_checkins")
    op.drop_index("ix_habits_user_id", table_name="habits")
    op.drop_table("habits")
