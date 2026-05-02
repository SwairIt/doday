# Plan 1 — Foundation + Auth (SchoolTodo MVP)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Запустить пустой FastAPI-проект на Docker Compose с PostgreSQL + Redis, реализовать регистрацию/подтверждение email/логин/логаут, минимальные landing/login/register страницы.

**Architecture:** Async FastAPI + async SQLAlchemy 2.0 + Alembic для миграций. Cookie-сессии через Starlette `SessionMiddleware`. Email через локальный Mailhog в dev. Все эндпоинты — через TDD с pytest + httpx AsyncClient.

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2.0 (async) · asyncpg · Alembic · Pydantic 2 · Argon2 (passwords) · Jinja2 · HTMX 2 · Tailwind CSS (CDN на этом этапе) · pytest · pytest-asyncio · Docker Compose · PostgreSQL 16 · Redis 7 · Mailhog (dev SMTP)

---

## Конвенции

- **TDD строго:** для каждой логической единицы — сначала падающий тест, потом код, который его проходит.
- **Коммиты после каждого зелёного теста.** Сообщения коммитов на русском, в Conventional Commits (feat/fix/test/chore/docs).
- **Все команды запускаются из корня проекта** `c:\www-Yaroslav\SchoolProject` если не указано иное.
- **Окружение Docker:** `docker compose up -d` поднимает postgres/redis/mailhog. Тесты запускаются на этих же контейнерах, но в отдельной БД `schooltodo_test`.
- **Запуск тестов:** `docker compose exec app pytest <args>` (или из локальной venv если она настроена с теми же env vars).

---

## Файловая структура (после выполнения этого плана)

```
SchoolProject/
├── .dockerignore
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── alembic.ini
├── README.md
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_create_users.py
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app + middleware
│   ├── config.py                    # pydantic-settings
│   ├── db.py                        # async engine + session
│   ├── templates/
│   │   ├── base.html                # общий layout
│   │   ├── landing.html
│   │   ├── _flash.html              # партиал для flash-сообщений
│   │   └── auth/
│   │       ├── register.html
│   │       ├── login.html
│   │       └── verify_pending.html
│   ├── static/
│   │   └── app.js                   # пара утилит, минимум JS
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── models.py                # User SQLAlchemy
│   │   ├── schemas.py               # Pydantic схемы
│   │   ├── security.py              # хэш паролей, токены
│   │   ├── service.py               # бизнес-логика регистрации/логина/верификации
│   │   ├── deps.py                  # current_user, require_auth
│   │   ├── email.py                 # отправка email
│   │   └── routes.py                # FastAPI router
│   └── routers/
│       ├── __init__.py
│       └── pages.py                 # серверный рендер landing
└── tests/
    ├── __init__.py
    ├── conftest.py                  # фикстуры: db, client, mailhog
    ├── test_health.py
    ├── test_auth/
    │   ├── __init__.py
    │   ├── test_security.py
    │   ├── test_register.py
    │   ├── test_verify.py
    │   ├── test_login.py
    │   └── test_logout.py
    └── test_pages.py
```

---

## Task 1: Базовая структура проекта и зависимости

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `.dockerignore`

- [ ] **Step 1.1: Создать `pyproject.toml` с зависимостями**

```toml
[project]
name = "schooltodo"
version = "0.1.0"
description = "Туду-лист для школьников на основе электронного дневника"
requires-python = ">=3.12"
dependencies = [
    "fastapi[standard]==0.115.6",
    "uvicorn[standard]==0.32.1",
    "sqlalchemy[asyncio]==2.0.36",
    "asyncpg==0.30.0",
    "alembic==1.14.0",
    "pydantic==2.10.3",
    "pydantic-settings==2.7.0",
    "argon2-cffi==23.1.0",
    "jinja2==3.1.4",
    "itsdangerous==2.2.0",
    "python-multipart==0.0.19",
    "aiosmtplib==3.0.2",
    "httpx==0.28.1",
    "email-validator==2.2.0",
]

[dependency-groups]
dev = [
    "pytest==8.3.4",
    "pytest-asyncio==0.25.0",
    "pytest-cov==6.0.0",
    "ruff==0.8.4",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
testpaths = ["tests"]
addopts = "-v --strict-markers"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N"]
ignore = ["E501"]
```

- [ ] **Step 1.2: Создать `.gitignore`**

```gitignore
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.env
.env.local
*.db
*.sqlite
.pytest_cache/
.ruff_cache/
.coverage
htmlcov/
.idea/
.vscode/
*.log
node_modules/
```

- [ ] **Step 1.3: Создать `.env.example`**

```dotenv
# App
APP_ENV=dev
APP_SECRET_KEY=replace-me-with-32-bytes-of-random
APP_BASE_URL=http://localhost:8000

# Postgres
POSTGRES_USER=schooltodo
POSTGRES_PASSWORD=schooltodo
POSTGRES_DB=schooltodo
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_TEST_DB=schooltodo_test

# Redis
REDIS_URL=redis://redis:6379/0

# SMTP (Mailhog в dev)
SMTP_HOST=mailhog
SMTP_PORT=1025
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM=noreply@schooltodo.local
```

- [ ] **Step 1.4: Создать `.dockerignore`**

```
__pycache__
*.pyc
.venv
venv
.git
.pytest_cache
.ruff_cache
.coverage
.env
.env.local
node_modules
```

- [ ] **Step 1.5: Закоммитить**

```bash
git add pyproject.toml .gitignore .env.example .dockerignore
git commit -m "chore: добавить структуру проекта и зависимости"
```

---

## Task 2: Docker Compose окружение

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`

- [ ] **Step 2.1: Создать `Dockerfile`**

```dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN pip install --no-cache-dir uv==0.5.11

