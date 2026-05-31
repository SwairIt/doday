"""HTTP routes for Doday PDD.

* ``router`` — public HTML pages mounted at ``/pdd``
* ``api_router`` — JSON endpoints mounted at ``/api/pdd``

Both consume ``app.pdd.service``; they never touch the ORM directly.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.auth.deps import CurrentUser, DbSession, RequiredUser
from app.billing.products import PRODUCTS
from app.pdd import seo, service
from app.pdd.schemas import AttemptIn, AttemptOut

router = APIRouter(prefix="/pdd", tags=["pdd"])
api_router = APIRouter(prefix="/api/pdd", tags=["pdd-api"])
_templates = Jinja2Templates(directory="app/templates")


# ─── public HTML pages ──────────────────────────────────────────────────────


@router.get("", include_in_schema=False)
@router.get("/", response_class=HTMLResponse)
async def hub(request: Request, session: DbSession, user: CurrentUser) -> HTMLResponse:
    tickets = await service.list_tickets(session)
    topics = await service.list_topics(session)
    total = await service.question_count(session)
    pro = await service.is_pdd_pro(session, user)
    return _templates.TemplateResponse(
        "pdd/index.html",
        {
            "request": request,
            "user": user,
            "is_pdd_pro": pro,
            "tickets": tickets,
            "topics": topics,
            "total_questions": total,
        },
    )


@router.get("/bilet/{number}", response_class=HTMLResponse)
async def ticket_page(
    request: Request, number: int, session: DbSession, user: CurrentUser
) -> HTMLResponse:
    ticket = await service.get_ticket(session, number)
    if ticket is None:
        raise HTTPException(404, "Билет не найден")
    questions = await service.ticket_questions(session, ticket.id)
    return _templates.TemplateResponse(
        "pdd/ticket.html",
        {
            "request": request,
            "user": user,
            "is_pdd_pro": await service.is_pdd_pro(session, user),
            "ticket": ticket,
            "questions": questions,
            "meta": seo.ticket_meta(ticket),
        },
    )


@router.get("/tema/{slug}", response_class=HTMLResponse)
async def topic_page(
    request: Request, slug: str, session: DbSession, user: CurrentUser
) -> HTMLResponse:
    topic = await service.get_topic_by_slug(session, slug)
    if topic is None:
        raise HTTPException(404, "Тема не найдена")
    questions = await service.topic_questions(session, topic.id)
    return _templates.TemplateResponse(
        "pdd/topic.html",
        {
            "request": request,
            "user": user,
            "is_pdd_pro": await service.is_pdd_pro(session, user),
            "topic": topic,
            "questions": questions,
            "meta": seo.topic_meta(topic),
        },
    )


@router.get("/vopros/{public_slug}", response_class=HTMLResponse)
async def question_page(
    request: Request, public_slug: str, session: DbSession, user: CurrentUser
) -> HTMLResponse:
    question = await service.get_question_by_slug(session, public_slug)
    if question is None:
        raise HTTPException(404, "Вопрос не найден")
    return _templates.TemplateResponse(
        "pdd/question.html",
        {
            "request": request,
            "user": user,
            "question": question,
            "meta": seo.question_meta(question),
            "jsonld": seo.question_jsonld(question),
        },
    )


@router.get("/pro", response_class=HTMLResponse)
async def pro_landing(request: Request, session: DbSession, user: CurrentUser) -> HTMLResponse:
    products = [p for p in PRODUCTS if p.code.startswith("pdd_")]
    return _templates.TemplateResponse(
        "pdd/pro.html",
        {
            "request": request,
            "user": user,
            "is_pdd_pro": await service.is_pdd_pro(session, user),
            "products": products,
        },
    )


@router.get("/my", response_class=HTMLResponse)
async def my_page(request: Request, session: DbSession, user: CurrentUser) -> Response:
    if user is None:
        return RedirectResponse("/auth/login?next=/pdd/my", status_code=303)
    mistakes = await service.recent_mistakes(session, user)
    stats = await service.attempt_stats(session, user)
    pro = await service.is_pdd_pro(session, user)
    weak_topics = await service.weak_topics(session, user) if pro else []
    return _templates.TemplateResponse(
        "pdd/my.html",
        {
            "request": request,
            "user": user,
            "is_pdd_pro": pro,
            "mistakes": mistakes,
            "stats": stats,
            "weak_topics": weak_topics,
        },
    )


@api_router.post("/attempt", response_model=AttemptOut)
async def record_attempt_endpoint(
    data: AttemptIn, user: RequiredUser, session: DbSession
) -> AttemptOut:
    """Persist one practice/exam/trainer answer for a logged-in user."""
    try:
        return await service.record_attempt(session, user, data)
    except service.NotFound as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/sitemap.xml")
async def sitemap(session: DbSession) -> Response:
    from xml.sax.saxutils import escape as xmlescape

    tickets = await service.list_tickets(session)
    topics = await service.list_topics(session)

    parts = ['<?xml version="1.0" encoding="UTF-8"?>']
    parts.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    parts.append(
        f"  <url><loc>{seo.BASE}/pdd/</loc><changefreq>weekly</changefreq>"
        "<priority>0.9</priority></url>"
    )
    parts.append(
        f"  <url><loc>{seo.BASE}/pdd/pro</loc><changefreq>monthly</changefreq>"
        "<priority>0.6</priority></url>"
    )
    for ticket in tickets:
        parts.append(
            f"  <url><loc>{seo.BASE}/pdd/bilet/{ticket.number}</loc>"
            "<changefreq>monthly</changefreq><priority>0.7</priority></url>"
        )
    for topic in topics:
        parts.append(
            f"  <url><loc>{seo.BASE}/pdd/tema/{xmlescape(topic.slug)}</loc>"
            "<changefreq>monthly</changefreq><priority>0.7</priority></url>"
        )
    # All questions — the bulk of the indexable surface.
    for question in await service.all_question_slugs(session):
        parts.append(
            f"  <url><loc>{seo.BASE}/pdd/vopros/{xmlescape(question)}</loc>"
            "<changefreq>monthly</changefreq><priority>0.5</priority></url>"
        )
    parts.append("</urlset>")
    return Response(content="\n".join(parts), media_type="application/xml")
