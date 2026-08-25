"""complaints.contact_email — почта для ответа (в т.ч. анонимам)

Публичная форма поддержки принимает обращения и от незалогиненных, поэтому
нужна почта для обратной связи. Nullable — у старых записей её нет.

Идемпотентность на проде дополнительно обеспечивает _repair_schema_on_startup
в app/main.py (ADD COLUMN IF NOT EXISTS).

Revision ID: 0052
Revises: 0051
"""

import sqlalchemy as sa
from alembic import op

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "complaints",
        sa.Column("contact_email", sa.String(length=320), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("complaints", "contact_email")
