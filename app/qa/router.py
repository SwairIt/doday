"""HTTP routes for Razbery (Doday Q&A).

Two routers exported:
* `router` — HTML pages mounted at `/qa/`
* `api_router` — JSON endpoints mounted at `/api/qa/`

Both consume the service layer (`app.qa.service`); they do not touch
the ORM directly. All state changes go through `service`.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.auth.deps import CurrentUser, DbSession, RequiredAdmin, RequiredUser
from app.qa import seo, service
from app.qa.models import QAQuestion, QAUserStats
from app.qa.schemas import (
    AnswerCreate,
    QuestionCreate,
    ReportIn,
    UserStatsUpdate,
    VoteIn,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.auth.models import User
from app.qa.service import (
    Forbidden,
    NotFound,
    QAError,
    RateLimited,
    ValidationError,
)

router = APIRouter(prefix="/qa", tags=["qa"])
api_router = APIRouter(prefix="/api/qa", tags=["qa-api"])
_templates = Jinja2Templates(directory="app/templates")


# ─── helpers ───────────────────────────────────────────────────────────────


def _err_to_http(exc: QAError) -> HTTPException:
    if isinstance(exc, NotFound):
        return HTTPException(404, str(exc))
    if isinstance(exc, Forbidden):
        return HTTPException(403, str(exc))
    if isinstance(exc, RateLimited):
        return HTTPException(429, str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(422, str(exc))
    return HTTPException(400, str(exc))


async def _user_stats_for(session: AsyncSession, user: User | None) -> QAUserStats | None:
    if user is None:
        return None
    stats: QAUserStats | None = await session.get(QAUserStats, user.id)
    return stats


# ─── HTML routes ───────────────────────────────────────────────────────────


@router.get("", include_in_schema=False)
@router.get("/", response_class=HTMLResponse)
async def hub(
    request: Request,
    session: DbSession,
    user: CurrentUser,
) -> HTMLResponse:
    subjects = await service.list_subjects(session)
    recent = await service.list_questions(session, sort="recent", limit=20)
    top = await service.list_questions(session, sort="top", limit=10)
    unanswered = await service.list_questions(session, only_unanswered=True, limit=10)
    stats = await _user_stats_for(session, user)
    return _templates.TemplateResponse(
        "qa/index.html",
        {
            "request": request,
            "user": user,
            "user_stats": stats,
            "subjects": subjects,
            "recent": recent,
            "top": top,
            "unanswered": unanswered,
        },
    )


@router.get("/s/{subject_slug}", response_class=HTMLResponse)
@router.get("/s/{subject_slug}/", response_class=HTMLResponse)
async def subject_page(
    request: Request,
    subject_slug: str,
    session: DbSession,
    user: CurrentUser,
    grade: int | None = Query(default=None, ge=5, le=11),
    sort: str = Query(default="recent"),
    page: int = Query(default=1, ge=1),
) -> HTMLResponse:
    subject = await service.get_subject_by_slug(session, subject_slug)
    if subject is None:
        raise HTTPException(404, "Предмет не найден")
    limit = 20
    offset = (page - 1) * limit
    questions = await service.list_questions(
        session,
        subject_id=subject.id,
        grade=grade,
        sort=sort,
        offset=offset,
        limit=limit,
    )
    total = await service.count_questions(session, subject_id=subject.id, grade=grade)
    stats = await _user_stats_for(session, user)
    return _templates.TemplateResponse(
        "qa/subject.html",
        {
            "request": request,
            "user": user,
            "user_stats": stats,
            "subject": subject,
            "questions": questions,
            "grade": grade,
            "sort": sort,
            "page": page,
            "limit": limit,
            "total": total,
            "has_more": offset + len(questions) < total,
        },
    )


@router.get("/s/{subject_slug}/{grade}", response_class=HTMLResponse)
async def subject_grade_page(
    request: Request,
    subject_slug: str,
    grade: int,
    session: DbSession,
    user: CurrentUser,
    sort: str = Query(default="recent"),
    page: int = Query(default=1, ge=1),
) -> HTMLResponse:
    if not (5 <= grade <= 11):
        raise HTTPException(404, "Класс вне допустимого диапазона")
    return await subject_page(
        request=request,
        subject_slug=subject_slug,
        session=session,
        user=user,
        grade=grade,
        sort=sort,
        page=page,
    )


@router.get("/q/{id_slug}", response_class=HTMLResponse)
async def question_page(
    request: Request,
    id_slug: str,
    session: DbSession,
    user: CurrentUser,
) -> Response:
    # Path matches both `665` and `665-chto-takoe-...` — split manually because
    # FastAPI path params cannot mix int-with-dash-string in one segment.
    if "-" in id_slug:
        id_part, question_slug = id_slug.split("-", 1)
    else:
        id_part, question_slug = id_slug, ""
    try:
        question_id = int(id_part)
    except ValueError as exc:
        raise HTTPException(404, "Вопрос не найден") from exc

    q = await service.get_question(session, question_id)
    if q is None:
        raise HTTPException(404, "Вопрос не найден")
    # Canonical-slug redirect
    if question_slug and question_slug != q.slug:
        return RedirectResponse(
            f"/qa/q/{q.id}-{q.slug}", status_code=status.HTTP_301_MOVED_PERMANENTLY
        )
    await service.increment_view_count(session, q.id)
    answers = await service.get_answers_for_question(session, q.id)
    subject = await service.get_subject(session, q.subject_id)
    stats = await _user_stats_for(session, user)

    # User's vote state
    user_q_votes: dict[int, int] = {}
    user_a_votes: dict[int, int] = {}
    if user is not None:
        user_q_votes = await service.get_user_votes(session, user.id, "q", [q.id])
        user_a_votes = await service.get_user_votes(session, user.id, "a", [a.id for a in answers])

    jsonld = seo.qapage_jsonld(q, answers, subject) if subject else {}

    # Author display info
    author_stats: QAUserStats | None = None
    if q.author_id is not None:
        author_stats = await session.get(QAUserStats, q.author_id)

    from uuid import UUID as _UUID

    answer_author_stats: dict[_UUID, QAUserStats] = {}
    for a in answers:
        if a.author_id is not None and a.author_id not in answer_author_stats:
            s = await session.get(QAUserStats, a.author_id)
            if s is not None:
                answer_author_stats[a.author_id] = s

    return _templates.TemplateResponse(
        "qa/question.html",
        {
            "request": request,
            "user": user,
            "user_stats": stats,
            "question": q,
            "answers": answers,
            "subject": subject,
            "author_stats": author_stats,
            "answer_author_stats": answer_author_stats,
            "user_q_votes": user_q_votes,
            "user_a_votes": user_a_votes,
            "jsonld": json.dumps(jsonld, ensure_ascii=False),
            "canonical_url": f"https://getdoday.ru/qa/q/{q.id}-{q.slug}",
        },
    )


@router.get("/ask", response_class=HTMLResponse)
async def ask_page(
    request: Request,
    session: DbSession,
    user: CurrentUser,
    subject: str | None = Query(default=None),
) -> Response:
    # Anonymous users get a friendly redirect to login, not a 401.
    # Doday auth doesn't honour `?next=`, so after login the user lands on
    # /doday/app/today and can return via the top-nav "Razbery" link.
    if user is None:
        return RedirectResponse("/auth/login", status_code=303)
    subjects = await service.list_subjects(session)
    stats = await service.ensure_user_stats(session, user)
    await session.commit()
    return _templates.TemplateResponse(
        "qa/ask.html",
        {
            "request": request,
            "user": user,
            "user_stats": stats,
            "subjects": subjects,
            "preselected_subject": subject,
        },
    )


@router.get("/u/{display_slug}", response_class=HTMLResponse)
async def user_profile(
    request: Request,
    display_slug: str,
    session: DbSession,
    user: CurrentUser,
) -> HTMLResponse:
    target_stats = await service.get_user_stats_by_slug(session, display_slug)
    if target_stats is None:
        raise HTTPException(404, "Пользователь не найден")
    questions = await service.list_user_questions(session, target_stats.user_id)
    answers = await service.list_user_answers(session, target_stats.user_id)
    stats = await _user_stats_for(session, user)
    return _templates.TemplateResponse(
        "qa/user.html",
        {
            "request": request,
            "user": user,
            "user_stats": stats,
            "target_stats": target_stats,
            "questions": questions,
            "answers": answers,
        },
    )


@router.get("/search", response_class=HTMLResponse)
async def search_page(
    request: Request,
    session: DbSession,
    user: CurrentUser,
    q: str = Query(default=""),
    subject_slug: str | None = Query(default=None),
    grade: int | None = Query(default=None, ge=5, le=11),
) -> HTMLResponse:
    subjects = await service.list_subjects(session)
    subject_id = None
    if subject_slug:
        s = await service.get_subject_by_slug(session, subject_slug)
        subject_id = s.id if s else None
    results = await service.search_questions(
        session, q, subject_id=subject_id, grade=grade, limit=40
    )
    stats = await _user_stats_for(session, user)
    return _templates.TemplateResponse(
        "qa/search.html",
        {
            "request": request,
            "user": user,
            "user_stats": stats,
            "query": q,
            "subjects": subjects,
            "subject_slug": subject_slug,
            "grade": grade,
            "results": results,
        },
    )


@router.get("/og/{question_id}.svg")
async def og_image(question_id: int, session: DbSession) -> Response:
    q = await service.get_question(session, question_id)
    if q is None:
        raise HTTPException(404)
    subject = await service.get_subject(session, q.subject_id)
    if subject is None:
        raise HTTPException(404)
    svg = seo.og_image_svg(q, subject)
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/sitemap.xml")
async def sitemap(session: DbSession) -> Response:
    from xml.sax.saxutils import escape as xmlescape

    subjects = await service.list_subjects(session)
    # All visible questions
    rows = (
        await session.execute(
            select(QAQuestion.id, QAQuestion.slug, QAQuestion.updated_at)
            .where(QAQuestion.is_hidden.is_(False))
            .order_by(QAQuestion.id.desc())
            .limit(50000)  # Google's sitemap limit per file
        )
    ).all()

    parts = ['<?xml version="1.0" encoding="UTF-8"?>']
    parts.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    parts.append(
        "  <url><loc>https://getdoday.ru/qa/</loc><changefreq>hourly</changefreq><priority>0.9</priority></url>"
    )
    for s in subjects:
        parts.append(
            f"  <url><loc>https://getdoday.ru/qa/s/{xmlescape(s.slug)}</loc>"
            f"<changefreq>daily</changefreq><priority>0.7</priority></url>"
        )
        for g in range(s.min_grade, s.max_grade + 1):
            parts.append(
                f"  <url><loc>https://getdoday.ru/qa/s/{xmlescape(s.slug)}/{g}</loc>"
                f"<changefreq>daily</changefreq><priority>0.6</priority></url>"
            )
    for qid, slug, updated_at in rows:
        lastmod = updated_at.isoformat() if updated_at else ""
        parts.append(
            f"  <url><loc>https://getdoday.ru/qa/q/{qid}-{xmlescape(slug)}</loc>"
            f"<lastmod>{lastmod}</lastmod><changefreq>weekly</changefreq><priority>0.5</priority></url>"
        )
    parts.append("</urlset>")
    return Response(content="\n".join(parts), media_type="application/xml")


@router.get("/admin/reports", response_class=HTMLResponse)
async def admin_reports(
    request: Request,
    session: DbSession,
    admin: RequiredAdmin,
) -> HTMLResponse:
    reports = await service.list_open_reports(session, limit=200)
    return _templates.TemplateResponse(
        "qa/admin_reports.html",
        {"request": request, "user": admin, "reports": reports},
    )


# ─── JSON API ──────────────────────────────────────────────────────────────


@api_router.post("/q", status_code=201)
async def api_create_question(
    payload: QuestionCreate,
    session: DbSession,
    user: RequiredUser,
) -> JSONResponse:
    try:
        q = await service.create_question(session, user, payload)
    except QAError as exc:
        raise _err_to_http(exc) from exc
    await session.commit()
    return JSONResponse(
        {"id": q.id, "url": f"/qa/q/{q.id}-{q.slug}"},
        status_code=201,
    )


@api_router.post("/q/{qid}/a", status_code=201)
async def api_create_answer(
    qid: int,
    payload: AnswerCreate,
    session: DbSession,
    user: RequiredUser,
) -> JSONResponse:
    try:
        a = await service.create_answer(session, user, qid, payload)
    except QAError as exc:
        raise _err_to_http(exc) from exc
    await session.commit()
    return JSONResponse({"id": a.id}, status_code=201)


@api_router.post("/vote")
async def api_vote(
    payload: VoteIn,
    session: DbSession,
    user: RequiredUser,
) -> JSONResponse:
    try:
        new_score = await service.vote(
            session, user, payload.target_type, payload.target_id, payload.value
        )
    except QAError as exc:
        raise _err_to_http(exc) from exc
    await session.commit()
    return JSONResponse({"score": new_score, "your_vote": payload.value})


@api_router.post("/a/{aid}/accept")
async def api_accept(
    aid: int,
    session: DbSession,
    user: RequiredUser,
) -> JSONResponse:
    try:
        await service.accept_answer(session, user, aid)
    except QAError as exc:
        raise _err_to_http(exc) from exc
    await session.commit()
    return JSONResponse({"accepted": True})


@api_router.post("/q/{qid}/unaccept")
async def api_unaccept(
    qid: int,
    session: DbSession,
    user: RequiredUser,
) -> JSONResponse:
    try:
        await service.unaccept_answer(session, user, qid)
    except QAError as exc:
        raise _err_to_http(exc) from exc
    await session.commit()
    return JSONResponse({"accepted": False})


@api_router.post("/report", status_code=201)
async def api_report(
    payload: ReportIn,
    session: DbSession,
    user: RequiredUser,
) -> JSONResponse:
    try:
        r = await service.report(session, user, payload)
    except QAError as exc:
        raise _err_to_http(exc) from exc
    await session.commit()
    return JSONResponse({"id": r.id, "status": r.status}, status_code=201)


@api_router.post("/profile")
async def api_update_profile(
    payload: UserStatsUpdate,
    session: DbSession,
    user: RequiredUser,
) -> JSONResponse:
    stats = await service.update_user_stats(session, user, payload)
    await session.commit()
    return JSONResponse(
        {
            "display_name": stats.display_name,
            "display_slug": stats.display_slug,
            "bio": stats.bio,
            "avatar_emoji": stats.avatar_emoji,
        }
    )


@api_router.get("/similar")
async def api_similar(
    title: str,
    session: DbSession,
    user: RequiredUser,
    subject_slug: str | None = None,
) -> JSONResponse:
    subject_id = None
    if subject_slug:
        s = await service.get_subject_by_slug(session, subject_slug)
        subject_id = s.id if s else None
    similar = await service.find_similar(session, title, subject_id=subject_id, limit=3)
    return JSONResponse(
        {
            "results": [
                {"id": q.id, "title": q.title, "url": f"/qa/q/{q.id}-{q.slug}"} for q in similar
            ]
        }
    )


@api_router.post("/admin/report/{rid}/resolve")
async def api_resolve_report(
    rid: int,
    session: DbSession,
    admin: RequiredAdmin,
    hide: bool = False,
) -> JSONResponse:
    try:
        r = await service.resolve_report(session, rid, hide_target=hide)
    except QAError as exc:
        raise _err_to_http(exc) from exc
    await session.commit()
    return JSONResponse({"id": r.id, "status": r.status})


# ─── form-based ask submit (HTMX-friendly, for users without JS) ───────────


@router.post("/ask", response_class=HTMLResponse)
async def ask_submit(
    request: Request,
    session: DbSession,
    user: RequiredUser,
    subject_slug: Annotated[str, Form()],
    title: Annotated[str, Form()],
    body_md: Annotated[str, Form()],
    grade: Annotated[int | None, Form()] = None,
) -> Response:
    payload = QuestionCreate(subject_slug=subject_slug, grade=grade, title=title, body_md=body_md)
    try:
        q = await service.create_question(session, user, payload)
    except QAError as exc:
        await session.rollback()
        subjects = await service.list_subjects(session)
        stats = await service.ensure_user_stats(session, user)
        return _templates.TemplateResponse(
            "qa/ask.html",
            {
                "request": request,
                "user": user,
                "user_stats": stats,
                "subjects": subjects,
                "preselected_subject": subject_slug,
                "error": str(exc),
                "form_title": title,
                "form_body_md": body_md,
                "form_grade": grade,
            },
            status_code=422 if isinstance(exc, ValidationError) else 400,
        )
    await session.commit()
    return RedirectResponse(f"/qa/q/{q.id}-{q.slug}", status_code=303)


@router.post("/q/{qid}/answer", response_class=HTMLResponse)
async def answer_submit(
    request: Request,
    qid: int,
    session: DbSession,
    user: RequiredUser,
    answer_md: Annotated[str, Form()],
    explanation_md: Annotated[str, Form()],
) -> Response:
    payload = AnswerCreate(answer_md=answer_md, explanation_md=explanation_md)
    try:
        await service.create_answer(session, user, qid, payload)
    except QAError as exc:
        await session.rollback()
        # Reload the question page with an error
        q = await service.get_question(session, qid)
        if q is None:
            raise HTTPException(404) from exc
        return RedirectResponse(
            f"/qa/q/{q.id}-{q.slug}?err={str(exc)[:200]}",
            status_code=303,
        )
    await session.commit()
    q = await service.get_question(session, qid)
    if q is None:
        raise HTTPException(404)
    return RedirectResponse(f"/qa/q/{q.id}-{q.slug}", status_code=303)
