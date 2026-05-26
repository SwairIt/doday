"""Lessio help-center router: `/lessio/help` + `/lessio/help/{slug}` + search."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.auth.deps import CurrentUser
from app.lessio.help.articles import (
    ARTICLES,
    CATEGORIES,
    articles_by_category,
    get_article,
    search_articles,
)

router = APIRouter(prefix="/lessio/help", tags=["lessio-help"])
_templates = Jinja2Templates(directory="app/templates")


@router.get("/articles.json", include_in_schema=False)
async def lessio_help_articles_json() -> JSONResponse:
    """Lightweight index — slug + title + summary. Body НЕ кладём — слишком жирно
    для in-app help-drawer'а; полный текст — на отдельной странице."""
    return JSONResponse(
        [
            {
                "slug": a["slug"],
                "title": a["title"],
                "summary": a["summary"],
                "icon": a["icon"],
                "category": a["category"],
            }
            for a in ARTICLES
        ]
    )


@router.get("", response_class=HTMLResponse, include_in_schema=False)
async def lessio_help_index(request: Request, user: CurrentUser) -> HTMLResponse:
    """Help-center index — все статьи сгруппированы по категориям + search box.

    Если есть `?q=<query>` — рендерим search-mode с подсветкой матчей.
    """
    q = request.query_params.get("q", "").strip()
    if q:
        results = search_articles(q)
        return _templates.TemplateResponse(
            request,
            "lessio/help/index.html",
            {
                "user": user,
                "articles": ARTICLES,
                "by_category": articles_by_category(),
                "categories": CATEGORIES,
                "search_query": q,
                "search_results": results,
                "total_count": len(ARTICLES),
            },
        )
    return _templates.TemplateResponse(
        request,
        "lessio/help/index.html",
        {
            "user": user,
            "articles": ARTICLES,
            "by_category": articles_by_category(),
            "categories": CATEGORIES,
            "search_query": "",
            "search_results": None,
            "total_count": len(ARTICLES),
        },
    )


@router.get("/{slug}", response_class=HTMLResponse, include_in_schema=False)
async def lessio_help_article(slug: str, request: Request, user: CurrentUser) -> HTMLResponse:
    article = get_article(slug)
    if article is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "статья не найдена")
    # Related: 3 другие статьи из той же категории
    same_cat = [a for a in ARTICLES if a["category"] == article["category"] and a["slug"] != slug]
    related = same_cat[:3] if same_cat else [a for a in ARTICLES if a["slug"] != slug][:3]
    return _templates.TemplateResponse(
        request,
        "lessio/help/article.html",
        {
            "user": user,
            "article": article,
            "articles": ARTICLES,
            "by_category": articles_by_category(),
            "categories": CATEGORIES,
            "related": related,
        },
    )
