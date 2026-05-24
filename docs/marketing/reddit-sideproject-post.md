# I'm 16 and I built a todo app with Telegram Stars payments — only legal way for me to monetize before turning 18

---

Hey r/SideProject,

So this is a weird story and I wanted to share it. Stick with me, the payment-processor part is genuinely funny.

I'm 16, live in Russia, and over the past 6 months I built **Doday** — a todo app that runs as a web app, a Telegram Mini App, and a Telegram bot, all sharing one backend. Basically a Todoist alternative with Pomodoro built in, kanban boards, school portal sync (for Russian students — this is the moat tbh), and team collaboration.

You can try it here: **[getdoday.ru](https://getdoday.ru)** · code: **[github.com/SwairIt/doday](https://github.com/SwairIt/doday)** · bot: **[@DodayTaskBot](https://t.me/DodayTaskBot)**

I want to talk about the monetization part because I think it might be useful for other minors who are trying to ship products.

## The problem

I'd been building Doday since May. By the time I wanted to add paid plans, the app already had 500+ users (mostly friends and people from my school plus a few random folks). I was running on `BETA_FREE_FOR_ALL=true` env flag, meaning everyone got Pro features for free. This was sustainable for a while but I wanted to actually validate that people would pay for the thing.

Plan was simple: register a Russian payment processor (YooKassa, formerly Yandex Kassa — pretty much the local Stripe equivalent), implement their checkout, done.

I'm registered as "self-employed" (самозанятый — a tax regime in Russia available from 14 with parental consent), so I have a tax ID and a real bank account. I figured this was enough.

## Three rejections in two days

**YooKassa** — login via gov-ID (Госуслуги, our equivalent of e-gov / single sign-on for government services). Instant rejection: *"Users with a child account on Госуслуги cannot sign in."* My Госуслуги account is **fully verified** — I pay taxes through it, do everything an adult does. But YooKassa checks date of birth and if you're under 18, no appeal. Hard wall.

OK, **manual entry**. I open the manual form — they want a scanned color passport upload. Their OCR reads the date of birth and rejects it. I tried with strategically blurred dates — got "could not verify identity" after an hour. Same wall.

OK, **T-Bank acquiring** (another major Russian processor). Sign-up flow gets to "you need to be a registered IP (individual entrepreneur) or LLC". Self-employed is allowed but only from 18+. To register as IP you also need to be 18 (16 with parental consent and notarized statement, but banks don't accept these for acquiring).

OK, **register under a parent's name**. Now the money legally belongs to them. If there's a dispute with a customer, my parent has to argue it. The tax office considers the income theirs. If they decide they don't want to be involved tomorrow, I lose my entire payment infrastructure overnight. Not happening.

OK, **wait until 18**. That's 18 more months. I can't justify investing that much more time into a product without seeing some financial validation.

I was honestly about to give up on monetization. Then I remembered Telegram Stars existed.

## Telegram Stars (XTR)

If you don't know — Telegram has its own in-app currency called Stars (currency code `XTR` in their Bot API). Users buy them through the Telegram client (Apple/Google in-app purchase). Bots can accept payments in Stars via `createInvoiceLink`. Developers get ~70% of Stars value, withdraw through TON crypto or via Fragment.

Key thing: **`@BotFather` is available from age 13**. No documents. No tax IDs. No banks. Your contract is with Telegram, not with a bank.

For me at 16, this is the only legitimate payment path that exists.

I sat down and wrote it.

## What I built (technical)

- **Schema migration** (`alembic 0039`): `users.pro_until` (timestamp), `star_payments` table with `UNIQUE(telegram_payment_charge_id)` for idempotency
- **Product catalog** (`app/billing/products.py`) — single source of truth for pricing. Pro 1m = 250⭐, Pro 12m = 2500⭐, Pro Lifetime = 12500⭐. Edit this file, that's it.
- **HMAC-signed invoice payloads** — `v1:{product}:{user_id_hex}:{nonce}:{sig}`. Without this, anyone could intercept the invoice URL and swap the product code to "pro_forever" before paying. With it, the signature breaks and Bot API rejects. Payload ≤80 bytes (Telegram cap is 128).
- **Idempotent payment application** — Telegram retries webhook on failure. I insert into `star_payments` with `UNIQUE` on charge_id; second insert raises `IntegrityError` → I catch and return existing row. No double-credit ever.
- **`effective_tier()` honors `pro_until`** — paid users with expired `pro_until` auto-revert to free with zero cron jobs. Lazy eval on every request. Lifetime purchases set `pro_until` to year 2099 as a sentinel.
- **Renewal extends from existing `pro_until`** — buying Pro 1 month when you still have 10 days left doesn't reset to 30 days. It extends to `current_pro_until + 30 days`. (Todoist does this wrong, FYI.)
- **Refund flow** — admin endpoint calls `refundStarPayment` Bot API + rolls back `pro_until`. Telegram allows refunds within 21 days.
- **Bot handlers** — `PreCheckoutQueryHandler` (must answer in 10 sec, verifies signature + amount), `MessageHandler(filters.SUCCESSFUL_PAYMENT)` (calls apply_successful_payment).

Tests: 24 unit tests covering signing, tampering rejection, amount mismatch, idempotency, renewal math, lifetime sentinel, expired→free fallback.

The Mini App UI uses `Telegram.WebApp.openInvoice(url, callback)` for in-app payment. The web UI opens the invoice URL in a new tab as a fallback for desktop.

I also closed a security hole I'd been sitting on — `POST /api/billing/change-tier` used to let any authenticated user upgrade themselves to Pro for free by POSTing `{"tier": "pro"}`. Closed it the same day I shipped Stars: upgrades now require 402 Payment Required, only downgrade to free is self-service.

## The stack (in case you care)

- FastAPI 0.115 + async SQLAlchemy 2.0 + Pydantic v2
- PostgreSQL 16 (asyncpg)
- Jinja2 + HTMX + Alpine.js + Tailwind via CDN — no React, no build step
- python-telegram-bot v21 for the bot worker
- `mypy --strict` enforced via pre-commit on every commit
- ~20k lines of Python, 850+ pytest tests, 39 Alembic migrations
- One-line deploy: `git push` → cron-poll on prod VPS pulls every minute, applies migrations, restarts uvicorn. Live in ~60 seconds.

## About using Claude Code

I wrote Doday in pair with Claude Code (Anthropic's AI coding assistant). I'm not hiding it — the architecture decisions are mine but Claude was a fast typist with good memory of the codebase. Every commit was reviewed before push. Lines I didn't understand got rewritten until I could explain them out loud.

The reason the codebase doesn't smell like AI slop is the rails: `mypy --strict` fails the build on type errors, every behavior change ships with a test, the Jinja linter catches bad Alpine patterns Claude tends to generate. With those guardrails, an AI assistant is just a fast pair-programmer.

Whether you consider that "real" coding depends on your definition. I think it does. I wouldn't have shipped this much in 6 months alone, but I also wouldn't have shipped it well without the taste for architecture and review.

## Honest stats

- First commit: May 2nd, 2026
- Total commits: 511
- Tests: 850
- ~20k lines of Python
- Active users: small, mostly from my school + friends-of-friends. I haven't really tried marketing yet — this Reddit post is one of the first attempts.
- Paying users: 0 — Stars literally went live yesterday
- Revenue so far: $0 (haven't asked anyone to pay yet)
- Roadmap: parent dashboard for Family tier, public API tokens, native iOS via Capacitor wrapping the Mini App

## What I'm asking

If you got curious, the live demo is at [getdoday.ru](https://getdoday.ru) — UI is Russian but English-readers can navigate with browser translation. The codebase on [github.com/SwairIt/doday](https://github.com/SwairIt/doday) is more interesting if you want to see how all the pieces fit (Mini App auth, Stars payment flow, team sharing, opt-in feature flags).

If you have feedback on the architecture, the payment flow, or you've also dealt with the "underage and trying to ship a SaaS" problem — I'd love to hear it.

If you've shipped your own Stars integration — there's one part I'm uncertain about: I'm currently keeping `provider_payment_charge_id` as nullable because I'm not sure when Telegram actually populates it. Anyone know?

And if you star the repo — it genuinely helps. I'm not running this for fun, I'd love to make a living from it eventually.

Cheers from a 16-year-old in Russia,
Yaroslav

---

**Edit:** if you're wondering why a Russian teenager is posting on Reddit — Doday is open source MIT and I want it to grow beyond Russian users. The codebase is English (docstrings, variable names, commit messages aside — those are Russian past-tense), so contributions are welcome. The Telegram Stars integration in particular is generic — works for anyone selling anything to anyone with Telegram.
