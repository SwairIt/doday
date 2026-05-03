"""create sections + tasks.section_id

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sections_project_id", "sections", ["project_id"])

    op.add_column(
        "tasks",
        sa.Column(
            "section_id",
            sa.Uuid(),
            sa.ForeignKey("sections.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_tasks_section_id", "tasks", ["section_id"])


def downgrade() -> None:
    op.drop_index("ix_tasks_section_id", table_name="tasks")
    op.drop_column("tasks", "section_id")
    op.drop_index("ix_sections_project_id", table_name="sections")
    op.drop_table("sections")
