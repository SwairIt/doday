"""add ical_token column to users (long-lived calendar feed token)

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("ical_token", sa.String(length=64), nullable=True))
    op.create_unique_constraint("uq_users_ical_token", "users", ["ical_token"])


def downgrade() -> None:
    op.drop_constraint("uq_users_ical_token", "users", type_="unique")
    op.drop_column("users", "ical_token")
