"""add telegram_links table — связь Doday-юзера с Telegram-чатом

Revision ID: 0023
Revises: 0022
Create Date: 2026-05-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telegram_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        # Telegram chat_id может быть NULL пока юзер ещё не написал боту /start.
        # После /start <token> → bot заполняет chat_id и обнуляет link_token.
        sa.Column("chat_id", sa.BigInteger(), nullable=True, unique=True),
        # Одноразовый токен для глубокой ссылки t.me/<bot>?start=<token>.
        # Активен пока chat_id IS NULL. После использования — NULL.
        sa.Column("link_token", sa.String(length=64), nullable=True, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_telegram_links_link_token", "telegram_links", ["link_token"])


def downgrade() -> None:
    op.drop_index("ix_telegram_links_link_token", "telegram_links")
    op.drop_table("telegram_links")
