"""Static / shared pages — landing, privacy."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.auth.deps import CurrentUser

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def landing(request: Request, user: CurrentUser) -> Response:
    """Anonymous → marketing landing. Logged-in → straight to the app."""
    if user is not None:
        return RedirectResponse(url="/app/today", status_code=302)
    return templates.TemplateResponse(request, "landing.html", {"user": None})


@router.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "privacy.html", {})
