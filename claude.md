# Claude instructions for Doday (formerly SchoolTodo)

## PROJECT PIVOT 2026-05-03

The product changed scope. It is no longer "todo for Russian schoolchildren" — it is now **"free todo for everyone"** (kids, adults, companies). The diary-parsing feature for Школьный портал МО / МЭШ is now an optional integration, not the core product.

- Working brand name: **Doday**
- Python package name: `schooltodo` (kept to avoid refactor churn)
- See `docs/superpowers/specs/2026-05-03-pivot-design-spec.md` for the current spec
- The 2026-05-02 spec is historical only

## Read first in every session

1. **`PROGRESS.md`** — current state, what's done, what's next, exact next chunk to execute.
2. **`docs/superpowers/specs/2026-05-03-pivot-design-spec.md`** — current product + design spec.
3. Memory in `~/.claude/projects/c--www-Yaroslav-SchoolProject/memory/`.

## Languages

- Chat with the user: **Russian**.
- Internal artifacts (memory, plans, specs, code comments, commit messages excluded): **English**.
- Git commit messages: **Russian, past tense** ("добавил X", "исправил Y").

## Tech stack

- Python 3.12 + FastAPI + Uvicorn
- SQLAlchemy 2.0 (async) + Alembic + asyncpg
- Pydantic v2 + pydantic-settings v2
- Jinja2 templates + HTMX 2 + Alpine.js (minimal JS)
- Tailwind CSS via CDN (build process deferred)
- structlog (JSON), argon2-cffi, itsdangerous, aiosmtplib
- Local Postgres on `localhost:5432` (user `postgres`, password `postgres`, dbs `schooltodo` / `schooltodo_test`)

## Quality bar (non-negotiable)

`uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy .` must all pass before any commit.

- ruff rule set: `E,F,I,UP,B,S,A,RUF`
- mypy `--strict`, no `# type: ignore` without an explanatory comment
- pydantic v2 `BaseModel` for any data crossing a boundary
- Tests: pytest-asyncio mode=auto, TRUNCATE between functions
- Per-feature folders `app/<feature>/{router,service,models,schemas}.py`

## Git workflow

- Repo: `https://github.com/SwairIt/SchoolProject.git`
- Branch: `master`. Push directly after each chunk.
- PAT in `.env` as `TOKEN`. Never write into `.git/config` or full command lines:
  ```bash
  TOKEN=$(grep '^TOKEN=' .env | cut -d= -f2- | tr -d '\r\n')
  git push "https://x-access-token:${TOKEN}@github.com/SwairIt/SchoolProject.git" master
  ```
- **Author email**: ALWAYS use `112168281+SwairIt@users.noreply.github.com` so commits show as SwairIt on GitHub. Never use the system-supplied userEmail.
- `.env` is gitignored. Verify before any `git add`.

## Uvicorn lifecycle (CRITICAL — repeated bug source)

**Symptom of the bug:** user opens `/app/<some-recently-added-route>` and gets `{"detail": "Not Found"}` even though `pytest` and `mypy` pass and the route is in the code. Cause: a stale uvicorn process from an earlier run is still bound to port 8000 with **old code**, and new uvicorn restarts have silently failed to take over.

**Always do these three things when starting uvicorn:**

1. **Kill anything on 8000 with PID-direct `Stop-Process -Id <pid> -Force`.** Do NOT rely on the `Get-NetTCPConnection | foreach Stop-Process` pattern alone — sometimes a process holds the port but isn't returned by `Get-NetTCPConnection -State Listen`. Check with raw `netstat -ano | Select-String ":8000\s+0.0.0.0:0\s+LISTENING"` first to find the PID, then force-kill.

2. **Start uvicorn with `--reload`.** This way subsequent code edits auto-reload without manual restart, eliminating the whole class of "wrong version of code is running" bugs:
   ```
   uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload > .uvicorn.log 2> .uvicorn.err
   ```
   Run via Bash `run_in_background: true`.

3. **Verify the new server actually owns the port AND serves new routes:**
   ```
   sleep 8
   curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/health   # expect 200
   curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/app/<new-route>  # expect 401, NOT 404
   ```
   `404` on a route that exists in code = the wrong process is still answering. `401` (auth required) = correct route is registered.

**Never skip step 3.** "Process started OK" / `/health` 200 is not enough — old uvicorn also serves `/health`. Check the specific route the new code added.

## What is RUNNING right now

- Local Postgres (scoop install): `C:\Users\Yaroslav\scoop\apps\postgresql\current\bin\pg_ctl.exe`
- Uvicorn: started via `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000`
- aiosmtpd debug SMTP on `127.0.0.1:1025`

## What we deliberately do NOT do

- ❌ AI auto-completion of homework (rejected at brainstorm)
- ❌ Copy Todoist verbatim (copyright + ToS)
- ❌ Use third-party account credentials provided by the user (security)
- ❌ React/Vue/Svelte (user weak in JS)

## After meaningful work

- Update `PROGRESS.md` (mark chunk done, advance pointer)
- Push to `origin master`
- For architectural shifts — write or update memory
