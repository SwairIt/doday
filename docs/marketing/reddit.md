# Reddit posts — 3 разных угла для 3 subreddit'ов

Не публикуй одно и то же. Reddit любит когда пост подогнан под subreddit. Распредели на 3 дня (не все в один — алгоритм флагнет как спам).

**Best time:** Tue-Thu, 8-11 AM EST (17:00-20:00 МСК).

**Reddit account:** если новый — поспам положительно в комментах перед своим постом (несколько дней). Иначе пост уйдёт в shadow-ban с -1 karma account'а.

---

## 1) r/SideProject — день +1

**Subreddit:** https://www.reddit.com/r/SideProject/
**Тон:** indie, support, без снобства. Любят полные истории.
**Title:**

```
I'm 15 and I shipped a Telegram Mini App todo in 10 days [open source]
```

**Body:**

```
Hi all. I'm Yaroslav from outside Moscow.

I started this on May 2nd because Todoist's free plan was too limited and
their Premium costs more than I have. Two weeks later I have a working
product: getdoday.ru.

It's three surfaces sharing one FastAPI backend:
- Web app
- Telegram Mini App (the bottom-sheet UI inside Telegram chats)
- Telegram bot (quick-add via /add, morning digest)

Features: tasks with priority/due/recurrence/subtasks, projects, sections,
labels, Pomodoro timer, comments, shared projects in Todoist style (invite by
email → join → both edit), task assignment to teammates, light/dark theme.

Tech: FastAPI + HTMX + Alpine + Tailwind CDN. Zero React. Zero JS build step.
Postgres + Alembic. 650 tests, mypy strict, runs on a $5 VPS.

Numbers: 350+ commits, ~40k LOC, deploy is `git push` → live in 60s via a
cron-poll on the VPS.

Code is MIT-licensed: github.com/SwairIt/doday

About the AI: I built it paired with Claude Code. Architecture, every
decision, every bug hunt — me. Typing — Claude. I review every diff. Tried
to be honest about this from the start.

What I'm proudest of: the permission model for shared projects went into
3 service functions (get_project, get_task, get_section), not 40 routers.
Final security review found 0 leaks. As a 15-year-old getting that right
first try felt great.

What I'd love feedback on:
- The Mini App UX in particular — try it via @DodayTaskBot, would love to
  hear what feels weird
- README / project structure if you have OSS taste
- Anyone shipped a Telegram Mini App? Curious about your launch grabli

Demo GIF in the README.

Cheers!
```

**After posting:**
- Reply to every comment within first 2 hours
- Don't ask for upvotes (instant -karma)
- If post stalls — fine, try r/InternetIsBeautiful with a different angle later

---

## 2) r/selfhosted — день +2

**Subreddit:** https://www.reddit.com/r/selfhosted/
**Тон:** practical, минимализм, любят open-source + low-resource.
**Title:**

```
[Self-Hosted] Doday — Telegram-native todo (FastAPI + HTMX, single-process, MIT)
```

**Body:**

```
Open-source todo with a Telegram Mini App, designed to self-host on a small VPS.

GitHub: github.com/SwairIt/doday  
Live (my hosted version): getdoday.ru

Why someone here might care:
- **Single process** — one uvicorn + one Postgres. No Redis, no Celery, no
  Docker required. Runs comfortably on a $5/mo VPS (current prod is uvicorn
  + 2 workers + PG16 on one tiny host).
- **Mini App** — opens inside Telegram, so users on mobile don't need to
  install a native app. Web works as a separate surface for desktop.
- **No JS build step.** HTMX + Alpine + Tailwind CDN. Setup = `uv sync` +
  `alembic upgrade head` + run uvicorn.
- **Real auth + sharing** — argon2 password hashing, signed-cookie sessions,
  shared projects with email invites, owner/member roles.
- **MIT license** — fork at will.

Stack: FastAPI 0.115, async SQLAlchemy 2.0, asyncpg, Pydantic v2,
python-telegram-bot v21.

Limitations to be aware of:
- UI is Russian only right now. Translation contributors welcome.
- Telegram bot polling can be flaky behind some hosting providers' firewalls
  (e.g. mine routes only 1 of 3 api.telegram.org IPs); README has notes.
- The Mini App relies on Telegram's WebApp SDK. If your users don't have
  Telegram, web works standalone but obviously you lose the mobile-native
  feel.

Setup time on a fresh Ubuntu 22.04 VPS: ~15 minutes (Postgres + uv +
clone + .env + migrate + nginx).

I'm the author, 15, building this in my free time. Happy to answer self-host
questions if you try it.
```

