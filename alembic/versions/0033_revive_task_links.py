"""Revive task_links table — re-introduces directional task↔task references
that were dropped in phase α (migration 0028). Re-added in 2026-05-23 as an
experimental feature gated by `users.experiments['graph']`. Schema matches
the original `0020_task_links` so any future data import is straightforward.

Revision ID: 0033
Revises: 0032
Create Date: 2026-05-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


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
