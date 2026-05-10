"""add users.is_admin and complaints table

Revision ID: 0022
Revises: 0021
Create Date: 2026-05-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.create_table(
        "complaints",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("page_url", sa.String(length=500), nullable=True),
        sa.Column("viewport", sa.String(length=20), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        # open / in_progress / resolved / dismissed
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        # low / normal / high
        sa.Column("priority", sa.String(length=10), nullable=False, server_default="normal"),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_complaints_status", "complaints", ["status"])
    op.create_index("ix_complaints_created_at", "complaints", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_complaints_created_at", "complaints")
    op.drop_index("ix_complaints_status", "complaints")
    op.drop_table("complaints")
    op.drop_column("users", "is_admin")
