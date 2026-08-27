"""users.signup_ip и users.signup_subnet — защита от массовой регистрации

Поводом послужили 170 ботов. Считать частоту регистраций по счётчику в
памяти нельзя: деплой перезапускает процесс на каждый пуш и обнуляет его.
Поэтому запоминаем адрес и подсеть прямо в строке пользователя и считаем
по таблице.

Revision ID: 0057
Revises: 0056
"""

import sqlalchemy as sa

from alembic import op

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("signup_ip", sa.String(length=45), nullable=True))
    op.add_column("users", sa.Column("signup_subnet", sa.String(length=45), nullable=True))
    op.create_index("ix_users_signup_ip", "users", ["signup_ip"])
    op.create_index("ix_users_signup_subnet", "users", ["signup_subnet"])


def downgrade() -> None:
    op.drop_index("ix_users_signup_subnet", table_name="users")
    op.drop_index("ix_users_signup_ip", table_name="users")
    op.drop_column("users", "signup_subnet")
    op.drop_column("users", "signup_ip")
