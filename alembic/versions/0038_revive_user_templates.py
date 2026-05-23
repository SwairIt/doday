"""Revive user_templates — save a project as a reusable snapshot. Same schema
as the original `0008_create_user_templates`. Opt-in via
`users.experiments['user_templates']`.

Revision ID: 0038
Revises: 0037
Create Date: 2026-05-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_templates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=False, server_default="violet"),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("payload", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_user_templates_user_id", "user_templates", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_templates_user_id", table_name="user_templates")
    op.drop_table("user_templates")
