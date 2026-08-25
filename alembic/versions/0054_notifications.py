"""notifications + complaints.admin_reply

Колокольчик уведомлений для всех пользователей. Источник — реакции админа на
обращения в поддержку («взял в работу», «ответил»). complaints.admin_reply —
последний ответ админа, чтобы в панели было видно, что уже отвечали.

Идемпотентность на проде дополнительно обеспечивает _repair_schema_on_startup.

Revision ID: 0054
Revises: 0053
"""

import sqlalchemy as sa
from alembic import op

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False, server_default="generic"),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("link", sa.String(length=300), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"])
    op.create_index(op.f("ix_notifications_created_at"), "notifications", ["created_at"])
    op.add_column("complaints", sa.Column("admin_reply", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("complaints", "admin_reply")
    op.drop_index(op.f("ix_notifications_created_at"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")
    op.drop_table("notifications")
