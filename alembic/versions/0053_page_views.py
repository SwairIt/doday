"""page_views — аналитика посещений для /app/root

Лёгкий учёт просмотров страниц: путь, кто (если залогинен), когда. Пишется
middleware'ом только для реальных HTML-страниц. Индексы на path и created_at —
под группировку top-страниц и выборки по диапазону дат.

Идемпотентность на проде дополнительно обеспечивает _repair_schema_on_startup
(CREATE TABLE IF NOT EXISTS).

Revision ID: 0053
Revises: 0052
"""

import sqlalchemy as sa
from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "page_views",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("path", sa.String(length=300), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_page_views_path"), "page_views", ["path"])
    op.create_index(op.f("ix_page_views_user_id"), "page_views", ["user_id"])
    op.create_index(op.f("ix_page_views_created_at"), "page_views", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_page_views_created_at"), table_name="page_views")
    op.drop_index(op.f("ix_page_views_user_id"), table_name="page_views")
    op.drop_index(op.f("ix_page_views_path"), table_name="page_views")
    op.drop_table("page_views")
