# SchoolTodo — Progress tracker

**Purpose of this file:** session-spanning progress tracker. When the context window resets or a new session starts, Claude should read this file and `claude.md` first to understand where we left off.

---

## Status as of 2026-05-02

**Current phase:** infrastructure clarification before executing Plan 1.

**Done:**
- ✅ Idea trimmed to a sane scope (no AI homework auto-completion).
- ✅ Platform decision: web first → Telegram bot → MAX.
- ✅ Monetization decision: child free; parent pays for parent dashboard (~199-299₽/mo, post-MVP).
- ✅ Diary scope decision: first source is Школьный портал МО (authedu.mosreg.ru); МЭШ added later. DiarySource abstraction from day one.
- ✅ Tech stack chosen: Python 3.12 + FastAPI + Jinja2 + HTMX + Alpine.js + Tailwind CSS + PostgreSQL + Dramatiq + Redis.
- ✅ Hosting plan: Russian provider (Selectel/Timeweb), Roskomnadzor PD-operator registration before public launch.
- ✅ Design document written: `docs/superpowers/specs/2026-05-02-school-todo-design.md` (still in Russian — will be migrated lazily; least-loaded doc).
- ✅ Plan 1 (Foundation + Auth) written **but in Russian and assumes Docker Postgres** — will be rewritten in English using user's external Postgres server.
- ✅ Git remote configured: `origin → https://github.com/SwairIt/SchoolProject.git`.
- ✅ `.gitignore` in place protecting `.env` (which holds the GitHub PAT).
- ✅ Memory updated to English; `claude.md` and this file translated.

**In progress:**
- 🟡 Waiting for user to confirm Postgres connection details and Docker availability so Plan 1 can be rewritten.

**Next:**
- ⏳ User answers the open questions (Postgres connection string, Docker availability, Mailhog vs alternative).
- ⏳ Rewrite Plan 1 in English with the user's actual infrastructure (no Docker Postgres assumption).
- ⏳ Execute Plan 1 in chunks, pushing to `origin master` at the end of each chunk.
- ⏳ Then write and execute Plan 2 (DiarySource + sync), Plan 3 (UI + gamification), Plan 4 (deploy + privacy + RKN).

---

## Key decisions (with rationale)

| Decision | Date | Why |
|---|---|---|
| Reject AI homework auto-completion | 2026-05-02 | Broken business model, legal risk, free alternatives |
| Web app as the first platform | 2026-05-02 | Lowest entry barrier, any device |
| Monetize via parent dashboard | 2026-05-02 | Parent is the actual paying customer, not the child |
| First diary source: authedu.mosreg.ru | 2026-05-02 | User's own school is on this system → he'll be dogfood user |
| DiarySource abstraction in MVP | 2026-05-02 | Cheap to add new diaries later vs. an expensive refactor |
| Python + FastAPI + HTMX | 2026-05-02 | User's strength is Python; HTMX avoids React (user weak in JS) |
| Russian hosting | 2026-05-02 | 152-FZ requires localization of Russian citizens' personal data |
| Manual token paste in MVP | 2026-05-02 | Simple and reliable; browser extension auth-helper comes after MVP |
| Parent dashboard after MVP | 2026-05-02 | Without live users there's no one to test the parent flow |
| Push directly to master | 2026-05-02 | Solo project, no PR overhead |
| Internal docs in English | 2026-05-02 | Token efficiency (Cyrillic ≈ 2-3× cost of ASCII) |
| Use user's external Postgres (no Docker for DB) | 2026-05-02 | User already has a Postgres server, no point running a second one in Docker |

---

## Open questions for user (blocking Plan 1 rewrite)

- 🔴 **Postgres connection string** for the user's server (host, port, user, password, db name). User said it exists but didn't put credentials in `.env` yet.
- 🔴 **Is Docker installed?** Affects how we run Mailhog (for email testing) and Redis (Plan 2 onward).
- 🔴 **Email-test approach** if no Docker: stub SMTP in tests, real SMTP, or run Mailhog binary natively?

---

## Things to verify experimentally during implementation

- 🔬 Exact auth scheme of the authedu.mosreg.ru API.
- 🔬 Session token lifetime.
- 🔬 Diary API rate limits.
- 🔬 Shape of `homework` and `schedule` API responses.

These are resolved during MosregSource implementation (Plan 2). Not blocking now.

---

## Session log

### 2026-05-02 — session 1
- Brainstormed the idea.
- Cut the AI homework feature.
- Agreed MVP scope, tech stack, monetization.
- Wrote the design document.
- Clarified RKN: PD-operator registration is required only before public launch, not before development.
- Added "UX & visual design" section + gamification (basic in MVP, advanced in phase 1.5).
- Wrote Plan 1 (Foundation + Auth) in Russian assuming dockerized Postgres.

### 2026-05-02 — session 2 (still ongoing)
- User chose subagent-driven execution mode.
- User added GitHub PAT to `.env`, requested push-to-master workflow on `https://github.com/SwairIt/SchoolProject.git`.
- User has external Postgres server — Plan 1 needs rewriting (no Docker Postgres).
- User requested all internal documentation in English to save tokens.
- Set up `origin` remote, created `.gitignore` protecting `.env`, translated memory + `claude.md` + this file to English.
- Plan 1 rewrite blocked on user answering Postgres + Docker questions.
