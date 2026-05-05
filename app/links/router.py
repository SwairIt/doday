"""HTTP API for task links — list, create, delete."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.auth.deps import DbSession, RequiredUser
from app.links.schemas import LinkedTaskOut, LinkIn
from app.links.service import create_link, delete_link, list_links_for_task

router = APIRouter(prefix="/api/tasks", tags=["links"])


@router.get("/{task_id}/links")
async def get_links(
    task_id: UUID, user: RequiredUser, session: DbSession
) -> list[LinkedTaskOut]:
    return await list_links_for_task(session, user.id, task_id)


@router.post("/{task_id}/links", status_code=status.HTTP_201_CREATED)
async def post_link(
    task_id: UUID,
    payload: LinkIn,
    user: RequiredUser,
    session: DbSession,
) -> dict[str, str]:
    try:
        link = await create_link(
            session,
            user.id,
            source_task_id=task_id,
            target_task_id=payload.target_task_id,
            note=payload.note,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e
    except PermissionError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    return {"id": str(link.id), "status": "ok"}


@router.delete("/{task_id}/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_link(
    task_id: UUID,
    link_id: UUID,
    user: RequiredUser,
    session: DbSession,
) -> None:
    ok = await delete_link(session, user.id, link_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "связь не найдена")
