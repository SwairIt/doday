"""Backup HTTP endpoints — JSON export + import."""

import json
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse, Response

from app.auth.deps import DbSession, RequiredUser
from app.backup.service import ImportError_, export_user_data, import_user_data

router = APIRouter(prefix="/api/backup", tags=["backup"])


@router.get("/export")
async def export_endpoint(user: RequiredUser, session: DbSession) -> Response:
    """Download a JSON dump of all the user's data — for backup or migration."""
    data = await export_user_data(session, user.id)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    filename = f"doday-backup-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.json"
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import", status_code=status.HTTP_200_OK)
async def import_endpoint(
    user: RequiredUser,
    session: DbSession,
    file: Annotated[UploadFile, File()],
) -> JSONResponse:
    """Import a JSON dump into the current user's account. Adds, never overwrites."""
    raw = await file.read()
    max_bytes = 5 * 1024 * 1024  # 5 MB — generous for a personal backup, caps memory abuse
    if len(raw) > max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "файл слишком большой (макс 5 МБ)"
        )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "не удалось разобрать JSON") from e
    try:
        result = await import_user_data(session, user.id, payload)
    except ImportError_ as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return JSONResponse(result)
