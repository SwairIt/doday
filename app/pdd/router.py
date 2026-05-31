"""HTTP routes for Doday PDD.

* ``router`` — public HTML pages mounted at ``/pdd`` (ABM) and ``/pdd/cd`` (CD)
* ``api_router`` — JSON endpoints mounted at ``/api/pdd``

ABM lives at the root (``/pdd/...``, the indexed default); CD mirrors it under
``/pdd/cd/...``. Shared ``_render_*`` helpers do the work; thin route pairs pass
the category. Both consume ``app.pdd.service`` — never the ORM directly.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.auth.deps import CurrentUser, DbSession, RequiredUser
from app.billing.products import PRODUCTS
from app.pdd import seo, service
from app.pdd.schemas import AttemptIn, AttemptOut, ExamSaveIn

router = APIRouter(prefix="/pdd", tags=["pdd"])
api_router = APIRouter(prefix="/api/pdd", tags=["pdd-api"])
_templates = Jinja2Templates(directory="app/templates")


def _ctx(request: Request, user: object, category: str, **extra: object) -> dict[str, object]:
    """Common template context — every category page carries the category code +
    its URL prefix so links stay category-scoped."""
    base: dict[str, object] = {
        "request": request,
        "user": user,
        "cat": category,
        "cat_prefix": service.category_prefix(category),
        "categories": service.CATEGORIES,
    }
    base.update(extra)
    return base


# ─── shared renderers ───────────────────────────────────────────────────────


async def _render_hub(
    request: Request, session: DbSession, user: CurrentUser, category: str
) -> HTMLResponse:
    tickets = await service.list_tickets(session, category)
    topics = await service.list_topics(session, category)
    total = await service.question_count(session, category)
    pro = await service.is_pdd_pro(session, user)
    progress = await service.ticket_progress(session, user, category) if user else {}
    return _templates.TemplateResponse(
        "pdd/index.html",
        _ctx(
            request,
            user,
            category,
            is_pdd_pro=pro,
            tickets=tickets,
            topics=topics,
            total_questions=total,
            progress=progress,
        ),
    )


async def _render_ticket(
    request: Request, number: int, session: DbSession, user: CurrentUser, category: str
) -> HTMLResponse:
    ticket = await service.get_ticket(session, category, number)
    if ticket is None:
        raise HTTPException(404, "Билет не найден")
    questions = await service.ticket_questions(session, ticket.id)
    return _templates.TemplateResponse(
        "pdd/ticket.html",
        _ctx(
            request,
            user,
            category,
            is_pdd_pro=await service.is_pdd_pro(session, user),
            ticket=ticket,
            questions=questions,
            meta=seo.ticket_meta(ticket),
        ),
    )


async def _render_topic(
    request: Request, slug: str, session: DbSession, user: CurrentUser, category: str
) -> HTMLResponse:
    topic = await service.get_topic_by_slug(session, slug)
    if topic is None:
        raise HTTPException(404, "Тема не найдена")
    questions = await service.topic_questions(session, topic.id, category)
    return _templates.TemplateResponse(
        "pdd/topic.html",
        _ctx(
            request,
            user,
            category,
            is_pdd_pro=await service.is_pdd_pro(session, user),
            topic=topic,
            questions=questions,
            meta=seo.topic_meta(topic, category),
        ),
    )


async def _render_exam(
    request: Request, session: DbSession, user: CurrentUser, category: str
) -> HTMLResponse:
    questions = await service.random_exam_questions(session, category)
    payload = service.exam_payload(questions)
    return _templates.TemplateResponse(
        "pdd/exam.html",
        _ctx(
            request,
            user,
            category,
            is_pdd_pro=await service.is_pdd_pro(session, user),
            exam_json=json.dumps(payload, ensure_ascii=False),
            exam_count=len(payload),
            mistake_limit=service.EXAM_MISTAKE_LIMIT,
        ),
    )


async def _render_marathon(
    request: Request, session: DbSession, user: CurrentUser, category: str
) -> HTMLResponse:
    total = await service.question_count(session, category)
    return _templates.TemplateResponse(
        "pdd/marathon.html",
        _ctx(request, user, category, total_questions=total),
    )


async def _render_search(
    request: Request, q: str, session: DbSession, user: CurrentUser, category: str
) -> HTMLResponse:
    results = await service.search_questions(session, category, q) if q else []
    return _templates.TemplateResponse(
        "pdd/search.html",
        _ctx(
            request,
            user,
            category,
            is_pdd_pro=await service.is_pdd_pro(session, user),
            query=q,
            results=results,
        ),
    )


async def _random_ticket_redirect(session: DbSession, category: str) -> RedirectResponse:
    number = await service.random_ticket_number(session, category)
    prefix = service.category_prefix(category)
    target = f"/pdd{prefix}/bilet/{number}" if number else f"/pdd{prefix}/"
    return RedirectResponse(target, status_code=303)


# ─── ABM (root) + CD (/cd) route pairs ──────────────────────────────────────


@router.get("", include_in_schema=False)
@router.get("/", response_class=HTMLResponse)
async def hub(request: Request, session: DbSession, user: CurrentUser) -> HTMLResponse:
    return await _render_hub(request, session, user, "ABM")


@router.get("/cd", include_in_schema=False)
@router.get("/cd/", response_class=HTMLResponse)
async def hub_cd(request: Request, session: DbSession, user: CurrentUser) -> HTMLResponse:
    return await _render_hub(request, session, user, "CD")


@router.get("/bilet/{number}", response_class=HTMLResponse)
async def ticket_page(
    request: Request, number: int, session: DbSession, user: CurrentUser
) -> HTMLResponse:
    return await _render_ticket(request, number, session, user, "ABM")


@router.get("/cd/bilet/{number}", response_class=HTMLResponse)
async def ticket_page_cd(
    request: Request, number: int, session: DbSession, user: CurrentUser
) -> HTMLResponse:
    return await _render_ticket(request, number, session, user, "CD")


@router.get("/tema/{slug}", response_class=HTMLResponse)
async def topic_page(
    request: Request, slug: str, session: DbSession, user: CurrentUser
) -> HTMLResponse:
    return await _render_topic(request, slug, session, user, "ABM")


@router.get("/cd/tema/{slug}", response_class=HTMLResponse)
async def topic_page_cd(
    request: Request, slug: str, session: DbSession, user: CurrentUser
) -> HTMLResponse:
    return await _render_topic(request, slug, session, user, "CD")


@router.get("/ekzamen", response_class=HTMLResponse)
async def exam_page(request: Request, session: DbSession, user: CurrentUser) -> HTMLResponse:
    return await _render_exam(request, session, user, "ABM")


@router.get("/cd/ekzamen", response_class=HTMLResponse)
async def exam_page_cd(request: Request, session: DbSession, user: CurrentUser) -> HTMLResponse:
    return await _render_exam(request, session, user, "CD")


@router.get("/marafon", response_class=HTMLResponse)
async def marathon_page(request: Request, session: DbSession, user: CurrentUser) -> HTMLResponse:
    return await _render_marathon(request, session, user, "ABM")


@router.get("/cd/marafon", response_class=HTMLResponse)
async def marathon_page_cd(request: Request, session: DbSession, user: CurrentUser) -> HTMLResponse:
    return await _render_marathon(request, session, user, "CD")


@router.get("/poisk", response_class=HTMLResponse)
async def search_page(
    request: Request, session: DbSession, user: CurrentUser, q: str = Query(default="")
) -> HTMLResponse:
    return await _render_search(request, q, session, user, "ABM")


@router.get("/cd/poisk", response_class=HTMLResponse)
async def search_page_cd(
    request: Request, session: DbSession, user: CurrentUser, q: str = Query(default="")
) -> HTMLResponse:
    return await _render_search(request, q, session, user, "CD")


@router.get("/sluchainyi-bilet")
async def random_ticket(session: DbSession) -> RedirectResponse:
    return await _random_ticket_redirect(session, "ABM")


@router.get("/cd/sluchainyi-bilet")
async def random_ticket_cd(session: DbSession) -> RedirectResponse:
    return await _random_ticket_redirect(session, "CD")


# ─── category-agnostic pages ────────────────────────────────────────────────


@router.get("/vopros/{public_slug}", response_class=HTMLResponse)
async def question_page(
    request: Request, public_slug: str, session: DbSession, user: CurrentUser
) -> HTMLResponse:
    question = await service.get_question_by_slug(session, public_slug)
    if question is None:
        raise HTTPException(404, "Вопрос не найден")
    return _templates.TemplateResponse(
        "pdd/question.html",
        _ctx(
            request,
            user,
            question.category,
            is_pdd_pro=await service.is_pdd_pro(session, user),
            question=question,
            meta=seo.question_meta(question),
            jsonld=seo.question_jsonld(question),
        ),
    )


@router.get("/pro", response_class=HTMLResponse)
async def pro_landing(request: Request, session: DbSession, user: CurrentUser) -> HTMLResponse:
    products = [p for p in PRODUCTS if p.code.startswith("pdd_")]
    return _templates.TemplateResponse(
        "pdd/pro.html",
        _ctx(
            request,
            user,
            "ABM",
            is_pdd_pro=await service.is_pdd_pro(session, user),
            products=products,
        ),
    )


@router.get("/my", response_class=HTMLResponse)
async def my_page(request: Request, session: DbSession, user: CurrentUser) -> Response:
    if user is None:
        return RedirectResponse("/auth/login?next=/pdd/my", status_code=303)
    mistakes = await service.recent_mistakes(session, user)
    stats = await service.attempt_stats(session, user)
    pro = await service.is_pdd_pro(session, user)
    weak_topics = await service.weak_topics(session, user) if pro else []
    exams = await service.list_exam_sessions(session, user) if pro else []
    return _templates.TemplateResponse(
        "pdd/my.html",
        _ctx(
            request,
            user,
            "ABM",
            is_pdd_pro=pro,
            mistakes=mistakes,
            stats=stats,
            weak_topics=weak_topics,
            exams=exams,
        ),
    )


@router.get("/trener", response_class=HTMLResponse)
async def trainer_page(request: Request, session: DbSession, user: CurrentUser) -> Response:
    if user is None:
        return RedirectResponse("/auth/login?next=/pdd/trener", status_code=303)
    if not await service.is_pdd_pro(session, user):
        return RedirectResponse("/pdd/pro", status_code=303)
    questions = await service.trainer_queue(session, user)
    return _templates.TemplateResponse(
        "pdd/trainer.html",
        _ctx(request, user, "ABM", is_pdd_pro=True, questions=questions),
    )


@router.get("/sbornik", response_class=HTMLResponse)
async def study_sheet_page(request: Request, session: DbSession, user: CurrentUser) -> Response:
    if user is None:
        return RedirectResponse("/auth/login?next=/pdd/sbornik", status_code=303)
    if not await service.is_pdd_pro(session, user):
        return RedirectResponse("/pdd/pro", status_code=303)
    return _templates.TemplateResponse(
        "pdd/sbornik.html",
        {
            "request": request,
            "user": user,
            "is_pdd_pro": True,
            "weak_topics": await service.weak_topics(session, user),
            "mistakes": await service.recent_mistakes(session, user),
        },
    )


# ─── JSON API ───────────────────────────────────────────────────────────────


@api_router.post("/attempt", response_model=AttemptOut)
async def record_attempt_endpoint(
    data: AttemptIn, user: RequiredUser, session: DbSession
) -> AttemptOut:
    """Persist one practice/exam/trainer answer for a logged-in user."""
    try:
        return await service.record_attempt(session, user, data)
    except service.NotFound as exc:
        raise HTTPException(404, str(exc)) from exc


@api_router.post("/exam/save")
async def save_exam_endpoint(
    data: ExamSaveIn, user: RequiredUser, session: DbSession
) -> dict[str, object]:
    """Persist a finished exam run — Pro only (free runs stay client-side)."""
    await service.require_pdd_pro(session, user)
    try:
        exam = await service.save_exam_session(session, user, data.answers)
    except service.NotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    return {
        "id": exam.id,
        "passed": exam.status == "passed",
        "mistakes": exam.mistakes,
        "total": exam.total,
    }


@api_router.get("/deck")
async def deck_endpoint(
    session: DbSession,
    category: str = Query(default="ABM"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
) -> dict[str, object]:
    """A page of question payloads for the marathon deck."""
    cat = service.normalize_category(category)
    questions = await service.deck_questions(session, cat, offset, limit)
    return {"questions": service.exam_payload(questions), "offset": offset, "limit": limit}


# ─── sitemap ────────────────────────────────────────────────────────────────


@router.get("/sitemap.xml")
async def sitemap(session: DbSession) -> Response:
    from xml.sax.saxutils import escape as xmlescape

    parts = ['<?xml version="1.0" encoding="UTF-8"?>']
    parts.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for cat in service.CATEGORIES:
        prefix = service.category_prefix(cat)
        parts.append(
            f"  <url><loc>{seo.BASE}/pdd{prefix}/</loc><changefreq>weekly</changefreq>"
            "<priority>0.9</priority></url>"
        )
        for ticket in await service.list_tickets(session, cat):
            parts.append(
                f"  <url><loc>{seo.BASE}/pdd{prefix}/bilet/{ticket.number}</loc>"
                "<changefreq>monthly</changefreq><priority>0.7</priority></url>"
            )
        for topic in await service.list_topics(session, cat):
            parts.append(
                f"  <url><loc>{seo.BASE}/pdd{prefix}/tema/{xmlescape(topic.slug)}</loc>"
                "<changefreq>monthly</changefreq><priority>0.6</priority></url>"
            )
    parts.append(
        f"  <url><loc>{seo.BASE}/pdd/pro</loc><changefreq>monthly</changefreq>"
        "<priority>0.6</priority></url>"
    )
    for slug in await service.all_question_slugs(session):
        parts.append(
            f"  <url><loc>{seo.BASE}/pdd/vopros/{xmlescape(slug)}</loc>"
            "<changefreq>monthly</changefreq><priority>0.5</priority></url>"
        )
    parts.append("</urlset>")
    return Response(content="\n".join(parts), media_type="application/xml")
