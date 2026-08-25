"""Типы блога: категория, пункт оглавления, статья."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Category:
    slug: str
    name: str
    emoji: str
    description: str
    seo_title: str
    seo_description: str


@dataclass(frozen=True)
class TocItem:
    level: int  # 2 или 3
    anchor: str
    text: str


@dataclass(frozen=True)
class FaqItem:
    question: str
    answer: str


@dataclass(frozen=True)
class Post:
    slug: str
    title: str
    summary: str
    category: str  # slug категории
    tags: tuple[str, ...]
    keywords: tuple[str, ...]
    published_at: str  # YYYY-MM-DD
    updated_at: str  # YYYY-MM-DD
    emoji: str
    featured: bool
    html: str
    toc: tuple[TocItem, ...]
    faq: tuple[FaqItem, ...]
    word_count: int
    reading_min: int
    search_text: str = field(repr=False, default="")
