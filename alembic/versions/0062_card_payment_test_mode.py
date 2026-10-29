"""Keep sandbox payments out of real revenue and access grants.

Revision ID: 0062
Revises: 0061
"""

import sqlalchemy as sa
from alembic import op

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "card_payments",
        sa.Column("is_test", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE card_payments SET is_test = true WHERE confirmation_url LIKE '%IsTest=1%'")
    op.create_index("ix_card_payments_status_paid_at", "card_payments", ["status", "paid_at"])


def downgrade() -> None:
    op.drop_index("ix_card_payments_status_paid_at", table_name="card_payments")
    op.drop_column("card_payments", "is_test")
