# Doday — Universal Free Todo App (pivot spec)

**Date:** 2026-05-03
**Status:** Active. Supersedes the 2026-05-02 schoolers-only spec.
**Working brand:** Doday

## 0. Why this exists

A free, fast, beautiful task manager that anyone — a 12-year-old doing homework, a freelancer juggling client work, a small team coordinating a project — can use without paying. Most polished todo products are paid (Todoist, TickTick, Things). Free alternatives feel either crude (basic notepad apps) or bloated (full project-management suites). Doday's pitch is simple: a delightful free todo app, **monetization deferred until we know what people pay for**.

The original schooler-specific diary parsing (Школьный портал МО / МЭШ) becomes one optional integration on a much larger product, not the product itself.

## 1. Audience

- **Individuals (kids 11+, adults)** — personal task lists, daily planning, habits, school/work mix.
- **Tiny teams (2–5 people)** — shared lists later (post-MVP).
- **Companies** — only after individuals love it; B2B is downstream.

Not in scope right now: enterprise SSO, fine-grained permissions, time tracking, Gantt, bug-tracker style fields.

## 2. Non-goals

- ❌ AI homework auto-solver (rejected for ethical/business reasons in 2026-05-02 brainstorm)
- ❌ Verbatim copies of any specific commercial product's UI or flow
- ❌ Native mobile apps in MVP (PWA-friendly responsive web only)
- ❌ Real-time multi-user collaboration in MVP (sharing comes later)
- ❌ Offline mode (online-only first; PWA caching later)

## 3. Brand & visual direction

### 3.1 Personality

Confident, calm, modern, slightly playful — not childish, not corporate. The product should feel like a tool a designer would happily use AND a 12-year-old wouldn't be embarrassed by.

### 3.2 Color palette

Primary axis: **violet → fuchsia gradients**, deep dark surfaces, generous whitespace.

**Light theme**
| Token | Hex | Use |
|---|---|---|
| `--color-bg` | `#fafaff` | App background |
| `--color-surface` | `#ffffff` | Cards, panels |
| `--color-surface-2` | `#f5f3ff` | Sidebar, elevated regions |
| `--color-border` | `#e9e5f6` | Soft separators |
| `--color-text` | `#1a1230` | Primary text |
| `--color-text-muted` | `#6b6587` | Secondary text |
| `--color-accent` | `#7c3aed` | Brand violet |
| `--color-accent-2` | `#a855f7` | Hover/lighter accent |
| `--color-accent-grad-from` | `#7c3aed` | Gradient start (violet-600) |
| `--color-accent-grad-to` | `#d946ef` | Gradient end (fuchsia-500) |
| `--color-success` | `#10b981` | Completed state |
| `--color-warning` | `#f59e0b` | Due-soon state |
| `--color-danger` | `#ef4444` | Overdue, destructive |

**Dark theme** (default for new accounts at night, user-toggleable)
| Token | Hex | Use |
|---|---|---|
| `--color-bg` | `#0d0820` | App background (deep purple-black) |
| `--color-surface` | `#161028` | Cards |
| `--color-surface-2` | `#1f1638` | Sidebar |
| `--color-border` | `#2a2048` | Soft separators |
| `--color-text` | `#f5f3ff` | Primary text |
| `--color-text-muted` | `#9890b8` | Secondary text |
| `--color-accent` | `#a78bfa` | Lifted-violet accent |
| `--color-accent-2` | `#c4b5fd` | Hover |
| Same gradient stops, `--color-success/warning/danger` slightly desaturated |

### 3.3 Typography

- **Font**: `Inter Variable` — load from Google Fonts via CDN with `display=swap`.
  Headings 600/700, body 400/500, monospace `JetBrains Mono Variable` only for keyboard hints / IDs.
- **Scale** (base 16px):
  - `xs` 12 / `sm` 14 / `base` 16 / `lg` 18 / `xl` 20 / `2xl` 24 / `3xl` 30 / `4xl` 36 / `5xl` 48 / `6xl` 60
