"""Дисковый кэш распарсенных статей.

Зачем: markdown-it парсит 300+ статей ~10 секунд. Без кэша это время платит
первый посетитель после каждого рестарта. Кэш кладём в JSON (не pickle —
не хотим исполняемый формат на диске), ключ — отпечаток каталога с контентом
(имя + mtime + размер каждого файла). Изменился хоть один .md — кэш протух.

Файл кэша в .gitignore: он машинно-локальный и восстанавливается сам.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from app.blog._types import FaqItem, Post, TocItem

logger = logging.getLogger("doday.blog")

CACHE_VERSION = 1
CACHE_PATH = Path(__file__).parent / ".posts-cache.json"


def content_fingerprint(content_dir: Path) -> str:
    """Отпечаток каталога статей: любой правленый/новый/удалённый файл меняет его."""
    parts: list[str] = [str(CACHE_VERSION)]
    for path in sorted(content_dir.glob("*/*.md")):
        st = path.stat()
        parts.append(f"{path.parent.name}/{path.name}:{st.st_mtime_ns}:{st.st_size}")
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _post_to_json(p: Post) -> dict[str, Any]:
    return {
        "slug": p.slug,
        "title": p.title,
        "summary": p.summary,
        "category": p.category,
        "tags": list(p.tags),
        "keywords": list(p.keywords),
        "published_at": p.published_at,
        "updated_at": p.updated_at,
        "emoji": p.emoji,
        "featured": p.featured,
        "html": p.html,
        "toc": [[t.level, t.anchor, t.text] for t in p.toc],
        "faq": [[f.question, f.answer] for f in p.faq],
        "word_count": p.word_count,
        "reading_min": p.reading_min,
        "search_text": p.search_text,
    }


def _post_from_json(d: dict[str, Any]) -> Post:
    return Post(
        slug=d["slug"],
        title=d["title"],
        summary=d["summary"],
        category=d["category"],
        tags=tuple(d["tags"]),
        keywords=tuple(d["keywords"]),
        published_at=d["published_at"],
        updated_at=d["updated_at"],
        emoji=d["emoji"],
        featured=d["featured"],
        html=d["html"],
        toc=tuple(TocItem(level=t[0], anchor=t[1], text=t[2]) for t in d["toc"]),
        faq=tuple(FaqItem(question=f[0], answer=f[1]) for f in d["faq"]),
        word_count=d["word_count"],
        reading_min=d["reading_min"],
        search_text=d["search_text"],
    )


def read_cache(fingerprint: str, path: Path = CACHE_PATH) -> list[Post] | None:
    """Читает кэш, если он есть и соответствует текущему контенту. Иначе None."""
    try:
        if not path.is_file():
            return None
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("fingerprint") != fingerprint:
            return None
        return [_post_from_json(d) for d in data["posts"]]
    except Exception:  # битый кэш не должен ронять сайт
        logger.warning("не удалось прочитать кэш блога, парсим заново", exc_info=True)
        return None


def write_cache(fingerprint: str, posts: list[Post], path: Path = CACHE_PATH) -> None:
    """Пишет кэш атомарно (tmp + rename), чтобы параллельный читатель не увидел половину."""
    try:
        payload = {"fingerprint": fingerprint, "posts": [_post_to_json(p) for p in posts]}
        fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".posts-cache-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False)
            os.replace(tmp_name, path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)
            raise
    except Exception:  # не смогли записать (read-only FS) — просто работаем медленнее
        logger.warning("не удалось записать кэш блога", exc_info=True)
