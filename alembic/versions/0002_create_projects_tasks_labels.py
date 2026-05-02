"""create projects, tasks, labels, task_labels

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # projects
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=False, server_default="violet"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_inbox", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_projects_user_id", "projects", ["user_id"])
    op.create_index(
        "uq_projects_user_slug",
        "projects",
        ["user_id", "slug"],
        unique=True,
    )
    op.create_index(
        "uq_projects_user_inbox",
        "projects",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_inbox = true"),
    )

    # labels
    op.create_table(
        "labels",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=40), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=False, server_default="violet"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_labels_user_id", "labels", ["user_id"])
    op.create_index(
        "uq_labels_user_slug",
        "labels",
        ["user_id", "slug"],
        unique=True,
    )

    # tasks (with priority enum)
    task_priority = sa.Enum("p1", "p2", "p3", "p4", name="task_priority", create_type=True)
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_task_id",
            sa.Uuid(),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_date_only", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("priority", task_priority, nullable=False, server_default="p4"),
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tasks_user_id", "tasks", ["user_id"])
    op.create_index("ix_tasks_project_id", "tasks", ["project_id"])
    op.create_index("ix_tasks_user_due_at", "tasks", ["user_id", "due_at"])
    op.create_index("ix_tasks_parent", "tasks", ["parent_task_id"])

    # M:N task_labels
    op.create_table(
        "task_labels",
        sa.Column(
            "task_id",
            sa.Uuid(),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "label_id",
            sa.Uuid(),
            sa.ForeignKey("labels.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("task_labels")
    op.drop_index("ix_tasks_parent", table_name="tasks")
    op.drop_index("ix_tasks_user_due_at", table_name="tasks")
    op.drop_index("ix_tasks_project_id", table_name="tasks")
    op.drop_index("ix_tasks_user_id", table_name="tasks")
    op.drop_table("tasks")
    sa.Enum(name="task_priority").drop(op.get_bind(), checkfirst=False)
    op.drop_index("uq_labels_user_slug", table_name="labels")
    op.drop_index("ix_labels_user_id", table_name="labels")
    op.drop_table("labels")
    op.drop_index("uq_projects_user_inbox", table_name="projects")
    op.drop_index("uq_projects_user_slug", table_name="projects")
    op.drop_index("ix_projects_user_id", table_name="projects")
    op.drop_table("projects")
