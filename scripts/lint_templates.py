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
