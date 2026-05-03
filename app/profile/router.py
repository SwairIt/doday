"""Profile management — currently just account deletion."""

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import delete

from app.auth.deps import DbSession, RequiredUser
from app.auth.models import User

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.post("/delete")
async def delete_account(request: Request, user: RequiredUser, session: DbSession) -> Response:
    """Cascade-delete the user. Tasks/projects/labels go with them via ON DELETE CASCADE."""
    await session.execute(delete(User).where(User.id == user.id))
    await session.commit()
    request.session.clear()
    return RedirectResponse(url="/?deleted=1", status_code=303)
