"""HTTP routes for the company-facing standup helpers."""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.auth.deps import DbSession, RequiredUser
from app.company.service import build_standup_report, render_markdown

router = APIRouter(prefix="/api/company", tags=["company"])


@router.get("/standup")
async def standup(user: RequiredUser, session: DbSession) -> dict[str, list[dict[str, object]]]:
    return await build_standup_report(session, user.id)


@router.get("/standup.md", response_class=PlainTextResponse)
async def standup_markdown(user: RequiredUser, session: DbSession) -> str:
    report = await build_standup_report(session, user.id)
    return render_markdown(report)
