# Project Structure Guardrails — Design Spec

**Date:** 2026-05-08
**Status:** awaiting user review
**Goal:** prevent regressions when adding new features. Catch typical breakages (`|tojson|safe` template bugs, type errors, broken routes, stale prod) before they reach production.

## Problem statement

The user has 22 feature folders with growing surface area. Recent history shows recurring breakage classes:
- `|tojson|safe` inside HTML attributes (6+ commits fixing the same pattern across templates)
- Stale uvicorn serving old code after redeploy (`__pycache__` + multiprocessing workers persistence)
- New routes returning 404 because uvicorn didn't pick them up
- Untested cross-feature interactions

The user explicitly stated his other parallel project suffers from "add new feature → break old features" and wants to prevent this here. Scope picked: **Medium** — automated checks + template linter + minimal contracts + docs, no architectural refactor.

## Approach: pragmatic hybrid

Use standard tools where they fit (`pre-commit` framework, GitHub Actions); custom Python for project-specific checks (Jinja-linter, smoke-test). Documentation lives next to code.

## Architecture

### New files and folders

```
.github/workflows/ci.yml          ← GitHub Actions on push to master
.pre-commit-config.yaml           ← pre-commit framework config
scripts/
  ├── lint_templates.py           ← custom Jinja-linter (Python, regex-based)
  └── smoke_test.py               ← curl-checks live endpoints, exit 1 on failure
docs/
  ├── CONTRIBUTING.md             ← one-page onboarding for the repo
  └── recipes/
      ├── add-feature.md          ← step-by-step new feature with code skeletons
      ├── add-migration.md        ← Alembic-migration recipe
      ├── add-template.md         ← Jinja conventions, the gotchas, z-index ladder
      └── add-test.md             ← test patterns (TRUNCATE, conftest, asyncio)
```

### Modified files (minimal)

- `pyproject.toml` — add `pre-commit>=4.0,<5` to `[dependency-groups].dev`
- `.tmp_ssh_inspect.py` — call `python scripts/smoke_test.py https://getdoday.ru` after `/health` curl

### Untouched

- Existing `app/<feature>/*` structure — no file moves, no renames
- `tests/` layout — kept as-is
- `app/templates/*` content — linter only **reports**; fixes happen in plan-phase, not in this spec

## Component 1: Pre-commit hook (local, runs on `git commit`)

Configured via `.pre-commit-config.yaml`. Each commit triggers (in order, fail-fast):

| Check | Tool | Time | Behavior |
|---|---|---|---|
| Format | `ruff format --check` | <1s | block if drift |
| Lint | `ruff check` | <1s | block on any rule violation |
| Types | `mypy --strict app/` | 5–10s | block on type error |
| Templates | `python scripts/lint_templates.py` | <1s | block on `error`-level rule, warn otherwise |

**Pytest is NOT in pre-commit** — too slow with 310+ tests; runs in CI instead.

Setup: developer runs `uv run pre-commit install` once after clone. From then on, hooks run automatically.

Bypass: `git commit --no-verify` — discouraged but possible for emergencies.

## Component 2: GitHub Actions CI (runs on push to master + PRs)

`.github/workflows/ci.yml` defines one job:

```yaml
runs-on: ubuntu-latest
services:
  postgres:
    image: postgres:16-alpine
    env:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: schooltodo_test
    options: --health-cmd pg_isready
steps:
  - checkout
  - setup-python 3.12
  - install uv
  - uv sync --all-groups
  - uv run pre-commit run --all-files   # all checks above
  - uv run alembic upgrade head        # against TEST_DATABASE_URL
  - uv run pytest -q
```

Expected runtime: 2–3 minutes. Status badge in `README.md` (deferred — not part of this spec).

**No auto-deploy.** User keeps explicit `python .tmp_ssh_inspect.py` workflow for production redeploy.

## Component 3: Jinja template linter

`scripts/lint_templates.py` — a single file, no external deps beyond stdlib.

### Architecture

```python
# Simplified shape
@dataclass
class Rule:
    name: str
    pattern: re.Pattern
    level: Literal["error", "warning"]
    message: str

RULES: list[Rule] = [
    Rule(
        name="tojson-safe-attr",
        pattern=re.compile(r"\|\s*tojson\s*\|\s*safe(?!\s*\|\s*(e\b|forceescape))"),
        level="error",
        message="`|tojson|safe` без последующего escape ломает значение в HTML-атрибуте — используй `|tojson|forceescape`",
    ),
    Rule(
        name="small-text",
        pattern=re.compile(r"text-\[(\d+)px\]"),
        level="warning",
        message="text-[{n}px] меньше 11px — плохо читается на мобиле",
        # extra: numeric-aware filter applied in code, only flags N<11
    ),
    Rule(
        name="long-inline-script",
        pattern=re.compile(r"<script>([\s\S]*?)</script>"),
        level="warning",
        message="inline <script> > 60 строк — пора выносить в отдельный файл",
        # extra: line-count check in code
    ),
]
```

### Suppression

Comment-based, line-targeted:
```html
{# lint-ignore-next-line: small-text — это PRO-badge, ему положено #}
<span class="text-[10px] uppercase">PRO</span>
```

### Output format

Pretty-printed text with file:line:col, snippet, fix hint:
```
app/templates/foo.html:42:13: error  tojson-safe-attr
   x-data="{{ data|tojson|safe }}"
            ^^^^^^^^^^^^^^^^^^
   используй `|tojson|forceescape`

1 error, 0 warnings
```

Exit 1 if any errors; exit 0 if only warnings or clean.

### Initial rule set

v1 ships with 3 rules above. Adding more is trivial — append to `RULES` list. Rules to consider for v2: `inline-style-too-long`, `unescaped-user-input-in-attr`, `missing-aria-label`. Not in scope for v1.

