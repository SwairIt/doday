# Project Structure Guardrails — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a regression-prevention safety net (pre-commit hooks, GitHub Actions CI, custom Jinja-linter, smoke-test, and onboarding docs) so adding new features doesn't break old ones.

**Architecture:** Standard tools where they fit (`pre-commit` framework + GitHub Actions); custom Python where the project has specific concerns (`scripts/lint_templates.py` for `|tojson|safe`-class bugs, `scripts/smoke_test.py` for live endpoint health). Documentation in `docs/CONTRIBUTING.md` plus four `recipes/` files for common tasks.

**Tech Stack:** Python 3.12 + uv + ruff + mypy --strict + pytest-asyncio + pre-commit framework + GitHub Actions + httpx (for smoke-test).

**Spec:** `docs/superpowers/specs/2026-05-08-project-structure-guardrails-design.md`

---

## File Structure

```
.github/
  workflows/
    ci.yml                              ← NEW: GitHub Actions CI

.pre-commit-config.yaml                  ← NEW: pre-commit framework config

scripts/
  __init__.py                            ← NEW: makes scripts/ importable
  lint_templates.py                      ← NEW: Jinja-linter
  smoke_test.py                          ← NEW: live endpoint smoke-test

tests/
  test_lint_templates.py                 ← NEW: TDD source for linter
  test_smoke_test.py                     ← NEW: TDD source for smoke-test

docs/
  CONTRIBUTING.md                        ← NEW: one-page repo onboarding
  recipes/
    add-feature.md                       ← NEW: how to add new feature
    add-migration.md                     ← NEW: Alembic recipe
    add-template.md                      ← NEW: Jinja conventions
    add-test.md                          ← NEW: test patterns

pyproject.toml                           ← MODIFY: add pre-commit dev dep + mypy include scripts/
.tmp_ssh_inspect.py                      ← MODIFY: call smoke_test.py after redeploy
TODO.md                                  ← MODIFY (rollout): list any first-run violations
```

**Each file's responsibility:**
- `scripts/lint_templates.py` — single source of truth for template rules. Pure functions + main(). Importable by tests.
- `scripts/smoke_test.py` — single source of truth for endpoint health-check. Pure functions + main(). Importable by tests.
- `.pre-commit-config.yaml` — declares which hooks run on `git commit`.
- `.github/workflows/ci.yml` — declares CI pipeline on push.
- `docs/CONTRIBUTING.md` — entry-point doc; links to recipes.
- `docs/recipes/*.md` — one recipe per common task; self-contained.

---

## Task 1: Add `pre-commit` to dev dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Read current dev-deps block to find exact place to insert**

Run:
```bash
grep -n "dependency-groups" pyproject.toml
grep -n "dev = " pyproject.toml
```

Expected: see `[dependency-groups]` and `dev = [...]` block around lines 22-28.

- [ ] **Step 2: Add `pre-commit` to the dev list**

In `pyproject.toml`, find:
```toml
[dependency-groups]
dev = [
    "pytest>=8.3,<9",
    "pytest-asyncio>=0.25,<1",
    "ruff>=0.8,<1",
    "mypy>=1.13,<2",
]
```

Replace with:
```toml
[dependency-groups]
dev = [
    "pytest>=8.3,<9",
    "pytest-asyncio>=0.25,<1",
    "ruff>=0.8,<1",
    "mypy>=1.13,<2",
    "pre-commit>=4.0,<5",
]
```

- [ ] **Step 3: Sync the venv**

Run: `uv sync --all-groups`
Expected: installs `pre-commit` and dependencies (`identify`, `cfgv`, `nodeenv`, `virtualenv`, `pyyaml`).

- [ ] **Step 4: Verify pre-commit is importable**

Run: `uv run pre-commit --version`
Expected: prints version like `pre-commit 4.0.x`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: добавил pre-commit в dev-зависимости"
```

---

## Task 2: Create `scripts/` package skeleton

**Files:**
- Create: `scripts/__init__.py`

- [ ] **Step 1: Create scripts/ directory with __init__.py**

Create file `scripts/__init__.py` with content:
```python
"""Project scripts (linters, smoke-tests, deploy helpers).

Importable as a package so tests can `from scripts.lint_templates import ...`.
"""
```

- [ ] **Step 2: Verify import works**

Run: `uv run python -c "import scripts; print(scripts.__doc__)"`
Expected: prints the docstring without error.

- [ ] **Step 3: Commit**

```bash
git add scripts/__init__.py
git commit -m "build: scripts/ — пакет под локальные скрипты (линтер, smoke-тест)"
```

---

## Task 3: Build Jinja-linter — `tojson-safe-attr` rule (TDD)

**Files:**
- Create: `tests/test_lint_templates.py`
- Create: `scripts/lint_templates.py`

- [ ] **Step 1: Write failing tests for the tojson-safe-attr rule**

Create `tests/test_lint_templates.py`:
```python
"""Tests for scripts/lint_templates.py — Jinja template linter."""

from pathlib import Path

import pytest

from scripts.lint_templates import check_text


@pytest.fixture
def fake_path(tmp_path: Path) -> Path:
    return tmp_path / "fake.html"


def test_tojson_safe_in_attribute_is_error(fake_path: Path) -> None:
    text = '<div x-data="{{ data|tojson|safe }}"></div>'
    violations = check_text(text, fake_path)
    assert len(violations) == 1
    assert violations[0].rule.name == "tojson-safe-attr"
    assert violations[0].rule.level == "error"


def test_tojson_forceescape_is_clean(fake_path: Path) -> None:
    text = '<div x-data="{{ data|tojson|forceescape }}"></div>'
    violations = check_text(text, fake_path)
    assert violations == []


def test_tojson_safe_e_is_clean(fake_path: Path) -> None:
    """`|tojson|safe|e` is the legacy-but-correct pattern; not flagged."""
    text = '<div x-data="{{ data|tojson|safe|e }}"></div>'
    violations = check_text(text, fake_path)
    assert violations == []
```

- [ ] **Step 2: Run tests, expect ImportError**

Run: `uv run pytest tests/test_lint_templates.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.lint_templates'`.

- [ ] **Step 3: Create scripts/lint_templates.py with minimal implementation**

Create `scripts/lint_templates.py`:
```python
"""Custom Jinja-template linter — catches project-specific gotchas.

CLI:  uv run python scripts/lint_templates.py [path]
Default path: app/templates

Exit code: 1 on any error-level violation, 0 if only warnings or clean.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class Rule:
    name: str
    level: Literal["error", "warning"]
    message: str
    pattern: re.Pattern[str]
    extra_check: Callable[[re.Match[str]], bool] | None = None


@dataclass(frozen=True)
class Violation:
    file: Path
    line: int
    col: int
    rule: Rule
    snippet: str


# Rule 1: `|tojson|safe` not followed by `|e` or `|forceescape`.
# Negative lookahead skips the legitimate-but-verbose `|tojson|safe|e` form.
_TOJSON_SAFE_PATTERN = re.compile(
    r"\|\s*tojson\s*\|\s*safe(?!\s*\|\s*(?:e\b|forceescape))"
)


RULES: list[Rule] = [
    Rule(
        name="tojson-safe-attr",
        level="error",
        message=(
            "`|tojson|safe` без последующего escape ломает значение в HTML-атрибуте — "
            "используй `|tojson|forceescape`"
        ),
        pattern=_TOJSON_SAFE_PATTERN,
    ),
]


def check_text(text: str, file: Path) -> list[Violation]:
    """Apply all rules to text, return violations sorted by line."""
    violations: list[Violation] = []
    for rule in RULES:
        for match in rule.pattern.finditer(text):
            if rule.extra_check is not None and not rule.extra_check(match):
                continue
            line_no = text.count("\n", 0, match.start()) + 1
            line_start = text.rfind("\n", 0, match.start()) + 1
            col = match.start() - line_start + 1
            snippet = text.splitlines()[line_no - 1].strip() if text else ""
            violations.append(Violation(file, line_no, col, rule, snippet))
    return violations


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    root = Path(args[0]) if args else Path("app/templates")
    if not root.exists():
        print(f"path does not exist: {root}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests, expect PASS**

Run: `uv run pytest tests/test_lint_templates.py -v`
Expected: 3 tests pass.

- [ ] **Step 5: Verify linter passes ruff + mypy**

Run: `uv run ruff check scripts/lint_templates.py && uv run mypy --strict scripts/lint_templates.py`
Expected: both clean.

- [ ] **Step 6: Commit**

```bash
git add scripts/lint_templates.py tests/test_lint_templates.py
git commit -m "feat: jinja-линтер — правило tojson-safe-attr (с тестами)"
```

---

## Task 4: Add `small-text` rule + line-suppression mechanism

**Files:**
- Modify: `tests/test_lint_templates.py`
- Modify: `scripts/lint_templates.py`

- [ ] **Step 1: Add failing tests for small-text rule and suppression**

Append to `tests/test_lint_templates.py`:
```python
def test_text_8px_warns(fake_path: Path) -> None:
    text = '<span class="text-[8px]">Tiny</span>'
    violations = check_text(text, fake_path)
    assert len(violations) == 1
    assert violations[0].rule.name == "small-text"
    assert violations[0].rule.level == "warning"


