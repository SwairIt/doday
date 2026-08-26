"""Массовый IndexNow-пинг: сообщить Яндексу и Bing обо всех публичных страницах.

Зачем: sitemap поисковики перечитывают по своему расписанию (иногда неделями),
а IndexNow — это push: «вот список URL, приходите сейчас». Особенно важно после
разовой публикации большого раздела (блог на 300+ статей).

Запуск НА СЕРВЕРЕ из каталога проекта (нужен INDEXNOW_KEY в .env):

    uv run python scripts/indexnow_ping.py            # все публичные URL
    uv run python scripts/indexnow_ping.py --only-blog
    uv run python scripts/indexnow_ping.py --dry-run  # показать, что отправится

IndexNow принимает максимум 10 000 URL за запрос — режем на пачки по 1000.
Ошибки не роняют скрипт: это best-effort сигнал, а не критичный процесс.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Mapping
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
# pydantic-settings ищет .env относительно рабочего каталога, а из планировщика
# скрипт стартует из домашней папки — без chdir настройки не находятся.
os.chdir(_ROOT)

import httpx  # noqa: E402

from app.blog.categories import CATEGORIES  # noqa: E402
from app.blog.posts import all_posts  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.help.articles import ARTICLES  # noqa: E402

BATCH = 1000

# Оба эндпоинта принимают один и тот же протокол и делятся сигналом между собой,
# но шлём в оба: Яндекс — основной рынок, api.indexnow.org покрывает Bing и тех,
# кто использует его индекс (DuckDuckGo, Ecosia, Yahoo).
ENDPOINTS = (
    "https://yandex.com/indexnow",
    "https://api.indexnow.org/indexnow",
)

STATIC_PATHS = (
    "/",
    "/blog",
    "/for-students",
    "/for-teachers",
    "/todoist-alternative",
    "/pricing",
    "/help",
    "/changelog",
    "/roadmap",
    "/privacy",
    "/terms",
    "/qa/",
    "/pdd/",
    "/lessio",
    "/all",
)


def collect_urls(base: str, *, only_blog: bool) -> list[str]:
    urls: list[str] = [f"{base}/blog"]
    urls += [f"{base}/blog/c/{c.slug}" for c in CATEGORIES]
    urls += [f"{base}/blog/{p.slug}" for p in all_posts()]
    if not only_blog:
        urls += [f"{base}{p}" for p in STATIC_PATHS if p != "/blog"]
        urls += [f"{base}/help/{a['slug']}" for a in ARTICLES]
    # Убираем дубли, сохраняя порядок.
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


async def ping_batch(client: httpx.AsyncClient, endpoint: str, body: Mapping[str, object]) -> str:
    try:
        r = await client.post(endpoint, json=body, timeout=20.0)
        return f"{r.status_code}"
    except Exception as exc:  # сеть/таймаут — не повод падать
        return f"ошибка: {type(exc).__name__}"


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-blog", action="store_true", help="только страницы блога")
    ap.add_argument("--dry-run", action="store_true", help="не отправлять, только показать")
    args = ap.parse_args()

    settings = get_settings()
    key = (settings.indexnow_key or "").strip()
    base = settings.app_base_url.rstrip("/")
    urls = collect_urls(base, only_blog=args.only_blog)

    print(f"URL к отправке: {len(urls)}")
    print(f"Первый: {urls[0]}")
    print(f"Последний: {urls[-1]}")

    if args.dry_run:
        print("\n--dry-run: ничего не отправлено")
        return 0

    if not key:
        print(
            "\nINDEXNOW_KEY не задан в .env — отправлять нечем.\n"
            "Что сделать: придумай случайную строку 8–128 символов (латиница и цифры),\n"
            "положи её в .env как INDEXNOW_KEY=<ключ> и перезапусти сервис.\n"
            f"Проверить: {base}/<ключ>.txt должен отдавать этот же ключ."
        )
        return 1

    # Самопроверка: поисковик примет пинг, только если ключ реально отдаётся
    # сайтом. Проверяем до отправки, иначе получим тихий отказ на их стороне.
    key_url = f"{base}/{key}.txt"
    async with httpx.AsyncClient(timeout=15.0) as probe:
        try:
            r = await probe.get(key_url)
            served = r.text.strip()
        except Exception as exc:
            print(f"\nНе удалось проверить {key_url}: {type(exc).__name__}")
            return 1
    if r.status_code != 200 or served != key:
        print(
            f"\n{key_url} → {r.status_code}, отдаёт {served[:32]!r}, а ключ {key[:8]}…\n"
            "Пинг не отправляю: поисковик такой запрос отвергнет.\n"
            "Причина обычно одна — сервис запущен со старым .env. "
            "Перезапусти его и повтори."
        )
        return 1
    print(f"Ключ подтверждён: {key_url} → 200")

    host = base.replace("https://", "").replace("http://", "").strip("/")
    batches = [urls[i : i + BATCH] for i in range(0, len(urls), BATCH)]
    async with httpx.AsyncClient() as client:
        for endpoint in ENDPOINTS:
            for n, chunk in enumerate(batches, 1):
                body = {
                    "host": host,
                    "key": key,
                    "keyLocation": f"{base}/{key}.txt",
                    "urlList": chunk,
                }
                status = await ping_batch(client, endpoint, body)
                name = endpoint.split("//")[1].split("/")[0]
                print(f"{name:24} пачка {n}/{len(batches)} ({len(chunk)} URL) → {status}")

    print(
        "\nГотово. Коды 200/202 означают «принято». Индексация занимает от часов до дней —\n"
        "следи в Яндекс.Вебмастере и Google Search Console."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
