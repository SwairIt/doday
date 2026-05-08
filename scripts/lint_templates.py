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
_TOJSON_SAFE_PATTERN = re.compile(r"\|\s*tojson\s*\|\s*safe(?!\s*\|\s*(?:e\b|forceescape))")

# Rule 2: text-[Npx] where N < 11 — too small for mobile readability.
_TEXT_PX_PATTERN = re.compile(r"text-\[(\d+)px\]")


def _small_text_check(match: re.Match[str]) -> bool:
    return int(match.group(1)) < 11


# Rule 3: inline <script> longer than 60 lines — extract to partial.
_SCRIPT_PATTERN = re.compile(r"<script[^>]*>(.*?)</script>", re.DOTALL)


def _long_script_check(match: re.Match[str]) -> bool:
    return match.group(1).count("\n") > 60


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
]

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


def main(argv: list[str] | None = None) -> int:
    # Force UTF-8 stdout — Windows console defaults to cp1251 which can't
    # encode ✓ U+2713 from snippets or Russian text from rule messages.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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


if __name__ == "__main__":
    raise SystemExit(main())