def test_text_10px_warns(fake_path: Path) -> None:
    text = '<span class="text-[10px]">Almost</span>'
    violations = check_text(text, fake_path)
    assert len(violations) == 1
    assert violations[0].rule.name == "small-text"


def test_text_11px_clean(fake_path: Path) -> None:
    text = '<span class="text-[11px]">OK</span>'
    violations = check_text(text, fake_path)
    assert violations == []


def test_text_16px_clean(fake_path: Path) -> None:
    text = '<span class="text-[16px]">Large</span>'
    violations = check_text(text, fake_path)
    assert violations == []


def test_suppression_disables_warning(fake_path: Path) -> None:
    text = (
        "{# lint-ignore-next-line: small-text #}\n"
        '<span class="text-[10px]">PRO</span>'
    )
    violations = check_text(text, fake_path)
    assert violations == []


def test_suppression_only_affects_immediate_next_line(fake_path: Path) -> None:
    text = (
        "{# lint-ignore-next-line: small-text #}\n"
        "<br>\n"
        '<span class="text-[10px]">PRO</span>'
    )
    violations = check_text(text, fake_path)
    assert len(violations) == 1
```

- [ ] **Step 2: Run tests, expect failures for the new ones**

Run: `uv run pytest tests/test_lint_templates.py -v`
Expected: 6 new tests fail (rule doesn't exist yet).

- [ ] **Step 3: Add small-text rule + suppression to lint_templates.py**

Modify `scripts/lint_templates.py`. Add after the `_TOJSON_SAFE_PATTERN` block:
```python
# Rule 2: text-[Npx] where N < 11 — too small for mobile readability.
_TEXT_PX_PATTERN = re.compile(r"text-\[(\d+)px\]")


def _small_text_check(match: re.Match[str]) -> bool:
    return int(match.group(1)) < 11
```

In the `RULES` list, add:
```python
RULES: list[Rule] = [
    Rule(
        name="tojson-safe-attr",
        level="error",
        message=(
            "`|tojson|safe` без последующего escape ломает значение в HTML-атрибуте — "
            "используй `|tojson|forceescape`"
        ),
        pattern=_TOJSON_SAFE_PATTERN,
    ),
    Rule(
        name="small-text",
        level="warning",
        message=(
            "text-[<N>px] меньше 11px — плохо читается на мобиле. "
            "Если намеренно (PRO-badge, счётчик) — добавь "
            "`{# lint-ignore-next-line: small-text #}` строкой выше."
        ),
        pattern=_TEXT_PX_PATTERN,
        extra_check=_small_text_check,
    ),
]
```

Add suppression support. Above `check_text`:
```python
_SUPPRESS_PATTERN = re.compile(r"\{#\s*lint-ignore-next-line:\s*([\w,\s-]+?)\s*#\}")


def _suppressed_rules_for_line(text: str, line_no: int) -> set[str]:
    """Return rule names suppressed for the given 1-based line.

    Suppression is inline `{# lint-ignore-next-line: <names> #}` placed
    exactly on the line above the offending code. Multiple names are
    comma-separated.
    """
    if line_no < 2:
        return set()
    lines = text.splitlines()
    if line_no - 2 >= len(lines):
        return set()
    prev = lines[line_no - 2]
    m = _SUPPRESS_PATTERN.search(prev)
    if not m:
        return set()
    return {r.strip() for r in m.group(1).split(",") if r.strip()}
```

Replace `check_text` body to use suppression:
```python
def check_text(text: str, file: Path) -> list[Violation]:
    """Apply all rules to text, return violations sorted by line."""
    violations: list[Violation] = []
    for rule in RULES:
        for match in rule.pattern.finditer(text):
            if rule.extra_check is not None and not rule.extra_check(match):
                continue
            line_no = text.count("\n", 0, match.start()) + 1
            line_start = text.rfind("\n", 0, match.start()) + 1
            col = match.start() - line_start + 1
            if rule.name in _suppressed_rules_for_line(text, line_no):
                continue
            snippet = text.splitlines()[line_no - 1].strip() if text else ""
            violations.append(Violation(file, line_no, col, rule, snippet))
    return violations
```

- [ ] **Step 4: Run tests, expect all pass**

Run: `uv run pytest tests/test_lint_templates.py -v`
Expected: 9 tests pass.

- [ ] **Step 5: Verify ruff + mypy still green**

Run: `uv run ruff check scripts/lint_templates.py && uv run mypy --strict scripts/lint_templates.py`
Expected: both clean.

- [ ] **Step 6: Commit**

```bash
git add scripts/lint_templates.py tests/test_lint_templates.py
git commit -m "feat: jinja-линтер — правило small-text + suppression-механизм"
```

---

## Task 5: Add `long-inline-script` rule

**Files:**
- Modify: `tests/test_lint_templates.py`
- Modify: `scripts/lint_templates.py`

- [ ] **Step 1: Add failing tests for long-inline-script rule**

Append to `tests/test_lint_templates.py`:
```python
def test_long_script_warns(fake_path: Path) -> None:
    body = "\n".join(["x = 1;"] * 70)
    text = f"<script>{body}</script>"
    violations = check_text(text, fake_path)
    assert len(violations) == 1
    assert violations[0].rule.name == "long-inline-script"
    assert violations[0].rule.level == "warning"


def test_short_script_clean(fake_path: Path) -> None:
    body = "\n".join(["x = 1;"] * 10)
    text = f"<script>{body}</script>"
    violations = check_text(text, fake_path)
    assert violations == []


def test_script_at_60_lines_clean(fake_path: Path) -> None:
    """60 lines is the boundary — only >60 warns."""
    body = "\n".join(["x = 1;"] * 60)
    text = f"<script>{body}</script>"
    violations = check_text(text, fake_path)
    assert violations == []
```

- [ ] **Step 2: Run tests, expect failures for the new ones**

Run: `uv run pytest tests/test_lint_templates.py -v`
Expected: 3 new tests fail.

- [ ] **Step 3: Add long-inline-script rule**

In `scripts/lint_templates.py`, add after the `_small_text_check` function:
```python
# Rule 3: inline <script> longer than 60 lines — extract to partial.
_SCRIPT_PATTERN = re.compile(r"<script[^>]*>(.*?)</script>", re.DOTALL)


def _long_script_check(match: re.Match[str]) -> bool:
    return match.group(1).count("\n") > 60
