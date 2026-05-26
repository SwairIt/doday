"""Lessio SEO niche-landings.

Каждая страница нацелена на конкретный long-tail-запрос в РФ-поиске и заточена
под одну нишу/use-case. Контент пишем в шаблонах — это не CMS.

URLs (kept transliterated where it boosts ru-keyword matching):
  /lessio/dlya-repetitorov
  /lessio/dlya-trenerov
  /lessio/dlya-psihologov
  /lessio/alternativa-calendly
  /lessio/oplata-cherez-telegram
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/lessio", tags=["lessio-seo"])
_templates = Jinja2Templates(directory="app/templates")


def _seo_meta(slug: str) -> dict[str, str]:
    """Подбор meta tags + JSON-LD данных по slug — заполняется в шаблонах,
    тут только canonical-URL и базовые поля."""
    return {
        "canonical": f"https://getdoday.ru/lessio/{slug}",
        "page_slug": slug,
    }


@router.get("/dlya-repetitorov", response_class=HTMLResponse, include_in_schema=False)
async def page_for_tutors(request: Request) -> HTMLResponse:
    return _templates.TemplateResponse(
        request,
        "lessio/seo/dlya_repetitorov.html",
        {
            "meta": _seo_meta("dlya-repetitorov"),
            "page_title": "Сервис записи и оплаты для репетиторов · Lessio",
            "page_description": (
                "Lessio — публичная страница записи для репетиторов: клиент тапает "
                "→ выбирает время → платит. Без сайта, переводов на сбер и Excel-таблиц."
            ),
        },
    )


@router.get("/dlya-trenerov", response_class=HTMLResponse, include_in_schema=False)
async def page_for_trainers(request: Request) -> HTMLResponse:
    return _templates.TemplateResponse(
        request,
        "lessio/seo/dlya_trenerov.html",
        {
            "meta": _seo_meta("dlya-trenerov"),
            "page_title": "Сервис записи для онлайн-тренеров · Lessio",
            "page_description": (
                "Для онлайн-тренеров: клиент выбирает время через вашу публичную "
                "страницу, оплата через Telegram Stars, автонапоминания и Jitsi-ссылка."
            ),
        },
    )


@router.get("/dlya-psihologov", response_class=HTMLResponse, include_in_schema=False)
async def page_for_psychologists(request: Request) -> HTMLResponse:
    return _templates.TemplateResponse(
        request,
        "lessio/seo/dlya_psihologov.html",
        {
            "meta": _seo_meta("dlya-psihologov"),
            "page_title": "Запись и оплата для онлайн-психологов · Lessio",
            "page_description": (
                "Для онлайн-психологов и коучей: анонимная страница записи, безопасная "
                "оплата в Telegram, автонапоминания за 24 часа и за час до встречи."
            ),
        },
    )


@router.get("/alternativa-calendly", response_class=HTMLResponse, include_in_schema=False)
async def page_calendly_alternative(request: Request) -> HTMLResponse:
    return _templates.TemplateResponse(
        request,
        "lessio/seo/alternativa_calendly.html",
        {
            "meta": _seo_meta("alternativa-calendly"),
            "page_title": "Альтернатива Calendly в России · Lessio",
            "page_description": (
                "Lessio — российская альтернатива Calendly: на русском, с приёмом оплаты "
                "через Telegram Stars (без РФ-карт), бесплатный тариф, без VPN."
            ),
        },
    )


@router.get("/oplata-cherez-telegram", response_class=HTMLResponse, include_in_schema=False)
async def page_telegram_payments(request: Request) -> HTMLResponse:
    return _templates.TemplateResponse(
        request,
        "lessio/seo/oplata_cherez_telegram.html",
        {
            "meta": _seo_meta("oplata-cherez-telegram"),
            "page_title": "Приём оплаты через Telegram Stars для учителей · Lessio",
            "page_description": (
                "Telegram Stars — как принимать оплату от клиентов через мессенджер. "
                "Без эквайринга, без расчётного счёта, для самозанятых и физлиц."
            ),
        },
    )
