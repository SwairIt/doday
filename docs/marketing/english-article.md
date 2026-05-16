# English article for dev.to / Medium / Hashnode

A ~700-word version of the Habr piece, tuned for English dev audience.

**Publish to:**
- **dev.to** — best fit (engaged developer audience, no algorithmic suppression)
- **Medium** — cross-post via canonical URL pointing to dev.to
- **Hashnode** — same canonical URL, gets some traffic

**Cover image:** [`/habr-cover.png`](../../habr-cover.png) works as-is.

**Tags (dev.to limits to 4):** `python`, `webdev`, `showdev`, `opensource`

---

## Title options

```
I'm 15 and I built a Telegram Mini App todo in 10 days
```
```
Building a real todo app with FastAPI + HTMX in 10 days (at age 15)
```
```
What I learned shipping a Telegram Mini App as a 15-year-old in 2 weeks
```

The first one has the cleanest hook. Pick it.

---

## Body

> _**TL;DR:** 15 years old. 10 days. Shipped a todo app with a web client, a Telegram Mini App, and a bot. FastAPI + HTMX + Alpine + Tailwind — zero React, zero JS build. 350 commits, 40k LOC, 650 tests, all green. Open source ([github.com/SwairIt/doday](https://github.com/SwairIt/doday)), free, live at [getdoday.ru](https://getdoday.ru). Here's what I learned._

I'm Yaroslav, a 9th-grader from outside Moscow.

I started [Doday](https://getdoday.ru) on May 2nd. The trigger was banal — our school uses an electronic homework portal whose UX is so bad that finding what's assigned for physics tomorrow takes three clicks and two spinners. I tried Todoist; Premium costs 229₽/month (~$2.50), Free cuts half the features. I thought "I'll just write my own". Two weeks later it's three things sharing one backend.

## What's in it

**Web app.** Tasks with priorities, due dates, recurrence (`daily`/`weekly`/`monthly`/`yearly`), subtasks, projects with sections, labels, search, Pomodoro timer with sessions persisted to Postgres, basic stats (streak, completed/day, by-project).

**Telegram Mini App.** Full feature parity in a native-feeling bottom-sheet UI. Swipe a task left for "tomorrow", right for "done" (with confetti). Drag-to-reorder. Long-press for quick actions. Light/dark/system theme that syncs with Telegram's chrome bar via `setHeaderColor` / `setBackgroundColor`. Pomodoro mini-widget that floats over the list.

**Bot.** Entry point for the Mini App, plus `/add buy milk tomorrow !!!` for quick add, `/today`, `/upcoming`, `/done`, and a 9:00 MSK morning digest email.

**Shared projects** in Todoist style — invite by email, owner/member roles, task assignment. Comments on tasks and subtasks.

100% free, no ads, no subscriptions yet. Early users will be grandfathered onto Pro forever when paid plans return.

## The stack: zero React

I learn JavaScript slower than Python. Picking React for a 2-week sprint when I needed to ship would have been brain-freeze. So the stack was chosen for "**max features at min JS pain**":

| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI 0.115 + async SQLAlchemy 2.0 + Pydantic v2 | Types everywhere, `mypy --strict` green, OpenAPI free |
| DB | PostgreSQL 16 (asyncpg) + Alembic | Production-grade, not SQLite |
| Templates | Jinja2 (server-side) | No hydration, fast first paint |
| Interactivity | HTMX 2 | SPA feel, no JSON API, no bundle |
| Micro-state | Alpine.js | `x-data`, `x-show`, `x-model` — inline JS without files |
| Styles | Tailwind CDN | **No build process at all** |
| Auth | argon2-cffi + signed session cookies | Standard, secure, no JWT confusion |
| Dev | uv, ruff, mypy --strict, pre-commit | Strictest possible Python on every commit |
| Deploy | `git push` → cron-poll on VPS → 60s live | No Kubernetes, no Docker, no CI/CD-from-hell |

**HTMX was a shock.** I tried it as a meme — switched a couple of polling-based widgets to `hx-get` + `hx-swap`, got a faster UI than React apps I'd seen, just from skipping JSON serialization + virtual DOM diffing + JS parsing.

## Grabli I'm sharing because nobody else has

### 1. `themeParams` from Telegram ruins your palette

The Telegram WebApp SDK exposes `themeParams` — your user's theme colors. Logical to apply them so your Mini App looks "native". **It's a trap.** If your user is on Telegram's light theme, you get `bg_color: #ffffff`. All your `rgba(255,255,255,0.06)` shimmer overlays, your `text-violet-400 bg-violet-500/15` chips, your `rgba(255,255,255,0.08)` borders — designed for dark backgrounds — render as soup on white.

Fix: ignore `themeParams`. Ship a fixed dark default (later: explicit user toggle for dark/light/system), and **push your color back into Telegram** via `setHeaderColor` / `setBackgroundColor` / `setBottomBarColor` so the chrome bar atop your Mini App matches your palette too.

### 2. `api.telegram.org` over IPv6 = dead bot on a VPS

`systemd-resolved` on my host returns only `AAAA` (IPv6) for `api.telegram.org`. The provider's IPv6 routing to Telegram is broken. httpx (inside python-telegram-bot) honors the IPv6 result, hangs 30s on connect, polling silently dies. `curl --resolve api.telegram.org:443:149.154.167.220 https://...` works fine because it skips DNS.

Worse: Telegram has 3 A-records. My provider only routes to **one** of them (`149.154.167.220`). The other two return `SYN-SENT` indefinitely.

Fix: monkey-patch `socket.getaddrinfo` AND `asyncio.base_events.BaseEventLoop.getaddrinfo` to return a single hardcoded IP for `api.telegram.org`. No sudo means no `/etc/hosts` edit; this is the next best thing.

### 3. `application.post_init = callback` is silently a no-op in PTB v21

I set `application.post_init = my_callback` (attribute assignment after `.build()`). It never ran. No warning, no error. The correct way is `Application.builder().token(...).post_init(my_callback).build()`. Lost an hour to that.

## About the AI

I wrote it in a pair with [Claude Code](https://claude.com/claude-code), and I'm transparent about that. Without AI a 15-year-old doesn't ship 40k LOC in 2 weeks. With AI plus a person who reviews every diff, who decides every architecture question, who hunts every bug — you can.

What I do, not the AI:
- Decide what to build, in what order, with what stack
- Read every diff before merging
- Find the bugs (the 6-hour `api.telegram.org` saga was me reading `ss -tnp`, not the AI)
- Maintain the test suite
- Talk to users

What the AI does:
- Type the boilerplate
- Suggest implementations I review

I can open any file in this repo and explain in a minute what it does and why. If I can't — that's where the AI ends and I haven't started yet. That's the test.

## Numbers

- **10 days** of writing
- **350+ commits** on master
- **~40,000 LOC** total (16k Python in `app/`, 14k Jinja, 9k tests)
- **650 tests**, green on every push, CI on GitHub Actions
- **38 modules** in `app/`
- **Deploy ~60 seconds** after `git push`
- **`mypy --strict`** + **`ruff` with `E,F,I,UP,B,S,A,RUF`** + Jinja linter — enforced via pre-commit

## What's next

- Make the bot work via webhook (current polling is fragile on this host)
- Translate UI to English for broader audience
- More integrations once I have a way to accept payments (I'm 15 — no business entity yet)

If any of this is interesting to you, the code is at [github.com/SwairIt/doday](https://github.com/SwairIt/doday). Issues and PRs welcome.

Thanks for reading.

---

## After publishing

- Add a comment on dev.to linking to the Habr Russian version
- Cross-post via Medium with `<link rel="canonical" href="...">` to dev.to
- Pin the article on your dev.to profile

## Expected outcome

dev.to with #showdev tag typically: ~300-2000 views in first week, ~5-20 followers, ~1-5 GitHub stars. Not massive but durable — articles stay discoverable for months.
