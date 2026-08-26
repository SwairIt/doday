"""ai_credentials — ключи LLM-провайдеров пользователей

Один ключ на пользователя, сам ключ хранится зашифрованным (Fernet),
рядом лежит версия схемы шифрования для будущей ротации.

Revision ID: 0055
Revises: 0054
"""

import sqlalchemy as sa

from alembic import op

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.String(length=255), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("key_ciphertext", sa.Text(), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("key_last4", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_ai_credentials_user"),
    )
    op.create_index("ix_ai_credentials_user_id", "ai_credentials", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_credentials_user_id", table_name="ai_credentials")
    op.drop_table("ai_credentials")
