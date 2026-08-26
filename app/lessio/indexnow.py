"""IndexNow protocol — мгновенный ping Яндекс/Bing для индексации новых tutor-страниц.

https://yandex.com/support/webmaster/indexnow/key.html

Ключ должен быть размещён на https://getdoday.ru/<key>.txt и совпадать с
INDEXNOW_KEY в env. Принцип «fire-and-forget» — fail silently, чтобы не
блокировать tutor-flow если поисковик недоступен.
"""

from __future__ import annotations

import httpx
import structlog

from app.config import get_settings

_log = structlog.get_logger(__name__)

_INDEXNOW_HOSTS = (
    "https://yandex.com/indexnow",
    # Bing и все, кто использует его индекс: DuckDuckGo, Ecosia, Yahoo.
    "https://api.indexnow.org/indexnow",
)


async def ping_indexnow(*, urls: list[str]) -> bool:
    """POST список URL в Yandex IndexNow. Returns True если accepted (HTTP 200/202).

    Не raise при любых ошибках — конверсия > точность сигнала.
    """
    settings = get_settings()
    key = (settings.indexnow_key or "").strip()
    if not key or not urls:
        return False
    base = settings.app_base_url.rstrip("/")
    host = base.replace("https://", "").replace("http://", "").strip("/")
    body = {
        "host": host,
        "key": key,
        "keyLocation": f"{base}/{key}.txt",
        "urlList": urls,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            accepted = False
            for endpoint in _INDEXNOW_HOSTS:
                r = await client.post(endpoint, json=body)
                ok = r.status_code in (200, 202)
                accepted = accepted or ok
                _log.info(
                    "lessio_indexnow_pinged",
                    endpoint=endpoint,
                    status=r.status_code,
                    urls_count=len(urls),
                    accepted=ok,
                )
            return accepted
    except Exception as exc:
        _log.warning("lessio_indexnow_failed", error=str(exc), urls_count=len(urls))
        return False