```

Append to the `RULES` list:
```python
    Rule(
        name="long-inline-script",
        level="warning",
        message=(
            "inline <script> длиннее 60 строк — пора выносить в отдельный "
            "_partials/-файл или statics. Большая JS-логика в шаблоне ломается тихо."
        ),
        pattern=_SCRIPT_PATTERN,
        extra_check=_long_script_check,
    ),
```

- [ ] **Step 4: Run tests, expect all pass**

Run: `uv run pytest tests/test_lint_templates.py -v`
Expected: 12 tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/lint_templates.py tests/test_lint_templates.py
git commit -m "feat: jinja-линтер — правило long-inline-script"
```

---

## Task 6: CLI for the linter (output format + main + directory walk)

**Files:**
- Modify: `tests/test_lint_templates.py`
- Modify: `scripts/lint_templates.py`

- [ ] **Step 1: Add tests for CLI output / directory walking**

Append to `tests/test_lint_templates.py`:
```python
from scripts.lint_templates import format_violation, lint_directory


def test_format_violation_includes_file_line_col_message(fake_path: Path) -> None:
    text = '<div x-data="{{ data|tojson|safe }}"></div>'
    violations = check_text(text, fake_path)
    assert len(violations) == 1
    output = format_violation(violations[0])
    assert str(fake_path) in output
    assert ":1:" in output  # line number
    assert "tojson-safe-attr" in output
    assert "error" in output


def test_lint_directory_walks_html_files(tmp_path: Path) -> None:
    bad = tmp_path / "bad.html"
    bad.write_text('<div x-data="{{ data|tojson|safe }}"></div>')
    good = tmp_path / "good.html"
    good.write_text('<div x-data="{{ data|tojson|forceescape }}"></div>')
    nested = tmp_path / "subdir" / "nested.html"
    nested.parent.mkdir()
    nested.write_text('<span class="text-[8px]">tiny</span>')

    violations = lint_directory(tmp_path)
    rule_names = {v.rule.name for v in violations}
    assert rule_names == {"tojson-safe-attr", "small-text"}


def test_lint_directory_ignores_non_html(tmp_path: Path) -> None:
    py = tmp_path / "x.py"
    py.write_text("data|tojson|safe")  # would match rule, but .py not scanned
    violations = lint_directory(tmp_path)
    assert violations == []


def test_main_returns_1_on_errors(tmp_path: Path) -> None:
    from scripts.lint_templates import main

    bad = tmp_path / "bad.html"
    bad.write_text('<div x-data="{{ data|tojson|safe }}"></div>')
    rc = main([str(tmp_path)])
    assert rc == 1


def test_main_returns_0_on_clean(tmp_path: Path) -> None:
    from scripts.lint_templates import main

    good = tmp_path / "good.html"
    good.write_text('<div x-data="{{ data|tojson|forceescape }}"></div>')
    rc = main([str(tmp_path)])
    assert rc == 0


def test_main_returns_0_on_warnings_only(tmp_path: Path) -> None:
    """Warnings shouldn't block — only errors."""
    from scripts.lint_templates import main

    warn = tmp_path / "warn.html"
    warn.write_text('<span class="text-[8px]">tiny</span>')
    rc = main([str(tmp_path)])
    assert rc == 0
```

- [ ] **Step 2: Run tests, expect failures**

Run: `uv run pytest tests/test_lint_templates.py -v`
Expected: 6 new tests fail.

- [ ] **Step 3: Implement format_violation, check_file, lint_directory, main**

In `scripts/lint_templates.py`, add after `check_text`:
```python
def check_file(path: Path) -> list[Violation]:
    """Lint a single .html file."""
    text = path.read_text(encoding="utf-8")
    return check_text(text, path)


def lint_directory(root: Path) -> list[Violation]:
    """Lint all .html files under root (recursive)."""
    violations: list[Violation] = []
    for path in sorted(root.rglob("*.html")):
        violations.extend(check_file(path))
    return violations


def format_violation(v: Violation) -> str:
    """Pretty-print one violation: path, line:col, level, name, snippet, message."""
    return (
        f"{v.file}:{v.line}:{v.col}: {v.rule.level}  {v.rule.name}\n"
        f"   {v.snippet}\n"
        f"   {v.rule.message}\n"
    )
```

Replace the existing `main` body:
```python
def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    root = Path(args[0]) if args else Path("app/templates")
    if not root.exists():
        print(f"path does not exist: {root}", file=sys.stderr)
        return 2

    violations = lint_directory(root)
    if not violations:
        print(f"checked {root} — all clean")
        return 0

    errors = [v for v in violations if v.rule.level == "error"]
    warnings = [v for v in violations if v.rule.level == "warning"]
    for v in violations:
        print(format_violation(v))
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0
```

- [ ] **Step 4: Run tests, expect all pass**

Run: `uv run pytest tests/test_lint_templates.py -v`
Expected: 18 tests pass.

- [ ] **Step 5: Run linter against real templates as a smoke-check**

Run: `uv run python scripts/lint_templates.py app/templates`
Expected: prints `0 error(s), N warning(s)` (warnings expected — there are many `text-[10px]` in real templates). N likely 30-60.

- [ ] **Step 6: Verify ruff + mypy clean**

Run: `uv run ruff check scripts/ tests/test_lint_templates.py && uv run mypy --strict scripts/`
Expected: both clean.

- [ ] **Step 7: Commit**

```bash
git add scripts/lint_templates.py tests/test_lint_templates.py
git commit -m "feat: jinja-линтер — CLI, обход директории, format_violation, exit-codes"
```

---

## Task 7: Build smoke-test (TDD)

**Files:**
- Create: `tests/test_smoke_test.py`
- Create: `scripts/smoke_test.py`

- [ ] **Step 1: Write failing tests using httpx.MockTransport**

Create `tests/test_smoke_test.py`:
```python
"""Tests for scripts/smoke_test.py — live-endpoint smoke-test."""

import httpx

from scripts.smoke_test import Endpoint, check_endpoints


def test_all_green_returns_no_failures() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    endpoints = [Endpoint("/", 200, "landing")]
    results = check_endpoints("https://example.com", endpoints, client=client)

    assert len(results) == 1
    assert results[0].actual_status == 200
    assert results[0].actual_status == results[0].endpoint.expected_status


def test_404_on_expected_200_marks_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    endpoints = [Endpoint("/", 200, "landing")]
    results = check_endpoints("https://example.com", endpoints, client=client)

    assert results[0].actual_status == 404
    assert results[0].actual_status != results[0].endpoint.expected_status


def test_404_where_401_expected_marks_failure() -> None:
    """Critical: protected route disappeared from registry."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    endpoints = [Endpoint("/app/today", 401, "auth-gate")]
    results = check_endpoints("https://example.com", endpoints, client=client)

    assert results[0].actual_status == 404
    assert results[0].actual_status != results[0].endpoint.expected_status


def test_401_on_protected_endpoint_is_success() -> None:
    """401 on /app/* means auth gate works AND route is registered."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    endpoints = [Endpoint("/app/today", 401, "auth-gate")]
    results = check_endpoints("https://example.com", endpoints, client=client)

    assert results[0].actual_status == 401
    assert results[0].actual_status == results[0].endpoint.expected_status


def test_timeout_marks_failure_with_error_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("simulated timeout", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    endpoints = [Endpoint("/", 200, "landing")]
    results = check_endpoints("https://example.com", endpoints, client=client)

    assert results[0].actual_status is None
    assert results[0].error is not None
    assert "Timeout" in results[0].error


def test_does_not_follow_redirects() -> None:
    """A redirect on a 200-expected endpoint is suspicious — keep raw status."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "/other"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    endpoints = [Endpoint("/", 200, "landing")]
    results = check_endpoints("https://example.com", endpoints, client=client)

    assert results[0].actual_status == 302  # not silently followed to 200
```

