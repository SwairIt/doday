# Doday Q&A (Razbery) — Overnight Implementation Plan

**Date:** 2026-05-28
**Spec:** [`2026-05-28-doday-qa-design.md`](../specs/2026-05-28-doday-qa-design.md)
**Mode:** Full-autonomy overnight execution (user is asleep, no /loop, single live session).
**Author:** Doday-Claude (Opus 4.7, 1M context)

---

## Approach

Build top-down: models → service → router → templates → seed → wire-in → test → ship.
Each chunk is independently committable. Push to master after every green chunk so `deploy-poll` keeps prod current.

### Why this order
- Models pin the contract every later layer relies on.
- Service layer can be unit-tested without HTTP, which catches the most bugs cheaply.
- Templates last because they touch the most files and benefit from a stable Python side.
- Seed content can be generated **in parallel** with code via Agent-tool sub-sessions — they run independently, write JSON to disk, the main session loads them after.

---

## Chunk 1 — Skeleton + models + migration

**Files:**
- `app/qa/__init__.py` (empty)
- `app/qa/models.py`
- `app/qa/schemas.py`
- `alembic/versions/2026_05_28_add_qa_<hash>.py`

**Tests:** none in this chunk; pytest will run when service is wired.

**Verification:**
- `uv run alembic upgrade head` succeeds locally (if local DB available — fallback: visually inspect migration SQL).
- `uv run python -c "from app.qa import models"` imports cleanly.

**Commit:** `feat(qa): модели + Alembic migration для Razbery (skeleton)`

---

## Chunk 2 — Rendering + reputation + rate limits

**Files:**
- `app/qa/rendering.py` — `render_markdown(md: str) -> str` with `markdown-it-py` + `bleach`; supports inline `$x$` / display `$$x$$` (markup left for client-side KaTeX, not server-rendered).
- `app/qa/reputation.py` — `REPUTATION_DELTAS` constants, `apply_delta()`, privilege checks (`can_downvote`, `can_edit_others`, `can_close`, etc).
- `app/qa/rate_limits.py` — `QARateLimit` enum with `(action, window, max_count)` tuples; wrapped around `app.auth.rate_limit.sliding_window`.

**Tests:**
- `tests/qa/test_rendering.py` — markdown sanitization (no `<script>`, no `javascript:`), preserves `$x$` markup, allows safe tags.
- `tests/qa/test_reputation.py` — delta application, privilege gates.

**Commit:** `feat(qa): rendering + reputation + rate limits`

---

## Chunk 3 — Service layer (CRUD + voting + accept + reports)

**Files:**
- `app/qa/service.py` — async functions:
  - `create_question(session, author, title, body_md, subject_slug, grade) -> Question`
  - `create_answer(session, author, question_id, answer_md, explanation_md) -> Answer`
  - `vote(session, voter, target_type, target_id, value) -> int` (returns new score)
  - `accept_answer(session, asker, answer_id) -> None`
  - `unaccept_answer(session, asker, question_id) -> None`
  - `list_questions(session, subject_id=None, grade=None, sort='recent'|'top', offset=0, limit=20) -> list[Question]`
  - `get_question(session, qid) -> tuple[Question, list[Answer], dict[Vote-state]]`
  - `search_questions(session, query, subject_id=None, grade=None) -> list[Question]`
  - `report(session, reporter, target_type, target_id, reason, comment) -> Report`
  - `ensure_user_stats(session, user) -> UserStats`
- Raises `QAError` subclasses: `NotFound`, `Forbidden`, `BelowMinLength`, `RateLimited`, `AlreadyVoted`.

**Tests:**
- `tests/qa/test_service.py` — happy paths for each, anti-cheating (short explanation rejected), rate-limits, vote ±1 idempotency, accept-only-by-asker.

**Commit:** `feat(qa): service layer (CRUD + voting + accept + reports)`

---

## Chunk 4 — SEO infrastructure

**Files:**
- `app/qa/seo.py`:
  - `qapage_jsonld(question, answers) -> dict` — schema.org/QAPage with Question + AcceptedAnswer + suggestedAnswer[].
  - `og_image_svg(question, subject) -> str` — SVG bytes for `/qa/og/<id>.svg`.
  - `sitemap_rows() -> list[dict]` — yields lastmod-ed entries for all visible questions + subjects.

**Tests:**
- `tests/qa/test_seo.py` — JSON-LD valid, OG SVG contains title chars escaped, sitemap doesn't include hidden Qs.

