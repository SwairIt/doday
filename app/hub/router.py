"""Doday Studio hub — root landing showing all sibling projects."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.auth.deps import CurrentUser

router = APIRouter(tags=["hub"])
_templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def hub_index(request: Request, user: CurrentUser) -> HTMLResponse:
    """The new studio root.

    Anonymous visitors see project cards + author intro. Logged-in visitors also
    see the hub (no redirect) so they can navigate to other products — login
    flow itself redirects to /doday/app/today directly (see `app.auth.router.login`).
    """
    return _templates.TemplateResponse(
        request,
        "hub/index.html",
        {"user": user},
    )
