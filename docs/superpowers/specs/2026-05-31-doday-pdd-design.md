# Doday ПДД — design spec

> Status: approved 2026-05-31. Author: Opus (autonomous session).
> Sibling specs: `2026-05-28-doday-qa-design.md` (Razbery — the pattern this reuses).

## 1. Why this product

The user asked for a **new** Doday Studio product that "will definitely make money
and won't shut down." A multi-lens ideation + adversarial workflow surfaced two
structural traps that kill most monetizable ideas under this user's constraints:

1. **Holding third-party money** = unlicensed payment intermediation. The Stars
   billing module is physically *single-merchant* (`app/billing/stars.py`:
   payments land on Doday's own bot balance and grant a tier to the **payer**).
   Any marketplace / creator-payout idea is therefore both illegal (minor
   самозанятый) and unbuildable. This kills the whole take-rate / creator-rails
   space.
2. **Telegram Stars ToS** forbids paying for offline/real-world services and
   competes with native platform features.

The only durable, legal shape is: **Doday is the sole merchant, selling its own
digital feature/content to the end user, paid in Stars.** That is exactly
Razbery's winning formula (free indexable SEO content as the growth engine +
a Pro layer of personal-prep tooling). **Doday ПДД applies that proven pattern
to a new evergreen vertical that does not overlap Razbery**: official Russian
driving-exam tickets (билеты ПДД).

### Why ПДД is durable

- **Evergreen + mandatory + recurring demand**: every new driver, every year a
  fresh cohort, categories А/В/М. The official ticket set updates yearly → each
  update is *more* indexable content, lowering acquisition cost over time.
- **Proven willingness to pay**: paid ПДД prep apps are an established RU
  category — unlike "pay to bookmark Q&A," demand for paid driving-test prep is
  market-validated.
- **SEO moat**: hundreds of pages each answering a real evergreen query
  ("разрешён ли обгон на перекрёстке", "что означает знак ..."). Ranks for years
  on Yandex/Google without paid ads.
- **Single-merchant + no UGC**: no third-party money, no moderation/152-ФЗ risk,
  no licensing. Solo-operable.
- **Not a duplicate**: Razbery = school-subject Q&A for kids 5–11; ПДД = adults
  getting a driving licence. Different audience, content type, and intent. The
  only shared DNA is "Doday helps you learn," which is the brand thesis.

## 2. Scope (decided)

- **URL namespace**: `getdoday.ru/pdd/`. No new bot — Stars invoices route through
  the existing `@DodayTaskBot` (pdd product codes do not start with `tutor_pro_`,
  so `_bot_token_for_product` already routes them to the main bot).
- **Content**: official **category АВМ** ticket set — 40 tickets × 20 questions
  ≈ 800 questions, **with images** (road-situation illustrations, signs). Public
  official material; a "по официальным билетам ГИБДД" disclaimer is shown.
- **Free vs Pro boundary** (the SEO motor stays fully open):
  - **Free, no login, indexable**: browse every ticket, every question, with the
    correct answer + official explanation; practice any ticket / any topic as an
    interactive quiz (unlimited); run the **official-rules exam simulator**
    (random 20, 20-min timer, ≤2 mistakes else +5 questions) — *ephemeral*, the
    run is scored on screen but not saved, no cross-session stats.
  - **Free, logged-in**: attempts are persisted → a basic mistakes list on
    `/pdd/my`.
  - **Pro (`pdd_pro` entitlement)** adds the *personal data/analytics layer*:
    **saved exam history**, **progress statistics dashboard**, the adaptive
    **mistake trainer** (spaced-repetition-lite over your wrong answers), and a
    **PDF "your weak topics"** export. The free simulator is generous on purpose
    (engagement + SEO); Pro sells the durable value of *your* progress over time.
- **Build budget**: 1–2 weeks, ideal architecture, no breakage of the existing
  ~850 Doday + ~234 Lessio tests.

## 3. Monetization architecture — standalone entitlement (Path 2)

The current model is a **single global** `user.tier` + `user.pro_until`; every
"pro" product (incl. Lessio) grants the same studio-wide `pro` tier. Folding ПДД
into that would (a) make any 250⭐ Doday Pro a backdoor to ПДД and entangle
pricing, (b) prevent independent ПДД economics. Instead ПДД Pro is a **standalone
entitlement**, added **additively** so existing products and tests are untouched.

### 3.1 New generic `Entitlement` model (`app/billing/models.py`)

```
Entitlement
  id            UUID PK
  user_id       FK users.id ON DELETE CASCADE, indexed
  feature       String(40)        # e.g. "pdd_pro" — generic for future verticals
  expires_at    DateTime(tz) NULL # NULL = lifetime
  source_code   String(50)        # product code that granted it (audit)
  created_at    DateTime(tz)
  updated_at    DateTime(tz)
  UNIQUE(user_id, feature)        # one row per user per feature; renewals extend
```

Generic on purpose: the next verticals (Экзамен, Собеседование) reuse the same
table with a different `feature` key. No per-product columns on `users`.

