"""Роутер блога: /blog, /blog/c/{cat}, /blog/{slug}, feed.xml, sitemap.xml."""

from __future__ import annotations

from html import escape as html_escape

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from app.auth.deps import CurrentUser
from app.blog.loader import post_to_dict
from app.blog.posts import (
    CATEGORIES,
    all_posts,
    categories_with_counts,
    get_category,
    get_post,
    latest_posts,
    posts_in_category,
    related_posts,
    search_posts,
)
from app.config import get_settings

router = APIRouter(prefix="/blog", tags=["blog"])
_templates = Jinja2Templates(directory="app/templates")


def _base_url() -> str:
    return get_settings().app_base_url.rstrip("/")


def _render_index(
    request: Request,
    user: CurrentUser,
    *,
    category_slug: str | None,
    query: str,
) -> HTMLResponse:
    category = get_category(category_slug) if category_slug else None
    if category_slug and category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Категория не найдена")
    if query:
        posts = search_posts(query, category.slug if category else None)
    elif category:
        posts = posts_in_category(category.slug)
    else:
        posts = list(all_posts())
    return _templates.TemplateResponse(
        request,
        "blog/index.html",
        {
            "user": user,
            "posts": posts,
            "total_count": len(all_posts()),
            "categories": categories_with_counts(),
            "all_categories": CATEGORIES,
            "category": category,
            "search_query": query,
            "base_url": _base_url(),
        },
    )


@router.get("", response_class=HTMLResponse, include_in_schema=False)
async def blog_index(request: Request, user: CurrentUser) -> HTMLResponse:
    q = request.query_params.get("q", "").strip()[:100]
    c = request.query_params.get("c", "").strip() or None
    return _render_index(request, user, category_slug=c, query=q)


@router.get("/c/{category_slug}", response_class=HTMLResponse, include_in_schema=False)
async def blog_category(request: Request, user: CurrentUser, category_slug: str) -> HTMLResponse:
    q = request.query_params.get("q", "").strip()[:100]
    return _render_index(request, user, category_slug=category_slug, query=q)


@router.get("/index.json", include_in_schema=False)
async def blog_index_json() -> JSONResponse:
    """Лёгкий индекс для мгновенного клиентского поиска."""
    return JSONResponse(
        {"posts": [post_to_dict(p) for p in all_posts()]},
        headers={"Cache-Control": "public, max-age=600"},
    )


@router.get("/feed.xml", include_in_schema=False)
async def blog_feed() -> Response:
    base = _base_url()
    posts = latest_posts(30)
    updated = posts[0].updated_at if posts else "2026-01-01"
    entries = "".join(
        "<entry>"
        f"<title>{html_escape(p.title)}</title>"
        f'<link href="{base}/blog/{p.slug}"/>'
        f"<id>{base}/blog/{p.slug}</id>"
        f"<updated>{p.updated_at}T00:00:00Z</updated>"
        f"<published>{p.published_at}T00:00:00Z</published>"
        f"<summary>{html_escape(p.summary)}</summary>"
        f'<category term="{html_escape(p.category)}"/>'
        "</entry>"
        for p in posts
    )
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom">'
        "<title>Блог Doday — учёба, домашка, продуктивность</title>"
        f'<link href="{base}/blog"/>'
        f'<link rel="self" href="{base}/blog/feed.xml"/>'
        f"<id>{base}/blog</id>"
        f"<updated>{updated}T00:00:00Z</updated>"
        "<author><name>Doday</name></author>"
        f"{entries}</feed>"
    )
    return Response(content=xml, media_type="application/atom+xml")


@router.get("/sitemap.xml", include_in_schema=False)
async def blog_sitemap() -> Response:
    base = _base_url()
    rows = [
        f"<url><loc>{base}/blog</loc><changefreq>daily</changefreq><priority>0.9</priority></url>"
    ]
    rows.extend(
        f"<url><loc>{base}/blog/c/{c.slug}</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>"
        for c, _ in categories_with_counts()
    )
    rows.extend(
        f"<url><loc>{base}/blog/{p.slug}</loc><lastmod>{p.updated_at}</lastmod>"
        "<changefreq>monthly</changefreq><priority>0.7</priority></url>"
        for p in all_posts()
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(rows) + "</urlset>"
    )
    return Response(content=xml, media_type="application/xml")


@router.get("/{slug}", response_class=HTMLResponse, include_in_schema=False)
async def blog_post(request: Request, user: CurrentUser, slug: str) -> HTMLResponse:
    post = get_post(slug)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Статья не найдена")
    category = get_category(post.category)
    return _templates.TemplateResponse(
        request,
        "blog/post.html",
        {
            "user": user,
            "post": post,
            "category": category,
            "related": related_posts(post),
            "base_url": _base_url(),
        },
    )
