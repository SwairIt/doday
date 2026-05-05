"""add pinned_at column to tasks (закрепить наверх)

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_tasks_pinned_at", "tasks", ["pinned_at"])


def downgrade() -> None:
    op.drop_index("ix_tasks_pinned_at", table_name="tasks")
    op.drop_column("tasks", "pinned_at")
