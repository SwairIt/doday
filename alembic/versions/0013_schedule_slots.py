"""create schedule_slots table for school weekly timetable

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "schedule_slots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("period", sa.Integer(), nullable=False),
        sa.Column("subject_code", sa.String(length=20), nullable=False),
        sa.Column("room", sa.String(length=40), nullable=True),
        sa.Column("teacher", sa.String(length=80), nullable=True),
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
        sa.UniqueConstraint("user_id", "weekday", "period", name="uq_user_slot"),
    )
    op.create_index("ix_schedule_slots_user_id", "schedule_slots", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_schedule_slots_user_id", table_name="schedule_slots")
    op.drop_table("schedule_slots")