- [ ] **Step 2: Run tests, expect ImportError**

Run: `uv run pytest tests/test_smoke_test.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.smoke_test'`.

- [ ] **Step 3: Implement scripts/smoke_test.py**

Create `scripts/smoke_test.py`:
```python
"""Live HTTP smoke-test — verifies key endpoints respond as expected.

CLI:  uv run python scripts/smoke_test.py [base_url]
Default base_url: https://getdoday.ru

Exit code: 0 if all green, 1 on any failure (with summary table on stderr).
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class Endpoint:
    path: str
    expected_status: int
    label: str


@dataclass(frozen=True)
class Result:
    endpoint: Endpoint
    actual_status: int | None  # None if request failed before getting a response
    error: str | None


# Endpoints checked by `main()`. Adding new public routes? Add them here too.
ENDPOINTS: list[Endpoint] = [
    Endpoint("/", 200, "landing"),
    Endpoint("/privacy", 200, "privacy"),
    Endpoint("/pricing", 200, "pricing"),
    Endpoint("/help", 200, "help"),
    Endpoint("/help/articles.json", 200, "help-articles"),
    Endpoint("/sitemap.xml", 200, "sitemap"),
    Endpoint("/robots.txt", 200, "robots"),
    Endpoint("/og.svg", 200, "og-image"),
    Endpoint("/favicon.ico", 200, "favicon"),
    Endpoint("/manifest.webmanifest", 200, "pwa-manifest"),
    Endpoint("/service-worker.js", 200, "pwa-sw"),
    Endpoint("/health", 200, "health"),
    Endpoint("/auth/register", 200, "register-page"),
    Endpoint("/auth/login", 200, "login-page"),
    Endpoint("/app/today", 401, "auth-gate-today"),
    Endpoint("/app/inbox", 401, "auth-gate-inbox"),
    Endpoint("/app/calendar", 401, "auth-gate-calendar"),
    Endpoint("/app/profile", 401, "auth-gate-profile"),
]


def check_endpoints(
    base_url: str,
    endpoints: Iterable[Endpoint],
    client: httpx.Client | None = None,
) -> list[Result]:
    """GET every endpoint, collect Result. Caller may pass a pre-built client
    (used in tests with MockTransport)."""
    base_url = base_url.rstrip("/")
    own_client = client is None
    if client is None:
        client = httpx.Client(timeout=10.0, follow_redirects=False)
    results: list[Result] = []
    try:
        for ep in endpoints:
            url = base_url + ep.path
            try:
                resp = client.get(url)
                results.append(Result(ep, resp.status_code, None))
            except (httpx.TimeoutException, httpx.RequestError) as e:
                results.append(Result(ep, None, f"{type(e).__name__}: {e}"))
    finally:
        if own_client:
            client.close()
    return results


def format_result(r: Result) -> str:
    if r.actual_status is None:
        return f"  ✗  {r.endpoint.path:32}  {r.error}"
    if r.actual_status == r.endpoint.expected_status:
        return f"  ✓  {r.endpoint.path:32}  {r.actual_status}"
    return (
        f"  ✗  {r.endpoint.path:32}  got {r.actual_status}, "
        f"expected {r.endpoint.expected_status}"
    )


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    base_url = args[0] if args else "https://getdoday.ru"
    print(f"smoke test against {base_url}\n")

    results = check_endpoints(base_url, ENDPOINTS)
    failed = [
        r
        for r in results
        if r.actual_status is None or r.actual_status != r.endpoint.expected_status
    ]

    for r in results:
        print(format_result(r))

    print()
    if failed:
        print(f"{len(failed)} of {len(results)} endpoints failed", file=sys.stderr)
        return 1
    print(f"all {len(results)} green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests, expect all pass**

Run: `uv run pytest tests/test_smoke_test.py -v`
Expected: 6 tests pass.

- [ ] **Step 5: Run smoke-test against live prod**

Run: `uv run python scripts/smoke_test.py https://getdoday.ru`
Expected: all 18 endpoints green, exit 0.

- [ ] **Step 6: Verify ruff + mypy clean**

Run: `uv run ruff check scripts/smoke_test.py tests/test_smoke_test.py && uv run mypy --strict scripts/smoke_test.py`
Expected: both clean.

- [ ] **Step 7: Commit**

```bash
git add scripts/smoke_test.py tests/test_smoke_test.py
git commit -m "feat: smoke-test — проверка живых endpoint'ов прода (с тестами на MockTransport)"
```

---

## Task 8: Configure pre-commit framework

**Files:**
- Create: `.pre-commit-config.yaml`

- [ ] **Step 1: Create .pre-commit-config.yaml**

Create `.pre-commit-config.yaml`:
```yaml
# pre-commit hooks. Install once after clone: `uv run pre-commit install`.
# Each hook runs on `git commit` against changed files.
# Bypass (only for emergencies): `git commit --no-verify`.

repos:
  - repo: local
    hooks:
      - id: ruff-format
        name: ruff format
        entry: uv run ruff format
        language: system
        types: [python]

      - id: ruff-check
        name: ruff check
        entry: uv run ruff check --fix
        language: system
        types: [python]

      - id: mypy
        name: mypy --strict
        entry: uv run mypy --strict app/ scripts/
        language: system
        pass_filenames: false
        types: [python]

      - id: lint-templates
        name: lint Jinja templates
        entry: uv run python scripts/lint_templates.py
        language: system
        pass_filenames: false
        files: ^app/templates/.*\.html$
```

- [ ] **Step 2: Verify pre-commit config is valid YAML**

Run: `uv run pre-commit validate-config`
Expected: no output, exit 0 (silently valid).

- [ ] **Step 3: Run all hooks against entire repo as baseline**

Run: `uv run pre-commit run --all-files`
Expected: ruff-format and ruff-check pass (we keep them green), mypy passes, lint-templates probably reports warnings (not errors) for existing `text-[10px]` usages.

If any hook errors: stop, capture output, fix the underlying issue (or document violations in TODO.md and adjust scope).

- [ ] **Step 4: Install hooks for local commits**

Run: `uv run pre-commit install`
Expected: prints `pre-commit installed at .git/hooks/pre-commit`.

- [ ] **Step 5: Verify hooks fire on commit (smoke-check)**

Touch a Python file (e.g., `app/main.py` — add a blank line, then remove it):
```bash
echo "" >> app/main.py && git add app/main.py && git diff --cached
```

Then run: `git commit -m "test: pre-commit smoke"` — but be ready to abort.
Expected: pre-commit runs all 4 hooks. If everything passes, the commit goes through.
Roll back: `git reset HEAD~1 && git checkout app/main.py`.

- [ ] **Step 6: Commit the config**

```bash
git add .pre-commit-config.yaml
git commit -m "build: pre-commit конфиг (ruff + mypy + jinja-linter)"
```

---

## Task 9: Wire smoke-test into the deploy script

**Files:**
- Modify: `.tmp_ssh_inspect.py`

- [ ] **Step 1: Read current deploy script tail**

Run: `tail -10 .tmp_ssh_inspect.py`
Expected: see the last block ending with the `/health` curl + `c.close()`.

- [ ] **Step 2: Modify .tmp_ssh_inspect.py to invoke smoke-test after `/health`**

Find:
```python
time.sleep(4)
print(">>> /health")
stdin, stdout, stderr = c.exec_command(
    "curl -sS -m 5 http://127.0.0.1:8011/health", timeout=10
)
print(stdout.read().decode("utf-8", errors="replace").encode("ascii", "replace").decode("ascii"))

c.close()
```