- **Line-height**: 1.5 body, 1.2 headings.
- **Letter-spacing**: tighten -0.02em on headings ≥ 2xl.

### 3.4 Spacing, radii, shadows

- Spacing scale: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 96 px.
- Border radius: `8` for inputs, `12` standard for cards/buttons, `16` for large cards, `24` for hero containers, full for avatars and floating action buttons.
- Shadows (light):
  - `shadow-sm`: `0 1px 2px rgba(31,16,56,0.04)`
  - `shadow`: `0 4px 12px -2px rgba(31,16,56,0.08)`
  - `shadow-lg`: `0 16px 40px -8px rgba(124,58,237,0.18)`
  - `shadow-glow` (hero): `0 0 60px -20px rgba(124,58,237,0.45)`

### 3.5 Motion

Use motion meaningfully, never decoratively.

- **Tap feedback**: scale 0.97 on `:active` (90 ms).
- **Hover lift**: cards translate-Y -2 px + shadow grows over 150 ms ease-out.
- **Check toggle**: SVG checkmark `stroke-dashoffset` 280 ms ease-out + a 360 ms confetti burst (optional, on by default for personal use, off in dense list mode).
- **Page transitions**: HTMX swaps with a 120 ms cross-fade; respect `prefers-reduced-motion`.
- **Modal**: backdrop fade 180 ms, panel scale 0.95→1 + opacity over 220 ms cubic-bezier(0.16, 1, 0.3, 1).
- **Toast**: slide-in 180 ms, auto-dismiss 4 s, scale-out 160 ms.

### 3.6 Iconography

