"""Retain anonymous revenue records when the customer deletes an account.

Revision ID: 0063
Revises: 0062
"""

import sqlalchemy as sa
from alembic import op

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "archived_payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("buyer_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("reference", sa.String(200), nullable=False),
        sa.Column("product_code", sa.String(50), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refunded_at", sa.DateTime(timezone=True)),
        sa.Column("is_test", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("provider", "reference", name="uq_archived_payment_provider_reference"),
    )
    op.create_index("ix_archived_payments_buyer_id", "archived_payments", ["buyer_id"])


def downgrade() -> None:
    op.drop_table("archived_payments")