Replace with:
```python
time.sleep(4)
print(">>> /health")
stdin, stdout, stderr = c.exec_command(
    "curl -sS -m 5 http://127.0.0.1:8011/health", timeout=10
)
print(stdout.read().decode("utf-8", errors="replace").encode("ascii", "replace").decode("ascii"))

c.close()

print(">>> external smoke-test https://getdoday.ru")
import subprocess
rc = subprocess.run(
    ["uv", "run", "python", "scripts/smoke_test.py", "https://getdoday.ru"],
    check=False,
).returncode
if rc != 0:
    print("!!! smoke-test failed — investigate before continuing", flush=True)
    raise SystemExit(rc)
print(">>> smoke-test green")
```

- [ ] **Step 3: Verify the script still parses (syntax check only)**

Run: `uv run python -c "import ast; ast.parse(open('.tmp_ssh_inspect.py', encoding='utf-8').read())"`
Expected: no output, exit 0.

- [ ] **Step 4: Commit**

```bash
git add .tmp_ssh_inspect.py
git commit -m "build: deploy-скрипт зовёт smoke-test после /health"
```

---

## Task 10: GitHub Actions CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create .github/workflows/ci.yml**

Create `.github/workflows/ci.yml`:
```yaml
name: CI

on:
  push:
    branches: [master]
  pull_request:
    branches: [master]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: schooltodo_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    env:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/schooltodo_test
      TEST_DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/schooltodo_test
      APP_SECRET_KEY: ci-test-secret-key-needs-to-be-at-least-32-chars
      APP_ENV: test
      APP_BASE_URL: http://localhost:8000

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: latest
          enable-cache: true

      - name: Setup Python 3.12
        run: uv python install 3.12

      - name: Sync dependencies
        run: uv sync --all-groups

      - name: Pre-commit checks (ruff + mypy + jinja-lint)
        run: uv run pre-commit run --all-files --show-diff-on-failure

      - name: Apply Alembic migrations to test DB
        run: uv run alembic upgrade head

      - name: Run pytest
        run: uv run pytest -q
```

- [ ] **Step 2: Verify YAML is valid**

Run: `uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
Expected: no output, exit 0.

- [ ] **Step 3: Commit and push to trigger first CI run**

```bash
git add .github/workflows/ci.yml
git commit -m "build: GitHub Actions CI — pre-commit + alembic + pytest на push"
TOKEN=$(grep '^TOKEN=' .env | cut -d= -f2- | tr -d '\r\n')
git push "https://x-access-token:${TOKEN}@github.com/SwairIt/SchoolProject.git" master
```

- [ ] **Step 4: Watch first CI run on GitHub**

Open: `https://github.com/SwairIt/SchoolProject/actions`
Expected: workflow `CI` is running. Click into it.

If it fails:
- Read the failing step's log
- Common causes: missing env var, mypy strict on test files (already excluded but verify), alembic migration assumes a config we didn't provide
- Fix the root cause in a follow-up commit, do not relax CI to make it pass

- [ ] **Step 5: Confirm CI green**

Run (after waiting ~3 min): `gh run list --limit 1` (if `gh` CLI installed) or check the GitHub UI.
Expected: latest run on master is `success`.

If green: done. If still red after 2 fix attempts: stop and escalate to user with the failing log.

---

## Task 11: Write CONTRIBUTING.md

**Files:**
- Create: `docs/CONTRIBUTING.md`

- [ ] **Step 1: Create the contributing doc**

Create `docs/CONTRIBUTING.md`:
```markdown
# Contributing to Doday

Это короткая шпаргалка для тех, кто работает над репозиторием — как клонировать, как добавить фичу, как деплоить.

## Старт

```bash
git clone https://github.com/SwairIt/SchoolProject.git
cd SchoolProject
uv sync --all-groups          # ставит app + dev зависимости
cp .env.example .env          # редактируй: DATABASE_URL, APP_SECRET_KEY и т.д.
uv run alembic upgrade head   # миграции на твоей локальной БД
uv run pre-commit install     # включает pre-commit hooks (один раз)
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Открой `http://127.0.0.1:8000` — должна показаться лендинг-страница.

## Перед коммитом

Pre-commit запустится автоматически на `git commit`. Он гоняет:

- `ruff format` — формат
- `ruff check` — линт
- `mypy --strict` — типы
- `scripts/lint_templates.py` — шаблонные правила (`|tojson|safe` в атрибутах и т.д.)

Если что-то падает — фикси и коммить заново. Никогда не используй `--no-verify`, кроме экстренных случаев.

Pytest в pre-commit **не** входит (310+ тестов = слишком долго). Гонять надо вручную:
```bash
uv run pytest -q                          # все тесты
uv run pytest tests/test_<feature>.py -v  # точечно
```

## Структура

```
app/<feature>/
  __init__.py
  router.py      # FastAPI endpoints
  service.py     # бизнес-логика (чистые async-функции, принимают AsyncSession)
  models.py      # SQLAlchemy ORM-модели
  schemas.py     # Pydantic v2 модели для I/O
  templates_data.py  # (опционально) встроенные данные (шаблоны проектов и т.п.)

app/templates/         # Jinja2 шаблоны
  base.html            # лендинг + auth shell
  app_base.html        # /app/* shell с sidebar + topbar
  _partials/           # переиспользуемые куски (task_row, modal'ы, и т.д.)
  app/<page>.html      # /app/<page> страницы
  auth/<page>.html     # /auth/<page> страницы

tests/                 # pytest файлы — один на feature
  conftest.py          # общие фикстуры; TRUNCATE между функциями

scripts/               # локальные утилиты (линтер, smoke-тест)
docs/                  # CONTRIBUTING + recipes
docs/superpowers/      # специи + планы
alembic/               # миграции БД
deploy/                # nginx, systemd, скрипты деплоя
```

## Как сделать N

См. `docs/recipes/`:

- [add-feature.md](recipes/add-feature.md) — добавить новую фичу с router/service/models/schemas/tests
- [add-migration.md](recipes/add-migration.md) — Alembic-миграция
- [add-template.md](recipes/add-template.md) — Jinja-шаблон без типичных багов
- [add-test.md](recipes/add-test.md) — паттерны тестирования

## Деплой

Прод — Yesbeat hosting, uvicorn на `127.0.0.1:8011`, FastPanel reverse-proxy за nginx + Let's Encrypt.

```bash
python .tmp_ssh_inspect.py    # git pull + clear pyc + restart uvicorn + smoke-test
```

После redeploy скрипт сам проверяет 18 ключевых endpoint'ов через `scripts/smoke_test.py`. Если что-то 404/5xx — падает с понятным выводом.

## Качество

- Ruff правила: `E, F, I, UP, B, S, A, RUF` (см. `pyproject.toml`)
- Mypy `--strict`, без `# type: ignore` без комментария-объяснения
- Pydantic v2 для всего, что пересекает границу
- Pytest-asyncio mode=auto, TRUNCATE между функциями (см. `tests/conftest.py`)

## Git

- Коммиты в master напрямую, без фича-бранчей (один разработчик пока)
- Сообщения коммитов на русском, прошедшее время («добавил X», «исправил Y»)
- Email коммита: `112168281+SwairIt@users.noreply.github.com`
- PAT в `.env` как `TOKEN`, для пушей через одноразовый URL (см. CLAUDE.md)
```

- [ ] **Step 2: Verify markdown renders without syntax errors**

Run: `uv run python -c "import pathlib; print(len(pathlib.Path('docs/CONTRIBUTING.md').read_text(encoding='utf-8')))"`
Expected: prints char count, no error.

- [ ] **Step 3: Commit**

```bash
git add docs/CONTRIBUTING.md
git commit -m "docs: CONTRIBUTING.md — одностраничная шпаргалка по репо"
```

---

## Task 12: Recipe — add-feature.md

**Files:**
- Create: `docs/recipes/add-feature.md`

- [ ] **Step 1: Create the recipe**

Create `docs/recipes/add-feature.md`:
```markdown
# Recipe: добавить новую фичу

