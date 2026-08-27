"""Static / shared pages — landing, privacy."""

from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.auth.deps import CurrentUser, DbSession, RequiredUser
from app.auth.rate_limit import client_ip, client_key, hit
from app.blog.posts import CATEGORY_BY_SLUG, all_posts, featured_posts
from app.config import get_settings
from app.pages.changelog_data import ENTRIES as CHANGELOG_ENTRIES
from app.pages.roadmap_data import SECTIONS as ROADMAP_SECTIONS

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def doday_landing(request: Request, user: CurrentUser) -> Response:
    """Doday Tasks marketing landing (todo-list product page).

    С 2026-08-24 снова живёт на `/`: основной домен getdoday.ru принадлежит
    продукту, а витрина студии переехала на /all и поддомен all.getdoday.ru.
    Путь /doday сохранён как алиас — на него ведут старые ссылки и реклама.
    Анонимным показываем лендинг, залогиненных уводим в приложение.
    """
    preview = request.query_params.get("preview") == "1"
    if user is not None and not preview:
        return RedirectResponse(url="/app/today", status_code=302)
    return templates.TemplateResponse(
        request,
        "landing.html",
        {
            "user": user,
            "beta_free_for_all": get_settings().beta_free_for_all,
            "blog_posts": featured_posts(6),
            "blog_total": len(all_posts()),
            "blog_categories": CATEGORY_BY_SLUG,
        },
    )


@router.get("/for-students", response_class=HTMLResponse)
async def for_students(request: Request, user: CurrentUser) -> HTMLResponse:
    """SEO landing — explicit student/учёба intent.

    Indexed in sitemap, linked from internal nav. Targets queries:
    «планировщик для школьников», «todo для студентов», «расписание уроков онлайн»,
    «помодоро для школьников»."""
    return templates.TemplateResponse(request, "seo/for_students.html", {"user": user})


@router.get("/for-teachers", response_class=HTMLResponse)
async def for_teachers(request: Request, user: CurrentUser) -> HTMLResponse:
    """SEO landing — teacher / репетитор intent.

    Targets: «планировщик для учителей», «дедлайны для учеников»,
    «прогресс ученика онлайн», «doday для учителя»."""
    return templates.TemplateResponse(request, "seo/for_teachers.html", {"user": user})


@router.get("/todoist-alternative", response_class=HTMLResponse)
async def todoist_alternative(request: Request, user: CurrentUser) -> HTMLResponse:
    """SEO landing — competitor-comparison intent.

    Targets: «альтернатива todoist», «todoist на русском», «бесплатный todoist»,
    «замена todoist». Includes FAQ schema for Google rich results."""
    return templates.TemplateResponse(request, "seo/todoist_alternative.html", {"user": user})


@router.get("/marketing-preview/{slug}/raw", include_in_schema=False)
async def marketing_preview_raw(slug: str) -> Response:
    """Serve the raw .md file as plain text — browser renders it as a text page,
    user does Ctrl+A → Ctrl+C → pastes into platforms that understand markdown
    natively (Indie Hackers, Dev.to, GitHub issues, HackerNews comments, etc.)."""
    import pathlib

    from fastapi import HTTPException, status

    allowed = {"vc-ru-post", "reddit-sideproject-post"}
    if slug not in allowed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    path = pathlib.Path("docs/marketing") / f"{slug}.md"
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file missing")
    return Response(
        content=path.read_text(encoding="utf-8"),
        media_type="text/plain; charset=utf-8",
    )


@router.get("/marketing-preview/{slug}", response_class=HTMLResponse, include_in_schema=False)
async def marketing_preview(slug: str) -> HTMLResponse:
    """Serve pre-rendered .html previews of marketing posts (VC.ru, Reddit)
    so the author can open them in a browser and use the «Copy post» button.

    Why a route and not a static file: opening a local .html in Cursor opens
    it in the editor (shows raw HTML source), not in a browser. Serving via
    URL forces the user's browser to render → ClipboardItem API works → one
    click copies HTML to clipboard for paste into VC.ru / Reddit editors.

    Pages are robots-noindex inside the HTML itself — they're not for
    discovery, they're a tool for the author.
    """
    import pathlib

    from fastapi import HTTPException, status

    # Hard-coded allowlist — only these two filenames map to a route. Anything
    # else returns 404 (defence-in-depth against path traversal even though
    # the slug is constrained to a small set).
    allowed = {"vc-ru-post", "reddit-sideproject-post"}
    if slug not in allowed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "preview not found")
    path = pathlib.Path("docs/marketing") / f"{slug}.html"
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "preview file missing")
    return HTMLResponse(path.read_text(encoding="utf-8"))


