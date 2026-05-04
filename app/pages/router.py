"""Static / shared pages — landing, privacy."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.auth.deps import CurrentUser

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def landing(request: Request, user: CurrentUser) -> Response:
    """Anonymous → marketing landing. Logged-in → /app/today (or landing if ?preview=1)."""
    preview = request.query_params.get("preview") == "1"
    if user is not None and not preview:
        return RedirectResponse(url="/app/today", status_code=302)
    return templates.TemplateResponse(request, "landing.html", {"user": user})


@router.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "privacy.html", {})
