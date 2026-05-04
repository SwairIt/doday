"""Profile management — account deletion + audience switching."""

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, status
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


@router.post("/audience")
async def update_audience(
    user: RequiredUser,
    session: DbSession,
    audience: Annotated[str, Form()],
) -> dict[str, str | None]:
    """Switch the user's audience (school / company / personal / clear).

    Empty string clears the choice; the audience-specific widgets revert to
    the generic experience until a new value is picked.
    """
    if audience == "":
        new_value: str | None = None
    elif audience in ("school", "company", "personal"):
        new_value = audience
    else:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "неизвестная аудитория")
    user.audience = new_value
    await session.commit()
    return {"audience": new_value}
