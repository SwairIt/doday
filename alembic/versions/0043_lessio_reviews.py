"""Lessio reviews — отзывы клиентов после завершённой встречи.

Один review = один booking (UNIQUE). Rating 1-5 (CHECK). Client-email/full_name
denormalized чтобы review остался читаемым если LessioClient удалят.

Revision ID: 0043
Revises: 0042
Create Date: 2026-05-26
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lessio_reviews",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "booking_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lessio_bookings.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "tutor_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lessio_tutor_profiles.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("client_email", sa.String(255), nullable=False),
        sa.Column("client_full_name", sa.String(120), nullable=False),
        sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("text", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_lessio_review_rating_1_5"),
    )


def downgrade() -> None:
    op.drop_table("lessio_reviews")
