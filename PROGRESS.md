# SchoolTodo — Progress tracker

**Purpose of this file:** session-spanning progress tracker. New sessions should read this and `claude.md` first to understand where we left off.

---

## Status as of 2026-05-02 (end of Plan 1)

**Current phase:** Plan 1 (Foundation + Auth) implemented. Awaiting end-to-end verification by user before starting Plan 2.

**Done:**
- ✅ Brainstorm + design doc.
- ✅ Memory and `claude.md` translated to English; user collaboration rules saved.
- ✅ GitHub remote `origin → https://github.com/SwairIt/SchoolProject.git`. Pushing to `master` directly per user instruction.
- ✅ `.gitignore` protects `.env`.
- ✅ **Plan 1 — Foundation + Auth** delivered in 4 chunks (5th was just docs polish):
  - **Chunk 1 (`bd2cf85`)** — pyproject (ruff strict + mypy --strict + pytest-asyncio mode=auto), `app/{config,db,logging_setup,main}.py`, `app/auth/models.py`, alembic + migration `0001_create_users`, `tests/conftest.py` (TRUNCATE between functions), `test_health.py`, `test_user_model.py`, README, `.env.example`.
  - **Chunk 2 (`f296346`)** — `app/auth/{security,schemas,service}.py` (argon2, RegisterIn/LoginIn, register_user, EmailAlreadyExists, email-verification tokens via itsdangerous). Tests: 7 security + 5 schemas + 2 register-service.
  - **Chunk 3 (`08a566f`)** — `app/auth/{email,router}.py` + `app/pages/router.py` + 4 templates (base, register, verify_pending, privacy). SMTP via aiosmtplib (mocked in tests). 1 email test + 7 register-endpoint tests.
  - **Chunk 4 (`271464c`)** — `mark_email_verified` + `authenticate` in service.py + `TokenInvalid`/`InvalidCredentials`/`EmailNotVerified` exceptions. `app/auth/deps.py` with `get_current_user`/`require_user`. Endpoints `/auth/verify`, `/auth/login`, `/auth/logout`. Landing page in `app/pages/router.py`. login.html + landing.html templates. 8 service tests + 6 endpoint tests + 2 landing tests.
- ✅ All static checks green at every chunk: `ruff check`, `ruff format --check`, `mypy --strict` on 31 source files.

**In progress:**
- 🟡 User runs `uv sync && uv run alembic upgrade head && uv run pytest` and reports green/red.
- 🟡 User does the end-to-end manual flow described in README (register → verify email → login → logout).

**Next (Plan 2 — DiarySource + sync):**
- ⏳ Write Plan 2 covering `DiarySource` Protocol, `MosregSource` implementation (authedu.mosreg.ru), Homework + Schedule + Subject ORM models + migrations, encrypted token storage, Dramatiq workers + Redis for periodic sync, sync triggered from UI button.
- ⏳ Then Plan 3 (UI + gamification: progress bars, animations, dark theme, mobile-first).
- ⏳ Then Plan 4 (production deploy: switch Tailwind to build, real SMTP, hosting on Selectel/Timeweb, full privacy text, Roskomnadzor PD-operator registration).

---

## Test count after Plan 1

| Module | # tests | Needs DB |
|---|---|---|
| `test_health.py` | 1 | no |
| `test_user_model.py` | 2 | yes |
| `test_auth/test_security.py` | 7 | no |
| `test_auth/test_schemas.py` | 5 | no |
| `test_auth/test_email.py` | 1 | no (SMTP mocked) |
| `test_auth/test_register_service.py` | 2 | yes |
| `test_auth/test_register_endpoint.py` | 7 | yes |
| `test_auth/test_verify_service.py` | 3 | yes |
| `test_auth/test_authenticate_service.py` | 5 | yes |
| `test_auth/test_verify_endpoint.py` | 2 | yes |
| `test_auth/test_login_endpoint.py` | 5 | yes |
| `test_landing.py` | 2 | yes |
| **Total** | **42** | |

---

## Key decisions (with rationale)

| Decision | Date | Why |
|---|---|---|
| Reject AI homework auto-completion | 2026-05-02 | Broken business model, legal risk, free alternatives |
| Web app as the first platform | 2026-05-02 | Lowest entry barrier, any device |
| Monetize via parent dashboard | 2026-05-02 | Parent is the actual paying customer, not the child |
| First diary source: authedu.mosreg.ru | 2026-05-02 | User's own school is on this system → he'll be dogfood user |
| DiarySource abstraction in MVP | 2026-05-02 | Cheap to add new diaries later vs. expensive refactor |
| Python + FastAPI + HTMX | 2026-05-02 | User's strength is Python; HTMX avoids React (user weak in JS) |
| Russian hosting | 2026-05-02 | 152-FZ requires localization of Russian citizens' personal data |
| Manual token paste in MVP | 2026-05-02 | Simple and reliable; browser extension auth-helper later |
| Parent dashboard after MVP | 2026-05-02 | Without live users there's no one to test the parent flow |
| Push directly to master | 2026-05-02 | Solo project, no PR overhead |
| Internal docs in English; chat + commits in Russian | 2026-05-02 | Token efficiency, with explicit per-channel choices |
| Use user's external Postgres (no Docker) | 2026-05-02 | User already has a Postgres server (SSH-tunneled to localhost:5433) |
| Strict tooling from day one (ruff strict + mypy --strict + pydantic v2) | 2026-05-02 | "Потом не переделывать" — quality bar set by user |
| TRUNCATE between test functions, not rollback | 2026-05-02 | App code calls .commit(); rollback wouldn't undo it |
| Per-feature folders (`app/<feature>/{router,service,schemas,models}.py`) | 2026-05-02 | Per user's structure rule; no global `models.py` |
| Annotated[X, Depends(...)] FastAPI style | 2026-05-02 | Modern (FastAPI 0.95+), passes ruff B008 |
| Mock SMTP in tests via `unittest.mock.patch` | 2026-05-02 | Avoids any SMTP server dependency for CI / dev |

---

## Things still to verify experimentally during implementation

- 🔬 Exact auth scheme of the authedu.mosreg.ru API (Plan 2).
- 🔬 Session token lifetime in the diary (Plan 2).
- 🔬 Diary API rate limits (Plan 2).
- 🔬 Shape of `homework` and `schedule` API responses (Plan 2).

---

## Session log

### 2026-05-02 — session 1
- Brainstormed the idea, cut the AI homework auto-completion feature.
- Agreed MVP scope, tech stack, monetization.
- Wrote the design document.
- Added "UX & visual design" section + gamification (basic in MVP, advanced in phase 1.5).
- Wrote first draft of Plan 1 in Russian assuming dockerized Postgres.

### 2026-05-02 — session 2
- User chose subagent-driven execution mode.
- User added GitHub PAT to `.env`, requested push-to-master workflow.
- User has external Postgres server — Plan 1 had to be redesigned (no Docker).
- User requested all internal documentation in English to save tokens.
- Translated memory + `claude.md` + `PROGRESS.md` to English.
- User set hard quality bar (ruff strict, mypy --strict, pydantic v2, per-feature folders, TRUNCATE-between-tests, structlog, Russian commits).
- User set DB credential isolation rule (never ask for DATABASE_URL/passwords; user runs tests + migrations locally).
- Implemented Plan 1 directly (without subagents — small enough): 4 feature chunks + this docs chunk.
- Pushed each chunk to `origin master`.