COPY pyproject.toml ./
RUN uv pip install --system --no-cache .

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

- [ ] **Step 2.2: Создать `docker-compose.yml`**

```yaml
services:
  app:
    build: .
    env_file: .env
    ports:
      - "8000:8000"
    volumes:
      - ./app:/app/app
      - ./tests:/app/tests
      - ./alembic:/app/alembic
      - ./alembic.ini:/app/alembic.ini
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
      mailhog:
        condition: service_started

  postgres:
    image: postgres:16-alpine
    env_file: .env
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 3s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  mailhog:
    image: mailhog/mailhog:latest
    ports:
      - "1025:1025"  # SMTP
      - "8025:8025"  # Web UI

volumes:
  postgres_data:
```

- [ ] **Step 2.3: Создать локальный `.env` из примера и проверить запуск**

```bash
cp .env.example .env
docker compose build
docker compose up -d postgres redis mailhog
docker compose ps
```

Expected: три сервиса в состоянии `Up`.

- [ ] **Step 2.4: Закоммитить**

```bash
git add Dockerfile docker-compose.yml
git commit -m "chore: docker compose с postgres/redis/mailhog"
```

---

## Task 3: Минимальное FastAPI-приложение и health-check (TDD)

**Files:**
- Create: `app/__init__.py` (пустой)
- Create: `app/config.py`
- Create: `app/main.py`
- Create: `tests/__init__.py` (пустой)
- Create: `tests/conftest.py` (минимальная версия)
- Create: `tests/test_health.py`

- [ ] **Step 3.1: Создать `app/__init__.py` и `tests/__init__.py` пустые**

```bash
mkdir -p app tests
type nul > app/__init__.py
type nul > tests/__init__.py
```

(Под Windows используется `type nul > file`. На Linux/Mac — `touch file`.)

- [ ] **Step 3.2: Написать падающий тест health-check**

`tests/test_health.py`:
```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_returns_ok():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 3.3: Запустить тест — должен упасть (нет `app.main`)**

```bash
docker compose run --rm app pytest tests/test_health.py -v
```

Expected: ImportError или ModuleNotFoundError.

- [ ] **Step 3.4: Создать `app/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    app_secret_key: str = "dev-secret-change-me"
    app_base_url: str = "http://localhost:8000"

    postgres_user: str = "schooltodo"
    postgres_password: str = "schooltodo"
    postgres_db: str = "schooltodo"
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_test_db: str = "schooltodo_test"

    redis_url: str = "redis://redis:6379/0"

    smtp_host: str = "mailhog"
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@schooltodo.local"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def test_database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_test_db}"
        )


settings = Settings()
```

- [ ] **Step 3.5: Создать минимальный `app/main.py`**

```python
from fastapi import FastAPI

app = FastAPI(title="SchoolTodo")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 3.6: Запустить тест — должен пройти**

```bash
docker compose run --rm app pytest tests/test_health.py -v
```

Expected: PASS.

- [ ] **Step 3.7: Закоммитить**

```bash
git add app/ tests/
git commit -m "feat: минимальное FastAPI приложение и health-check"
```

---

## Task 4: Async DB-инфраструктура и тестовая БД

**Files:**
- Create: `app/db.py`
- Modify: `tests/conftest.py`

- [ ] **Step 4.1: Создать `app/db.py`**

```python
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
```

- [ ] **Step 4.2: Написать `tests/conftest.py` с фикстурой тестовой БД**

Здесь два важных нюанса с асинхронным pytest:
1. **Сетап БД делаем sync-обёрткой** через `asyncio.run()`, чтобы избежать конфликта loop scope.
2. **Между тестами TRUNCATE-им все таблицы**, потому что наш код вызывает `commit()`, и обычный rollback его не отменит — данные протекают между тестами.

```python
import asyncio
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db import Base, get_session
from app.main import app


async def _setup_test_db() -> None:
    """Дропает и пересоздаёт тестовую БД, накатывает схему."""
    admin_engine = create_async_engine(
        f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/postgres",
        isolation_level="AUTOCOMMIT",
    )
    async with admin_engine.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {settings.postgres_test_db}"))
        await conn.execute(text(f"CREATE DATABASE {settings.postgres_test_db}"))
    await admin_engine.dispose()

    test_engine = create_async_engine(settings.test_database_url)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await test_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _ensure_test_database():
    """Sync-обёртка: один раз на тестовую сессию подготавливает БД."""
    asyncio.run(_setup_test_db())
    yield


async def _truncate_all(engine) -> None:
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE'))


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    test_engine = create_async_engine(settings.test_database_url)
    TestSession = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with TestSession() as session:
        yield session
    await _truncate_all(test_engine)
    await test_engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_get_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

- [ ] **Step 4.3: Перезапустить health тест чтобы убедиться что не сломали**

```bash
docker compose run --rm app pytest tests/test_health.py -v
```

Expected: PASS (тест не использует БД, но conftest должен загрузиться без ошибок).

- [ ] **Step 4.4: Закоммитить**

```bash
git add app/db.py tests/conftest.py
git commit -m "feat: async SQLAlchemy engine и фикстуры тестовой БД"
```

---

## Task 5: Alembic — настройка миграций

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`

- [ ] **Step 5.1: Инициализировать Alembic шаблон**

```bash
docker compose run --rm app alembic init -t async alembic
```

Expected: создаются `alembic/`, `alembic.ini`. Будем перезаписывать ключевые файлы ниже.

