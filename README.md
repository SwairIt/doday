# SchoolTodo

Todo-list for Russian schoolchildren that auto-syncs homework from electronic school diaries.

See the [design doc](docs/superpowers/specs/2026-05-02-school-todo-design.md) for the full picture and [PROGRESS.md](PROGRESS.md) for current status.

## Local setup

Prerequisites: [uv](https://docs.astral.sh/uv/), Python 3.12+, access to a Postgres server.

1. Copy `.env.example` to `.env` and fill in values:
   - `APP_SECRET_KEY` — random ≥32 chars (`python -c "import secrets; print(secrets.token_urlsafe(48))"`).
   - `DATABASE_URL` — your Postgres URL.
   - `TEST_DATABASE_URL` — a separate Postgres database for tests.

2. Create the two databases on your Postgres server:

   ```sql
   CREATE USER schooltodo WITH PASSWORD '<your password>';
   CREATE DATABASE schooltodo OWNER schooltodo;
   CREATE DATABASE schooltodo_test OWNER schooltodo;
   ```

3. Sync dependencies and apply migrations:

   ```bash
   uv sync
   uv run alembic upgrade head
   ```

4. Run tests:

   ```bash
   uv run pytest
   ```

5. Run the app:

   ```bash
   uv run uvicorn app.main:app --reload
   ```

   Then `http://localhost:8000/health` → `{"status":"ok"}`.

## Quality bar

- `uv run ruff check .` — lint
- `uv run ruff format --check .` — formatting
- `uv run mypy .` — strict type checking

All three must pass before any commit.

## Layout

```
app/                FastAPI application
├── config.py       Settings (pydantic-settings)
├── db.py           Async SQLAlchemy engine + session factory
├── logging_setup.py  structlog (JSON) configuration
├── main.py         FastAPI app entrypoint
└── auth/           Auth feature (router/service/models/schemas come per chunk)
    └── models.py   User SQLAlchemy model

alembic/            Migrations
tests/              pytest suite (TRUNCATE between test functions)
docs/superpowers/   Specs and implementation plans
```
