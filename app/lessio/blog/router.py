"""Lessio blog router: /lessio/blog + /lessio/blog/{slug}.

В отличие от help-center'а — публичные SEO-страницы (индексируется),
никаких user-data в URL. Index + per-post страница + ?q= server-side search.
"""

from __future__ import annotations

from html import escape as html_escape

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from app.lessio.blog.posts import (
    CATEGORIES,
    POSTS,
    get_post,
    posts_by_category,
    search_posts,
)

router = APIRouter(prefix="/lessio/blog", tags=["lessio-blog"])
_templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse, include_in_schema=False)
async def blog_index(request: Request) -> HTMLResponse:
    q = request.query_params.get("q", "").strip()
    if q:
        results = search_posts(q)
        return _templates.TemplateResponse(
            request,
            "lessio/blog/index.html",
            {
                "posts": POSTS,
                "by_category": posts_by_category(),
                "categories": CATEGORIES,
                "search_query": q,
                "search_results": results,
                "total_count": len(POSTS),
            },
        )
    return _templates.TemplateResponse(
        request,
        "lessio/blog/index.html",
        {
            "posts": POSTS,
            "by_category": posts_by_category(),
            "categories": CATEGORIES,
            "search_query": "",
            "search_results": None,
            "total_count": len(POSTS),
        },
    )


@router.get("/feed.xml", include_in_schema=False)
async def blog_feed() -> Response:
    """Atom 1.0 feed для блога. Подписаны RSS-ридеры + поисковые системы.

    Atom вместо RSS 2.0 — лучше по UTF-8 (нет двусмысленности с кодировками)
    и поддерживается всеми современными ридерами.
    """
    base = "https://getdoday.ru"
    feed_url = f"{base}/lessio/blog/feed.xml"
    # Последнее обновление = max published_at среди всех постов
    last_updated = max(p["published_at"] for p in POSTS) if POSTS else "2026-05-26"

    entries: list[str] = []
    for p in POSTS:
        post_url = f"{base}/lessio/blog/{p['slug']}"
        # Atom requires Updated timestamps in ISO-8601 format with timezone
        published_iso = f"{p['published_at']}T00:00:00Z"
        entries.append(
            "<entry>"
            f"<title>{html_escape(p['title'])}</title>"
            f'<link href="{post_url}"/>'
            f"<id>{post_url}</id>"
            f"<published>{published_iso}</published>"
            f"<updated>{published_iso}</updated>"
            f'<category term="{html_escape(p["category"])}"/>'
            f"<summary>{html_escape(p['summary'])}</summary>"
            f"<author><name>Doday Studio</name></author>"
            "</entry>"
        )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="ru">'
        "<title>Блог Lessio</title>"
        "<subtitle>Сравнения, гайды и объяснения для онлайн-учителей в РФ</subtitle>"
        f'<link rel="self" href="{feed_url}"/>'
        f'<link href="{base}/lessio/blog"/>'
        f"<id>{feed_url}</id>"
        f"<updated>{last_updated}T00:00:00Z</updated>"
        "<author><name>Doday Studio</name><email>doday.support@gmail.com</email></author>"
        + "".join(entries)
        + "</feed>"
    )
    return Response(content=body, media_type="application/atom+xml; charset=utf-8")


@router.get("/{slug}", response_class=HTMLResponse, include_in_schema=False)
async def blog_post(slug: str, request: Request) -> HTMLResponse:
    post = get_post(slug)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "статья не найдена")
    # Related: 3 другие статьи из той же категории
    same_cat = [p for p in POSTS if p["category"] == post["category"] and p["slug"] != slug]
    related = same_cat[:3] if same_cat else [p for p in POSTS if p["slug"] != slug][:3]
    return _templates.TemplateResponse(
        request,
        "lessio/blog/post.html",
        {
            "post": post,
            "posts": POSTS,
            "by_category": posts_by_category(),
            "categories": CATEGORIES,
            "related": related,
        },
    )
