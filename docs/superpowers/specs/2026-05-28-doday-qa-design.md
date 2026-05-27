# Doday Q&A — Design Spec

**Date:** 2026-05-28
**Author:** Brainstorming session between Yaroslav and Doday-Claude (Opus 4.7)
**Status:** Approved (autonomy-mode — user is asleep, full-autonomy authorized via READ-FIRST §9)
**Working codename:** Razbery (RU: «разбери») — final brand subject to user confirmation
**URL prefix:** `/qa/`

---

## 1. Goal

Build a **community-driven Q&A platform for Russian school students (grades 5–11)** as a new flagship of `getdoday.ru`. Each question becomes a public, SEO-indexed page. Answers are structured to teach, not enable copy-paste cheating. Long-term moat = a growing corpus of high-quality educational content that earns organic Google/Yandex traffic for millions of "как решить …" / "что такое …" queries.

Lives inside the Doday monorepo at `app/qa/*`. Reuses Doday auth, billing (Stars, phase 2), templates base, SEO infrastructure (sitemap, robots, IndexNow).

## 2. Why this is a flagship-scale bet

- **Total addressable market:** ~16M Russian school students. Even 0.1% MAU = 16k MAU.
- **Compounding moat:** every accepted Q&A becomes an indexed page. After 12 months of growth, the content base is self-defending against new entrants — and zero-marginal-cost per visitor.
- **Defensible vs incumbents:** Otvety.Mail closed in 2024, Znanija.com is mass-flooded with AI-junk. Niche is open.
- **No per-user AI cost:** the entire MVP runs on Postgres + Jinja + Alpine. AI is only used at **dev time** to bootstrap seed content (one-time spend, not operational).
- **Monetization (phase 2):** Telegram Stars tips on accepted answers + Pro tier (no-ads, profile boost, custom badge). Both nullable for MVP-1.

## 3. Decisions table (brainstorming output)

