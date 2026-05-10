# Doday

Free todo-list for everyone — kids, adults, companies. Hosted at **https://getdoday.ru**.

Was originally "SchoolTodo" with auto-sync of Russian electronic school diaries (МО / МЭШ); pivoted 2026-05-03 to a universal product. Diary parsing kept as an optional integration. See [pivot spec](docs/superpowers/specs/2026-05-03-pivot-design-spec.md) and [PROGRESS.md](PROGRESS.md) for current status.

## What's implemented (Plan 1 — auth foundation)

- Email + password registration with mandatory privacy-policy consent.
- Email verification (token via `itsdangerous`, sent via SMTP).
- Login with session cookie (signed via Starlette `SessionMiddleware`).
- Logout.
- Landing page that shows different state for anonymous vs logged-in users.
- Privacy policy stub at `/privacy` (final text comes pre-launch).

What's intentionally **not** here yet: diary integration, homework UI, parent dashboard, gamification, notifications. Those land in Plans 2–4.

## Local setup

Prerequisites: [uv](https://docs.astral.sh/uv/), Python 3.12+, access to a Postgres server.

1. Copy `.env.example` to `.env` and fill in real values:

   - `APP_SECRET_KEY` — random ≥32 chars (`python -c "import secrets; print(secrets.token_urlsafe(48))"`).
   - `DATABASE_URL` — your Postgres URL.
   - `TEST_DATABASE_URL` — a separate Postgres database used by tests (truncated between test functions).
   - `SMTP_*` — defaults assume a local debug SMTP on `localhost:1025`. For real email, point to a real provider before going public.

2. Create the two databases on your Postgres server:

   ```sql
   CREATE USER schooltodo WITH PASSWORD '<your password>';
   CREATE DATABASE schooltodo OWNER schooltodo;
   CREATE DATABASE schooltodo_test OWNER schooltodo;
   ```

3. Sync deps and apply migrations:

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

## End-to-end manual check

For a one-time SMTP capture during dev, install [aiosmtpd](https://aiosmtpd.aio-libs.org/) globally and run a debug catcher in another terminal:

```bash
uv run python -m aiosmtpd -n -l localhost:1025
```

Then:

1. Open `http://localhost:8000` → see "Зарегистрироваться" / "Войти" buttons.
2. Click "Зарегистрироваться", fill form, **check the privacy box**, submit.
3. The aiosmtpd terminal prints the verification email — copy the link.
4. Paste the link → redirected to `/auth/login`.
5. Log in with the same credentials → land on `/` showing your email + "Выйти" button.
6. Click "Выйти" → back to anonymous landing.

## Quality bar

All three must be green before any commit:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
```

## Layout

```
app/                FastAPI application
├── config.py       Settings (pydantic-settings v2)
├── db.py           Async SQLAlchemy engine + session factory
├── logging_setup.py  structlog (JSON) configuration
├── main.py         FastAPI entrypoint + middleware + router includes
├── auth/           Auth feature
│   ├── deps.py     get_current_user / require_user
│   ├── email.py    send_verification_email
│   ├── models.py   User
│   ├── router.py   /auth/* endpoints
│   ├── schemas.py  RegisterIn / LoginIn
│   ├── security.py argon2 hashing + email-verification tokens
│   └── service.py  register_user / mark_email_verified / authenticate
├── pages/          Shared pages
│   └── router.py   GET / and GET /privacy
└── templates/      Jinja2 (Tailwind via CDN, HTMX preloaded)

alembic/            Migrations
tests/              pytest suite (TRUNCATE between test functions)
docs/superpowers/   Specs and implementation plans
```