### 3.2 `Product` gains `grants_entitlement` (`app/billing/products.py`)

- `grants_tier` becomes `str | None`. When `None`, the payment-apply path does
  **not** touch `user.tier`/`user.pro_until`.
- New field `grants_entitlement: str | None = None`. When set, payment-apply
  upserts an `Entitlement` row, extending `expires_at` from
  `max(now, current expires_at)` by `duration_months` (lifetime when
  `duration_months is None`), mirroring the existing `pro_until` extension logic.
- **Existing products keep `grants_tier="pro"|"family"` and
  `grants_entitlement=None` → their apply behaviour is byte-for-byte identical.**

New ПДД products (in the same `PRODUCTS` tuple):

| code | title | duration_months | stars | grants_tier | grants_entitlement |
|---|---|---|---|---|---|
| `pdd_pro_1m` | ПДД Pro · 1 месяц | 1 | 199 | None | `pdd_pro` |
| `pdd_pro_3m` | ПДД Pro · до экзамена (3 мес) | 3 | 399 | None | `pdd_pro` |
| `pdd_pro_forever` | ПДД Pro · навсегда | None | 990 | None | `pdd_pro` |

`pdd_pro_3m` is the hero — a one-time, exam-window purchase that sidesteps Stars'
lack of web auto-renew (the churn cycle is the exam, not a month).

### 3.3 Payment-apply change (`app/billing/stars.py::apply_successful_payment`)

After the idempotent `StarPayment` insert, branch:

```
if product.grants_tier is not None:
    user.tier = product.grants_tier
    user.pro_until = <existing lifetime/extend logic>
if product.grants_entitlement is not None:
    upsert Entitlement(user_id, feature=product.grants_entitlement,
                       expires_at=<lifetime/extend>, source_code=product.code)
```

Refund path (`refund_payment`) symmetrically shrinks the entitlement and deletes
it when it lapses. `validate_pre_checkout` is unchanged (it only checks the
amount against the catalog). **No bot changes** — `on_pre_checkout_query` /
`on_successful_payment` are already product-agnostic.

### 3.4 Gating helpers (`app/billing/service.py`)

```
async def has_entitlement(session, user, feature) -> bool
    # True if beta_free_for_all, else an active (non-expired) Entitlement row.
```

`app/pdd/service.py` wraps it: `is_pdd_pro(session, user)` →
`has_entitlement(session, user, "pdd_pro")`. ПДД Pro is **independent** of the
global tier (Doday Pro does not auto-grant ПДД Pro — clean per-product economics).
`require_pdd_pro(...)` raises 402 for API routes, mirroring `require_pro`.

### 3.5 Catalog scoping

`GET /api/billing/products` (Doday Tasks pricing page) excludes `pdd_*` codes;
`ProductOut.grants_tier` becomes `str | None`. ПДД buys reuse the existing
`POST /api/billing/stars/invoice` with `product_code="pdd_pro_3m"` — no new
billing endpoint.

## 4. Content data model (`app/pdd/models.py`)

```
PddTopic                       # official thematic grouping → SEO + weak-topic analytics
  id PK, slug UNIQUE, title, position INT, description TEXT, seo_intro TEXT

PddTicket                      # the 40 АВМ exam tickets
  id PK, number INT UNIQUE (1..40), title (nullable)

PddQuestion
  id PK (UUID), public_slug UNIQUE,        # /pdd/vopros/{public_slug}
  ticket_id FK, position_in_ticket INT(1..20),
  topic_id FK,
  text TEXT, image_path String NULL,       # /static/pdd/img/...
  explanation TEXT,                        # official комментарий
  correct_position INT                     # 1-based index into PddOption.position

PddOption                      # normalized answer options (immutable seed content)
  id PK, question_id FK, position INT, text TEXT
  UNIQUE(question_id, position)
```

User-state (Pro analytics; logged-in only):

```
PddAttempt                     # event log powering trainer + stats
  id PK, user_id FK, question_id FK,
  chosen_position INT, is_correct BOOL,
  source String(12)            # "practice" | "exam" | "trainer"
  created_at DateTime(tz), indexed (user_id, question_id), (user_id, created_at)

PddExamSession                 # one official-rules simulator run
  id PK, user_id FK,
  started_at, finished_at NULL,
  question_ids JSONB,          # ordered set served this run
  total INT, mistakes INT, extra_added INT,
  status String(12)            # "in_progress" | "passed" | "failed" | "abandoned"
```

Weak topics + trainer queue are **derived** from `PddAttempt` aggregation (no
denormalized mistake table). Anonymous practice writes nothing.

## 5. Routes & templates

HTML router `router` (prefix `/pdd`), JSON router `api_router` (prefix
`/api/pdd`); both go through `app/pdd/service.py` (routers never touch the ORM
directly — same rule as qa). Templates under `app/templates/pdd/`, pages extend
a new `pdd/_base.html` (mirrors `qa/_base.html`: `title`/`description`/`canonical`
blocks, Tailwind CDN + Alpine + HTMX, shared header/footer).