| # | Question | Decision |
|---|---|---|
| 1 | Audience | **School grades 5–11** only (no university, no hobby/life). Cleanest taxonomy, highest-frequency SEO queries (ОГЭ/ЕГЭ), parent-supervised users. |
| 2 | Anti-cheating UX | **Medium / two-field structure**: every answer requires "Ответ" (short result) + "Объяснение" (≥150 chars, mandatory). Without the second field, submit is blocked client+server. |
| 3 | Cold-start seeding | **Doday-Claude generates as many seed Q&As as the overnight session allows — target ≥1000, stretch goal 2000+** via parallel agent-jobs grouped by subject and grade. One-time dev work, not per-user. Tagged `[редакторский]` and attributed to a dedicated `bot@razbery` system user, NOT fake users. The more pages indexed on launch, the faster SEO compounds — there is no "too many" in v1. |
| 4 | URL pattern | Top-level `/qa/` (short, brandable, doesn't collide with `/lessio/` or Doday cabinet). |
| 5 | Auth | **Reuse Doday `app.auth.deps`** (session-cookie). No fresh auth subsystem; users created via Doday's existing email/password register flow. Magic-link is phase-2. |
| 6 | Anonymity | **Pseudonymous by default.** Users pick a `display_name` separate from email; no real-name shown anywhere. |
| 7 | Monetization | **Phase 2** — Stars-tips on accepted answers, Pro tier. MVP-1 ships free with placeholder Pro-CTA. |

## 4. URL map and roles

| URL | Who | What |
|---|---|---|
| `/qa/` | public | Hub — latest questions, top tags, subject grid, search box. |
| `/qa/s/<subject_slug>` | public | Subject landing — all questions for the subject, grade filter, "ask a question" CTA. |
| `/qa/s/<subject_slug>/<grade>` | public | Subject × grade landing (heavy SEO targeting). |
| `/qa/q/<id>-<slug>` | public | **Question detail** — title, body, answers (sorted by score desc, then created_at), comment threads, vote buttons (logged-in). |
| `/qa/u/<display_slug>` | public | User profile — bio, top answers, rep, badges. |
| `/qa/ask` | logged-in | Ask-a-question form. |
| `/qa/edit/q/<id>` | author or rep≥200 | Edit question. |
| `/qa/edit/a/<id>` | author or rep≥200 | Edit answer. |
| `/qa/search?q=…&subject=…&grade=…` | public | Search (Postgres full-text). |
| `/qa/tags` | public | Tag cloud. |
| `/qa/t/<tag_slug>` | public | Questions for tag. |
| `POST /api/qa/q` | logged-in | Create question (JSON). |
| `POST /api/qa/a` | logged-in | Create answer. |
| `POST /api/qa/vote` | rep≥1 (up) / rep≥50 (down) | Up/down vote. |
| `POST /api/qa/accept` | question author only | Mark answer accepted. |
| `POST /api/qa/report` | logged-in | Report Q/A as inappropriate / off-topic / spam. |
| `GET /qa/sitemap.xml` | crawlers | Lazy-built sitemap of all `/qa/q/*` and `/qa/s/*` URLs. |

Existing Doday cabinet (`/today`, `/cabinet`) remains untouched. The `/qa/` hub is reachable from the marketing landing (`/`) via a top-nav link added in phase-1.

## 5. Data model

All models in `app/qa/models.py`. Foreign keys to existing `users.id` (Doday auth) — no new auth table.

### `qa_subject`
| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `slug` | String(50) UNIQUE NOT NULL | Used in URLs — `matematika`, `russkij`, `fizika`, `himiya`, etc. |
| `name` | String(100) NOT NULL | Display name — «Математика» |
| `min_grade` | Integer NOT NULL | E.g. 5 |
| `max_grade` | Integer NOT NULL | E.g. 11 |
| `position` | Integer NOT NULL default 0 | For sorting in subject grid. |
| `description` | Text | SEO blurb shown on `/qa/s/<slug>` page. |
| `icon` | String(20) | Emoji or lucide-icon name. |

Seeded at migration time with 16 standard Russian school subjects (see §10).

### `qa_question`
| Field | Type | Notes |
|---|---|---|
| `id` | BigInt PK (autoincrement) | Plain int for shorter URL slugs `/qa/q/1234-…`. |
| `author_id` | FK users.id NULLABLE | NULL = anon/system seed content. |
| `subject_id` | FK qa_subject.id NOT NULL | |
| `grade` | Integer NULLABLE | 5–11; NULL = subject-wide. |
| `title` | String(250) NOT NULL | |
| `slug` | String(120) NOT NULL | URL-safe, derived from title at create. |
| `body_md` | Text NOT NULL | Markdown body. ≥30 chars. |
| `body_html` | Text NOT NULL | Pre-rendered safe HTML (markdown-it + bleach). |
| `score` | Integer NOT NULL default 0 | Cached vote sum. |
| `answer_count` | Integer NOT NULL default 0 | Cached. |
| `view_count` | Integer NOT NULL default 0 | |
| `accepted_answer_id` | FK qa_answer.id NULLABLE | Set on accept; cleared on un-accept. |
| `is_seed` | Boolean NOT NULL default false | Editorial-bot questions. |
| `is_hidden` | Boolean NOT NULL default false | Score ≤ −5 or mod-hidden. |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |
| `tsv` | TSVECTOR | GIN-indexed; rebuilt via trigger. |

Indexes: `(subject_id, created_at DESC)`, `(score DESC)`, GIN on `tsv`.

### `qa_answer`
| Field | Type | Notes |
|---|---|---|
| `id` | BigInt PK | |
| `question_id` | FK qa_question.id NOT NULL | |
| `author_id` | FK users.id NULLABLE | NULL = seed-bot. |
| `answer_md` | Text NOT NULL | The short result. ≥10 chars. |
| `answer_html` | Text NOT NULL | Rendered. |
| `explanation_md` | Text NOT NULL | The mandatory explanation. **≥150 chars.** |
| `explanation_html` | Text NOT NULL | Rendered. |
| `score` | Integer NOT NULL default 0 | |
| `is_accepted` | Boolean NOT NULL default false | Mirror of `qa_question.accepted_answer_id`. |
| `is_seed` | Boolean NOT NULL default false | |
| `is_hidden` | Boolean NOT NULL default false | |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

Index: `(question_id, score DESC, created_at ASC)`.

### `qa_vote`
| Field | Type | Notes |
|---|---|---|
| `id` | BigInt PK | |
| `user_id` | FK users.id NOT NULL | |
| `target_type` | String(1) NOT NULL | `'q'` or `'a'`. |
| `target_id` | BigInt NOT NULL | |
| `value` | Smallint NOT NULL | `+1` or `−1`. |
| `created_at` | TIMESTAMPTZ | |

UNIQUE `(user_id, target_type, target_id)`. Updating an existing vote replaces it; "un-voting" deletes the row.

### `qa_user_stats`
Singleton-per-user derived projection — saves us aggregations on hot paths.

| Field | Type | Notes |
|---|---|---|
| `user_id` | FK users.id PK | |
| `display_name` | String(50) NOT NULL | Free-form, validated unique-ish via `display_slug`. |
| `display_slug` | String(50) UNIQUE NOT NULL | URL-safe lower-kebab; auto-generated from `display_name`. |
| `bio` | String(280) NULLABLE | Pseudonymous bio. |
| `avatar_emoji` | String(8) NOT NULL default '📚' | One unicode emoji — no upload cost. |
| `reputation` | Integer NOT NULL default 1 | Capped at 0 floor; new users start at 1. |
| `q_count` | Integer NOT NULL default 0 | |
| `a_count` | Integer NOT NULL default 0 | |
| `accepted_count` | Integer NOT NULL default 0 | |
| `created_at` | TIMESTAMPTZ | |

Row created lazily on first `/qa/*` action by user. Updated transactionally by `service.recalc_stats` after vote / accept / new-post.

### `qa_report`
| Field | Type | Notes |
|---|---|---|
| `id` | BigInt PK | |
| `reporter_id` | FK users.id NOT NULL | |
| `target_type` | `'q'` or `'a'` | |
| `target_id` | BigInt NOT NULL | |
| `reason` | String(50) NOT NULL | Enum: `spam`, `offtopic`, `wrong_answer`, `abuse`, `cheating_request`. |
| `comment` | String(500) NULLABLE | |
| `status` | String(20) NOT NULL default `'open'` | `open` / `resolved` / `rejected`. |
| `created_at` | TIMESTAMPTZ | |

### `qa_tag` (deferred to phase-2 — MVP uses subject+grade only)

Not in MVP-1 — subject + grade gives enough taxonomy. Avoiding tag-bloat that plagued StackOverflow's early days.

## 6. Anti-cheating UX — concrete

The two-field structure is the visible brand-stance. UX details:

### Answer form
```
[ Ответ ]                                    ← short result, plain textarea, ≥10 chars
┌────────────────────────────────────────┐
│ x = -3 или x = 2                       │
└────────────────────────────────────────┘

[ Объяснение — обязательно ]              ← min 150 chars; counter visible
┌────────────────────────────────────────┐
│ Это квадратное уравнение. Применяем    │
│ дискриминант: D = b² - 4ac = …         │
│                                        │
└────────────────────────────────────────┘
  152 / минимум 150 символов ✓

[ Помочь разобраться ]   (submit, disabled until both fields meet minimums)
```

Server validates same minimums (defence in depth — never trust client).

### Question form
Asker fills:
- Subject (required, select)
- Grade (optional, select 5–11)
- Title (required, ≥10 chars, ≤250)
- Body (required, ≥30 chars, markdown, supports `$…$` LaTeX inline rendering via KaTeX CDN)
- Auto-suggest at the bottom: "Похожие вопросы" (top-3 by tsvector match) — reduces duplicates.

### Rendering on `/qa/q/<id>-<slug>`
Each answer renders as two stacked blocks:
```
┌─ Ответ ─────────────────────────┐
│  x = -3 или x = 2               │
└─────────────────────────────────┘
┌─ Как это получилось ────────────┐
│  Это квадратное уравнение. …    │
└─────────────────────────────────┘
       ↑12  ✓ Принят    💬 3
```

The Pro/copy-only user can grab the answer. The learning user reads the explanation. The site brand-promises: "не списывание, а понимание".

## 7. Reputation system

Inspired by StackOverflow but trimmed to MVP essentials.

| Action | Effect on author rep |
|---|---|
| Your question upvoted | +5 |
| Your question downvoted | −2 |
| Your answer upvoted | +10 |
| Your answer downvoted | −2 |
| Your answer accepted | +15 |
| You accepted someone's answer | +2 (small reward for closing the loop) |
| You cast a downvote | −1 (price of skepticism) |
| Your Q/A hidden by mods | −20 |

Privileges by rep:
| Rep | Privilege |
|---|---|
| 1 | Create Q, create A, upvote |
| 15 | Self-flag own content for deletion |
| 50 | **Downvote** (the −2 hits author; downvoter pays −1) |
| 200 | Edit other users' Q/A |
| 500 | Vote-to-close obvious-cheating / off-topic / duplicate questions (3 votes close) |
| 1000 | Vote-to-delete |
| 2000 | Cast moderator powers (un-hide, un-close) |

Floor: reputation cannot go below 0.

Stored on `qa_user_stats.reputation`. Recomputed transactionally inside `service._adjust_reputation()` whenever votes/accepts change.

## 8. Subject taxonomy (seeded at migration)

| slug | name | grades | icon |
|---|---|---|---|
| `matematika` | Математика | 5–6 | 🔢 |
| `algebra` | Алгебра | 7–11 | 📐 |
| `geometriya` | Геометрия | 7–11 | 📏 |
| `russkij` | Русский язык | 5–11 | 📝 |
| `literatura` | Литература | 5–11 | 📖 |
| `english` | Английский язык | 5–11 | 🇬🇧 |
| `fizika` | Физика | 7–11 | ⚛️ |
| `himiya` | Химия | 8–11 | 🧪 |
| `biologiya` | Биология | 5–11 | 🌱 |
| `geografiya` | География | 5–11 | 🌍 |
| `istoriya` | История | 5–11 | 🏛️ |
| `obshhestvoznanie` | Обществознание | 6–11 | ⚖️ |
| `informatika` | Информатика | 5–11 | 💻 |
| `okruzhajushhij-mir` | Окружающий мир | 5–6 | 🌳 |
| `obzh` | ОБЖ | 5–11 | 🚦 |
| `tehnologiya` | Технология | 5–8 | 🔧 |

16 subjects. Seeded via Alembic data-migration alongside the schema.

## 9. Cold-start: seed content generation

The **single most important non-code task** of MVP-1. Implementation:

1. A Python module `app/qa/seeding.py` defines a `SeedTask` dataclass: `subject_slug`, `grade`, `topic` (e.g. "квадратные уравнения").
2. A static list of ~200 seed topics across the 16 subjects, mapped to the FIPI ОГЭ/ЕГЭ codifiers (and grade-appropriate topics for younger grades) — committed as `app/qa/seed_topics.py`.
3. Per topic, **Doday-Claude (this session) writes 2–3 Q&A pairs** as agent subtasks. Output JSON: `{"title": …, "body_md": …, "answers": [{"answer_md": …, "explanation_md": …}, …]}`.
4. A management script `python -m app.qa.seed_load --file=seed_content.json` reads the JSON, creates a `bot@razbery` system user (idempotent), and inserts `qa_question` + `qa_answer` rows with `is_seed=true`. The first answer per question is marked accepted.
5. `is_seed=true` content displays a small badge "📚 Редакторский ответ" — transparency. It still ranks normally in Google.

This produces **≥1000 seed Q&A pages (stretch goal 2000+)**. Combined with subject and grade landing pages, the sitemap submitted to Google/Yandex on day-1 has thousands of indexable URLs. Indexing typically completes in 2–4 weeks; first organic traffic by day-30.

## 10. SEO infrastructure

- **Title pattern:** `<question title> — Решение и объяснение | Razbery`
- **Meta description:** First 160 chars of question body, stripped of markdown.
- **Canonical URL:** `https://getdoday.ru/qa/q/<id>-<slug>` — uses `<id>-` prefix so renaming the slug doesn't break links.
- **JSON-LD:** `schema.org/QAPage` with embedded `Question` + `AcceptedAnswer` + `suggestedAnswer[]`. Google's "rich result" eligible.
- **Open Graph:** auto-generated OG image — SVG-server-rendered, reusing the `lessio/og_image.py` pattern. Shows subject icon + question title + grade badge.
- **Sitemap:** `/qa/sitemap.xml` builds dynamically — paginated 1000-per-file when corpus grows. Submitted via IndexNow (we already have `app/lessio/indexnow.py` to reuse).
- **Robots:** all `/qa/*` allow; `/qa/edit/*` and `/qa/search` disallow.
- **Internal linking:** every question page links 3 "Похожие вопросы" (tsvector match) and breadcrumb `Razbery > <Subject> > <Grade>`.

## 11. Moderation

- **Hide threshold:** `score ≤ −5` auto-sets `is_hidden=true`. Author sees a small "ваше сообщение скрыто — отредактируйте чтобы вернуть" CTA.
- **Report queue:** simple admin page at `/qa/admin/reports` (gated by Doday `RequiredAdmin`). Shows open reports; admin can hide / un-hide / dismiss.
- **Anti-spam:** sliding-window rate limit (reuse `app/auth/rate_limit.py`): 3 questions / hour, 10 answers / hour, 30 votes / hour per user. Stricter for users with rep < 5.
- **Forbidden patterns:** server-side regex rejects answers that look like pure cheating requests ("реши за меня", "сделай домашку", phone numbers, contact swaps, profanity). Soft block — friendly error message.
- **No AI moderation in MVP.** Heuristics + human admin queue.

## 12. Stars integration (Phase 2 — out of MVP-1)

Documented here so MVP doesn't paint into a corner.

- **Stars-tip on accepted answer**: question author can tip answerer 10 / 50 / 100 Stars via the existing `app/billing/stars` flow.
- **Pro tier (250 Stars / month):** no-ad UI placeholder (we don't run ads yet so this is just a perk + badge), prominent profile slot, "Pro" tag on every answer, ability to vote-to-close from rep 200 instead of 500.
- **Revenue split idea:** 70% answerer / 30% platform on tips.

Stars work is gated behind `qa_billing_enabled` setting; MVP ships with that flag false but the schema columns exist (`qa_user_stats.pro_until: TIMESTAMPTZ`, `qa_answer.tips_total_stars: Integer`).

## 13. Out of scope (MVP-1)

- Tags (subject+grade are enough taxonomy for v1).
- Image upload (markdown links to imgur or similar acceptable in body; no native upload).
- Mobile native app (PWA-friendly Tailwind only).
- Email digests / notifications (deferred to phase 2 once we know what users care about).
- Real-time updates (no SSE / WebSocket).
- Tutors / paid Q&A (huge can of worms; not for MVP).
- Internationalization (RU only).
- Comments under Q/A (deferred — only votes + answers in v1).

## 14. Tech stack reuse from monorepo

- **DB:** existing managed Postgres via `DATABASE_URL`.
- **ORM models:** SQLAlchemy 2.0 async + Alembic migration.
- **Templates:** Jinja2 inheriting from a new `templates/qa/_base.html` that extends `templates/_base_marketing.html` (so the top-nav and footer match the rest of the site).
- **Auth:** Doday session-cookie via `app.auth.deps.CurrentUser` / `RequiredUser`.
- **Logging:** `structlog` — same as everywhere else.
- **Sentry:** auto-captured.
- **Frontend:** Tailwind CDN + Alpine.js for interactive bits (vote buttons, ajax submit, char counter); HTMX for partial reloads where it makes sense.
- **Math rendering:** KaTeX 0.16 CDN (auto-render on `$…$` and `$$…$$`).
- **Markdown rendering:** `markdown-it-py` server-side + `bleach` for sanitization (already used by Lessio's blog).
- **Rate limit:** `app.auth.rate_limit.sliding_window`.
- **Sitemap / IndexNow:** extend `app/main.py` sitemap-builder + reuse `app/lessio/indexnow.py`.

## 15. Success criteria

MVP-1 (week 1–2) shipped with:
- All routes from §4 working.
- 200+ seed Q&As live, sitemap submitted.
- Tests covering: ask → answer → accept → vote → reputation update; rate-limit triggers; report flow; anti-cheating server-side validation; sitemap renders.
- No regression in Doday Tasks (850+ tests) or Lessio (234 tests).
- Lighthouse SEO ≥ 95 on `/qa/q/<sample>`.

Post-launch (weeks 3–8):
- Google indexes >50% of seed pages.
- First organic search visitor lands on `/qa/q/*` from Google.
- First real user-authored question.

12-month north star:
- 10k+ Q&As (mostly user-authored after seed kicks the flywheel).
- 100k+ organic monthly visitors.
- 5k+ MAU.

## 16. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Seed content is AI-generated and Google de-ranks AI-content | Hand-edit critical 50 pages; the rest are CC-quality but transparently labelled `[редакторский]`. Google's policy targets **deceptive** AI content, not labelled helpful content. |
| First users post junk / cheating-only "answer me" questions | Anti-cheating client+server validation; rate limit; report queue. |
| Subject taxonomy too rigid | The 16 subjects map 1:1 to RU school curriculum — well-known, won't churn. |
| Markdown XSS | Server sanitizes via `bleach` allow-list (no `<script>`, no `javascript:`). KaTeX rendered client-side from text — no eval. |
| Slug collisions | `id-slug` URL pattern means slugs are decorative; collisions impossible. |
| Reputation farming via sockpuppets | Phase-2 problem; for now, throttle by IP + rep ≥ 50 needed to downvote keeps damage bounded. |
| Spec contradicts itself | This spec was self-reviewed before commit. If you find a contradiction, ping the author. |

---

## Appendix A — File layout

```
app/qa/
  __init__.py
  models.py           # Subject, Question, Answer, Vote, UserStats, Report
  schemas.py          # Pydantic v2
  service.py          # business logic — create_q, create_a, vote, accept, etc.
  router.py           # HTTP — JSON API + HTML pages
  rendering.py        # markdown → safe HTML, KaTeX hint markup
  seeding.py          # SeedTask dataclass + loader
  seed_topics.py      # static list of 200 seed topics
  seo.py              # JSON-LD builder, OG-image SVG, sitemap rows
  rate_limits.py      # per-action sliding-window thresholds
  reputation.py       # reputation deltas + privilege checks
templates/qa/
  _base.html
  index.html          # /qa hub
  subject.html        # /qa/s/<slug>[/<grade>]
  question.html       # /qa/q/<id>-<slug>
  ask.html
  user.html
  search.html
  tags.html
  _answer_block.html
  _vote_buttons.html
alembic/versions/
  <yyyymmdd>_add_qa_<hash>.py   # one migration file with all tables + subject seed
```

## Appendix B — Out-of-band tasks (post-MVP)

- Build admin moderation UI at `/qa/admin/`.
- Add comments threading.
- Add image upload (S3-compatible? Yandex Object Storage).
- Add email digest: weekly best answers in your followed subjects.
- Implement Stars tip flow + Pro tier (per §12).
- Internationalization (KZ / BY markets).
