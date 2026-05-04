"""Help-center HTML routes — list of articles + individual article pages."""

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.auth.deps import CurrentUser
from app.help.articles import ARTICLES, get_article

router = APIRouter(prefix="/help", tags=["help"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def help_index(request: Request, user: CurrentUser) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "help/index.html",
        {"articles": ARTICLES, "user": user},
    )


@router.get("/{slug}", response_class=HTMLResponse)
async def help_article(slug: str, request: Request, user: CurrentUser) -> HTMLResponse:
    article = get_article(slug)
    if article is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "статья не найдена")
    return templates.TemplateResponse(
        request,
        "help/article.html",
        {"article": article, "articles": ARTICLES, "user": user},
    )
