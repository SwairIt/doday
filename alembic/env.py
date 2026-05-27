"""Alembic environment — reads DATABASE_URL from app settings."""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.admin import models as _admin_models  # noqa: F401
from app.auth import models as _auth_models  # noqa: F401  register tables with Base.metadata
from app.config import get_settings
from app.db import Base
from app.labels import models as _labels_models  # noqa: F401
from app.lessio import models as _lessio_models  # noqa: F401
from app.projects import models as _projects_models  # noqa: F401
from app.qa import models as _qa_models  # noqa: F401
from app.sections import models as _sections_models  # noqa: F401
from app.tasks import models as _tasks_models  # noqa: F401
from app.telegram import models as _telegram_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# `%` in password (e.g. URL-encoded special chars) clashes with configparser
# interpolation; escape as `%%` so alembic.ini accepts it.
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