- [ ] **Step 5.2: Заменить `alembic.ini` на минимальную версию**

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
sqlalchemy.url = driver://user:pass@host/dbname

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 5.3: Заменить `alembic/env.py`**

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import settings
from app.db import Base
import app.auth.models  # noqa: F401  чтобы Alembic увидел модели

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
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
```

- [ ] **Step 5.4: Закоммитить**

```bash
git add alembic.ini alembic/
git commit -m "chore: настроен alembic для async миграций"
```

---

## Task 6: Модель User (TDD)

**Files:**
- Create: `app/auth/__init__.py` (пустой)
- Create: `app/auth/models.py`
- Create: `tests/test_auth/__init__.py` (пустой)
- Create: `tests/test_auth/test_user_model.py`

- [ ] **Step 6.1: Создать пакеты**

```bash
mkdir -p app/auth tests/test_auth
type nul > app/auth/__init__.py
type nul > tests/test_auth/__init__.py
```

- [ ] **Step 6.2: Написать падающий тест модели User**

`tests/test_auth/test_user_model.py`:
```python
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.auth.models import User


@pytest.mark.asyncio
async def test_create_user_with_required_fields(db_session):
    user = User(
        email="kid@school.ru",
        password_hash="argon2hash",
    )
    db_session.add(user)
    await db_session.commit()

    result = await db_session.execute(select(User).where(User.email == "kid@school.ru"))
    saved = result.scalar_one()

    assert saved.id is not None
    assert saved.email == "kid@school.ru"
    assert saved.password_hash == "argon2hash"
    assert saved.email_verified_at is None
    assert isinstance(saved.created_at, datetime)
    assert saved.created_at.tzinfo is not None  # timezone-aware


@pytest.mark.asyncio
async def test_email_must_be_unique(db_session):
    db_session.add(User(email="dup@school.ru", password_hash="h1"))
    await db_session.commit()
    db_session.add(User(email="dup@school.ru", password_hash="h2"))
    with pytest.raises(Exception):  # IntegrityError по сути
        await db_session.commit()
```

- [ ] **Step 6.3: Запустить тест — должен упасть**

```bash
docker compose run --rm app pytest tests/test_auth/test_user_model.py -v
```

Expected: ImportError на `app.auth.models`.

- [ ] **Step 6.4: Создать `app/auth/models.py`**

```python
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
```

- [ ] **Step 6.5: Запустить тест — должен пройти**

```bash
docker compose run --rm app pytest tests/test_auth/test_user_model.py -v
```

Expected: PASS, оба теста зелёные.

- [ ] **Step 6.6: Закоммитить**

```bash
git add app/auth/ tests/test_auth/
git commit -m "feat(auth): модель User"
```

---

## Task 7: Alembic-миграция для users

**Files:**
- Create: `alembic/versions/0001_create_users.py`

- [ ] **Step 7.1: Сгенерировать миграцию автоматически**

```bash
docker compose run --rm app alembic revision --autogenerate -m "create users"
```

Проверить что в `alembic/versions/` появился файл, переименовать его в `0001_create_users.py` если автогенерация дала кривое имя. Содержимое должно быть примерно такое (если автогенерация даёт что-то сильно другое — заменить):

```python
"""create users

Revision ID: 0001
Revises:
Create Date: 2026-05-02

"""
from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
```

- [ ] **Step 7.2: Применить миграцию к dev БД**

```bash
docker compose run --rm app alembic upgrade head
```

Expected: `INFO [alembic.runtime.migration] Running upgrade  -> 0001, create users`.

- [ ] **Step 7.3: Закоммитить**

```bash
git add alembic/versions/
git commit -m "feat(auth): миграция users"
```

---

## Task 8: Хэширование паролей через Argon2 (TDD)

**Files:**
- Create: `app/auth/security.py`
- Create: `tests/test_auth/test_security.py`

- [ ] **Step 8.1: Написать падающие тесты**

`tests/test_auth/test_security.py`:
```python
import pytest

from app.auth.security import hash_password, verify_password


def test_hash_password_returns_argon2_hash():
    hashed = hash_password("hunter2")
    assert hashed.startswith("$argon2")
    assert hashed != "hunter2"


