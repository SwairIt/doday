"""Razbery (Doday Q&A): таблицы qa_* + seed справочника предметов.

Revision ID: 0047
Revises: 0046
Create Date: 2026-05-28
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


_SUBJECTS = [
    (
        "matematika",
        "Математика",
        5,
        6,
        10,
        "🔢",
        "Натуральные и десятичные числа, дроби, проценты, базовая арифметика для 5–6 классов.",
    ),
    (
        "algebra",
        "Алгебра",
        7,
        11,
        20,
        "📐",
        "Уравнения, неравенства, прогрессии, логарифмы, тригонометрия, производные.",
    ),
    (
        "geometriya",
        "Геометрия",
        7,
        11,
        30,
        "📏",
        "Планиметрия, стереометрия, теоремы, доказательства.",
    ),
    (
        "russkij",
        "Русский язык",
        5,
        11,
        40,
        "📝",
        "Орфография, пунктуация, морфология, синтаксис, культура речи.",
    ),
    (
        "literatura",
        "Литература",
        5,
        11,
        50,
        "📖",
        "Анализ произведений, тропы, образы, литературоведческие термины.",
    ),
    (
        "english",
        "Английский язык",
        5,
        11,
        60,
        "🇬🇧",
        "Грамматика, времена, словарный запас, ОГЭ/ЕГЭ.",
    ),
    (
        "fizika",
        "Физика",
        7,
        11,
        70,
        "⚛️",
        "Механика, термодинамика, электричество, оптика, квантовая физика.",
    ),
    ("himiya", "Химия", 8, 11, 80, "🧪", "Реакции, расчёты, органика, неорганика, ОВР."),
    ("biologiya", "Биология", 5, 11, 90, "🌱", "Цитология, генетика, анатомия, экология."),
    (
        "geografiya",
        "География",
        5,
        11,
        100,
        "🌍",
        "Физическая и экономическая география мира и России.",
    ),
    (
        "istoriya",
        "История",
        5,
        11,
        110,
        "🏛️",
        "Древний мир, средневековье, новейшая история России и мира.",
    ),
    (
        "obshhestvoznanie",
        "Обществознание",
        6,
        11,
        120,
        "⚖️",
        "Общество, экономика, право, политика, культура.",
    ),
    (
        "informatika",
        "Информатика",
        5,
        11,
        130,
        "💻",
        "Алгоритмы, программирование (Python), системы счисления, логика.",
    ),
    (
        "okruzhajushhij-mir",
        "Окружающий мир",
        5,
        6,
        140,
        "🌳",
        "Природа, человек, общество, безопасность для младших классов.",
    ),
    ("obzh", "ОБЖ", 5, 11, 150, "🚦", "Безопасность, первая помощь, ПДД, ЗОЖ."),
    (
        "tehnologiya",
        "Технология",
        5,
        8,
        160,
        "🔧",
        "Кулинария, шитьё, столярка, электротехника, профориентация.",
    ),
]


def upgrade() -> None:
    # qa_subject
    op.create_table(
        "qa_subject",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("min_grade", sa.SmallInteger, nullable=False),
        sa.Column("max_grade", sa.SmallInteger, nullable=False),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("icon", sa.String(20), nullable=False, server_default="📚"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_qa_subject_slug", "qa_subject", ["slug"], unique=True)

    # qa_question
    op.create_table(
        "qa_question",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "author_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "subject_id",
            sa.Integer,
            sa.ForeignKey("qa_subject.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("grade", sa.SmallInteger, nullable=True),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("body_md", sa.Text, nullable=False),
        sa.Column("body_html", sa.Text, nullable=False),
        sa.Column("score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("answer_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("view_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("accepted_answer_id", sa.BigInteger, nullable=True),
        sa.Column("is_seed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_hidden", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("tsv", sa.dialects.postgresql.TSVECTOR, nullable=True),
    )
    op.create_index("ix_qa_question_subject_created", "qa_question", ["subject_id", "created_at"])
    op.create_index("ix_qa_question_score", "qa_question", ["score"])
    op.create_index("ix_qa_question_author", "qa_question", ["author_id"])
    op.create_index(
        "ix_qa_question_subject_grade_score", "qa_question", ["subject_id", "grade", "score"]
    )
    op.create_index("ix_qa_question_tsv", "qa_question", ["tsv"], postgresql_using="gin")

    # tsv trigger: keep tsv up-to-date on insert/update
    op.execute(
        """
        CREATE OR REPLACE FUNCTION qa_question_tsv_update() RETURNS trigger AS $$
        BEGIN
          NEW.tsv :=
            setweight(to_tsvector('russian', coalesce(NEW.title, '')), 'A') ||
            setweight(to_tsvector('russian', coalesce(NEW.body_md, '')), 'B');
          RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER qa_question_tsv_trigger
        BEFORE INSERT OR UPDATE OF title, body_md ON qa_question
        FOR EACH ROW EXECUTE FUNCTION qa_question_tsv_update();
        """
    )

    # qa_answer
    op.create_table(
        "qa_answer",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "question_id",
            sa.BigInteger,
            sa.ForeignKey("qa_question.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("answer_md", sa.Text, nullable=False),
        sa.Column("answer_html", sa.Text, nullable=False),
        sa.Column("explanation_md", sa.Text, nullable=False),
        sa.Column("explanation_html", sa.Text, nullable=False),
        sa.Column("score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_accepted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_seed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_hidden", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("tips_total_stars", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_qa_answer_question_score", "qa_answer", ["question_id", "score"])
    op.create_index("ix_qa_answer_author", "qa_answer", ["author_id"])

    # Now wire accepted_answer_id FK (deferred to avoid circular dep at table-create)
    op.create_foreign_key(
        "fk_qa_question_accepted_answer",
        "qa_question",
        "qa_answer",
        ["accepted_answer_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # qa_vote
    op.create_table(
        "qa_vote",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_type", sa.String(1), nullable=False),
        sa.Column("target_id", sa.BigInteger, nullable=False),
        sa.Column("value", sa.SmallInteger, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_unique_constraint(
        "uq_qa_vote_target", "qa_vote", ["user_id", "target_type", "target_id"]
    )
    op.create_index("ix_qa_vote_target", "qa_vote", ["target_type", "target_id"])

    # qa_user_stats
    op.create_table(
        "qa_user_stats",
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("display_name", sa.String(50), nullable=False),
        sa.Column("display_slug", sa.String(50), nullable=False, unique=True),
        sa.Column("bio", sa.String(280), nullable=True),
        sa.Column("avatar_emoji", sa.String(8), nullable=False, server_default="📚"),
        sa.Column("reputation", sa.Integer, nullable=False, server_default="1"),
        sa.Column("q_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("a_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("accepted_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("pro_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_qa_user_stats_display_slug", "qa_user_stats", ["display_slug"], unique=True)

    # qa_report
    op.create_table(
        "qa_report",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "reporter_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_type", sa.String(1), nullable=False),
        sa.Column("target_id", sa.BigInteger, nullable=False),
        sa.Column("reason", sa.String(50), nullable=False),
        sa.Column("comment", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_qa_report_status", "qa_report", ["status"])
    op.create_index("ix_qa_report_target", "qa_report", ["target_type", "target_id"])

    # Seed subjects
    subj_table = sa.table(
        "qa_subject",
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
        sa.column("min_grade", sa.SmallInteger),
        sa.column("max_grade", sa.SmallInteger),
        sa.column("position", sa.Integer),
        sa.column("icon", sa.String),
        sa.column("description", sa.Text),
    )
    op.bulk_insert(
        subj_table,
        [
            {
                "slug": s[0],
                "name": s[1],
                "min_grade": s[2],
                "max_grade": s[3],
                "position": s[4],
                "icon": s[5],
                "description": s[6],
            }
            for s in _SUBJECTS
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_qa_report_target", table_name="qa_report")
    op.drop_index("ix_qa_report_status", table_name="qa_report")
    op.drop_table("qa_report")

    op.drop_index("ix_qa_user_stats_display_slug", table_name="qa_user_stats")
    op.drop_table("qa_user_stats")

    op.drop_index("ix_qa_vote_target", table_name="qa_vote")
    op.drop_constraint("uq_qa_vote_target", "qa_vote")
    op.drop_table("qa_vote")

    op.drop_constraint("fk_qa_question_accepted_answer", "qa_question", type_="foreignkey")

    op.drop_index("ix_qa_answer_author", table_name="qa_answer")
    op.drop_index("ix_qa_answer_question_score", table_name="qa_answer")
    op.drop_table("qa_answer")

    op.execute("DROP TRIGGER IF EXISTS qa_question_tsv_trigger ON qa_question")
    op.execute("DROP FUNCTION IF EXISTS qa_question_tsv_update()")
    op.drop_index("ix_qa_question_tsv", table_name="qa_question")
    op.drop_index("ix_qa_question_subject_grade_score", table_name="qa_question")
    op.drop_index("ix_qa_question_author", table_name="qa_question")
    op.drop_index("ix_qa_question_score", table_name="qa_question")
    op.drop_index("ix_qa_question_subject_created", table_name="qa_question")
    op.drop_table("qa_question")

    op.drop_index("ix_qa_subject_slug", table_name="qa_subject")
    op.drop_table("qa_subject")
