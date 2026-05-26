"""TypedDict definitions for Lessio blog — отдельный модуль чтобы не было цикла
import'а между posts.py (создаёт упорядоченный список) и posts_content.py
(содержит сам контент).
"""

from __future__ import annotations

from typing import TypedDict


class BlogPost(TypedDict):
    slug: str
    title: str
    summary: str
    category: str  # "Сравнения" · "Гайды" · "Объяснения"
    keywords: list[str]
    published_at: str  # YYYY-MM-DD — для JSON-LD datePublished
    reading_min: int  # «5 мин чтения»
    hero_emoji: str  # большой emoji в hero-блоке
    body: str  # HTML
