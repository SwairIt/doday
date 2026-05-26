"""Lessio blog posts — фиксированный список TypedDict.

Каждый пост — long-form HTML (400-700 слов) с фокусом на конкретный поисковый
запрос. Разделены на 3 категории:
- comparison: «X vs Y», commercial intent
- guide: «как стать N» / «как сделать X», educational
- explainer: «что такое X», informational top-of-funnel

Content body — заполняется отдельно (см. posts_content.py — статьи длинные
и держать всё в одном файле было бы 5000+ строк).
"""

from __future__ import annotations

from app.lessio.blog._types import BlogPost
from app.lessio.blog.posts_content import POSTS_BY_SLUG


def _build_posts() -> list[BlogPost]:
    """Build the canonical ordered list of blog posts.

    Order — обратный хронологический (новые сверху). Все статьи опубликованы
    одной датой запуска (2026-05-26) — Lessio запускается с готовой подборкой.
    """
    return [POSTS_BY_SLUG[slug] for slug in _POSTS_ORDER]


# Порядок отображения — новейшие сверху, по группам в карусели категорий
_POSTS_ORDER: list[str] = [
    # ── Сравнения ──────────────────────────────────────────────────
    "calendly-vs-lessio",
    "profi-ru-vs-sajt",
    "yclients-vs-lessio",
    "skillbox-vs-chastnyy-repetitor",
    "zoom-vs-jitsi-vs-meet",
    "telegram-stars-vs-yukassa-vs-sbp",
    "simplybook-vs-setmore-vs-lessio",
    "getcourse-vs-skillbox",
    # ── Гайды (How to become / how to) ─────────────────────────────
    "kak-stat-repetitorom-anglijskogo",
    "kak-najti-pervyh-klientov",
    "kak-naznachit-tsenu-za-urok",
    "skolko-zarabatyvayut-repetitory",
    "kak-stat-onlajn-psihologom",
    "kak-prinimat-oplatu-onlajn",
    # ── Объяснения (What is) ───────────────────────────────────────
    "chto-takoe-telegram-stars",
    "chto-takoe-booking-servis",
    "kto-takoj-onlajn-kouch",
    "samozanyatost-dlya-repetitora",
]


POSTS: list[BlogPost] = _build_posts()


CATEGORIES: list[tuple[str, str]] = [
    ("Сравнения", "⚖️"),
    ("Гайды", "🎯"),
    ("Объяснения", "💡"),
]


__all__ = ["CATEGORIES", "POSTS", "BlogPost", "get_post", "posts_by_category", "search_posts"]


def get_post(slug: str) -> BlogPost | None:
    return next((p for p in POSTS if p["slug"] == slug), None)


def posts_by_category() -> dict[str, list[BlogPost]]:
    out: dict[str, list[BlogPost]] = {}
    for p in POSTS:
        out.setdefault(p["category"], []).append(p)
    return out


def search_posts(query: str) -> list[BlogPost]:
    """Поиск по title/summary/keywords/body, scoring как в help-center."""
    q = query.strip().lower()
    if not q:
        return []
    scored: list[tuple[int, BlogPost]] = []
    for p in POSTS:
        score = 0
        if q in p["title"].lower():
            score += 10
        if q in p["summary"].lower():
            score += 5
        if any(q in kw.lower() for kw in p["keywords"]):
            score += 8
        if q in p["body"].lower():
            score += 1
        if score > 0:
            scored.append((score, p))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored]
