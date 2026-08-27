"""school_integrations.auth_token — шифротекст вместо открытого токена

Токен портала (`aupd_token` от dnevnik.mos.ru или Школьного портала МО) даёт
полный доступ к дневнику ребёнка и лежал в базе открытым текстом. Теперь он
шифруется (app/school/crypto.py); шифротекст длиннее исходного значения,
поэтому колонка расширяется до Text.

Старые записи остаются как есть: они читаются без расшифровки и
перешифровываются при следующем сохранении интеграции.

Revision ID: 0058
Revises: 0057
"""

import sqlalchemy as sa

from alembic import op

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "school_integrations",
        "auth_token",
        existing_type=sa.String(length=2048),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "school_integrations",
        "auth_token",
        existing_type=sa.Text(),
        type_=sa.String(length=2048),
        existing_nullable=True,
    )
