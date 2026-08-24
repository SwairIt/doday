"""card_payments — приём оплаты картой через Robokassa

Отдельная таблица от star_payments: у провайдеров разные идентификаторы и
разный жизненный цикл (у Telegram Stars нет состояния «ожидает оплаты»).
Колонка provider оставлена на будущее — эквайер может смениться.

Revision ID: 0050
Revises: 0049
"""

import sqlalchemy as sa
from alembic import op

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "card_payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        # Robokassa требует числовой номер счёта: UUID она не принимает.
        sa.Column("inv_id", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=64), nullable=False),
        sa.Column("product_code", sa.String(length=50), nullable=False),
        sa.Column("amount_kopecks", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("confirmation_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("inv_id"),
        # Идемпотентность вебхука: повторная доставка падает в IntegrityError.
        sa.UniqueConstraint("provider", "provider_payment_id", name="uq_card_payment_provider_id"),
    )
    op.create_index(op.f("ix_card_payments_user_id"), "card_payments", ["user_id"])
    # Последовательность для InvId — номер счёта должен быть монотонным.
    op.execute("CREATE SEQUENCE IF NOT EXISTS card_payment_inv_id_seq OWNED BY card_payments.inv_id")
    op.execute("ALTER TABLE card_payments ALTER COLUMN inv_id SET DEFAULT nextval('card_payment_inv_id_seq')")


def downgrade() -> None:
    op.drop_index(op.f("ix_card_payments_user_id"), table_name="card_payments")
    op.drop_table("card_payments")
    op.execute("DROP SEQUENCE IF EXISTS card_payment_inv_id_seq")