**Commit:** `feat(qa): SEO — JSON-LD + OG-image + sitemap rows`

---

## Chunk 5 — Router (JSON API + HTML routes)

**Files:**
- `app/qa/router.py` — mounts both `/qa/*` HTML routes and `/api/qa/*` JSON routes (one APIRouter each, both exported).

**Routes (HTML):** `/qa/`, `/qa/s/<slug>`, `/qa/s/<slug>/<grade>`, `/qa/q/<id>-<slug>`, `/qa/u/<display_slug>`, `/qa/ask`, `/qa/edit/q/<id>`, `/qa/edit/a/<id>`, `/qa/search`, `/qa/og/<id>.svg`, `/qa/sitemap.xml`, `/qa/admin/reports` (RequiredAdmin).

**Routes (JSON):** `/api/qa/q`, `/api/qa/a`, `/api/qa/vote`, `/api/qa/accept`, `/api/qa/unaccept`, `/api/qa/report`, `/api/qa/q/<id>` (DELETE — author or rep≥1000).

**Tests:**
- `tests/qa/test_router.py` — httpx happy-path: ask → answer → upvote → accept (full flow).
- Per-route auth gate tests (401/403).
- Anti-cheating: POST /api/qa/a with short explanation → 422.

**Commit:** `feat(qa): HTTP router (HTML + JSON API)`

---

## Chunk 6 — Seeding pipeline

**Files:**
- `app/qa/seed_topics.py` — static list ≥300 topics. Each: `{subject_slug, grade, topic, n_questions: int}`.
- `app/qa/seeding.py`:
  - `SeedQuestion`, `SeedAnswer` pydantic models.
  - `load_seed_file(path) -> list[SeedQuestion]` reads JSON.
  - `apply_seed(session, items) -> int` — idempotent (uses `(title, subject_id, grade)` tuple as natural key), creates `bot@razbery` system user, inserts Q+A rows with `is_seed=true`, first answer accepted.
  - `python -m app.qa.seed_load --file=seed_content.json` entry point.

**Tests:**
- `tests/qa/test_seeding.py` — apply twice = same row count (idempotent), seed-bot user created once.

**Commit:** `feat(qa): seeding pipeline + 300+ seed topics`

---

## Chunk 7 — Jinja templates

**Files:**
- `templates/qa/_base.html` — extends `_base_marketing.html`, adds `/qa/` breadcrumb shell + side meta column.
- `templates/qa/index.html` — hub: latest 20 questions, top 5 subjects, search box.
- `templates/qa/subject.html` — questions for subject, grade tabs, pagination.
- `templates/qa/question.html` — question detail with answers, vote buttons, accept button.
- `templates/qa/ask.html` — ask form (HTMX + Alpine for live char counter + similar-question suggestion).
- `templates/qa/answer_form.html` — partial included on question.html, two-field structure with live char counter.
- `templates/qa/user.html` — user profile with answers, rep, badges.
- `templates/qa/search.html` — search results.
- `templates/qa/_answer_block.html` — single answer card.
- `templates/qa/_vote_buttons.html` — up/down arrows.
- `templates/qa/_question_card.html` — list-row card.
- `templates/qa/admin_reports.html` — admin queue.

**Aesthetic direction:** clean academic look, Tailwind. Color accent `bg-indigo-600` (Razbery brand). Mobile-first responsive. KaTeX CDN at the bottom of base for math.

**Tests:**
- `tests/qa/test_templates.py` — render-doesn't-crash for each route, contains expected anchor.

**Commit:** `feat(qa): шаблоны Jinja для всех страниц Razbery`

---

## Chunk 8 — Wire-in to app/main.py

**Edits:**
- `app/main.py`:
  - Import `qa_router` and `qa_api_router`, include in app.
  - Register `/qa/og/<id>.svg` + `/qa/sitemap.xml` correctly.
  - Add main sitemap (`/sitemap.xml`) entries for `/qa/` and top-level subjects (paginated `/qa/sitemap.xml` for the questions themselves).
  - Add top-nav link to `/qa/` in `_base_marketing.html`.
- `app/main.py` robots.txt: allow `/qa/`, disallow `/qa/edit/*` and `/qa/search`, `/qa/admin/*`.

**Tests:**
- `tests/qa/test_integration.py` — full route walk via httpx (every `/qa/*` returns 200 or expected redirect).

**Commit:** `feat(qa): integration — main.py wiring, sitemap, robots, top-nav`

---

