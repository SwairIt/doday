"""users.session_epoch — возможность отозвать сессии

Сессия хранится только в подписанной cookie, серверного состояния нет: смена
пароля не выкидывала того, кто увёл cookie, и она продолжала работать все две
недели. Номер поколения кладётся в cookie при входе и сверяется на каждом
запросе; смена пароля его увеличивает.

У выданных ранее cookie номера нет — они считаются нулевыми, поэтому никто не
разлогинивается при выкладке.

Revision ID: 0059
Revises: 0058
"""

import sqlalchemy as sa

from alembic import op

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("session_epoch", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "session_epoch")
