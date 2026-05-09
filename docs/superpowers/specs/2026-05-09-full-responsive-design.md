# Full responsive sprint — design spec

**Date:** 2026-05-09
**Status:** approved by user, in progress
**Predecessor work:**
- `2026-05-08-public-pages-responsive-design.md` — 8 public pages on 375/1024/1440 (DONE 2026-05-09 morning).
- PROGRESS.md `2026-05-09 (продолжение)` — 16 app pages on 375 with 5 fixes (project header, quick_add, graph buttons, labels form, filters_manage).
- Recent commit `2bbd5e8` — onboarding card mobile/tablet, floating buttons sizing, content bottom padding.

## Goal

All 71 templates (8 public + 22 app + ~40 partials) render correctly on
**320 / 375 / 414 / 768 px**, with **realistic seeded data** (not empty
states), and the open ROADMAP NEXT items + Responsive/UX backlog items are
closed in the same sweep.

## Non-goals

- Visual redesign of components, colors, fonts, or design tokens.
- New features outside the responsive/UX scope.
- Touch-up at desktop widths >1024 (those have been audited already).
- Cross-browser polyfills (Chromium-only target — what Playwright tests).

## Method

1. **Tooling:** Playwright MCP for screenshots at every audited viewport.
   No "screenshot, declare success" — every fix gets a re-snapshot to
   visually confirm the issue is gone and no regression introduced.
2. **CSS approach:** Tailwind responsive prefixes only. Mobile-first
   (default classes are for 320px, `sm:` adds at 640px+, `md:` at 768px+).
3. **No layout backdoor:** never use `overflow-hidden` to mask a layout bug.
   Fix the layout properly (`min-w-0`, `flex-wrap`, stacking on small,
   shorter labels, two-line buttons on the smallest viewport).
4. **Touch targets:** every clickable element ≥ 36 × 36 px on mobile
   (Tailwind `h-10 w-10` = 40 × 40 px is the safe default).
5. **Text size floor:** no text smaller than `text-xs` (12 px) on mobile.
   Caveat: small badges where compact size is intentional.
6. **In-place fixes:** edit the existing template/partial, no new files
   except where a redesign genuinely warrants a new partial (calendar week
   view default, schedule single-day view).
7. **Granularity:** one git commit per logical chunk, Russian past-tense
   message ("исправил overflow в kanban-карточках на 320px"), push to
   `master` after each chunk.

## Test data (Phase 1)

Seed via existing `.tmp_ssh_seed_test_data.py` (already present, pushes
data to prod for `responsive-test@doday.local`). The script creates:

- **4 projects:** Inbox + «Работа Q3 — переезд офиса и онбординг» (long
  name to stress sidebar/header layout), «Дом», «Учёба в магистратуре»
  (favorite=true).
- **6 sections** across two of those projects (long names included).
- **15 root tasks + 3 subtasks** with realistic mix of priorities (P1-P4),
  due dates (overdue / today / tomorrow / week / 20 days / no date),
  multi-line markdown descriptions, and 1 task already completed.
- **4 labels:** срочно/дом/работа/идеи with rose/amber/sky/violet colors.
- **2 comments** on the most-loaded task (inc. markdown).
- **1 task-link** to populate links panel + graph view.

Local dev needs the same data — added a complementary local seed step:
run the python from `_seed.py` against the local Postgres directly.

For **kanban**: the «Работа Q3» project has 3 sections (Срочное / На этой
неделе / Бэклог). Add a 4th section «Готово» locally before the audit so
kanban has 4 columns. Add 8 tasks distributed across them.

For **habits / mood / time-tracking** views: add 2 habits with 14-day
checkin history + 7 mood entries to populate those screens.

## Phases

### Phase 1 — seed real test data (~20 min)

- Run `.tmp_ssh_seed_test_data.py` against prod (already exists) to verify
  it works and audit screens at https://getdoday.ru with that user.
- Mirror the seed against **local** Postgres so we can iterate fast at
  http://127.0.0.1:8000 with `--reload` instead of hitting prod after
  every Tailwind tweak.

### Phase 2 — public pages on 320px (~1h)

8 templates: `landing`, `pricing`, `help/index`, `help/article`, `privacy`,
`auth/login`, `auth/register`, `auth/verify_pending`.

For each: snap at 320px → list defects → fix in template → re-snap.
Defects expected to be rare since these were audited at 375px already, but
320px is 55px narrower so headers/CTAs/comparison-table will likely break.

### Phase 3 — app pages on 320px with real data (~2h)

