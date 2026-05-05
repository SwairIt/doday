"""create task_links table

Revision ID: 0020
Revises: 0019
Create Date: 2026-05-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "task_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_task_id",
            sa.Uuid(),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_task_id",
            sa.Uuid(),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("source_task_id", "target_task_id", name="uq_task_link_pair"),
        sa.CheckConstraint("source_task_id <> target_task_id", name="ck_task_link_no_self"),
    )
    op.create_index("ix_task_links_source", "task_links", ["source_task_id"])
    op.create_index("ix_task_links_target", "task_links", ["target_task_id"])
    op.create_index("ix_task_links_user_id", "task_links", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_task_links_user_id", table_name="task_links")
    op.drop_index("ix_task_links_target", table_name="task_links")
    op.drop_index("ix_task_links_source", table_name="task_links")
    op.drop_table("task_links")
