"""HTML view endpoints for the signed-in app shell.

Each view loads the user's projects (for the sidebar) and renders a template
extending `app_base.html`. Concrete views (today / upcoming / calendar / project)
land in subsequent chunks; this module bootstraps the shell and a /app redirect.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.auth.deps import DbSession, RequiredUser
from app.projects.service import list_projects

router = APIRouter(prefix="/app", tags=["app"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", include_in_schema=False)
async def app_root() -> Response:
    return RedirectResponse(url="/app/today", status_code=302)


@router.get("/today", response_class=HTMLResponse)
async def today_view(request: Request, user: RequiredUser, session: DbSession) -> HTMLResponse:
    projects = await list_projects(session, user.id)
    return templates.TemplateResponse(
        request,
        "app/placeholder.html",
        {
            "current_user": user,
            "current_view": "today",
            "projects": projects,
            "view_title": "Сегодня",
            "subtitle": "Тут появятся задачи на сегодня — реализация в C10.",
        },
    )
