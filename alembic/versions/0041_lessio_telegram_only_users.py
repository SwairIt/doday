"""Lessio: users.password_hash → nullable (Telegram-only signups for Lessio MVP).

Lessio юзеры заходят через Mini App initData — это HMAC-проверка от Telegram,
не пароль. Они не имеют email (генерируем placeholder `lessio_tg_<id>@auto.lessio`),
не имеют password (`password_hash = NULL`). Telegram-only path не требует
ни одного из этих полей.

Email остаётся NOT NULL UNIQUE — placeholder email хранится в БД, чтобы
не плодить partial-unique-index. Когда Lessio-юзер привязывает реальный email
через `/app/profile` — placeholder заменяется.

Revision ID: 0041
Revises: 0040
Create Date: 2026-05-25
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=True)


def downgrade() -> None:
    # Заполним NULL'ы placeholder'ом перед NOT NULL — иначе downgrade сломает.
    op.execute(
        "UPDATE users SET password_hash = 'lessio_telegram_only_no_password' "
        "WHERE password_hash IS NULL"
    )
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=False)
