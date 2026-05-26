"""Minimal refactor — move Doday cabinet (/app, /htmx) под /doday/* prefix.

Trogает только что user видит в URL bar. API/auth/marketing — позже отдельным batch'ем.

Regex (?<![\\w-]) исключает /lessio/app/, /lessio/htmx/ — слово-character предшествует.

Запуск: cd <root> && uv run python scripts/refactor_doday_prefix.py
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent


# (router_file, old_prefix, new_prefix) — НЕ trogает lessio router'ы
ROUTER_CHANGES: list[tuple[str, str, str]] = [
    ("app/views/router.py", '"/app"', '"/doday/app"'),
    ("app/views/htmx.py", '"/htmx"', '"/doday/htmx"'),
]


# Regex look-behind: НЕ word-char (буквы/цифры/_) и НЕ дефис перед /app/ или /htmx/.
# Это исключает /lessio/app/ (т.к. перед /app/ стоит 'o' — word char).
URL_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?<![\w-])/app/"), "/doday/app/"),
    (re.compile(r"(?<![\w-])/htmx/"), "/doday/htmx/"),
]


def _apply_router_changes() -> int:
    n = 0
    for rel_path, old, new in ROUTER_CHANGES:
        f = ROOT / rel_path
        if not f.exists():
            print(f"SKIP missing: {rel_path}")
            continue
        text = f.read_text(encoding="utf-8")
        old_line = f"prefix={old}"
        new_line = f"prefix={new}"
        if old_line in text and new_line not in text:
            text = text.replace(old_line, new_line)
            f.write_text(text, encoding="utf-8")
            print(f"  router prefix: {rel_path}  {old}  -->  {new}")
            n += 1
    return n


def _replace_in_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text
    for pattern, replacement in URL_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def _walk_and_replace(root: Path, glob: str, label: str) -> int:
    count = 0
    for path in root.rglob(glob):
        if any(part in {".venv", "__pycache__", "node_modules", "alembic"} for part in path.parts):
            continue
        if path.name == "refactor_doday_prefix.py":
            continue
        if _replace_in_file(path):
            print(f"  {label}: {path.relative_to(ROOT)}")
            count += 1
    return count


def main() -> None:
    print("\n=== Router prefix changes ===")
    n1 = _apply_router_changes()
    print(f"  -> {n1} router files\n")

    print("=== Templates ===")
    n2 = _walk_and_replace(ROOT / "app" / "templates", "*.html", "tmpl")
    print(f"  -> {n2}\n")

    print("=== App python ===")
    n3 = _walk_and_replace(ROOT / "app", "*.py", "py")
    print(f"  -> {n3}\n")

    print("=== Tests ===")
    n4 = _walk_and_replace(ROOT / "tests", "*.py", "test")
    print(f"  -> {n4}\n")

    print("=== Scripts ===")
    if (ROOT / "scripts").exists():
        n5 = _walk_and_replace(ROOT / "scripts", "*.py", "script")
    else:
        n5 = 0
    print(f"  -> {n5}\n")

    print(f"TOTAL: {n1 + n2 + n3 + n4 + n5}")


if __name__ == "__main__":
    main()
