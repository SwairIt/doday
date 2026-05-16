# Show HN post

**Submit URL:** https://news.ycombinator.com/submit

**Best time to post:** Tuesday-Thursday, 8:00 AM EST (17:00 МСК)

---

## Title (≤ 80 chars, mandatory `Show HN:` prefix)

```
Show HN: Doday – Telegram Mini App todo built in 10 days at age 15
```

**Alternative titles** if first doesn't land:

```
Show HN: I'm 15 and built a Telegram-native todo with FastAPI + HTMX
```
```
Show HN: A todo app that lives inside Telegram (no React, no build step)
```

Pick the first — it has all 3 hooks (Telegram Mini App + 10 days + 15 years).

## URL field

```
https://getdoday.ru
```

If your `/` page redirects logged-out users somewhere awkward — link to the GitHub README instead:
```
https://github.com/SwairIt/doday
```

## Body text (first comment, post yourself within 1 minute of submit)

```
Hi HN. I'm Yaroslav, 15, from Russia. Started writing Doday on May 2 — today
is two weeks later and it's running in production at getdoday.ru.

It's a to-do app with three surfaces sharing one FastAPI backend:
- Web app (HTMX + Alpine + Tailwind, no React, no JS build step)
- Telegram Mini App (full feature parity in a native-feeling bottom-sheet UI)
- Telegram bot (entry point: /start opens the Mini App)

What I built in 2 weeks (350+ commits, ~40k LOC, 650 tests, mypy --strict):
- Tasks with priority, due dates, recurrence, subtasks, labels
- Projects with sections, drag-to-reorder, kanban
- Pomodoro timer (sessions persisted in DB)
- Comments on tasks (works in web and Mini App)
- **Shared projects** in Todoist style — invite by email, owner/member roles,
  task assignment to teammates
- Light/dark/system theme toggle
- Daily morning digest email + per-task reminders

Authorization model that I'm slightly proud of: every router calls 3 service
functions — `get_project`, `get_task`, `get_section`. When I added sharing
in Phase δ, I wired the membership check into those 3 functions instead of
patching 40 routers. Final security review found 0 data leaks.

Tech stack:
- FastAPI 0.115 + async SQLAlchemy 2.0 + Pydantic v2
- PostgreSQL 16 (asyncpg) + Alembic
- HTMX 2 + Alpine.js + Tailwind CDN
- argon2 + signed session cookies
- python-telegram-bot v21 for the Mini App WebApp SDK integration
- structlog (JSON) + Sentry + Yandex Metrika

Deploy is `git push` → live in ~60s (cron polls origin/master on the VPS,
runs alembic upgrade, restarts uvicorn).

About the AI angle: I wrote it in a pair with Claude Code, and I'm
transparent about that. I made every architectural decision myself,
reviewed every diff, debugged every grabli — but the typing was paired.
Without AI a 15-year-old wouldn't ship 40k LOC in 2 weeks. With AI plus
human review, you can. I'd rather be honest about it than pretend.

A longer write-up (in Russian, with grabli — including 6 hours of debugging
why my bot couldn't reach api.telegram.org through my hosting provider's
firewall) is on Habr: https://habr.com/ru/articles/<id>

Code is MIT-licensed: https://github.com/SwairIt/doday

The UI is currently Russian-only. If anyone hits open source contribution
appetite for an English translation — pull requests welcome.

Happy to answer questions about anything: the stack, the deploy model, the
authorization layer, the AI workflow, growing up writing software, school
software in Russia, anything.
```

## Tips for HN specifically

- **Subscribe to your own thread.** HN doesn't notify — refresh manually first 30 min.
- **Respond to every top-level comment within first hour.** HN algorithm boosts active threads.
- **Don't argue.** If someone says "FastAPI is bad" — say "tell me why" not "you're wrong".
- **Don't ask for upvotes anywhere.** HN bans for this immediately.
- **If the post stalls at <10 points in first 2 hours** — don't repost the same day. Wait 48 hours, try a different angle.
- **Watch for second-chance pool** — HN sometimes resurfaces good posts that didn't catch first time, ~24h after submit.

## Expected outcome

If post lands on HN front page (top 30):
- **~5k-50k visitors to getdoday.ru** within 24h
- **~50-500 GitHub stars** within 48h
- **~10-50 sign-ups** if site doesn't fall over
- ~3-5 thoughtful technical comments worth reading

If it stalls at <5 points — that's fine, try Lobste.rs in a week with different framing.
