"""confirmation_url → TEXT (ссылка Robokassa длиннее varchar(500))

Ссылка на страницу оплаты Robokassa содержит url-кодированный фискальный чек и
легко переваливает за 500 символов. varchar(500) обрывал её при UPDATE с
StringDataRightTruncationError, и заведение счёта падало в 500. Расширяем до
TEXT (без лимита длины).

Идемпотентность на проде дополнительно обеспечивает _repair_schema_on_startup
в app/main.py — на случай, если учёт alembic разошёлся с реальной схемой.

Revision ID: 0051
Revises: 0050
"""

import sqlalchemy as sa
from alembic import op

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "card_payments",
        "confirmation_url",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "card_payments",
        "confirmation_url",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=True,
    )