| Path | Index? | Auth | Purpose |
|---|---|---|---|
| `/pdd/` | index | none | hub: intro, 40 tickets, topics, CTA |
| `/pdd/bilet/{n}` | index | none | all 20 Q of a ticket, answers+explanations, interactive |
| `/pdd/tema/{slug}` | index | none | all Q of a topic |
| `/pdd/vopros/{slug}` | index | none | single-question page — max SEO surface + JSON-LD |
| `/pdd/my` | noindex | login | dashboard: progress, mistakes, Pro CTA |
| `/pdd/trener` | noindex | Pro | adaptive mistake trainer |
| `/pdd/ekzamen` | noindex | free (ephemeral) / Pro (saved + stats) | official-rules simulator |
| `/pdd/pro` | index | none | Pro landing (what you get, Stars price) |
| `/pdd/sitemap.xml` | — | none | hub + tickets + topics + questions |

JSON (`/api/pdd`): `POST /attempt` (record), `POST /exam/start`,
`POST /exam/{id}/answer`, `POST /exam/{id}/finish`, `GET /trainer/next`,
`GET /pdf/weak-topics` (Pro, returns application/pdf).

Interactive practice: questions are fully present in server-rendered HTML (SEO);
Alpine handles client-side reveal/selection. Attempt persistence uses explicit
`fetch().then(...)` (per the htmx+Alpine dynamic-form gotcha), not lazy `hx-post`.

## 6. SEO

- `app/pdd/seo.py`: per-page title/description/canonical + JSON-LD. Question pages
  emit `schema.org/Question` (+ `acceptedAnswer`); ticket/topic pages emit
  `Quiz`/`ItemList`. Helps rich results.
- `/pdd/sitemap.xml` built from the DB (hub, 40 tickets, all topics, all
  questions). Add a `Sitemap:` line to `robots.txt` next to the existing
  `/qa/sitemap.xml`; `Disallow: /pdd/my`, `/pdd/trener`, `/pdd/ekzamen`.
- Hub portfolio card for ПДД on the Doday Studio page (like the recent Razbery
  card).

## 7. PDF export (`app/pdd/pdf.py`)

Pure-Python **fpdf2** (no native deps — safe on the FastPanel VPS, unlike
weasyprint). Renders "Твои слабые темы" from `PddAttempt` aggregation with a
bundled Cyrillic TTF. New dependency `fpdf2` → `uv add fpdf2`; **after deploy,
verify the dep installed** (known prod `uv sync` skip gotcha → 502 on new deps).
PDF is the last/heaviest chunk and is gated, so it ships after the cheaper Pro
features and the pre-sell signal.

## 8. Monetization placement + the "prove the ruble" guard

The studio-wide unproven hypothesis is "people pay Stars." Guard: **ship the Pro
CTA early** (on `/pdd/my`, after exam results, on the Nth practice mistake) with a
Yandex-Metrika goal on click, *before* building the heavy PDF. If real ПДД
traffic doesn't click in ~2 weeks, cut Pro depth — the free content keeps
compounding SEO regardless. ПДД's market-validated willingness-to-pay makes this
lower-risk than Razbery bookmarks.

## 9. Migration & data ops (user runs locally — DB-credential isolation)

- One Alembic migration `0048_doday_pdd.py`, `down_revision="0047"`, creating
  `entitlements`, `pdd_topics`, `pdd_tickets`, `pdd_questions`, `pdd_options`,
  `pdd_attempts`, `pdd_exam_sessions`.
- Tests build schema from `Base.metadata.create_all`; add
  `from app.pdd import models as _pdd_models` to `tests/conftest.py`.
- Content seeding: `app/pdd/seed_load.py` (mirrors `qa/seed_load.py`) ingests an
  official АВМ dataset (questions JSON + images) into the schema. The model writes
  the loader + a schema doc for the dataset; **the user runs the seed and the
  migration locally** and drops images under `app/static/pdd/img/`.

## 10. Testing

- TDD for the billing change (it touches the shared payment path): entitlement
  grant on `pdd_*` payment, idempotency, renewal extension, lifetime, refund
  shrink/delete, and **regression: existing `pro_*`/`tutor_pro_*` payments still
  set tier + pro_until and do NOT create entitlements**.
- pdd service: free practice (anon, no writes), attempt persistence (logged-in),
  exam simulator scoring (≤2 mistakes pass, +5 penalty) — ephemeral for free,
  saved for Pro, trainer queue ordering, weak-topic aggregation, Pro gating
  (402 for non-Pro on trainer/PDF/exam-history), SEO sitemap/canonical.
- Happy-path + edge per feature. All existing tests stay green.

## 11. Reuse (do not rebuild)

`auth.deps` (CurrentUser/RequiredUser), `billing` (extended), sitemap/robots auto
infra, structlog→Sentry, OG-image style, Jinja/Tailwind/Alpine/HTMX conventions,
the hub portfolio card pattern.

## 12. Out of scope (YAGNI)

Category CD tickets, audio, mobile app, purchase of individual tickets, social
features, AI hints, auto-renew (Stars web has none — addressed via the
exam-window 3-month hero + lifetime tier).
