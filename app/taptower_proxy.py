"""Тонкий reverse-proxy: /taptower/* → бэкенд игры Tap Tower на 127.0.0.1:8012.

Позволяет отдавать отдельный проект (игру) под getdoday.ru/taptower/,
переиспользуя существующий TLS + домен. Цель проксирования — localhost,
поэтому async httpx здесь безопасен: проблема uvloop/IPv4 касается только
DNS-резолва api.telegram.org, локальные соединения не затронуты."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response

router = APIRouter(tags=["taptower"])

_GAME_BACKEND = "http://127.0.0.1:8012"
_HOP_BY_HOP = {"content-length", "transfer-encoding", "connection", "host", "keep-alive"}


@router.get("/taptower", include_in_schema=False)
async def taptower_root() -> RedirectResponse:
    return RedirectResponse(url="/taptower/", status_code=308)


@router.api_route("/taptower/{path:path}", methods=["GET", "POST"], include_in_schema=False)
async def taptower_proxy(request: Request, path: str = "") -> Response:
    url = f"{_GAME_BACKEND}/{path}"
    body = await request.body()
    fwd_headers = {k: v for k, v in request.headers.items() if k.lower() not in _HOP_BY_HOP}
    try:
        async with httpx.AsyncClient(timeout=65.0) as client:
            upstream = await client.request(
                request.method,
                url,
                params=request.query_params,
                content=body,
                headers=fwd_headers,
            )
    except httpx.HTTPError:
        return Response(content=b"Tap Tower backend unavailable", status_code=502)

    resp_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in _HOP_BY_HOP}
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=resp_headers,
        media_type=upstream.headers.get("content-type"),
    )