@router.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "privacy.html", {})


@router.get("/terms", response_class=HTMLResponse)
async def terms(request: Request) -> HTMLResponse:
    """Публичная оферта на оказание услуг — нужна для подключения эквайринга
    (ЮKassa/T-Bank проверяют наличие условий на сайте)."""
    return templates.TemplateResponse(request, "terms.html", {})


@router.get("/support", response_class=HTMLResponse)
async def support_form(request: Request, user: CurrentUser) -> HTMLResponse:
    """Публичная форма обращения в поддержку — доступна всем, даже без входа."""
    return templates.TemplateResponse(
        request,
        "support.html",
        {
            "user": user,
            "sent": request.query_params.get("sent") == "1",
            "error": None,
            "prefill": "",
        },
    )


@router.post("/support", response_class=HTMLResponse)
async def support_submit(
    request: Request,
    user: CurrentUser,
    session: DbSession,
    message: Annotated[str, Form()],
    email: Annotated[str, Form()] = "",
    website: Annotated[str, Form()] = "",  # honeypot: люди это поле не видят
) -> Response:
    """Приём обращения от кого угодно.

    Сохраняем на сайт (видно в /app/root) И шлём владельцу письмо. Оба канала
    сразу, как просил владелец. Антиспам: honeypot + rate-limit по IP. Письмо —
    best-effort: даже если SMTP не настроен, обращение уже сохранено.
    """
    from app.admin.service import create_complaint
    from app.auth.email import send_support_notification

    # Honeypot заполнен — это бот. Тихо отвечаем «успехом», ничего не делая.
    if website.strip():
        return RedirectResponse(url="/support?sent=1", status_code=303)

    ip = client_ip(request)
    if not hit(client_key(ip, "support"), max_calls=5, per_seconds=600):
        return templates.TemplateResponse(
            request,
            "support.html",
            {
                "user": user,
                "sent": False,
                "error": "Слишком много обращений подряд. Подожди пару минут.",
                "prefill": message,
            },
            status_code=429,
        )

    message = message.strip()
    if len(message) < 3:
        return templates.TemplateResponse(
            request,
            "support.html",
            {
                "user": user,
                "sent": False,
                "error": "Напиши хотя бы пару слов — что случилось?",
                "prefill": message,
            },
            status_code=400,
        )

    contact = (email.strip() or (user.email if user else "")) or None
    complaint = await create_complaint(
        session,
        user_id=user.id if user else None,
        body=message,
        contact_email=contact,
        page_url=request.headers.get("referer"),
        viewport=None,
        user_agent=request.headers.get("user-agent"),
    )

    try:
        await send_support_notification(
            to=get_settings().root_admin_email,
            message=message,
            reply_to=contact,
            from_user=(user.email if user else None),
            page_url=complaint.page_url,
        )
    except Exception:
        import logging

        logging.getLogger("doday.support").warning(
            "не удалось отправить письмо о поддержке (обращение сохранено на сайте)",
            exc_info=True,
        )

    return RedirectResponse(url="/support?sent=1", status_code=303)


@router.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request, user: CurrentUser) -> HTMLResponse:
    """Тарифы Free / Pro / Family.

    Способ оплаты на странице зависит от РЕАЛЬНОГО состояния магазина: пока
    ключи Robokassa не заполнены, показываем только Telegram Stars и честно
    пишем, что карты не принимаем. Как только эквайринг включён — появляется
    кнопка оплаты картой. Страница не должна обещать то, чего нет.
    """
    from app.billing import robokassa
    from app.billing.service import paid_tier

    return templates.TemplateResponse(
        request,
        "pricing.html",
        {
            "user": user,
            "beta_free_for_all": get_settings().beta_free_for_all,
            "cards_enabled": robokassa.is_configured(),
            # Реально оплаченный тариф (без беты/триала): по нему прячем «Купить»
            # у того, кто этот тариф уже держит. Аноним → None.
            "paid_tier": paid_tier(user) if user else None,
        },
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
