"""Static / shared pages — landing, privacy."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.auth.deps import CurrentUser, DbSession, RequiredUser
from app.config import get_settings
from app.pages.changelog_data import ENTRIES as CHANGELOG_ENTRIES
from app.pages.roadmap_data import SECTIONS as ROADMAP_SECTIONS

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def landing(request: Request, user: CurrentUser) -> Response:
    """Anonymous → marketing landing. Logged-in → /app/today (or landing if ?preview=1)."""
    preview = request.query_params.get("preview") == "1"
    if user is not None and not preview:
        return RedirectResponse(url="/app/today", status_code=302)
    return templates.TemplateResponse(
        request,
        "landing.html",
        {"user": user, "beta_free_for_all": get_settings().beta_free_for_all},
    )


@router.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "privacy.html", {})


@router.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request, user: CurrentUser) -> HTMLResponse:
    """Three-tier pricing page — Free / Pro / Family. Real checkout disabled
    until ЮKassa shop is registered (CTA shows 'Скоро')."""
    return templates.TemplateResponse(
        request,
        "pricing.html",
        {"user": user, "beta_free_for_all": get_settings().beta_free_for_all},
    )


@router.get("/changelog", response_class=HTMLResponse)
async def changelog(request: Request, user: CurrentUser) -> HTMLResponse:
    """Public changelog feed. Источник: app/pages/changelog_data.py."""
    return templates.TemplateResponse(
        request,
        "pages/changelog.html",
        {"user": user, "entries": CHANGELOG_ENTRIES},
    )


@router.get("/roadmap", response_class=HTMLResponse)
async def roadmap(request: Request, user: CurrentUser) -> HTMLResponse:
    """Public roadmap — Now / Next / Maybe. Источник:
    app/pages/roadmap_data.py."""
    return templates.TemplateResponse(
        request,
        "pages/roadmap.html",
        {"user": user, "sections": ROADMAP_SECTIONS},
    )


async def _build_invite_context(token: str, session: DbSession) -> "dict[str, object]":
    """Shared helper — look up invitation, project and inviter by token."""
    from app.auth.models import User
    from app.projects.models import Project, ProjectInvitation

    inv = (
        await session.execute(select(ProjectInvitation).where(ProjectInvitation.token == token))
    ).scalar_one_or_none()

    project = None
    inviter_email = None
    if inv is not None:
        project = await session.get(Project, inv.project_id)
        inviter = await session.get(User, inv.inviter_id)
        inviter_email = inviter.email if inviter else None

    return {"invitation": inv, "project": project, "inviter_email": inviter_email}


@router.get("/invite/{token}", response_class=HTMLResponse)
async def invite_page(
    token: str, request: Request, user: CurrentUser, session: DbSession
) -> HTMLResponse:
    """Render the invitation accept page. Works for anonymous users too."""
    ctx = await _build_invite_context(token, session)
    return templates.TemplateResponse(
        request,
        "invite.html",
        {
            "token": token,
            "current_user": user,
            "error": None,
            **ctx,
        },
    )


@router.post("/invite/{token}", response_class=HTMLResponse)
async def invite_accept(
    token: str, request: Request, user: RequiredUser, session: DbSession
) -> Response:
    """Accept the invitation as the currently logged-in user."""
    from app.projects.invitations import InvitationError, accept_invitation

    try:
        await accept_invitation(session, token=token, user_id=user.id, user_email=user.email)
    except InvitationError as e:
        ctx = await _build_invite_context(token, session)
        return templates.TemplateResponse(
            request,
            "invite.html",
            {
                "token": token,
                "current_user": user,
                "error": str(e),
                **ctx,
            },
        )
    return RedirectResponse("/app/projects", status_code=303)
