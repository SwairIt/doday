"""school_integrations.student_id — portal student id for family-web API

Revision ID: 0031
Revises: 0030
Create Date: 2026-05-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "school_integrations",
        sa.Column("student_id", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("school_integrations", "student_id")
