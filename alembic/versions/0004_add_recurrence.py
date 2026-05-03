"""add tasks.recurrence

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("recurrence", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tasks", "recurrence")
