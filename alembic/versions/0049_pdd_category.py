"""Doday ПДД: категория билетов (ABM / CD).

Revision ID: 0049
Revises: 0048
Create Date: 2026-05-31
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing rows are all ABM (server_default backfills them).
    op.add_column(
        "pdd_tickets",
        sa.Column("category", sa.String(8), nullable=False, server_default="ABM"),
    )
    op.create_index("ix_pdd_tickets_category", "pdd_tickets", ["category"])
    # Ticket number is unique per category, not globally.
    op.drop_index("ix_pdd_tickets_number", table_name="pdd_tickets")
    op.create_index("ix_pdd_tickets_number", "pdd_tickets", ["number"])
    op.create_unique_constraint(
        "uq_pdd_ticket_category_number", "pdd_tickets", ["category", "number"]
    )

    op.add_column(
        "pdd_questions",
        sa.Column("category", sa.String(8), nullable=False, server_default="ABM"),
    )
    op.create_index("ix_pdd_questions_category", "pdd_questions", ["category"])


def downgrade() -> None:
    op.drop_index("ix_pdd_questions_category", table_name="pdd_questions")
    op.drop_column("pdd_questions", "category")
    op.drop_constraint("uq_pdd_ticket_category_number", "pdd_tickets", type_="unique")
    op.drop_index("ix_pdd_tickets_number", table_name="pdd_tickets")
    op.create_index("ix_pdd_tickets_number", "pdd_tickets", ["number"], unique=True)
    op.drop_index("ix_pdd_tickets_category", table_name="pdd_tickets")
    op.drop_column("pdd_tickets", "category")
