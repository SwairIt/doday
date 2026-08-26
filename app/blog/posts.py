"""Доступ к статьям: кэш, поиск, категории, похожие."""

from __future__ import annotations

import logging
import threading
from functools import lru_cache

from app.blog._types import Category, Post
from app.blog.cache import content_fingerprint, read_cache, write_cache
from app.blog.categories import CATEGORIES, CATEGORY_BY_SLUG, get_category
from app.blog.loader import CONTENT_DIR, load_all_posts

logger = logging.getLogger("doday.blog")

__all__ = [
    "CATEGORIES",
    "CATEGORY_BY_SLUG",
    "all_posts",
    "categories_with_counts",
    "featured_posts",
    "get_category",
    "get_post",
    "latest_posts",
    "posts_by_category",
    "posts_in_category",
    "related_posts",
    "reset_cache",
    "search_posts",
    "warm_cache",
]


@lru_cache(maxsize=1)
def all_posts() -> tuple[Post, ...]:
    """Все статьи, отсортированные по дате (новые первыми).

    Сначала пробуем дисковый кэш: парсинг 300+ markdown-файлов занимает ~10 с,
    и без кэша это время платил бы первый посетитель после каждого рестарта.
    """
    fingerprint = content_fingerprint(CONTENT_DIR)
    cached = read_cache(fingerprint)
    if cached is not None:
        return tuple(cached)
    posts = load_all_posts()
    write_cache(fingerprint, posts)
    return tuple(posts)


def warm_cache() -> None:
    """Прогреть кэш в фоне — вызывается на старте приложения.

    Отдельным демон-потоком, чтобы не задерживать старт uvicorn: пока идёт
    парсинг, приложение уже принимает запросы (не-блоговые страницы работают).
    """

    def _run() -> None:
        try:
            all_posts()
        except Exception:  # блог не должен ронять старт приложения
            logger.exception("не удалось прогреть кэш блога")

    threading.Thread(target=_run, name="blog-warm-cache", daemon=True).start()


@lru_cache(maxsize=1)
def _by_slug() -> dict[str, Post]:
    return {p.slug: p for p in all_posts()}


def reset_cache() -> None:
    all_posts.cache_clear()
    _by_slug.cache_clear()


def get_post(slug: str) -> Post | None:
    return _by_slug().get(slug)


def posts_by_category() -> dict[str, list[Post]]:
    out: dict[str, list[Post]] = {c.slug: [] for c in CATEGORIES}
    for p in all_posts():
        out.setdefault(p.category, []).append(p)
    return out


def posts_in_category(slug: str) -> list[Post]:
    return [p for p in all_posts() if p.category == slug]


def categories_with_counts() -> list[tuple[Category, int]]:
    counts = {slug: len(posts) for slug, posts in posts_by_category().items()}
    return [(c, counts.get(c.slug, 0)) for c in CATEGORIES if counts.get(c.slug, 0) > 0]


def latest_posts(n: int = 6) -> list[Post]:
    return list(all_posts()[:n])


def featured_posts(n: int = 6) -> list[Post]:
    """Статьи для лендинга: сначала помеченные featured, добираем свежими."""
    picked = [p for p in all_posts() if p.featured][:n]
    if len(picked) < n:
        seen = {p.slug for p in picked}
        picked.extend(p for p in all_posts() if p.slug not in seen)
    return picked[:n]


def search_posts(query: str, category: str | None = None) -> list[Post]:
    """Взвешенный поиск: заголовок ×10, ключи ×8, summary ×5, теги ×4, текст ×1.

    Запрос режется на слова; каждое слово должно встретиться хотя бы где-то,
    иначе статья отбрасывается — так «егэ математика» не вытащит всё про ЕГЭ.
    """
    words = [w for w in query.lower().split() if len(w) > 1]
    if not words:
        return []
    scored: list[tuple[int, Post]] = []
    for p in all_posts():
        if category and p.category != category:
            continue
        title = p.title.lower()
        summary = p.summary.lower()
        kws = " ".join(p.keywords).lower()
        tags = " ".join(p.tags).lower()
        score = 0
        for w in words:
            hit = 0
            if w in title:
                hit += 10
            if w in kws:
                hit += 8
            if w in summary:
                hit += 5
            if w in tags:
                hit += 4
            if w in p.search_text:
                hit += 1
            if hit == 0:
                score = 0
                break
            score += hit
        if score > 0:
            scored.append((score, p))
    scored.sort(key=lambda x: (-x[0], x[1].title))
    return [p for _, p in scored]


def related_posts(post: Post, n: int = 4) -> list[Post]:
    """Похожие: общие теги важнее, затем та же категория, затем свежесть."""
    tags = set(post.tags)
    scored: list[tuple[int, Post]] = []
    for p in all_posts():
        if p.slug == post.slug:
            continue
        score = len(tags & set(p.tags)) * 3
        if p.category == post.category:
            score += 2
        if score > 0:
            scored.append((score, p))
    scored.sort(key=lambda x: (-x[0], x[1].published_at), reverse=False)
    return [p for _, p in scored[:n]]