22 templates: `today`, `inbox`-redirect, `upcoming`, `calendar`,
`calendar_week`, `done`, `trash`, `habits`, `stats`, `activity`,
`projects_archive`, `project`, `kanban`, `schedule`, `profile`, `graph`,
`labels`, `filters_manage`, `filter`, `custom_filter`, `placeholder`.

Plus key partials that render their own structure: `task_detail` (modal
panel), `task_row`, `quick_add`, `topbar`, `mobile_nav`, `sidebar`,
`onboarding_card`, `morning_briefing`, `standup_widget`, `today_schedule`,
`sprint_widget`, `retro_widget`, `school_streak`, `school_holiday`,
`week_plan`, `mood_widget`, `daily_note`, `countdown_pins`,
`completed_today`, `bulk_bar`, `undo_toast`, `reminders`,
`shortcuts`/`help_drawer`.

### Phase 4 — ROADMAP NEXT deep-dive (~1.5h)

- **kanban.html** with 4 real columns + 8 cards: column scroll behavior on
  mobile (horizontal swipe vs stacked), card touch targets, drag-handle
  visibility on touch devices.
- **task_detail.html**: the right-side sliding panel takes full width on
  mobile. Verify scroll works, close button is reachable above the fold,
  comment editor is usable on small keyboards.
- **profile.html** (208 Tailwind classes): largest page. Deep audit on
  every viewport. Likely fixes around the achievements grid, integrations
  cards, audience switcher, calendar-subscription block.

### Phase 5 — UX redesigns from backlog (~2h)

Each is a small but meaningful design change, in-template, with `hidden
md:block` / `block md:hidden` toggles to keep desktop unchanged:

1. **Comparison table on landing** — currently `overflow-x-auto`. Replace
   with a card-stack on `<md`: 3 vertical cards (Doday Free / Todoist Free
   / TickTick Free), each listing the same rows from the table. Desktop
   keeps the existing table.

2. **Calendar week view default on mobile** — currently month view is
   default everywhere; the 7-col grid is hard to read on 320px. On mobile,
   make week-view the default if no `?view=` param, with a prominent
   toggle between week/month at the top.

3. **Schedule single-day view on mobile** — currently 7-col table with
   `overflow-x-auto`. Replace on `<md`: tabs along top for Пн-Сб, single
   day's slots displayed as a vertical list. Desktop keeps the grid.

4. **Bottom-nav on iPad portrait (768px)** — currently `md:hidden`. iPad
   portrait sidebar is also hidden behind hamburger, so bottom-nav should
   stay visible up to `lg:` (1024px). Change to `lg:hidden`.

### Phase 6 — regression on 414/768 (~30 min)

Spot-check the most-touched pages (today, project, kanban, calendar,
profile, landing) at 414 and 768 to ensure 320px-targeted fixes didn't
break the bigger viewports.

### Phase 7 — verify & ship (~30 min)

- `uv run python scripts/lint_templates.py` — 0 errors.
- `uv run python scripts/smoke_test.py http://127.0.0.1:8000` — 18/18.
- `uv run pre-commit run --all-files`.
- Update PROGRESS.md with new chunk log + commit count.
- Update ROADMAP.md — strike out closed NEXT items + closed Responsive/UX
  backlog items.
- Final push to master.

## Acceptance criteria

- Every audited viewport for every page shows: no horizontal scrollbar,
  no clipped text, no overlapping elements, no buttons cut off, no
  unreachable controls, no touch target < 36px.
- All ROADMAP NEXT items struck through with commit references.
- All 4 listed Responsive/UX backlog items struck through.
- `scripts/smoke_test.py` 18/18 green against local + prod.
- `scripts/lint_templates.py` 0 errors.
- All chunk commits pushed to `master` with author email
  `112168281+SwairIt@users.noreply.github.com`.

## Out of scope (explicitly)

- Comparison table redesign WITH new copy (just restructure existing rows
  into cards).
- Calendar event-rendering improvements (just the view-default toggle).
- Schedule slot-creation modal (just the view).
- New help articles for the new mobile navigation patterns.
- React Native / native mobile app.

## Risks

- **Prod reseed wipes existing test-account data**: the seed script
  `delete`s before insert. Acceptable for `responsive-test@doday.local`
  (it's a dedicated audit account), but never run against `yarik@doday.app`.
- **Regression in 1440 desktop**: addressed by Phase 6 spot-check + the
  fact that all changes are mobile-first (defaults stay scoped to small,
  `md:` reverts to current behavior).
- **Long sprint context bloat**: addressed by per-phase commits and
  PROGRESS.md updates so the work survives session compaction.
