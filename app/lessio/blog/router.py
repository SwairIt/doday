"""Lessio blog router: /lessio/blog + /lessio/blog/{slug}.

В отличие от help-center'а — публичные SEO-страницы (индексируется),
никаких user-data в URL. Index + per-post страница + ?q= server-side search.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse
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
