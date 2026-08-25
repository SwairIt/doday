"""Проверка статей блога: frontmatter, объём, структура, ссылки.

CLI: uv run python scripts/blog_check.py [--min-words 900] [--strict]

Выход 1, если есть ошибки. Предупреждения (warning) не роняют, кроме --strict.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.blog.categories import CATEGORY_BY_SLUG
from app.blog.loader import CONTENT_DIR, BlogContentError, load_post_file

_INTERNAL_LINK = re.compile(r"\]\((/blog/([a-z0-9-]+))[)#]")
_KNOWN_SITE_PATHS = (
    "/", "/auth/register", "/auth/login", "/for-students", "/for-teachers", "/pricing",
    "/help", "/qa/", "/qa/ask", "/todoist-alternative", "/blog", "/pdd/", "/lessio",
    "/support", "/changelog", "/roadmap",
)  # fmt: skip
_FORBIDDEN = (
    ("14 дней pro", "триала нет — нельзя обещать 14 дней Pro"),
    ("14 дней бесплатно", "триала нет"),
    ("как ии", "не упоминать, что текст писал ИИ"),
    ("как нейросеть", "не упоминать нейросеть-автора"),
    ("saml", "SAML SSO в продукте нет"),
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-words", type=int, default=900)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    slugs: set[str] = set()
    posts = []
    files = sorted(CONTENT_DIR.glob("*/*.md"))
    for path in files:
        cat = path.parent.name
        if cat not in CATEGORY_BY_SLUG:
            errors.append(f"{path}: папка {cat!r} не является категорией")
            continue
        try:
            post = load_post_file(path, cat)
        except BlogContentError as exc:
            errors.append(str(exc))
            continue
        posts.append((path, post))
        slugs.add(post.slug)

    by_cat = Counter(p.category for _, p in posts)
    for path, post in posts:
        rel = path.relative_to(CONTENT_DIR)
        raw = path.read_text(encoding="utf-8")
        low = raw.lower()
        if post.word_count < args.min_words:
            errors.append(f"{rel}: {post.word_count} слов < {args.min_words}")
        h2 = sum(1 for t in post.toc if t.level == 2)
        if h2 < 4:
            errors.append(f"{rel}: только {h2} заголовков h2 (нужно ≥4)")
        if not post.faq:
            warnings.append(f"{rel}: нет секции «## Частые вопросы» с ### вопросами")
        if len(post.summary) < 80:
            warnings.append(f"{rel}: summary короткий ({len(post.summary)} симв.)")
        if len(post.title) > 90:
            warnings.append(f"{rel}: title длинный ({len(post.title)} симв.)")
        if not post.keywords:
            warnings.append(f"{rel}: нет keywords")
        if "<table" not in post.html and "<ol" not in post.html:
            warnings.append(f"{rel}: нет ни таблицы, ни нумерованного списка")
        for needle, why in _FORBIDDEN:
            if needle in low:
                errors.append(f"{rel}: запрещённая фраза «{needle}» — {why}")
        for m in _INTERNAL_LINK.finditer(raw):
            if m.group(2) not in slugs:
                errors.append(f"{rel}: ссылка на несуществующую статью /blog/{m.group(2)}")
        n_internal = len(_INTERNAL_LINK.findall(raw))
        if n_internal < 2:
            warnings.append(f"{rel}: мало внутренних ссылок ({n_internal})")
        has_product = any(
            f"]({p})" in raw or f"]({p}#" in raw for p in _KNOWN_SITE_PATHS if p != "/"
        )
        if not has_product:
            warnings.append(f"{rel}: нет ссылки на продукт (Doday/Razbery)")

    print(f"Статей: {len(posts)}  (файлов: {len(files)})")
    for slug, n in sorted(by_cat.items()):
        print(f"  {slug:14} {n}")
    for w in warnings:
        print("WARN ", w)
    for err in errors:
        print("ERROR", err)
    print(f"\nошибок: {len(errors)}, предупреждений: {len(warnings)}")
    if errors or (args.strict and warnings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