Допустим, нужна фича `notes` — заметки, не привязанные к задачам. Шаги:

## 1. Создать пакет фичи

```
app/notes/
  __init__.py
  models.py
  schemas.py
  service.py
  router.py
```

`app/notes/__init__.py`:
```python
"""Notes feature — standalone notes, no task-linkage."""
```

`app/notes/models.py`:
```python
"""SQLAlchemy ORM model for notes."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

`app/notes/schemas.py`:
```python
"""Pydantic schemas for notes I/O."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = ""


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = None


class NoteOut(BaseModel):
    id: UUID
    title: str
    body: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

`app/notes/service.py`:
```python
"""Business logic for notes — pure async functions, no FastAPI deps."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.notes.models import Note


class NoteNotFound(Exception):
    """Raised when looking up a note that doesn't exist or isn't owned by user."""


async def list_notes(session: AsyncSession, user_id: UUID) -> list[Note]:
    result = await session.execute(
        select(Note).where(Note.user_id == user_id).order_by(Note.updated_at.desc())
    )
    return list(result.scalars().all())


async def create_note(
    session: AsyncSession, user_id: UUID, *, title: str, body: str
) -> Note:
    note = Note(user_id=user_id, title=title, body=body)
    session.add(note)
    await session.commit()
    await session.refresh(note)
    return note


async def get_note(session: AsyncSession, user_id: UUID, note_id: UUID) -> Note:
    note = await session.get(Note, note_id)
    if note is None or note.user_id != user_id:
        raise NoteNotFound(str(note_id))
    return note