Use [Lucide](https://lucide.dev/) icon set served as inline SVG sprite (open-source, MIT). Standard sizes 16/20/24 px stroke-width 1.5.

## 4. Layout

### 4.1 Anatomy (signed-in app)

```
┌────────────────────────────────────────────────────────────────┐
│  Topbar  [Logo]  [Search ⌘K]                  [+] [🌗] [Avatar]│
├──────────┬─────────────────────────────────────────────────────┤
│          │                                                     │
│ Sidebar  │          Main canvas                                │
│ - Inbox  │   - View header                                     │
│ - Today  │   - Quick-add row                                   │
│ - Up-    │   - Task list / calendar grid                       │
│   coming │                                                     │
│ - Filter │                                                     │
│   & Lab- │                                                     │
│   els    │                                                     │
│ - Proj-  │                                                     │
│   ects   │                                                     │
│ + new    │                                                     │
│  project │                                                     │
└──────────┴─────────────────────────────────────────────────────┘
```

- Sidebar: fixed 264 px on ≥lg, collapsible to icon-only at md, hidden behind hamburger on sm.
- Topbar 56 px tall, sticky, frosted (`backdrop-filter: blur(12px)` on translucent surface).
- Main canvas max-width 880 px centered for list views, full-width for calendar.

### 4.2 Mobile (≤640 px)

- Topbar persists, search collapses to icon.
- Sidebar becomes a bottom-sheet drawer triggered from a hamburger.
- Bottom navigation: Today / Upcoming / Add (FAB) / Calendar / Profile.
- Quick-add becomes a modal sheet from the bottom.

### 4.3 Auth/marketing pages (signed-out)

- Centered hero with headline, subheading, primary CTA, gradient orb backgrounds (CSS `radial-gradient` blurred via `filter: blur(80px)`).
- Single column, max-width 640 px, generous vertical rhythm.

## 5. Information architecture

### 5.1 Sidebar entries

Default for every account, in order:

1. **Inbox** — uncategorized tasks. Default destination of new tasks if no project chosen.
2. **Today** — tasks whose `due_at` is today (local TZ) or overdue.
3. **Upcoming** — tasks due in next 7 days, grouped by date.
4. **Calendar** — month view, click a day to see tasks.
5. *(separator)*
6. **Filters & Labels** — saved smart filters and label chips.
7. **Projects** — user-created collapsible list. `+` button to add.

### 5.2 URL structure

| URL | What |
|---|---|
| `/` | Landing (anonymous) OR redirect to `/app/today` (logged in) |
| `/auth/register`, `/auth/login`, `/auth/verify`, `/auth/verify-pending`, `/auth/logout` | Existing |
| `/privacy`, `/terms` | Static |
| `/app/inbox` | Inbox view |
| `/app/today` | Today view (default after login) |
| `/app/upcoming` | Upcoming (next 7 days, grouped) |
| `/app/calendar?month=YYYY-MM` | Month grid |
| `/app/calendar/day/YYYY-MM-DD` | Day detail |
| `/app/projects/{slug}` | Project view |
| `/app/labels/{slug}` | Tasks tagged with label |
| `/app/search?q=` | Full-text search |
| `/app/profile` | Account settings, delete |
| `/api/tasks` etc. | HTMX-target endpoints (HTML responses) |

## 6. Data model

ORM models live per-feature: `app/tasks/models.py`, `app/projects/models.py`, `app/labels/models.py`. They share `app.db.Base`.

### 6.1 Project

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK → users.id, on delete CASCADE | |
| `name` | str(80) | Required |
| `slug` | str(80) unique per user | Generated from name + nanoid suffix |
| `color` | str(20) | Token name (`violet`, `fuchsia`, `sky`, `emerald`, `amber`, `rose`, `slate`) |
| `position` | int | For reorder |
| `is_inbox` | bool default false | One per user, auto-created on signup |
| `is_archived` | bool default false | |
| `created_at`, `updated_at` | datetime tz | |

Constraint: exactly one `is_inbox=true` per user (unique partial index).

### 6.2 Task

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK CASCADE | |
| `project_id` | UUID FK → projects.id, ON DELETE SET DEFAULT to inbox | |
| `parent_task_id` | UUID FK → tasks.id NULLABLE | Subtasks (1 level deep in MVP) |
| `title` | str(500) | Required |
| `description` | text NULLABLE | Markdown stripped to text on render |
| `due_at` | datetime tz NULLABLE | If only date is set, time is 23:59 local |
| `due_date_only` | bool default true | If true, hide time in UI |
| `priority` | enum {`p1`,`p2`,`p3`,`p4`} default `p4` | p1 = urgent (red), p4 = none |
| `is_completed` | bool default false | |
| `completed_at` | datetime tz NULLABLE | |
| `position` | int | For drag-reorder within project |
| `created_at`, `updated_at` | datetime tz | |

Index: `(user_id, due_at)` for the Today/Upcoming queries.

### 6.3 Label

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK CASCADE | |
| `name` | str(40) | Required |
| `slug` | str(40) unique per user | |
| `color` | same set as Project | |

### 6.4 task_labels (M:N)

| `task_id` | UUID FK CASCADE |
| `label_id` | UUID FK CASCADE |
| Composite PK |

### 6.5 Auto-provisioning on signup

After `register_user` succeeds and email is verified, create one default `Project(name="Inbox", is_inbox=true, color="slate")` and three sample tasks ("Попробуй закрыть эту задачу — кликни кружок", "Перетащи меня в проект", "Создай свою задачу через `+` сверху"). Sample tasks land in Inbox.

## 7. Functional spec — MVP behaviors

### 7.1 Quick add

- Sticky row at the top of any list view: a single text input + a `[+]` button (also Enter submits).
- Smart parsing of natural language inside the input:
  - Trailing `сегодня` / `завтра` / `пт` / `пн` / dates `25.05` → sets `due_at`.
  - `!` `!!` `!!!` `!!!!` (1–4) → priority p4 → p1.
  - `#projectname` → moves to that project (must exist).
  - `@labelname` → attaches a label (auto-creates if not exists, with default color).
- Submit creates task and prepends it to the current list with a 240 ms slide-in.

### 7.2 Task row

- Left: round circle button (radio look). Hover scales it 1.1 with priority-color stroke.
- Click: animated checkmark draw, row fades to muted, strikethrough title, slides into a "Completed today" subgroup at bottom.
- Middle: title (click to inline-edit; Enter saves, Esc cancels).
- Right: due-date chip (color-coded), priority flag, label chips (max 3 visible + "+N more").
- Right-edge actions on hover: edit, delete, change-project, schedule.
- Drag handle on left edge for reorder (`SortableJS` via CDN — open-source MIT).
- Subtasks (1 level): expand caret to the left of the circle.

### 7.3 Today view

- Header: "Сегодня · {weekday, DD month}".
- Two sections: "Просрочено" (overdue, red top border) — collapsed by default if > 5; "Сегодня" (due today).
- Quick-add fills `due_at = today 23:59`.
- Empty state: friendly illustration + "Сегодня всё чисто. Можешь отдохнуть или [запланировать что-нибудь]".

### 7.4 Upcoming view

- Header with date range chip: "Эта неделя · 03–09 мая".
- Day-grouped sections, each header sticky while scrolling its section.
- Quick-add fills `due_at = today` by default; user can change date inside the chip.

### 7.5 Calendar view

- Month grid 7×6 (rows extend if needed), each cell shows up to 3 task chips + "+N more" count.
- Click a day → side panel slides in from right with day's tasks + quick-add for that date.
- Top toolbar: prev / next month, "Сегодня" jump, view-mode segmented control (Месяц / Неделя — week is post-MVP nice-to-have).
- Drag a task between days to reschedule.

### 7.6 Project view

- Header: project name, color dot, count of incomplete tasks, project menu (rename, change color, archive, delete).
- Section for incomplete + collapsed "Completed" section at bottom.
- Drag-reorder within project.

### 7.7 Inbox

- Same as Project view but pinned, can't be deleted/archived.

### 7.8 Search

- `⌘K` (or `Ctrl+K`) opens a full-screen palette modal.
- Type 2+ chars → live results across tasks (title + description) + projects + labels.
- Click a result → navigate to that view with the task highlighted.
- Postgres `to_tsvector` with `russian` configuration for Cyrillic stemming; fallback `simple` for non-Russian terms via `to_tsquery('simple', plainto_tsquery_text)`.

### 7.9 Settings / profile

- Change password, change email (requires re-verification), choose default view (Today/Inbox/Upcoming).
- Theme toggle (Auto/Light/Dark).
- Language (RU now; EN later).
- Export all data as JSON.
- Delete account (confirmation modal, types own email to confirm, irreversible cascade).

### 7.10 Empty states & onboarding

Every empty state has a friendly Russian copy + a clear next-action button. After signup the user lands on Today with the 3 sample tasks visible.

## 8. Email integration

Production must send real verification emails. Configurable provider via SMTP env vars — works with **Resend**, **Brevo**, **Mailgun**, **SendGrid**, **Yandex Mail**.

Recommended for MVP: **Resend** (free 3000 emails/mo). User signs up at resend.com, generates API key, adds to `.env`:

```
SMTP_HOST=smtp.resend.com
SMTP_PORT=587
SMTP_USERNAME=resend
SMTP_PASSWORD=<api key>
SMTP_START_TLS=true
SMTP_FROM=onboarding@resend.dev
```

Resend free constraint: without a verified domain, emails can only be sent to the email address used to register on Resend. For broader sending → verify a domain (one-time setup, no extra cost).

Alternative: **Brevo** (formerly Sendinblue) — 300 emails/day free, easier verification:

```
SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USERNAME=<your brevo login email>
SMTP_PASSWORD=<smtp key from dashboard>
SMTP_START_TLS=true
SMTP_FROM=<verified sender from brevo dashboard>
```

Code change required: none (existing `app/auth/email.py` already reads SMTP_* from settings and uses `aiosmtplib.send`). The README and a new `docs/setup-email.md` document this.

## 9. Implementation chunks

Each chunk = one bounded piece of work, ends with a green ruff/mypy + commit + push to master. Order is the order of execution.

| # | Chunk | Files touched | Done when |
|---|---|---|---|
| C0 | Pivot: spec + memory + claude.md (this iteration) | spec, claude.md, memory | Committed and pushed |
| C1 | Brand + design tokens: Tailwind config inlined in `base.html`, CSS variables for both themes, font loading | `app/templates/base.html`, `app/static/app.css` | Page sources show new tokens; existing pages still render |
| C2 | Models + migration: Project, Task, Label, task_labels | `app/projects/models.py`, `app/tasks/models.py`, `app/labels/models.py`, `alembic/versions/0002_*.py` | `alembic upgrade head` succeeds; tests for model uniqueness |
| C3 | Project service + router (CRUD) | `app/projects/{service,schemas,router}.py`, tests | Endpoints return JSON + HTML, tests green |
| C4 | Task service + router (CRUD, complete, reorder) | `app/tasks/{service,schemas,router}.py`, tests | Same |
| C5 | Label service + router | `app/labels/{service,schemas,router}.py`, tests | Same |
| C6 | Auto-provisioning Inbox + sample tasks on email-verify | `app/auth/service.py` extension, tests | New user has Inbox + 3 tasks |
| C7 | Layout: sidebar + topbar redesigned `base.html`; landing redesigned (purple gradient hero) | templates, CSS | Visual confirms |
| C8 | Auth pages redesigned to match | templates | Same |
| C9 | App shell layout `app_base.html` (sidebar always visible at ≥md) | templates | Same |
| C10 | Today view | `app/views/today.py` (or in pages/router), template, HTMX endpoint for task toggle | Mark-complete works without full reload |
| C11 | Upcoming view | similar | Renders, day-grouped |
| C12 | Calendar view | template, alpine.js for the grid | Click day → panel |
| C13 | Project view | template | Renders, drag-reorder works |
| C14 | Quick-add with NL parsing | shared partial, JS via Alpine | Sets due_at/priority/labels |
| C15 | Inline edit, delete, schedule, change-project | HTMX endpoints, partials | Works without page reload |
| C16 | Search palette (⌘K) | template, endpoint, postgres FTS migration | Type → live results |
| C17 | Profile page (theme, default view, export, delete account) | template, endpoints | Delete cascades, export downloads JSON |
| C18 | Mobile polish (drawer sidebar, FAB, bottom nav) | CSS, base templates | Looks correct on 360px viewport |
| C19 | New-feature tests pass; existing tests still green | tests | `uv run pytest` all green |
| C20 | README + PROGRESS final + push | docs | Complete |

## 10. Acceptance for "MVP-2 (pivot) ready"

- [ ] All 20 chunks above marked complete in PROGRESS.md
- [ ] `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest` exits 0
- [ ] Manual flow on a fresh account: register → verify → today view → add task via quick-add with `завтра !!` → it appears in Upcoming with priority p2 — works
- [ ] Calendar grid renders with task chips
- [ ] Drag-reorder persists
- [ ] Search palette finds a task
- [ ] Profile delete actually removes user + all related rows
- [ ] Mobile viewport (360 × 800) is fully usable

## 11. Out-of-scope for this pivot (later milestones)

- Sharing / multi-user collaboration
- Comments on tasks
- File attachments
- Recurring tasks (`every Monday`)
- Push notifications / native PWA install banners
- Diary parsing (Школьный портал МО, МЭШ) — re-introduced as an opt-in integration for school accounts
- Telegram / MAX bots
- Gamification (streaks, XP) — designed earlier, deferred
- Parent dashboard + paid subscription — deferred until product traction is real
- Russian Roskomnadzor PD operator registration — required before public launch with real users

## 12. Risks and how we'll handle them

| Risk | Mitigation |
|---|---|
| The chunk plan is too big for one overnight session | Each chunk independently shippable; PROGRESS.md is the resume pointer |
| Drag-reorder library quirk (Sortable.js + HTMX) breaks ordering | Server returns new ordered list; client re-applies |
| Postgres full-text Russian stemming gives weird matches | Use `simple` config as fallback; document in code |
| Tailwind via CDN bloats payload | Acceptable for MVP; build pipeline lands in C1.5 if perf is bad |
| Email sender domain not verified | README explicitly explains Resend domain limit; Brevo alternative documented |
| Subagents run away with context | We're not using subagents in this loop run — controller does the work directly |
