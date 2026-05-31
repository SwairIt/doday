"""Doday ПДД: таблицы pdd_* + generic entitlements (для pdd_pro).

Revision ID: 0048
Revises: 0047
Create Date: 2026-05-31
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── entitlements (generic per-user per-feature grant; powers pdd_pro) ──
    op.create_table(
        "entitlements",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("feature", sa.String(40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_code", sa.String(50), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("user_id", "feature", name="uq_entitlement_user_feature"),
    )
    op.create_index("ix_entitlements_user_id", "entitlements", ["user_id"])

    # ── pdd_topics ──
    op.create_table(
        "pdd_topics",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("seo_intro", sa.Text, nullable=False, server_default=""),
    )
    op.create_index("ix_pdd_topics_slug", "pdd_topics", ["slug"], unique=True)

    # ── pdd_tickets ──
    op.create_table(
        "pdd_tickets",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("number", sa.Integer, nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
    )
    op.create_index("ix_pdd_tickets_number", "pdd_tickets", ["number"], unique=True)

    # ── pdd_questions ──
    op.create_table(
        "pdd_questions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("public_slug", sa.String(80), nullable=False),
        sa.Column(
            "ticket_id",
            sa.Integer,
            sa.ForeignKey("pdd_tickets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position_in_ticket", sa.Integer, nullable=False),
        sa.Column(
            "topic_id",
            sa.Integer,
            sa.ForeignKey("pdd_topics.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("image_path", sa.String(255), nullable=True),
        sa.Column("explanation", sa.Text, nullable=False, server_default=""),
        sa.Column("correct_position", sa.Integer, nullable=False),
        sa.UniqueConstraint("ticket_id", "position_in_ticket", name="uq_pdd_question_ticket_pos"),
    )
    op.create_index("ix_pdd_questions_public_slug", "pdd_questions", ["public_slug"], unique=True)
    op.create_index("ix_pdd_questions_ticket_id", "pdd_questions", ["ticket_id"])
    op.create_index("ix_pdd_questions_topic_id", "pdd_questions", ["topic_id"])

    # ── pdd_options ──
    op.create_table(
        "pdd_options",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "question_id",
            sa.Integer,
            sa.ForeignKey("pdd_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.UniqueConstraint("question_id", "position", name="uq_pdd_option_question_pos"),
    )
    op.create_index("ix_pdd_options_question_id", "pdd_options", ["question_id"])

    # ── pdd_attempts ──
    op.create_table(
        "pdd_attempts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "question_id",
            sa.Integer,
            sa.ForeignKey("pdd_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chosen_position", sa.Integer, nullable=False),
        sa.Column("is_correct", sa.Boolean, nullable=False),
        sa.Column("source", sa.String(12), nullable=False, server_default="practice"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_pdd_attempt_user_question", "pdd_attempts", ["user_id", "question_id"])
    op.create_index("ix_pdd_attempt_user_created", "pdd_attempts", ["user_id", "created_at"])

    # ── pdd_exam_sessions ──
    op.create_table(
        "pdd_exam_sessions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "question_ids",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("total", sa.Integer, nullable=False, server_default="20"),
        sa.Column("mistakes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("extra_added", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(12), nullable=False, server_default="in_progress"),
    )
    op.create_index("ix_pdd_exam_sessions_user_id", "pdd_exam_sessions", ["user_id"])


def downgrade() -> None:
    op.drop_table("pdd_exam_sessions")
    op.drop_table("pdd_attempts")
    op.drop_table("pdd_options")
    op.drop_table("pdd_questions")
    op.drop_table("pdd_tickets")
    op.drop_table("pdd_topics")
    op.drop_table("entitlements")