```

`app/notes/router.py`:
```python
"""Notes HTTP endpoints — JSON CRUD."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.auth.deps import DbSession, RequiredUser
from app.notes.schemas import NoteCreate, NoteOut, NoteUpdate
from app.notes.service import NoteNotFound, create_note, get_note, list_notes

router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.get("", response_model=list[NoteOut])
async def list_endpoint(user: RequiredUser, session: DbSession) -> list[NoteOut]:
    notes = await list_notes(session, user.id)
    return [NoteOut.model_validate(n) for n in notes]


@router.post("", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
async def create_endpoint(
    payload: NoteCreate, user: RequiredUser, session: DbSession
) -> NoteOut:
    note = await create_note(session, user.id, title=payload.title, body=payload.body)
    return NoteOut.model_validate(note)


@router.get("/{note_id}", response_model=NoteOut)
async def get_endpoint(
    note_id: UUID, user: RequiredUser, session: DbSession
) -> NoteOut:
    try:
        note = await get_note(session, user.id, note_id)
    except NoteNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "заметка не найдена") from e
    return NoteOut.model_validate(note)
```

## 2. Зарегистрировать router

В `app/main.py`, рядом с другими `include_router(...)`, добавь:
```python
from app.notes.router import router as notes_router
# ...
app.include_router(notes_router)
```

## 3. Создать миграцию

```bash
uv run alembic revision --autogenerate -m "notes: initial table"
```

Откроется файл `alembic/versions/<hash>_notes_initial_table.py`. Проверь:
- `op.create_table('notes', ...)` — присутствует
- ForeignKey на `users.id` с `ondelete='CASCADE'`
- Индекс на `user_id`

Применить локально:
```bash
uv run alembic upgrade head
```

Проверить reversibility:
```bash
uv run alembic downgrade -1
uv run alembic upgrade head
```

## 4. Написать тесты

См. [add-test.md](add-test.md) для паттернов. Минимум — `tests/test_notes.py` с 4 тестами:

```python
"""Tests for app/notes/."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_note_returns_201_with_payload(
    auth_client: AsyncClient,
) -> None:
    resp = await auth_client.post("/api/notes", json={"title": "first", "body": "hello"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "first"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_notes_returns_users_own_notes(auth_client: AsyncClient) -> None:
    await auth_client.post("/api/notes", json={"title": "n1", "body": ""})
    await auth_client.post("/api/notes", json={"title": "n2", "body": ""})
    resp = await auth_client.get("/api/notes")
    assert resp.status_code == 200
    titles = {n["title"] for n in resp.json()}
    assert titles == {"n1", "n2"}


@pytest.mark.asyncio
async def test_get_other_users_note_returns_404(
    auth_client: AsyncClient, second_auth_client: AsyncClient
) -> None:
    created = await auth_client.post("/api/notes", json={"title": "private", "body": ""})
    note_id = created.json()["id"]
    resp = await second_auth_client.get(f"/api/notes/{note_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_unauthenticated_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/api/notes")
    assert resp.status_code == 401
```

(Фикстуры `auth_client`, `second_auth_client`, `client` уже определены в `tests/conftest.py`.)

## 5. Прогон

```bash
uv run pytest tests/test_notes.py -v
uv run mypy --strict app/notes/
uv run ruff check app/notes/ tests/test_notes.py
```

Все три должны быть зелёными.

## 6. Smoke-тест на проде после деплоя

Если у фичи есть публичный URL — добавь в `scripts/smoke_test.py` в `ENDPOINTS`:
```python
Endpoint("/api/notes", 401, "auth-gate-notes"),
```

(401 потому что без токена.) Чтобы знать что роут зарегистрирован после redeploy.

## 7. Коммит

```bash
git add app/notes/ tests/test_notes.py alembic/versions/<hash>*.py
# (если поменял scripts/smoke_test.py — добавь и его)
git commit -m "feat: notes — стандалон-заметки + CRUD-эндпоинты + миграция"
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/recipes/add-feature.md
git commit -m "docs: recipe — как добавить новую feature по канону"
```

---

## Task 13: Recipe — add-migration.md

**Files:**
- Create: `docs/recipes/add-migration.md`

- [ ] **Step 1: Create the recipe**

Create `docs/recipes/add-migration.md`:
```markdown
# Recipe: добавить миграцию БД

## Создать ревизию

```bash
uv run alembic revision --autogenerate -m "<feature>: <что-делает>"
```

Пример сообщения: `"notes: add archived flag column"`.

Файл создаётся в `alembic/versions/<hash>_<message>.py`.

## Проверить SQL

`alembic --autogenerate` НЕ всегда правильно угадывает изменения. Открой файл и убедись:

- `op.create_table` — все нужные столбцы, типы, FK, индексы есть
- `op.alter_column` — `nullable` правильное (если меняешь existing column на NOT NULL — нужен default или backfill)
- Индексы создаются после столбцов, не до
- ENUM-типы создаются явно (`postgresql.ENUM(...).create(op.get_bind())`)

Если автоген сгенерировал что-то не то — отредактируй вручную, это нормально.

## Применить локально

```bash
uv run alembic upgrade head
```

Если падает — фикси миграцию или модель.

## Проверить reversibility

```bash
uv run alembic downgrade -1
uv run alembic upgrade head
```

Если `downgrade` падает — допиши `op.drop_table` / `op.drop_column` руками в `def downgrade()`.

## Backfill данных

Если миграция требует backfill (например, заполнить новый NOT NULL столбец на существующих строках), используй чистый SQL внутри `def upgrade()`:

```python
def upgrade() -> None:
    op.add_column("users", sa.Column("trial_ends_at", sa.DateTime(timezone=True)))
    op.execute("UPDATE users SET trial_ends_at = NOW() + INTERVAL '14 days' WHERE trial_ends_at IS NULL")
    op.alter_column("users", "trial_ends_at", nullable=False)
```

## Прод-деплой

После пуша на master, на сервере:
```bash
ssh getdoday@getdoday.ru
cd /var/www/getdoday/data/www/getdoday.ru/app
uv run alembic upgrade head
```

(Или встроить в `.tmp_ssh_inspect.py` — но обычно миграции редкие, проще руками.)

## Откат на проде если миграция сломала

```bash
uv run alembic downgrade -1
git revert HEAD     # откатить код-коммит
git push ...
python .tmp_ssh_inspect.py    # redeploy откаченного кода
```

## Анти-паттерны

- ❌ Не редактировать уже применённую миграцию (если она в master + на проде) — делай новую
- ❌ Не использовать `import` приложения внутри миграции (модели могут поменяться, миграция должна быть статичной)
- ❌ Не делать `DROP TABLE` без бэкапа БД сначала
```

- [ ] **Step 2: Commit**

```bash
git add docs/recipes/add-migration.md
git commit -m "docs: recipe — Alembic-миграции, проверка reversibility, backfill"
```

---

## Task 14: Recipe — add-template.md

**Files:**
- Create: `docs/recipes/add-template.md`

- [ ] **Step 1: Create the recipe**

Create `docs/recipes/add-template.md`:
```markdown
# Recipe: добавить Jinja-шаблон

## Где живут шаблоны

```
app/templates/
  base.html               # для public-страниц (лендинг, /auth/*, /privacy)
  app_base.html           # для /app/* (sidebar + topbar + bottom-nav)
  _partials/              # переиспользуемые куски, начинаются с _
  app/<page>.html         # /app/<page>
  auth/<page>.html        # /auth/<page>
  help/<page>.html        # /help/<page>
```

## Минимальный новый шаблон

```html
{% extends "app_base.html" %}
{% block title %}Заметки — Doday{% endblock %}
{% block view_title %}Заметки{% endblock %}
{% block content %}

<h1 class="text-3xl font-bold mb-4">Заметки</h1>

<div class="card p-6">
  <p class="text-[var(--text-muted)]">Здесь будут твои заметки.</p>
</div>

{% endblock %}
```

`{% extends "app_base.html" %}` даёт sidebar + topbar + bottom-nav и Yandex.Metrika.
`{% extends "base.html" %}` — голый shell для лендинга и auth-страниц.

## Регистрация view

В `app/views/router.py` (или соответствующем `app/<feature>/router.py`):

```python
@router.get("/app/notes", response_class=HTMLResponse)
async def notes_view(
    request: Request, user: RequiredUser, session: DbSession
) -> HTMLResponse:
    notes = await list_notes(session, user.id)
    return templates.TemplateResponse(
        request,
        "app/notes.html",
        {"notes": notes, "current_user": user, "current_view": "notes"},
    )
```

## JSON в HTML-атрибуте

**Только** через `|tojson|forceescape`:

```html
<div x-data="{ items: {{ items|tojson|forceescape }} }">
```

**Никогда** так:
```html
<!-- ✗ ЛОМАЕТСЯ — кавычки внутри JSON разрушают атрибут -->
<div x-data="{ items: {{ items|tojson|safe }} }">
```

Pre-commit поймает `|tojson|safe` без последующего escape — увидишь ошибку.

## Z-index ладдер

Чтобы модал перекрывал sidebar, sidebar перекрывал bottom-nav, и так далее — придерживайся:

| Слой | Z | Файл |
|---|---|---|
| Модал (новый проект, фильтр-эдитор, апгрейд) | `z-50` | `_partials/*_modal.html` |
| Поиск/Cmd-K палитра | `z-50` | `_partials/search_palette.html` |
| Sidebar drawer на мобиле | `z-40` | `_partials/sidebar.html` |
| Bulk-bar | `z-40` | `_partials/bulk_bar.html` |
| Sidebar overlay (затемнение под drawer'ом) | `z-[35]` | `_partials/sidebar.html` |
| Bottom-nav (mobile) | `z-30` | `_partials/mobile_nav.html` |
| Help-кнопка ?, mobile FAB | `z-30` | `_partials/help_drawer.html`, `app_base.html` |
| Sticky topbar | `z-20` | `_partials/topbar.html` |
| Dropdown в строке задачи (приоритет, проект) | `z-20` / `z-30` | `_partials/task_row.html` |
| Tooltip-карточки на graph.html | `z-10` | `app/graph.html` |

Если добавляешь новый floating-элемент — выбери уровень из таблицы, не выдумывай свой.

## Touch-targets

Кнопки на мобиле — минимум **36×36px**. Для иконочных кнопок:

```html
<button class="w-9 h-9 inline-flex items-center justify-center rounded-lg hover:bg-[var(--surface-2)] transition">
  <svg class="w-4 h-4" ...></svg>
</button>
```

`w-9 h-9` = 36px touch-target, иконка `w-4 h-4` = 16px по центру.

## Размер шрифта

Не используй `text-[Npx]` где N < 11 — плохо читается на мобиле. Pre-commit (warning, не error) предупредит.

Если намеренно нужен мелкий (PRO-badge, счётчик) — добавь suppression:
```html
{# lint-ignore-next-line: small-text — это PRO-badge #}
<span class="text-[10px] uppercase font-bold">PRO</span>
```

## HTMX

Шаблоны с `hx-get`/`hx-post` дают partial-update без full-page reload. Паттерн:

```html
<button
  hx-post="/htmx/tasks/{{ task.id }}/toggle"
  hx-target="#task-{{ task.id }}"
  hx-swap="outerHTML swap:160ms"
  class="..."
>...</button>
```

Эндпоинт в `app/views/htmx.py` (или `app/<feature>/router.py`) возвращает `templates.TemplateResponse(request, "_partials/task_row.html", {...})`.

## Alpine.js inline

Малая клиент-side логика — Alpine `x-data`. Большая — выноси в `_partials/<name>.html` или вообще `<script>` в `base.html`.

```html
<div x-data="{ open: false }">
  <button @click="open = !open">Toggle</button>
  <div x-show="open">...</div>
</div>
```

Если `<script>` в шаблоне начинает быть длиннее 60 строк — линтер предупредит. Подумай — может пора в отдельный partial.

## Доступность

- Каждая иконочная кнопка — `aria-label="..."` или `title="..."`
- `<input>` с `placeholder=" "` нуждается в видимом `<label>` или `aria-label`
- Цветовой контраст — Tailwind дефолты обычно ок, но не используй `text-[var(--text-muted)]` для важной инфы
```

- [ ] **Step 2: Commit**

```bash
git add docs/recipes/add-template.md
git commit -m "docs: recipe — Jinja-шаблоны (forceescape, z-index ладдер, touch-targets)"
```

---

## Task 15: Recipe — add-test.md

**Files:**
- Create: `docs/recipes/add-test.md`

- [ ] **Step 1: Create the recipe**

Create `docs/recipes/add-test.md`:
```markdown
# Recipe: написать тест

## Конвенции

- Один файл на feature: `tests/test_<feature>.py`
- Pytest-asyncio mode=auto → `async def test_x(...)` работает без декоратора
- Между функциями `tests/conftest.py` делает TRUNCATE всех таблиц — каждый тест видит чистую БД
- Используем существующие фикстуры из `conftest.py`: `client`, `auth_client`, `second_auth_client`, `db_session`

## Минимальный тест

```python
"""Tests for app/notes/."""

from httpx import AsyncClient


async def test_create_note_returns_201(auth_client: AsyncClient) -> None:
    resp = await auth_client.post("/api/notes", json={"title": "first", "body": ""})
    assert resp.status_code == 201
    assert resp.json()["title"] == "first"


async def test_list_returns_only_own_notes(
    auth_client: AsyncClient, second_auth_client: AsyncClient
) -> None:
    await auth_client.post("/api/notes", json={"title": "mine", "body": ""})
    await second_auth_client.post("/api/notes", json={"title": "yours", "body": ""})

    mine_resp = await auth_client.get("/api/notes")
    titles = [n["title"] for n in mine_resp.json()]
    assert titles == ["mine"]
```

## Тестирование service-функций напрямую

Если хочется протестить service-слой без HTTP:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.notes.service import create_note, list_notes


async def test_create_note_persists(
    db_session: AsyncSession, test_user: User
) -> None:
    note = await create_note(db_session, test_user.id, title="t", body="b")
    assert note.id is not None
    fetched = await list_notes(db_session, test_user.id)
    assert len(fetched) == 1
    assert fetched[0].title == "t"
```

## Параметризация

Для повторяющихся кейсов с разными входами:

```python
import pytest


@pytest.mark.parametrize(
    "title,expected_status",
    [
        ("normal", 201),
        ("", 422),                    # пустой — Pydantic min_length=1
        ("x" * 201, 422),             # слишком длинный — max_length=200
    ],
)
async def test_title_validation(
    auth_client: AsyncClient, title: str, expected_status: int
) -> None:
    resp = await auth_client.post("/api/notes", json={"title": title, "body": ""})
    assert resp.status_code == expected_status
```

## Проверка состояния через DB напрямую

Иногда нужно проверить что fields в БД соответствуют ожиданию (а не возврат API):

```python
from sqlalchemy import select

from app.notes.models import Note


async def test_create_note_sets_user_id_correctly(
    auth_client: AsyncClient, db_session: AsyncSession, test_user: User
) -> None:
    await auth_client.post("/api/notes", json={"title": "t", "body": ""})
    result = await db_session.execute(select(Note).where(Note.user_id == test_user.id))
    notes = result.scalars().all()
    assert len(notes) == 1
```

## Запуск

```bash
uv run pytest tests/test_notes.py -v       # один файл
uv run pytest tests/test_notes.py::test_create_note_returns_201 -v   # одна функция
uv run pytest -q                           # всё
uv run pytest -q -k "create"               # фильтр по имени
```

## Анти-паттерны

- ❌ Не мокай БД — у нас Postgres-test инстанс, conftest TRUNCATE'ит таблицы между функциями. Mock-БД и реальная Postgres ведут себя по-разному (transactions, FK, ENUMs)
- ❌ Не делай `time.sleep(...)` для ожидания async — пиши `await` правильно
- ❌ Не пиши тест без assert'ов («просто проверить что не падает») — это не тест
- ❌ Не завись от порядка тестов (`test_a` потом `test_b`) — каждый тест должен быть автономен; conftest TRUNCATE гарантирует этим
```

- [ ] **Step 2: Commit**

```bash
git add docs/recipes/add-test.md
git commit -m "docs: recipe — паттерны pytest (TRUNCATE, fixtures, параметризация)"
```

---

## Task 16: Update CLAUDE.md to reference new tooling

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Read current CLAUDE.md to find the «Quality bar» block**

Run: `grep -n "Quality bar" CLAUDE.md`
Expected: line ~46 mentions "Quality bar (non-negotiable)".

- [ ] **Step 2: Add a sentence about pre-commit + smoke-test in the Quality bar section**

Find this block in `CLAUDE.md`:
```markdown
## Quality bar (non-negotiable)

`uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy .` must all pass before any commit.
```

Replace with:
```markdown
## Quality bar (non-negotiable)

Pre-commit hook (после `uv run pre-commit install`) гоняет `ruff format --check`, `ruff check`, `mypy --strict app/ scripts/` и `python scripts/lint_templates.py` автоматом на каждом `git commit`. Всё должно быть зелёное.

После redeploy `.tmp_ssh_inspect.py` зовёт `python scripts/smoke_test.py https://getdoday.ru` — проверяет 18 ключевых endpoint'ов. Если красный — диагностируй до того как считать деплой завершённым.

CI на GitHub Actions запускает то же самое + полный `pytest -q` на каждый push в master. Бейдж зелёный — baseline.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md — упомянул pre-commit + smoke-test + CI как часть Quality bar"
```

---

## Task 17: Final rollout — baseline run, document any violations

**Files:**
- Possibly modify: `TODO.md` (only if violations exist that we choose not to fix immediately)

- [ ] **Step 1: Run all pre-commit hooks against the entire codebase**

Run: `uv run pre-commit run --all-files`
Expected: ruff and mypy must pass (we keep them clean already). `lint-templates` will likely produce **warnings** for existing `text-[10px]` and similar (these are warnings, not errors — pre-commit returns 0 for warnings-only).

Capture output. Number of warnings expected: 30-60 (mostly small-text in PRO-badges and counters).

- [ ] **Step 2: Decide on warnings**

Read the warning list. For each `text-[10px]` warning:
- If it's a legitimate small-badge use (PRO chip, counter, daily-note timestamp) — leave the warning. Future cleanup may add suppression comments, but warnings don't block anything.
- If it's actually a place where mobile readability suffers — fix the size or suppress.

Default action for v1: leave warnings as-is. They surface real density issues that we can address incrementally without blocking the rollout.

- [ ] **Step 3: Run full pytest to confirm nothing broke**

Run: `uv run pytest -q`
Expected: all tests pass (no regressions from new tooling).

- [ ] **Step 4: Run live smoke-test once more to capture baseline**

Run: `uv run python scripts/smoke_test.py https://getdoday.ru`
Expected: all 18 endpoints green.

- [ ] **Step 5: Push everything and verify CI green**

```bash
git status   # confirm nothing uncommitted
TOKEN=$(grep '^TOKEN=' .env | cut -d= -f2- | tr -d '\r\n')
git push "https://x-access-token:${TOKEN}@github.com/SwairIt/SchoolProject.git" master
```

Wait ~3 minutes, then check `https://github.com/SwairIt/SchoolProject/actions` — latest run should be green.

If CI red:
- Read failing step
- Fix root cause in a follow-up commit
- Push again

- [ ] **Step 6: Update PROGRESS.md with one-line entry**

Find the most recent `### YYYY-MM-DD` section in `PROGRESS.md` and add a new one below it:

```markdown
### 2026-05-08 (вечер) — guardrails

Добавил pre-commit (ruff+mypy+jinja-lint), GitHub Actions CI, `scripts/lint_templates.py` (с suppression-механизмом), `scripts/smoke_test.py` (18 endpoint'ов проверяются после redeploy), CONTRIBUTING + 4 recipes. Все 18 тестов линтера и smoke-теста зелёные. CI на master тоже зелёный.
```

- [ ] **Step 7: Commit and push**

```bash
git add PROGRESS.md
git commit -m "docs: PROGRESS — финальная запись об инфре guardrails"
TOKEN=$(grep '^TOKEN=' .env | cut -d= -f2- | tr -d '\r\n')
git push "https://x-access-token:${TOKEN}@github.com/SwairIt/SchoolProject.git" master
```

---

## Self-Review

**1. Spec coverage:** Each spec section maps to tasks:
- Architecture / file structure → Tasks 1-2 (deps + scripts package)
- Component 1 (pre-commit) → Task 8
- Component 2 (CI) → Task 10
- Component 3 (Jinja-linter) → Tasks 3-6 (one rule per task + CLI)
- Component 4 (smoke-test) → Task 7
- Component 5 (docs) → Tasks 11-15 (CONTRIBUTING + 4 recipes)
- Rollout plan → Task 17 + Task 9 (deploy-script wire-up) + Task 16 (CLAUDE.md)
- Testing strategy: lint_templates and smoke_test both have their own tests in tests/ as part of TDD steps in tasks 3-7. ✓

**2. Placeholders scan:** No `TBD`, no "implement later", no "similar to Task N". Every code step has full code. Every command has expected output. ✓

**3. Type consistency:**
- `Rule`, `Violation`, `Endpoint`, `Result` — defined once each, used consistently
- `check_text(text: str, file: Path)` — same signature in all tasks
- `check_endpoints(base_url, endpoints, client=None)` — same signature in all tasks
- `main(argv: list[str] | None = None) -> int` — same signature for both scripts
- `format_violation`, `format_result`, `lint_directory`, `check_file` — defined once, never renamed

✓ All consistent.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-08-project-structure-guardrails.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
