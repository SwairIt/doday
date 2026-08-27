"""HTTP-общение с LLM-провайдером по OpenAI-совместимому протоколу.

Ключ пользователя нигде не логируется и не попадает в текст ошибки: сообщения
для пользователя собираются из фиксированных фраз, а не из ответа провайдера.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Sequence
from typing import TypedDict

import httpx
import structlog

logger = structlog.get_logger(__name__)

# Один токен — нам нужно лишь убедиться, что ключ принят и модель существует.
_VERIFY_MAX_TOKENS = 1


class Message(TypedDict):
    """Сообщение в формате OpenAI-совместимого API."""

    role: str
    content: str


class AiProviderError(Exception):
    """Провайдер отказал. user_message безопасен для показа пользователю.

    provider_detail — что ответил сам провайдер, с вырезанным ключом. Без
    него человек видит только «ключ не принят» и не понимает, чинить ключ,
    модель или тариф.
    """

    def __init__(self, user_message: str, provider_detail: str = "") -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.provider_detail = provider_detail


# Признаки «дело в ключе» в теле ответа. Нужны потому, что провайдеры не
# сходятся в кодах: Cloud.ru на неверный ключ отвечает 400 (проверено
# 2026-08-27), большинство остальных — 401.
_BAD_KEY_MARKERS = ("api key", "api_key", "apikey", "unauthorized", "invalid key", "ключ")

_BAD_KEY_MESSAGE = (
    "Ключ не принят провайдером. Проверь, что скопировал его целиком, "
    "что выбран тот же провайдер, где ключ выпущен, и что ключ ещё не отозван."
)


def _sanitized_detail(body: str, api_key: str) -> str:
    """Ответ провайдера, пригодный для показа: без ключа и без разметки."""
    text = body.replace(api_key, "···") if api_key else body
    if api_key and len(api_key) > 8:
        text = text.replace(api_key[:8], "···")
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())[:300]


def _looks_like_bad_key(body: str) -> bool:
    low = body.lower()
    return any(marker in low for marker in _BAD_KEY_MARKERS)


def _message_for(status: int, body: str) -> str:
    """Понятная фраза по коду ответа и телу.

    Тело используем только для классификации — наружу оно не попадает, чтобы
    не утащить в интерфейс лишние подробности провайдера.
    """
    if status in (401, 403):
        return _BAD_KEY_MESSAGE
    if status == 402:
        return "На счету провайдера закончились средства."
    if status == 404:
        return "Провайдер не знает такой модели — проверь название."
    if status == 429:
        return "Слишком часто: провайдер ограничил частоту запросов. Попробуй через минуту."
    if status == 400:
        if _looks_like_bad_key(body):
            return _BAD_KEY_MESSAGE
        return "Провайдер отклонил запрос — проверь адрес API и название модели."
    return "Провайдер не отвечает. Попробуй позже."


async def verify_key(*, base_url: str, api_key: str, model: str, timeout_s: float = 20.0) -> None:
    """Сделать минимальный запрос и убедиться, что ключ рабочий.

    Возвращается молча при успехе, иначе AiProviderError.
    """
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "max_tokens": _VERIFY_MAX_TOKENS,
        "messages": [{"role": "user", "content": "ping"}],
    }
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.post(
                url, json=payload, headers={"Authorization": f"Bearer {api_key}"}
            )
    except httpx.HTTPError as exc:
        logger.warning("ai_verify_transport_error", error=type(exc).__name__)
        raise AiProviderError("Провайдер не отвечает. Попробуй позже.") from exc

    if response.status_code >= 400:
        body = response.text[:500]
        logger.info("ai_verify_rejected", status=response.status_code)
        raise AiProviderError(
            _message_for(response.status_code, body), _sanitized_detail(body, api_key)
        )


async def stream_completion(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: Sequence[Message],
    max_tokens: int = 2000,
    timeout_s: float = 120.0,
) -> AsyncIterator[str]:
    """Отдаёт куски ответа модели по мере генерации.

    Провайдер шлёт server-sent events: строки «data: {json}», последняя —
    «data: [DONE]». Разбираем построчно и отдаём только текст.

    Вызывающий обязан закрыть генератор (например, выйти из `async for`) при
    обрыве соединения с пользователем — иначе токены продолжат тратиться.
    """
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "stream": True,
        "messages": list(messages),
    }
    try:
        async with (
            httpx.AsyncClient(timeout=timeout_s) as client,
            client.stream(
                "POST", url, json=payload, headers={"Authorization": f"Bearer {api_key}"}
            ) as response,
        ):
            if response.status_code >= 400:
                body = (await response.aread()).decode("utf-8", "replace")[:500]
                logger.info("ai_stream_rejected", status=response.status_code)
                raise AiProviderError(
                    _message_for(response.status_code, body), _sanitized_detail(body, api_key)
                )
            async for line in response.aiter_lines():
                chunk = _chunk_from_line(line)
                if chunk:
                    yield chunk
    except httpx.HTTPError as exc:
        logger.warning("ai_stream_transport_error", error=type(exc).__name__)
        raise AiProviderError("Провайдер не отвечает. Попробуй позже.") from exc


def _chunk_from_line(line: str) -> str:
    """Достать текст из строки SSE. Пустая строка — нечего отдавать."""
    if not line.startswith("data:"):
        return ""
    data = line[5:].strip()
    if not data or data == "[DONE]":
        return ""
    try:
        parsed = json.loads(data)
        choices = parsed.get("choices") or []
        if not choices:
            return ""
        delta = choices[0].get("delta") or {}
        content = delta.get("content")
        return str(content) if content else ""
    except (json.JSONDecodeError, AttributeError, IndexError):
        # Провайдер прислал что-то неожиданное — пропускаем кусок, но не
        # роняем весь ответ: остальные куски могут быть валидными.
        return ""
