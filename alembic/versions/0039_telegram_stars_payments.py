"""Telegram Stars payments — paid Pro infrastructure.

Adds:
- `users.pro_until` — timestamp when the user's paid Pro expires. NULL = no paid
  subscription. `effective_tier()` returns "pro" only while pro_until > now() OR
  trial_ends_at > now(). Mutually-exclusive with `trial_ends_at` semantically
  (paid users normally have trial=None, but we don't enforce it — trial just
  gives free Pro features while it lasts).
- `star_payments` — every Telegram Stars charge for idempotency, refund, and
  audit. Unique constraint on telegram_payment_charge_id catches re-delivered
  webhooks; status tracks paid/refunded.

Revision ID: 0039
Revises: 0038
Create Date: 2026-05-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("pro_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "star_payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # Telegram's idempotency key from the SuccessfulPayment update.
        # Unique → a re-delivered webhook lands as a no-op (DB integrity check).
        sa.Column(
            "telegram_payment_charge_id",
            sa.String(length=200),
            nullable=False,
            unique=True,
        ),
        sa.Column("provider_payment_charge_id", sa.String(length=200), nullable=True),
        # Product catalog key — see app/billing/products.py.
        sa.Column("product_code", sa.String(length=50), nullable=False),
        # Stars amount the user paid (XTR currency, integer per Bot API contract).
        sa.Column("stars_amount", sa.Integer(), nullable=False),
        # What we wrote into Telegram's invoice payload (signed).
        sa.Column("invoice_payload", sa.String(length=200), nullable=False),
        # paid → refunded after successful refundStarPayment call.
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="paid",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refund_reason", sa.String(length=500), nullable=True),
    )
    op.create_index(
        "ix_star_payments_user_created",
        "star_payments",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_star_payments_user_created", table_name="star_payments")
    op.drop_table("star_payments")
    op.drop_column("users", "pro_until")
