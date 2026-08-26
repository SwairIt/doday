"""Загрузка статей из markdown-файлов.

Формат файла ``content/<category>/<slug>.md``::

    ---
    title: Заголовок
    summary: Одно-два предложения для карточки и description.
    category: domashka
    tags: дз, продуктивность
    keywords: как быстро сделать домашнее задание, как делать уроки быстро
    published: 2026-08-25
    updated: 2026-08-25        # необязательно
    emoji: ⚡
    featured: true             # необязательно — попадает на лендинг
    ---
    Текст в markdown. ``## Заголовки`` и ``### подзаголовки`` попадают в оглавление.
    Секция ``## Частые вопросы`` с ``### Вопрос`` → FAQPage JSON-LD.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.token import Token

from app.blog._types import FaqItem, Post, TocItem
from app.blog.categories import CATEGORY_BY_SLUG

CONTENT_DIR = Path(__file__).parent / "content"

# Средняя скорость чтения по-русски для нехудожественного текста.
WORDS_PER_MINUTE = 160

_FAQ_HEADINGS = ("частые вопросы", "faq", "вопросы и ответы", "частозадаваемые вопросы")

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "j", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya",
}  # fmt: skip


class BlogContentError(ValueError):
    """Файл статьи оформлен неправильно."""


def slugify(text: str) -> str:
    """Латинский якорь из русского заголовка: «Что делать?» → ``chto-delat``."""
    out: list[str] = []
    for ch in text.lower():
        if ch in _TRANSLIT:
            out.append(_TRANSLIT[ch])
        elif ch.isalnum() and ch.isascii():
            out.append(ch)
        else:
            out.append("-")
    slug = re.sub(r"-+", "-", "".join(out)).strip("-")
    return slug or "section"


@dataclass
class _Frontmatter:
    data: dict[str, str]
    body: str


def parse_frontmatter(raw: str) -> _Frontmatter:
    text = raw.lstrip("﻿")
    if not text.startswith("---"):
        raise BlogContentError("нет frontmatter (файл должен начинаться с ---)")
    end = text.find("\n---", 3)
    if end == -1:
        raise BlogContentError("frontmatter не закрыт (---)")
    head = text[3:end].strip("\n")
    body = text[end + 4 :].lstrip("\n")
    data: dict[str, str] = {}
    for line in head.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise BlogContentError(f"строка frontmatter без «:»: {line!r}")
        key, _, value = line.partition(":")
        data[key.strip().lower()] = value.strip().strip('"').strip("'")
    return _Frontmatter(data=data, body=body)


def _split_list(value: str) -> tuple[str, ...]:
    return tuple(v.strip() for v in value.split(",") if v.strip())


def _md() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": True, "linkify": False, "typographer": False})
    md.enable(["table", "strikethrough"])
    return md


_MD = _md()


def _inline_text(token: Token) -> str:
    """Плоский текст inline-токена (для оглавления и FAQ)."""
    if token.children is None:
        return token.content
    parts: list[str] = []
    for child in token.children:
        if child.type in ("text", "code_inline"):
            parts.append(child.content)
        elif child.type == "softbreak" or child.type == "hardbreak":
            parts.append(" ")
    return unescape("".join(parts)).strip()


def _annotate_headings(tokens: Sequence[Token]) -> tuple[list[TocItem], list[FaqItem]]:
    """Проставляет id заголовкам h2/h3, собирает оглавление и FAQ."""
    toc: list[TocItem] = []
    faq: list[FaqItem] = []
    used: set[str] = set()
    in_faq = False
    current_q: str | None = None
    answer_parts: list[str] = []

    def flush() -> None:
        nonlocal current_q, answer_parts
        if current_q and answer_parts:
            faq.append(FaqItem(question=current_q, answer=" ".join(answer_parts).strip()))
        current_q = None
        answer_parts = []

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "heading_open" and tok.tag in ("h2", "h3"):
            inline = tokens[i + 1]
            text = _inline_text(inline)
            base = slugify(text)
            anchor = base
            n = 2
            while anchor in used:
                anchor = f"{base}-{n}"
                n += 1
            used.add(anchor)
            tok.attrSet("id", anchor)
            level = 2 if tok.tag == "h2" else 3
            toc.append(TocItem(level=level, anchor=anchor, text=text))
            if level == 2:
                flush()
                in_faq = text.strip().lower().rstrip("?:") in _FAQ_HEADINGS
            elif in_faq:
                flush()
                current_q = text
            i += 3
            continue
        if (
            in_faq
            and current_q
            and tok.type == "inline"
            and i > 0
            and tokens[i - 1].type in ("paragraph_open", "list_item_open")
        ):
            answer_parts.append(_inline_text(tok))
        i += 1
    flush()
    return toc, faq


def _render_with_table_wrap(tokens: Sequence[Token]) -> str:
    for tok in tokens:
        if tok.type == "table_open":
            tok.attrSet("class", "blog-table")
    html = str(_MD.renderer.render(list(tokens), _MD.options, {}))
    return html.replace('<table class="blog-table">', '<div class="table-wrap"><table>').replace(
        "</table>", "</table></div>"
    )


_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+(?:[-'’][A-Za-zА-Яа-яЁё0-9]+)*")
_TAG_RE = re.compile(r"<[^>]+>")


def count_words(text: str) -> int:
    return len(_WORD_RE.findall(text))


def render_markdown(body: str) -> tuple[str, list[TocItem], list[FaqItem]]:
    tokens = _MD.parse(body)
    toc, faq = _annotate_headings(tokens)
    html = _render_with_table_wrap(tokens)
    return html, toc, faq


def load_post_file(path: Path, category_slug: str | None = None) -> Post:
    raw = path.read_text(encoding="utf-8")
    fm = parse_frontmatter(raw)
    d = fm.data
    missing = [k for k in ("title", "summary", "category", "published") if not d.get(k)]
    if missing:
        raise BlogContentError(f"{path.name}: нет обязательных полей {missing}")
    category = d["category"]
    if category not in CATEGORY_BY_SLUG:
        raise BlogContentError(f"{path.name}: неизвестная категория {category!r}")
    if category_slug is not None and category_slug != category:
        raise BlogContentError(
            f"{path.name}: лежит в папке {category_slug!r}, а category={category!r}"
        )
    slug = d.get("slug") or path.stem
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise BlogContentError(f"{path.name}: slug должен быть латиницей через дефис: {slug!r}")
    html, toc, faq = render_markdown(fm.body)
    plain = unescape(_TAG_RE.sub(" ", html))
    words = count_words(plain)
    # Таблицы и код читают медленнее — небольшая надбавка.
    extra = html.count("<tr>") * 2 + html.count("<pre>") * 15
    reading_min = max(1, math.ceil((words + extra) / WORDS_PER_MINUTE))
    published = d["published"]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", published):
        raise BlogContentError(f"{path.name}: published должен быть YYYY-MM-DD")
    updated = d.get("updated") or published
    tags = _split_list(d.get("tags", ""))
    keywords = _split_list(d.get("keywords", ""))
    search_text = " ".join([d["title"], d["summary"], *tags, *keywords, plain]).lower()
    return Post(
        slug=slug,
        title=d["title"],
        summary=d["summary"],
        category=category,
        tags=tags,
        keywords=keywords,
        published_at=published,
        updated_at=updated,
        emoji=d.get("emoji") or CATEGORY_BY_SLUG[category].emoji,
        featured=d.get("featured", "").lower() in ("true", "yes", "1"),
        html=html,
        toc=tuple(toc),
        faq=tuple(faq) if d.get("faq", "true").lower() not in ("false", "no", "0") else (),
        word_count=words,
        reading_min=reading_min,
        search_text=search_text,
    )


def load_all_posts(content_dir: Path = CONTENT_DIR) -> list[Post]:
    """Читает все статьи. Падает с BlogContentError на первом же кривом файле."""
    posts: list[Post] = []
    seen: dict[str, Path] = {}
    if not content_dir.exists():
        return posts
    for cat_dir in sorted(p for p in content_dir.iterdir() if p.is_dir()):
        if cat_dir.name not in CATEGORY_BY_SLUG:
            raise BlogContentError(f"папка {cat_dir.name!r} не соответствует ни одной категории")
        for path in sorted(cat_dir.glob("*.md")):
            post = load_post_file(path, cat_dir.name)
            if post.slug in seen:
                raise BlogContentError(f"дубль slug {post.slug!r}: {path} и {seen[post.slug]}")
            seen[post.slug] = path
            posts.append(post)
    # Новые статьи первыми; при равной дате — по алфавиту (предсказуемый порядок).
    posts.sort(key=lambda p: p.title)
    posts.sort(key=lambda p: p.published_at, reverse=True)
    return posts


def post_to_dict(post: Post) -> dict[str, Any]:
    """Для JSON-выдачи (клиентский поиск)."""
    return {
        "slug": post.slug,
        "title": post.title,
        "summary": post.summary,
        "category": post.category,
        "tags": list(post.tags),
        "reading_min": post.reading_min,
        "emoji": post.emoji,
        "published_at": post.published_at,
    }
