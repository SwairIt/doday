"""Doday Arena — браузерный FPS на Three.js, отдаётся как статика с /arena/.

Игра — обычные ES-модули без сборщика, поэтому весь смысл роутера в том, чтобы
отдать `app/static/arena/` по адресу /arena/ и подставить index.html на корень.
Отдельный роутер (а не общий StaticFiles) нужен ради заголовков: WASM-физике
Rapier требуется корректный content-type, а игровые ассеты стоит кэшировать
иначе, чем остальную статику сайта.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

router = APIRouter(tags=["game"])

_ARENA_ROOT = (Path(__file__).resolve().parent.parent / "static" / "arena").resolve()

# Типы, которые Starlette/mimetypes на Windows определяет неверно или никак
_CONTENT_TYPES = {
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".wasm": "application/wasm",
    ".json": "application/json; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
}


@router.get("/arena", include_in_schema=False)
async def arena_root() -> RedirectResponse:
    return RedirectResponse(url="/arena/", status_code=308)


@router.get("/arena/{path:path}", include_in_schema=False)
async def arena_asset(path: str = "") -> FileResponse:
    """Отдаёт файл игры, защищаясь от выхода за пределы каталога."""
    target = (_ARENA_ROOT / (path or "index.html")).resolve()
    if not target.is_relative_to(_ARENA_ROOT) or not target.is_file():
        raise HTTPException(status_code=404)

    media_type = _CONTENT_TYPES.get(target.suffix.lower())
    return FileResponse(target, media_type=media_type)