---

## 3) r/programming — день +5-7 (другой угол: HTMX manifesto)

**Subreddit:** https://www.reddit.com/r/programming/
**Тон:** тех-снобы. Любят анти-холивары. Поход: provoke в комментах, не в посте.
**Title:**

```
Building a SPA-feel todo app without React: 10 days, 0 JS bundle, 40k LOC
```

**Body:**

```
A practical write-up: built a todo app over 2 weeks using FastAPI + HTMX +
Alpine + Tailwind CDN — no React, no bundler, no node_modules. Want to
share the architecture, the grabli, and what wasn't worth the trade.

Site: getdoday.ru (Russian UI)
Code: github.com/SwairIt/doday (MIT)
Full write-up on Habr (Russian): habr.com/ru/articles/<id>

The interesting parts (for r/programming taste):

**Stack choice was constrained**. I'm 15 and I learn JS slower than Python.
Picking React for a 2-week sprint that needed to ship was a non-starter. So
the stack was chosen for "max feature density per JS line written":
FastAPI for backend, Jinja templates for first paint, HTMX for partial
updates, Alpine for the 30 lines of in-page state.

**HTMX surprised me**. I tried it as a meme — replaced a few polling
widgets with `hx-get` / `hx-swap`, got SPA-feel without JSON serialization,
virtual DOM diffing, or JS parsing overhead. On mobile in particular it
feels snappier than React apps I've built. Whether it scales to "real"
apps is the open question; I'll find out.

**Authorization is centrally enforced**. When I added shared projects in
the final phase, I didn't want to patch 40 routers. The fix: the membership
check went into 3 service functions (`get_project`, `get_task`,
`get_section`). Every router already called those — they automatically
inherit the new gate. Security review found 0 leaks.

**Deploy is `git push`**. A cron job on the VPS polls origin/master every
60 seconds. If HEAD differs: git reset + alembic upgrade + restart uvicorn.
No Kubernetes. No Docker. No CI/CD-from-hell. 60-second deploy.

**Tooling**: `mypy --strict`, `ruff` with `E,F,I,UP,B,S,A,RUF`, Jinja linter,
all enforced via `pre-commit`. 650 tests, green on every push. The strictest
Python setup I've seen on a side project.

The things that DIDN'T work:
- Bot polling on this hosting provider: their firewall routes 1 of 3
  api.telegram.org IPs. Took 6 hours to debug — `ss -tnp` showed
  `SYN-SENT` indefinitely. Workaround: monkey-patch resolver.
- Telegram's `themeParams` for the Mini App were a trap. Light theme on
  the user's side broke my dark-only palette. Now I ship a fixed default
  and let users toggle.

About AI: yes, paired with Claude Code. Architecture and reviews were me.
Typing was Claude. Without AI a 15-year-old doesn't ship 40k LOC in 2
weeks. With AI plus a person who reviews every diff, you can. I'm honest
about this because it's the obvious question.

Curious what r/programming thinks of HTMX in 2026 — fad or
back-to-basics?
```

**Каждый пост — wait 24-48h between** to avoid Reddit's "duplicate detection" hammer.

## Что делать в комментах

- **Отвечай в течение 1 часа** на первые 5-10 комментов
- **На критику стека** — благодарность + честный ответ ("yes I know X has Y problems, here's why I chose it anyway")
- **На "you're using AI"** — спокойно объясни (как в HN-постe)
- **На "show numbers"** — конкретные цифры из README

## Если стрельнёт

- ~10k+ visitors / day = серверу будет жарко. Проверь что `uvicorn --workers 4` (сейчас вроде 2)
- Sentry будет ловить незнакомые баги — будь готов фиксить hotfix'ы быстро
