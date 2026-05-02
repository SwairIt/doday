# Claude instructions for SchoolTodo

## Read first in every session

1. Read **`PROGRESS.md`** at the project root — current state, what's done, what's next.
2. Read **`docs/superpowers/specs/2026-05-02-school-todo-design.md`** — main project specification.
3. Read your `MEMORY.md` (in `~/.claude/projects/c--www-Yaroslav-SchoolProject/memory/`) — user/project/feedback memory.

## Languages

- **Chat with the user: Russian.** The user writes in Russian and expects Russian responses.
- **All internal artifacts: English.** This includes: `claude.md`, `MEMORY.md`, all memory files, design docs, plans, subagent prompts, code comments, commit messages, PROGRESS.md. The user explicitly requested this to save tokens (Cyrillic costs ~2-3× more tokens than ASCII).

## Always use superpowers

In this project, on every step of development use skills from the **superpowers** plugin:

- **`superpowers:brainstorming`** — before any creative work / new feature.
- **`superpowers:writing-plans`** — to draft an implementation plan.
- **`superpowers:executing-plans`** OR **`superpowers:subagent-driven-development`** — to execute the plan.
- **`superpowers:test-driven-development`** — mandatory for all business-critical code (sync, billing, diary sources).
- **`superpowers:systematic-debugging`** — for any bug or test failure.
- **`superpowers:verification-before-completion`** — before claiming "done".
- **`superpowers:requesting-code-review`** — after meaningful chunks of work.

If a relevant skill exists (even 1% chance it applies) — invoke it via the Skill tool.

## Tech stack

See full list in the spec. Summary:
- Backend: Python 3.12 + FastAPI
- Frontend: Jinja2 + HTMX + Alpine.js + Tailwind CSS (minimum JS!)
- DB: PostgreSQL (user has an external Postgres server — connection details in `.env`)
- ORM: SQLAlchemy 2.0 (async) + Alembic
- Queues: Dramatiq + Redis (Redis location TBD with user before Plan 2)
- Deploy: TBD in Plan 4 (Russian hosting per 152-FZ)

**Do NOT use:** React, Vue, Svelte, Celery, Django, MongoDB.

## Git workflow

- Repo: `https://github.com/SwairIt/SchoolProject.git` (remote `origin`).
- Branch: work on `master`. Push directly after each completed chunk.
- PAT for push is in `.env` (variable `TOKEN`). NEVER write the token into `.git/config`, commit messages, or commands that get logged with their full text. Read it from `.env` at push time only:
  ```bash
  TOKEN=$(grep '^TOKEN=' .env | cut -d= -f2)
  git push https://x-access-token:${TOKEN}@github.com/SwairIt/SchoolProject.git master
  ```
- `.env` is in `.gitignore`. Verify before any `git add`.

## User specifics

The main developer is experienced overall, **but weak in JavaScript**. Explain JS terms in plain language. Architecturally avoid heavy client-side JS.

## Things we deliberately do NOT do

- ❌ AI auto-completion of homework (rejected for ethical / business reasons).
- ❌ Show grades.
- ❌ Parse МЭШ in MVP (only authedu.mosreg.ru).
- ❌ Use React/Vue/Svelte for the frontend.
- ❌ Store users' diary passwords (only session tokens, encrypted).

## After meaningful work

- Update `PROGRESS.md` (what's done, what's next).
- For important architectural decisions — update or create a project memory file in `~/.claude/projects/c--www-Yaroslav-SchoolProject/memory/`.
- After each completed chunk — push to `origin master`.