## Component 4: Smoke-test

`scripts/smoke_test.py` — standalone, takes one argument (base URL).

### Endpoints checked

| Group | Path | Expected status |
|---|---|---|
| Public landing | `/` | 200 |
| Public legal | `/privacy` | 200 |
| Public pricing | `/pricing` | 200 |
| Public help | `/help` | 200 |
| Public help API | `/help/articles.json` | 200 |
| Static SEO | `/sitemap.xml` | 200 |
| Static SEO | `/robots.txt` | 200 |
| Static asset | `/og.svg` | 200 |
| Static asset | `/favicon.ico` | 200 |
| PWA | `/manifest.webmanifest` | 200 |
| PWA | `/service-worker.js` | 200 |
| Health | `/health` | 200 |
| Auth UI | `/auth/register` | 200 |
| Auth UI | `/auth/login` | 200 |
| Auth gate | `/app/today` | 401 |
| Auth gate | `/app/inbox` | 401 |
| Auth gate | `/app/calendar` | 401 |
| Auth gate | `/app/profile` | 401 |

### Failure semantics

- 5xx — fail
- 404 where 200 expected — fail
- 404 where 401 expected — fail (route disappeared from registry)
- timeout >10s — fail
- network error — fail

Exit 0 on all-green; exit 1 with summary table on any failure.

### Integration points

1. `.tmp_ssh_inspect.py` — call after `/health` curl to verify deeper endpoints actually respond
2. Manual ad-hoc — developer can run `python scripts/smoke_test.py https://getdoday.ru` anytime
3. CI — optional `smoke` job runs after `pytest`, hits the live URL (not staging — we don't have one)

## Component 5: Docs

### CONTRIBUTING.md (~80 lines)

One page covering:
- Local setup (clone → uv sync → pre-commit install → uvicorn)
- Pre-commit behavior (what runs, how to bypass)
- File layout convention (`app/<feature>/{router,service,models,schemas}.py`)
- Deploy procedure (`.tmp_ssh_inspect.py` → smoke-test confirms)
- Links to recipes/

### docs/recipes/ — 4 markdown files

1. **add-feature.md** — concrete walkthrough using a hypothetical `app/notes/` feature. Provides full code skeletons for `__init__.py`, `models.py`, `schemas.py`, `service.py`, `router.py`, `tests/test_notes.py`. Step-by-step: scaffold → register router in main.py → autogenerate migration → write tests → run pytest.

2. **add-migration.md** — Alembic flow: `alembic revision --autogenerate -m '...'` → review SQL → upgrade locally → confirm reversibility via `downgrade -1 + upgrade head`.

3. **add-template.md** — Jinja conventions:
   - Always extend `base.html` or `app_base.html`
   - JSON in attributes: **only** `|tojson|forceescape`, **never** `|tojson|safe`
   - Z-index ladder: modal `z-50`, sidebar drawer `z-40`, sidebar overlay `z-[35]`, bottom-nav `z-30`, sticky topbar `z-20`, dropdown `z-10`
   - Touch targets ≥36px (use `w-9 h-9` for icon buttons, `inline-flex items-center justify-center` for centering)
   - Suppression syntax for linter

4. **add-test.md** — tests/conftest.py provides `client` and `db_session` fixtures with TRUNCATE between tests. `pytest-asyncio` with `mode=auto` means `async def test_X(...): ...` works directly.

## Rollout plan

1. **Step 0** — implement everything in this spec in a single PR / sequence of commits.
2. **Step 1** — `uv run pre-commit run --all-files` against current codebase to surface existing violations.
3. **Step 2** — if ≤5 errors: fix inline. If >5: add allowlist to `.pre-commit-config.yaml` with TODO.md tracking, fix in follow-up PR.
4. **Step 3** — `uv run pre-commit install` activates hooks locally for the user.
5. **Step 4** — CI green on master baseline. Any future regression visible.

## Non-goals (explicit)

- No architectural refactor of `app/<feature>` folders
- No `__init__.py` re-exports / public API surface design
- No cross-feature import linter (out of "Medium" scope)
- No feature scaffolder script (`make new-feature`) — recipes/add-feature.md covers this manually
- No staging environment
- No auto-deploy on green CI
- No Windows-runner CI matrix — Linux-only
- No template AST parser — regex sufficient for our 3 rules

## Testing strategy

The new tooling itself needs verification:

- `scripts/lint_templates.py` — has its own pytest tests in `tests/test_lint_templates.py` covering: detects `|tojson|safe` correctly, ignores `|tojson|forceescape`, ignores `|tojson|safe|e` (legacy-but-correct pattern), detects `text-[8px]`, ignores suppressed lines.
- `scripts/smoke_test.py` — has tests using `httpx.MockTransport` to assert correct exit code on various scenarios.
- Pre-commit config: smoke-test by running `pre-commit run --all-files` after install — should produce expected output on a fresh clone.

## Success criteria

- A new contributor (or future-Claude) running `git clone && uv sync && pre-commit install` is fully set up.
- Adding a new feature following `recipes/add-feature.md` results in a working, tested, type-safe module without manual reference to existing features.
- The 3 most-recent regression classes (tojson-safe, stale-uvicorn, route-404) are caught by automation:
  - tojson-safe → caught by `lint_templates.py`
  - stale-uvicorn → already mitigated by `.tmp_ssh_inspect.py` `lsof:8011 + kill -9` step
  - route-404 → caught by `smoke_test.py` `/app/today expect 401 not 404` rule

## Open questions

None. Scope confirmed as Medium per user's selection. Approach A (pragmatic hybrid) approved.
