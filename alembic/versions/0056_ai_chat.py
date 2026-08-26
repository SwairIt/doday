"""ai_messages, ai_usage_daily, users.ai_terms_accepted_at

История чата с моделью, суточные лимиты и отметка о принятии условий
ИИ-помощника (возраст 18+, ответы генерирует нейросеть).

Счётчик лимитов держим в БД: деплой перезапускает процесс на каждый пуш,
и счётчик в памяти обнулялся бы вместе с ним.

Revision ID: 0056
Revises: 0055
"""

import sqlalchemy as sa

from alembic import op

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_messages_user_id", "ai_messages", ["user_id"])
    op.create_index("ix_ai_messages_created_at", "ai_messages", ["created_at"])
    op.create_index("ix_ai_messages_thread", "ai_messages", ["user_id", "task_id", "created_at"])

    op.create_table(
        "ai_usage_daily",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("requests", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "day"),
    )

    op.add_column(
        "users", sa.Column("ai_terms_accepted_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "ai_terms_accepted_at")
    op.drop_table("ai_usage_daily")
    op.drop_index("ix_ai_messages_thread", table_name="ai_messages")
    op.drop_index("ix_ai_messages_created_at", table_name="ai_messages")
    op.drop_index("ix_ai_messages_user_id", table_name="ai_messages")
    op.drop_table("ai_messages")