def test_verify_password_correct():
    hashed = hash_password("hunter2")
    assert verify_password("hunter2", hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("hunter2")
    assert verify_password("wrong", hashed) is False


def test_each_hash_is_unique_due_to_salt():
    h1 = hash_password("hunter2")
    h2 = hash_password("hunter2")
    assert h1 != h2
```

- [ ] **Step 8.2: Запустить — должны упасть**

```bash
docker compose run --rm app pytest tests/test_auth/test_security.py -v
```

Expected: ImportError.

- [ ] **Step 8.3: Реализовать `app/auth/security.py`**

```python
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except VerifyMismatchError:
        return False
```

- [ ] **Step 8.4: Запустить — все 4 теста зелёные**

```bash
docker compose run --rm app pytest tests/test_auth/test_security.py -v
```

- [ ] **Step 8.5: Закоммитить**

```bash
git add app/auth/security.py tests/test_auth/test_security.py
git commit -m "feat(auth): хэширование паролей argon2"
```

---

## Task 9: Pydantic-схемы и сервис регистрации (TDD)

**Files:**
- Create: `app/auth/schemas.py`
- Create: `app/auth/service.py`
- Create: `tests/test_auth/test_register.py`

- [ ] **Step 9.1: Написать падающий тест сервиса регистрации**

`tests/test_auth/test_register.py`:
```python
import pytest
from sqlalchemy import select

from app.auth.models import User
from app.auth.schemas import RegisterIn
from app.auth.service import EmailAlreadyExists, register_user


@pytest.mark.asyncio
async def test_register_creates_user_with_hashed_password(db_session):
    payload = RegisterIn(email="new@school.ru", password="strongpass123")
    user = await register_user(db_session, payload)

    assert user.id is not None
    assert user.email == "new@school.ru"
    assert user.password_hash.startswith("$argon2")
    assert user.email_verified_at is None


@pytest.mark.asyncio
async def test_register_raises_on_duplicate_email(db_session):
    payload = RegisterIn(email="dup@school.ru", password="strongpass123")
    await register_user(db_session, payload)

    with pytest.raises(EmailAlreadyExists):
        await register_user(db_session, payload)


@pytest.mark.asyncio
async def test_register_lowercases_email(db_session):
    payload = RegisterIn(email="MIXED@School.RU", password="strongpass123")
    user = await register_user(db_session, payload)
    assert user.email == "mixed@school.ru"
```

- [ ] **Step 9.2: Запустить — должны упасть**

```bash
docker compose run --rm app pytest tests/test_auth/test_register.py -v
```

- [ ] **Step 9.3: Реализовать `app/auth/schemas.py`**

```python
from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.lower().strip()


class LoginIn(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.lower().strip()
```

- [ ] **Step 9.4: Реализовать `app/auth/service.py`**

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.schemas import RegisterIn
from app.auth.security import hash_password


class EmailAlreadyExists(Exception):
    pass


async def register_user(session: AsyncSession, payload: RegisterIn) -> User:
    existing = await session.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise EmailAlreadyExists(payload.email)

    user = User(email=payload.email, password_hash=hash_password(payload.password))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
```

- [ ] **Step 9.5: Запустить — все три теста зелёные**

```bash
docker compose run --rm app pytest tests/test_auth/test_register.py -v
```

- [ ] **Step 9.6: Закоммитить**

```bash
git add app/auth/schemas.py app/auth/service.py tests/test_auth/test_register.py pyproject.toml
git commit -m "feat(auth): сервис регистрации с проверкой уникальности email"
```

---

## Task 10: Email-токены подтверждения (TDD)

**Files:**
- Modify: `app/auth/security.py`
- Modify: `tests/test_auth/test_security.py`

- [ ] **Step 10.1: Дописать тесты для verification token**

Добавить в `tests/test_auth/test_security.py`:
```python
import pytest

from app.auth.security import (
    InvalidToken,
    create_email_verification_token,
    verify_email_verification_token,
)


def test_create_and_verify_email_token():
    token = create_email_verification_token("user-id-123")
    assert isinstance(token, str)
    assert len(token) > 20

    user_id = verify_email_verification_token(token)
    assert user_id == "user-id-123"


def test_verify_token_with_garbage_raises():
    with pytest.raises(InvalidToken):
        verify_email_verification_token("not-a-real-token")


def test_verify_expired_token_raises(monkeypatch):
    import app.auth.security as sec

    monkeypatch.setattr(sec, "EMAIL_TOKEN_MAX_AGE_SECONDS", 0)
    token = sec.create_email_verification_token("user-id-123")
    import time

    time.sleep(1)
    with pytest.raises(InvalidToken):
        sec.verify_email_verification_token(token)
```

- [ ] **Step 10.2: Запустить — должны упасть**

```bash
docker compose run --rm app pytest tests/test_auth/test_security.py -v
```

- [ ] **Step 10.3: Дописать `app/auth/security.py`**

Добавить в конец файла:
```python
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import settings

EMAIL_TOKEN_SALT = "email-verify"
EMAIL_TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 3  # 3 дня


class InvalidToken(Exception):
    pass


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.app_secret_key, salt=EMAIL_TOKEN_SALT)


def create_email_verification_token(user_id: str) -> str:
    return _serializer().dumps(user_id)


def verify_email_verification_token(token: str) -> str:
    try:
        return _serializer().loads(token, max_age=EMAIL_TOKEN_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired) as exc:
        raise InvalidToken(str(exc)) from exc
```

- [ ] **Step 10.4: Запустить — должны пройти**

```bash
docker compose run --rm app pytest tests/test_auth/test_security.py -v
```

- [ ] **Step 10.5: Закоммитить**

```bash
git add app/auth/security.py tests/test_auth/test_security.py
git commit -m "feat(auth): токены подтверждения email через itsdangerous"
```

---

## Task 11: Отправка email через SMTP (TDD с Mailhog)

**Files:**
- Create: `app/auth/email.py`
- Create: `tests/test_auth/test_email.py`

- [ ] **Step 11.1: Написать падающий тест отправки**

Mailhog предоставляет HTTP API на `:8025/api/v2/messages` — можем читать оттуда отправленные письма.

`tests/test_auth/test_email.py`:
```python
import pytest
import httpx

from app.auth.email import send_verification_email


@pytest.fixture(autouse=True)
async def _clear_mailhog():
    async with httpx.AsyncClient() as c:
        await c.delete("http://mailhog:8025/api/v1/messages")
    yield


@pytest.mark.asyncio
async def test_send_verification_email_lands_in_mailhog():
    await send_verification_email(
        to="kid@school.ru",
        verification_url="http://localhost:8000/auth/verify?token=abc",
    )

    async with httpx.AsyncClient() as c:
        resp = await c.get("http://mailhog:8025/api/v2/messages")
    data = resp.json()
    assert data["total"] == 1
    msg = data["items"][0]
    assert "kid@school.ru" in [
        f"{r['Mailbox']}@{r['Domain']}" for r in msg["To"]
    ]
    body = msg["Content"]["Body"]
    assert "abc" in body
```

- [ ] **Step 11.2: Запустить — должен упасть**

```bash
docker compose run --rm app pytest tests/test_auth/test_email.py -v
```

- [ ] **Step 11.3: Реализовать `app/auth/email.py`**

```python
from email.message import EmailMessage

import aiosmtplib

from app.config import settings


async def send_verification_email(*, to: str, verification_url: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = "Подтверждение почты — SchoolTodo"
    msg.set_content(
        f"Привет!\n\n"
        f"Подтверди свою почту, перейдя по ссылке:\n{verification_url}\n\n"
        f"Если ты не регистрировался — просто проигнорируй это письмо.\n"
    )

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username or None,
        password=settings.smtp_password or None,
        start_tls=False,
    )
```

- [ ] **Step 11.4: Запустить — должен пройти**

```bash
docker compose run --rm app pytest tests/test_auth/test_email.py -v
```

Если падает с "connection refused" — убедись что mailhog поднят: `docker compose up -d mailhog`.

- [ ] **Step 11.5: Закоммитить**

```bash
git add app/auth/email.py tests/test_auth/test_email.py
git commit -m "feat(auth): отправка email через SMTP с тестом на mailhog"
```

---

## Task 12: HTTP-эндпоинт регистрации (TDD)

**Files:**
- Create: `app/auth/routes.py`
- Modify: `app/main.py`
- Create: `tests/test_auth/test_register_endpoint.py`

- [ ] **Step 12.1: Написать падающий интеграционный тест эндпоинта**

`tests/test_auth/test_register_endpoint.py`:
```python
import pytest
import httpx
from sqlalchemy import select

from app.auth.models import User


@pytest.fixture(autouse=True)
async def _clear_mailhog():
    async with httpx.AsyncClient() as c:
        await c.delete("http://mailhog:8025/api/v1/messages")
    yield


@pytest.mark.asyncio
async def test_register_endpoint_creates_user_and_sends_email(client, db_session):
    response = await client.post(
        "/auth/register",
        data={
            "email": "kid@school.ru",
            "password": "strongpass123",
            "agree_privacy": "on",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303  # redirect
    assert response.headers["location"] == "/auth/verify-pending"

    result = await db_session.execute(select(User).where(User.email == "kid@school.ru"))
    user = result.scalar_one()
    assert user.email_verified_at is None

    async with httpx.AsyncClient() as c:
        msgs = await c.get("http://mailhog:8025/api/v2/messages")
    assert msgs.json()["total"] == 1


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_form_with_error(client):
    await client.post(
        "/auth/register",
        data={
            "email": "dup@school.ru",
            "password": "strongpass123",
            "agree_privacy": "on",
        },
    )
    response = await client.post(
        "/auth/register",
        data={
            "email": "dup@school.ru",
            "password": "strongpass123",
            "agree_privacy": "on",
        },
    )
    assert response.status_code == 400
    assert "уже зарегистрирован" in response.text


@pytest.mark.asyncio
async def test_register_short_password_returns_validation_error(client):
    response = await client.post(
        "/auth/register",
        data={
            "email": "kid@school.ru",
            "password": "short",
            "agree_privacy": "on",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_without_privacy_consent_blocked(client):
    response = await client.post(
        "/auth/register",
        data={
            "email": "kid@school.ru",
            "password": "strongpass123",
            # agree_privacy не отправлен — чекбокс не отмечен
        },
    )
    assert response.status_code == 400
    assert "согласие" in response.text.lower()
```

- [ ] **Step 12.2: Запустить — должны упасть**

```bash
docker compose run --rm app pytest tests/test_auth/test_register_endpoint.py -v
```

- [ ] **Step 12.3: Создать `app/auth/routes.py`**

```python
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.email import send_verification_email
from app.auth.schemas import RegisterIn
from app.auth.security import create_email_verification_token
from app.auth.service import EmailAlreadyExists, register_user
from app.config import settings
from app.db import get_session

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/register", response_class=HTMLResponse)
async def register_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth/register.html", {"error": None})


@router.post("/register")
async def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    agree_privacy: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
):
    if agree_privacy != "on":
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            {"error": "Нужно дать согласие на обработку персональных данных."},
            status_code=400,
        )

    try:
        payload = RegisterIn(email=email, password=password)
    except ValueError as e:
        return HTMLResponse(str(e), status_code=422)

    try:
        user = await register_user(session, payload)
    except EmailAlreadyExists:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            {"error": "Этот email уже зарегистрирован."},
            status_code=400,
        )

    token = create_email_verification_token(str(user.id))
    verify_url = f"{settings.app_base_url}/auth/verify?token={token}"
    await send_verification_email(to=user.email, verification_url=verify_url)

    return RedirectResponse(url="/auth/verify-pending", status_code=303)


@router.get("/verify-pending", response_class=HTMLResponse)
async def verify_pending(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth/verify_pending.html", {})
```

- [ ] **Step 12.4: Подключить router в `app/main.py`**

Заменить содержимое `app/main.py`:
```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.auth.routes import router as auth_router
from app.config import settings

app = FastAPI(title="SchoolTodo")

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.app_secret_key,
    same_site="lax",
    https_only=False,  # на dev
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(auth_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 12.5: Создать минимальные шаблоны для теста**

`app/templates/base.html`:
```html
<!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{% block title %}SchoolTodo{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
</head>
<body class="bg-slate-50 text-slate-900 min-h-screen">
    <main class="max-w-2xl mx-auto p-4">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

`app/templates/auth/register.html`:
```html
{% extends "base.html" %}
{% block title %}Регистрация — SchoolTodo{% endblock %}
{% block content %}
<h1 class="text-2xl font-bold mb-4">Регистрация</h1>
{% if error %}
<div class="bg-red-100 text-red-800 p-3 rounded mb-4">{{ error }}</div>
{% endif %}
<form method="post" action="/auth/register" class="space-y-3">
    <input type="email" name="email" required placeholder="Почта"
           class="w-full p-3 border rounded">
    <input type="password" name="password" required minlength="8" placeholder="Пароль (от 8 символов)"
           class="w-full p-3 border rounded">
    <label class="flex items-start gap-2 text-sm text-slate-700">
        <input type="checkbox" name="agree_privacy" required class="mt-1">
        <span>Согласен с обработкой персональных данных и
            <a href="/privacy" class="text-indigo-600 underline">политикой конфиденциальности</a>.
        </span>
    </label>
    <button type="submit" class="w-full p-3 bg-indigo-600 text-white rounded font-semibold">
        Зарегистрироваться
    </button>
</form>
<p class="mt-4 text-sm text-slate-600">
    Уже есть аккаунт? <a href="/auth/login" class="text-indigo-600 underline">Войти</a>
</p>
{% endblock %}
```

`app/templates/auth/verify_pending.html`:
```html
{% extends "base.html" %}
{% block content %}
<h1 class="text-2xl font-bold mb-4">Проверь почту</h1>
<p>Мы отправили письмо со ссылкой для подтверждения. Открой его и кликни по ссылке.</p>
{% endblock %}
```

- [ ] **Step 12.6: Создать пустой `app/static/app.js`**

```bash
mkdir -p app/static
type nul > app/static/app.js
```

- [ ] **Step 12.7: Запустить тесты — должны пройти**

```bash
docker compose run --rm app pytest tests/test_auth/test_register_endpoint.py -v
```

- [ ] **Step 12.8: Закоммитить**

```bash
git add app/ tests/
git commit -m "feat(auth): эндпоинт регистрации + базовые шаблоны"
```

---

## Task 13: Подтверждение email (TDD)

**Files:**
- Modify: `app/auth/service.py`
- Modify: `app/auth/routes.py`
- Create: `tests/test_auth/test_verify.py`

- [ ] **Step 13.1: Написать падающий тест**

`tests/test_auth/test_verify.py`:
```python
import pytest
from sqlalchemy import select

from app.auth.models import User
from app.auth.schemas import RegisterIn
from app.auth.security import create_email_verification_token
from app.auth.service import register_user


@pytest.mark.asyncio
async def test_verify_email_endpoint_marks_user_verified(client, db_session):
    user = await register_user(
        db_session,
        RegisterIn(email="kid@school.ru", password="strongpass123"),
    )
    token = create_email_verification_token(str(user.id))

    response = await client.get(f"/auth/verify?token={token}", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login"

    await db_session.refresh(user)
    assert user.email_verified_at is not None


@pytest.mark.asyncio
async def test_verify_with_invalid_token_returns_400(client):
    response = await client.get("/auth/verify?token=garbage")
    assert response.status_code == 400
    assert "недействительна" in response.text.lower()
```

- [ ] **Step 13.2: Запустить — должен упасть**

```bash
docker compose run --rm app pytest tests/test_auth/test_verify.py -v
```

- [ ] **Step 13.3: Дописать сервис в `app/auth/service.py`**

Добавить в конец файла:
```python
from datetime import UTC, datetime
from uuid import UUID


class TokenInvalid(Exception):
    pass


async def mark_email_verified(session: AsyncSession, user_id: str) -> User:
    try:
        uid = UUID(user_id)
    except ValueError as e:
        raise TokenInvalid("malformed user id") from e

    user = await session.get(User, uid)
    if user is None:
        raise TokenInvalid("user not found")
    user.email_verified_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(user)
    return user
```

- [ ] **Step 13.4: Дописать роуты в `app/auth/routes.py`**

Добавить:
```python
from app.auth.security import (
    InvalidToken,
    create_email_verification_token,
    verify_email_verification_token,
)
from app.auth.service import (
    EmailAlreadyExists,
    TokenInvalid,
    mark_email_verified,
    register_user,
)


@router.get("/verify")
async def verify(
    token: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        user_id = verify_email_verification_token(token)
        await mark_email_verified(session, user_id)
    except (InvalidToken, TokenInvalid):
        return HTMLResponse(
            "Ссылка недействительна или истекла. Запроси новое письмо.",
            status_code=400,
        )
    return RedirectResponse(url="/auth/login", status_code=303)
```

- [ ] **Step 13.5: Запустить — должен пройти**

```bash
docker compose run --rm app pytest tests/test_auth/test_verify.py -v
```

- [ ] **Step 13.6: Закоммитить**

```bash
git add app/auth/ tests/test_auth/test_verify.py
git commit -m "feat(auth): подтверждение email по токену"
```

---

## Task 14: Логин и сессия (TDD)

**Files:**
- Modify: `app/auth/service.py`
- Modify: `app/auth/routes.py`
- Create: `app/auth/deps.py`
- Create: `tests/test_auth/test_login.py`
- Create: `app/templates/auth/login.html`

- [ ] **Step 14.1: Написать падающий тест логина**

`tests/test_auth/test_login.py`:
```python
from datetime import UTC, datetime

import pytest

from app.auth.schemas import RegisterIn
from app.auth.service import register_user


async def _make_verified_user(db_session, email="kid@school.ru", password="strongpass123"):
    user = await register_user(db_session, RegisterIn(email=email, password=password))
    user.email_verified_at = datetime.now(UTC)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_login_with_correct_credentials_sets_session(client, db_session):
    await _make_verified_user(db_session)

    response = await client.post(
        "/auth/login",
        data={"email": "kid@school.ru", "password": "strongpass123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "session" in response.cookies


@pytest.mark.asyncio
async def test_login_with_wrong_password_returns_form_with_error(client, db_session):
    await _make_verified_user(db_session)
    response = await client.post(
        "/auth/login",
        data={"email": "kid@school.ru", "password": "wrong-one"},
    )
    assert response.status_code == 401
    assert "неверный" in response.text.lower()


@pytest.mark.asyncio
async def test_login_with_unverified_email_blocked(client, db_session):
    await register_user(
        db_session, RegisterIn(email="kid@school.ru", password="strongpass123")
    )  # email_verified_at = None
    response = await client.post(
        "/auth/login",
        data={"email": "kid@school.ru", "password": "strongpass123"},
    )
    assert response.status_code == 403
    assert "подтверди" in response.text.lower()
```

- [ ] **Step 14.2: Запустить — должны упасть**

```bash
docker compose run --rm app pytest tests/test_auth/test_login.py -v
```

- [ ] **Step 14.3: Дописать сервис login в `app/auth/service.py`**

Добавить:
```python
from app.auth.security import verify_password


class InvalidCredentials(Exception):
    pass


class EmailNotVerified(Exception):
    pass


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    email = email.lower().strip()
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentials()
    if user.email_verified_at is None:
        raise EmailNotVerified()
    return user
```

- [ ] **Step 14.4: Создать `app/auth/deps.py`**

```python
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.db import get_session


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User | None:
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    from uuid import UUID

    try:
        uid = UUID(user_id)
    except ValueError:
        return None
    return await session.get(User, uid)


async def require_user(user: User | None = Depends(get_current_user)) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "не авторизован")
    return user
```

- [ ] **Step 14.5: Дописать routes**

В `app/auth/routes.py` добавить:
```python
from app.auth.service import EmailNotVerified, InvalidCredentials, authenticate


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth/login.html", {"error": None})


@router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    try:
        user = await authenticate(session, email, password)
    except InvalidCredentials:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {"error": "Неверный email или пароль."},
            status_code=401,
        )
    except EmailNotVerified:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {"error": "Сначала подтверди email — мы отправили тебе письмо."},
            status_code=403,
        )

    request.session["user_id"] = str(user.id)
    return RedirectResponse(url="/", status_code=303)
```

- [ ] **Step 14.6: Создать `app/templates/auth/login.html`**

```html
{% extends "base.html" %}
{% block title %}Вход — SchoolTodo{% endblock %}
{% block content %}
<h1 class="text-2xl font-bold mb-4">Вход</h1>
{% if error %}
<div class="bg-red-100 text-red-800 p-3 rounded mb-4">{{ error }}</div>
{% endif %}
<form method="post" action="/auth/login" class="space-y-3">
    <input type="email" name="email" required placeholder="Почта"
           class="w-full p-3 border rounded">
    <input type="password" name="password" required placeholder="Пароль"
           class="w-full p-3 border rounded">
    <button type="submit" class="w-full p-3 bg-indigo-600 text-white rounded font-semibold">
        Войти
    </button>
</form>
<p class="mt-4 text-sm text-slate-600">
    Нет аккаунта? <a href="/auth/register" class="text-indigo-600 underline">Зарегистрироваться</a>
</p>
{% endblock %}
```

- [ ] **Step 14.7: Запустить тесты — должны пройти**

```bash
docker compose run --rm app pytest tests/test_auth/test_login.py -v
```

- [ ] **Step 14.8: Закоммитить**

```bash
git add app/auth/ tests/test_auth/test_login.py app/templates/auth/login.html
git commit -m "feat(auth): логин с проверкой пароля и подтверждения email"
```

---

## Task 15: Логаут и защищённый эндпоинт (TDD)

**Files:**
- Modify: `app/auth/routes.py`
- Create: `tests/test_auth/test_logout.py`
- Create: `app/routers/__init__.py`
- Create: `app/routers/pages.py`
- Modify: `app/main.py`
- Create: `app/templates/landing.html`

- [ ] **Step 15.1: Написать тест логаута и защищённой главной**

`tests/test_auth/test_logout.py`:
```python
from datetime import UTC, datetime

import pytest

from app.auth.schemas import RegisterIn
from app.auth.service import register_user


async def _login_as(client, db_session, email="kid@school.ru", password="strongpass123"):
    user = await register_user(db_session, RegisterIn(email=email, password=password))
    user.email_verified_at = datetime.now(UTC)
    await db_session.commit()
    await client.post("/auth/login", data={"email": email, "password": password})
    return user


@pytest.mark.asyncio
async def test_logout_clears_session(client, db_session):
    await _login_as(client, db_session)

    response = await client.post("/auth/logout", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"

    home = await client.get("/")
    assert "Войти" in home.text  # видно ссылку "Войти" — значит не залогинен


@pytest.mark.asyncio
async def test_landing_shows_login_link_when_anonymous(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert "Войти" in response.text
    assert "Зарегистрироваться" in response.text


@pytest.mark.asyncio
async def test_landing_shows_user_email_when_logged_in(client, db_session):
    await _login_as(client, db_session)
    response = await client.get("/")
    assert response.status_code == 200
    assert "kid@school.ru" in response.text
```

- [ ] **Step 15.2: Запустить — должны упасть**

```bash
docker compose run --rm app pytest tests/test_auth/test_logout.py -v
```

- [ ] **Step 15.3: Добавить логаут в routes**

В `app/auth/routes.py` дописать:
```python
@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)
```

- [ ] **Step 15.4: Создать `app/routers/__init__.py` и `app/routers/pages.py`**

```bash
mkdir -p app/routers
type nul > app/routers/__init__.py
```

`app/routers/pages.py`:
```python
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.auth.deps import get_current_user
from app.auth.models import User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def landing(
    request: Request,
    user: User | None = Depends(get_current_user),
) -> HTMLResponse:
    return templates.TemplateResponse(request, "landing.html", {"user": user})


@router.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "privacy.html", {})
```

Также создать заглушку `app/templates/privacy.html`:
```html
{% extends "base.html" %}
{% block title %}Политика конфиденциальности — SchoolTodo{% endblock %}
{% block content %}
<h1 class="text-2xl font-bold mb-4">Политика конфиденциальности</h1>
<p class="text-slate-600">
    Финальная редакция политики будет здесь перед публичным запуском (Plan 4).
    Краткая суть: мы храним твою почту и токен дневника, не передаём их никому,
    можно удалить аккаунт со всеми данными в один клик из профиля.
</p>
{% endblock %}
```

- [ ] **Step 15.5: Подключить pages router в `app/main.py`**

Добавить импорт и include:
```python
from app.routers.pages import router as pages_router

# после include_router(auth_router):
app.include_router(pages_router)
```

- [ ] **Step 15.6: Создать `app/templates/landing.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1 class="text-3xl font-bold mb-6">SchoolTodo</h1>
<p class="text-lg mb-8">Туду-лист для школьников. Подключи дневник — и больше не забывай ДЗ.</p>

{% if user %}
<div class="bg-white p-4 rounded shadow">
    <p>Ты зашёл как <strong>{{ user.email }}</strong>.</p>
    <form method="post" action="/auth/logout" class="mt-3">
        <button class="px-4 py-2 bg-slate-200 rounded">Выйти</button>
    </form>
</div>
{% else %}
<div class="space-x-3">
    <a href="/auth/register" class="px-4 py-2 bg-indigo-600 text-white rounded">Зарегистрироваться</a>
    <a href="/auth/login" class="px-4 py-2 border border-indigo-600 text-indigo-600 rounded">Войти</a>
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 15.7: Запустить тесты — должны пройти**

```bash
docker compose run --rm app pytest tests/test_auth/test_logout.py -v
```

- [ ] **Step 15.8: Закоммитить**

```bash
git add app/ tests/
git commit -m "feat: логаут и landing-страница"
```

---

## Task 16: Финальный прогон всех тестов и README

**Files:**
- Create: `README.md`

- [ ] **Step 16.1: Прогнать все тесты целиком**

```bash
docker compose run --rm app pytest -v --cov=app --cov-report=term-missing
```

Expected: все тесты зелёные, покрытие модулей `app/auth/*` >= 80%.

- [ ] **Step 16.2: Создать README.md**

```markdown
# SchoolTodo

Туду-лист для школьников на основе электронного дневника.

## Документы

- [Дизайн-документ](docs/superpowers/specs/2026-05-02-school-todo-design.md)
- [PROGRESS.md](PROGRESS.md)
- [Планы реализации](docs/superpowers/plans/)

## Стек

Python 3.12 · FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL · Redis · Jinja2 · HTMX · Tailwind CDN.

## Запуск локально

```bash
cp .env.example .env
docker compose up -d
docker compose exec app alembic upgrade head
```

Открой http://localhost:8000 — landing страница.
Открой http://localhost:8025 — Mailhog (просмотр отправленных писем).

## Тесты

```bash
docker compose run --rm app pytest -v
```

## Миграции

Создать новую миграцию:
```bash
docker compose run --rm app alembic revision --autogenerate -m "описание"
```

Применить:
```bash
docker compose run --rm app alembic upgrade head
```
```

- [ ] **Step 16.3: Ручная проверка через браузер**

```bash
docker compose up -d
docker compose exec app alembic upgrade head
```

Открыть http://localhost:8000:
- [ ] Видна landing страница с кнопками "Зарегистрироваться" и "Войти".
- [ ] Перейти на /auth/register, ввести email/пароль, отправить.
- [ ] Открыть http://localhost:8025 (Mailhog) — должно прийти письмо.
- [ ] Кликнуть по ссылке в письме — должен быть редирект на /auth/login.
- [ ] Залогиниться — попасть на landing с email и кнопкой "Выйти".
- [ ] Нажать "Выйти" — снова видны кнопки регистрации/входа.

- [ ] **Step 16.4: Обновить PROGRESS.md**

Добавить в `PROGRESS.md` под "Лог сессий" новую запись:
```markdown
### 2026-05-02 — Plan 1 завершён
- Project foundation (Docker Compose, FastAPI, async SQLAlchemy, Alembic).
- Auth: регистрация, подтверждение email, логин, логаут, защищённая landing.
- Все 13+ тестов зелёные, ручная проверка пройдена.
- Готовы переходить к Plan 2: подключение Школьного портала МО + синхронизация ДЗ.
```

- [ ] **Step 16.5: Закоммитить README и PROGRESS**

```bash
git add README.md PROGRESS.md
git commit -m "docs: README и обновление прогресса по Plan 1"
```

---

## Критерии успеха Plan 1

- [ ] Все автоматические тесты зелёные.
- [ ] Покрытие критичных модулей (`app/auth/`) >= 80%.
- [ ] Ручной end-to-end тест регистрации → подтверждения email → логина → логаута проходит без ошибок.
- [ ] `docker compose up -d` поднимает рабочее окружение в один клик.
- [ ] Все коммиты осмысленные, по одному на логическую единицу работы.

---

## Что НЕ входит в Plan 1 (будет в следующих)

- DiarySource абстракция и `MosregSource` реализация → **Plan 2**.
- Модели Homework/Schedule/Subject + миграции → **Plan 2**.
- Dramatiq workers и периодическая синхронизация → **Plan 2**.
- UI с прогресс-барами, чекбоксами, темами, анимациями → **Plan 3**.
- Производственный деплой (Selectel, nginx, certbot, не-CDN Tailwind) → **Plan 4**.
- Геймификация фазы 1.5 (стрики, XP, ачивки) → отдельный спек после MVP.
- Родительский кабинет и биллинг → отдельный спек после MVP.