## Chunk 9 — Seed content generation (PARALLEL — dispatched at start of session, harvested at the end)

This chunk runs **in parallel** with code chunks via the `Agent` tool with `subagent_type=general-purpose`.

For each (subject × grade) bucket, one agent is dispatched with the brief:
> Generate N Russian-language school-Q&A pairs for subject X grade Y. Output strict JSON array. Each item: `{title, subject_slug, grade, body_md, answers: [{answer_md, explanation_md}, …]}`. Title is a natural question a student would google. Body explains setup. Answer is the short result (1-3 sentences). Explanation walks through the reasoning step-by-step (≥150 chars). At least 1 answer per question; up to 3 answers for variety. No external URLs. No `<script>`. Markdown only. Russian only.

Buckets (subject × grade) — see spec §8 for the 16 subjects. Each bucket aims for ~30–80 Q&As. Total target: **≥1000 questions, stretch ≥2000**.

After all agents return, JSON files are concatenated, run through `python -m app.qa.seed_load`, committed as `app/qa/seed_data/*.json` (gitignored if too large — fallback: commit only the seed_topics.py and let the loader run from prod).

**Commit:** `feat(qa): первая массовая загрузка seed-контента (N=…)` — once seed-load runs successfully.

---

## Chunk 10 — Tests, lint, mypy, ship

**Run order:**
1. `uv run ruff format app/qa tests/qa`
2. `uv run ruff check app/qa tests/qa --fix`
3. `uv run mypy --strict app/qa`
4. `uv run pytest tests/qa -x --tb=short -q`
5. `uv run pytest -x -q -k "not slow"` (smoke against rest of suite to ensure no regression)
6. `git push` (master) — `deploy-poll` picks it up
7. Wait ~90s, curl `https://getdoday.ru/qa/` + `/qa/sitemap.xml` + a random `/qa/q/*` page.

**Commit-and-push cadence:** After each chunk above, regardless. So worst case the user wakes up to N partial commits, not a single mega-commit.

---

## Chunk 11 — Documentation updates

**Files:**
- `READ-FIRST.md` section 3 — add row for **Razbery / Doday Q&A** to existing-projects table.
- `PROGRESS.md` — append dated entry summarizing: what was built, what's deployed, what's pending (e.g. final smoke, seed content loading on prod, real-user testing).

**Commit:** `docs: Razbery shipped — READ-FIRST + PROGRESS updates`

---

## Time budget (rough)

| Chunk | Estimated tokens | Wall-clock-ish |
|---|---|---|
| 1 — models + migration | 15k out | 20 min |
| 2 — rendering + rep + RL | 10k | 15 min |
| 3 — service layer | 25k | 30 min |
| 4 — SEO | 12k | 15 min |
| 5 — router | 20k | 25 min |
| 6 — seeding pipeline | 10k | 15 min |
| 7 — templates | 40k | 50 min |
| 8 — wire-in | 8k | 10 min |
| 9 — seed content (in parallel) | varies | runs alongside others |
| 10 — tests + ship | 20k | 30 min |
| 11 — docs | 5k | 10 min |
| **Total** | **~165k** | **~3.5 hours, sequential** |

With parallel seed generation, wall-clock should be lower. Plenty of head-room within one 1M-context session.

---

## Fallback / failure modes

- **Local DB not reachable:** still commit code; the migration will run on prod via `alembic upgrade head` in `deploy-poll`.
- **Tests need DB:** use SQLite-backed in-memory fixtures where possible; fall back to skip-marker if migration is Postgres-specific.
- **An Agent sub-session returns invalid JSON:** skip that bucket, log, continue. Don't block the whole run.
- **Production breaks after push:** prior chunk was committable, revert is `git revert HEAD` — but every chunk has tests passing locally before push, so this should be rare.
- **Ran out of context before all chunks done:** PROGRESS.md is updated continuously so the next session can pick up cleanly. Code partially done is committed and visible.

---

## Out-of-scope reminders

(Re-stating from spec — to keep night-Claude honest):

- ❌ No AI calls in any user-facing code path. AI is only for **dev-time** seed generation.
- ❌ No Telegram-bot wiring. Stars / TG-tipping is phase-2.
- ❌ No comments under Q&A.
- ❌ No image upload.
- ❌ No email digests / notifications.
- ❌ No mods auto-hiding via heuristics in MVP — community votes only + admin queue.
- ❌ Do not break Doday Tasks (850+ tests) or Lessio (234+ tests).

---

End of plan. Time to build.
