"""Тесты блога /blog. Не требуют БД: контент — файлы, роутер не ходит в Postgres."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.blog.cache import content_fingerprint, read_cache, write_cache
from app.blog.categories import CATEGORIES, CATEGORY_BY_SLUG
from app.blog.loader import (
    BlogContentError,
    parse_frontmatter,
    render_markdown,
    slugify,
)
from app.blog.posts import all_posts, get_post, related_posts, search_posts
from app.main import app

SEED_SLUG = "kak-bystro-sdelat-domashnee-zadanie"


@pytest.fixture
async def blog_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ── loader ────────────────────────────────────────────────────────────────


def test_slugify_transliterates_russian() -> None:
    assert slugify("Шаг 1. Выпиши всё, что задано") == "shag-1-vypishi-vse-chto-zadano"
    assert slugify("???") == "section"


def test_parse_frontmatter_requires_delimiters() -> None:
    fm = parse_frontmatter("---\ntitle: X\ntags: a, b\n---\nbody")
    assert fm.data["title"] == "X"
    assert fm.body == "body"
    with pytest.raises(BlogContentError):
        parse_frontmatter("title: X\nbody")


def test_render_markdown_builds_toc_and_faq() -> None:
    md = (
        "Intro\n\n## Первый\n\ntext\n\n### Под\n\n## Частые вопросы\n\n"
        "### Сколько?\n\nДва.\n\n### Почему?\n\nПотому.\n\n| a | b |\n|---|---|\n| 1 | 2 |\n"
    )
    html, toc, faq = render_markdown(md)
    assert [t.anchor for t in toc] == ["pervyj", "pod", "chastye-voprosy", "skolko", "pochemu"]
    assert [t.level for t in toc] == [2, 3, 2, 3, 3]
    assert 'id="pervyj"' in html
    assert '<div class="table-wrap"><table>' in html
    assert [(f.question, f.answer) for f in faq] == [("Сколько?", "Два."), ("Почему?", "Потому.")]


def test_all_content_files_load_and_are_valid() -> None:
    posts = all_posts()
    assert len(posts) >= 1
    slugs = [p.slug for p in posts]
    assert len(slugs) == len(set(slugs)), "дубли slug"
    for p in posts:
        assert p.category in CATEGORY_BY_SLUG
        assert p.title and p.summary
        assert p.reading_min >= 1
        assert p.word_count > 300
        assert any(t.level == 2 for t in p.toc), p.slug
    # Папка = категория
    for path in Path("app/blog/content").glob("*/*.md"):
        assert path.parent.name in CATEGORY_BY_SLUG, path


def test_seed_post_metrics() -> None:
    p = get_post(SEED_SLUG)
    assert p is not None
    assert p.category == "domashka"
    assert p.featured is True
    assert p.reading_min >= 5
    assert len(p.faq) >= 3
    assert any(t.level == 2 and t.anchor.startswith("shag-1") for t in p.toc)


def test_search_scores_title_higher_and_requires_all_words() -> None:
    hits = search_posts("домашнее задание")
    # Все статьи в выдаче содержат оба слова, seed-статья — в первой десятке.
    assert hits
    assert SEED_SLUG in [p.slug for p in hits[:10]]
    for p in hits[:5]:
        assert "домашн" in p.search_text
    # Слово, которого нет ни в одной статье, обнуляет выдачу.
    assert search_posts("квазимодоплюмбум") == []
    assert search_posts("") == []


def test_search_filters_by_category() -> None:
    hits = search_posts("домашнее задание", category="domashka")
    assert hits
    assert all(p.category == "domashka" for p in hits)


def test_disk_cache_roundtrip(tmp_path: Path) -> None:
    """Кэш восстанавливает статьи один в один и протухает при смене отпечатка."""
    posts = list(all_posts())
    cache_file = tmp_path / "posts.json"
    write_cache("fp-1", posts, cache_file)
    restored = read_cache("fp-1", cache_file)
    assert restored is not None
    assert [p.slug for p in restored] == [p.slug for p in posts]
    first = next(p for p in restored if p.slug == SEED_SLUG)
    origin = next(p for p in posts if p.slug == SEED_SLUG)
    assert first == origin
    # Отпечаток другой — кэш игнорируется.
    assert read_cache("fp-2", cache_file) is None
    # Битый файл не роняет сайт.
    cache_file.write_text("{ not json", encoding="utf-8")
    assert read_cache("fp-1", cache_file) is None


def test_related_excludes_self() -> None:
    p = get_post(SEED_SLUG)
    assert p is not None
    assert all(r.slug != SEED_SLUG for r in related_posts(p))


# ── routes ────────────────────────────────────────────────────────────────


async def test_index_lists_posts_and_categories(blog_client: AsyncClient) -> None:
    r = await blog_client.get("/blog")
    assert r.status_code == 200
    html = r.text
    assert f'href="/blog/{SEED_SLUG}"' in html
    assert "мин чтения" in html
    assert 'id="blog-search"' in html
    assert '"@type": "Blog"' in html
    for c in CATEGORIES:
        if any(p.category == c.slug for p in all_posts()):
            assert f'href="/blog/c/{c.slug}"' in html


async def test_category_page(blog_client: AsyncClient) -> None:
    r = await blog_client.get("/blog/c/domashka")
    assert r.status_code == 200
    assert CATEGORY_BY_SLUG["domashka"].seo_title in r.text
    assert (await blog_client.get("/blog/c/nope")).status_code == 404


async def test_search_query(blog_client: AsyncClient) -> None:
    r = await blog_client.get("/blog", params={"q": "домашнее"})
    assert r.status_code == 200
    assert SEED_SLUG in r.text
    assert "noindex" in r.text
    r = await blog_client.get("/blog", params={"q": "qwertyuiop"})
    assert "Ничего не нашлось" in r.text


async def test_post_page_has_progress_toc_and_jsonld(blog_client: AsyncClient) -> None:
    r = await blog_client.get(f"/blog/{SEED_SLUG}")
    assert r.status_code == 200
    html = r.text
    assert 'id="reading-progress"' in html
    assert 'id="toc-nav"' in html
    assert 'class="toc-link' in html
    assert 'id="shag-1-vypishi-vse-chto-zadano-v-odno-mesto"' in html
    assert '"@type": "BlogPosting"' in html
    assert '"@type": "FAQPage"' in html
    assert '"@type": "BreadcrumbList"' in html
    assert f'rel="canonical" href="https://getdoday.ru/blog/{SEED_SLUG}"' in html
    assert "мин чтения" in html
    assert 'class="table-wrap"' in html
    assert "Читайте также" in html or len(all_posts()) == 1


async def test_post_404(blog_client: AsyncClient) -> None:
    assert (await blog_client.get("/blog/no-such-post")).status_code == 404


async def test_feed_is_valid_atom(blog_client: AsyncClient) -> None:
    r = await blog_client.get("/blog/feed.xml")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/atom+xml")
    root = ET.fromstring(r.text)  # noqa: S314 — наш собственный response
    ns = {"a": "http://www.w3.org/2005/Atom"}
    assert root.findall("a:entry", ns)


async def test_blog_sitemap_and_index_json(blog_client: AsyncClient) -> None:
    r = await blog_client.get("/blog/sitemap.xml")
    assert r.status_code == 200
    root = ET.fromstring(r.text)  # noqa: S314 — наш собственный response
    locs = [u.text for u in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
    assert f"https://getdoday.ru/blog/{SEED_SLUG}" in locs
    assert "https://getdoday.ru/blog/c/domashka" in locs
    j = (await blog_client.get("/blog/index.json")).json()
    assert any(p["slug"] == SEED_SLUG for p in j["posts"])


async def test_robots_allows_blog_and_lists_sitemap(blog_client: AsyncClient) -> None:
    r = await blog_client.get("/robots.txt")
    assert "Allow: /blog" in r.text
    assert "/blog/sitemap.xml" in r.text


def test_fingerprint_changes_when_content_changes(tmp_path: Path) -> None:
    (tmp_path / "domashka").mkdir()
    f = tmp_path / "domashka" / "x.md"
    f.write_text("hello", encoding="utf-8")
    before = content_fingerprint(tmp_path)
    f.write_text("hello world", encoding="utf-8")
    assert content_fingerprint(tmp_path) != before
