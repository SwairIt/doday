"""HTTP-общение с LLM-провайдером по OpenAI-совместимому протоколу.

Ключ пользователя нигде не логируется и не попадает в текст ошибки: сообщения
для пользователя собираются из фиксированных фраз, а не из ответа провайдера.
"""

from __future__ import annotations

import httpx
import structlog

logger = structlog.get_logger(__name__)

# Один токен — нам нужно лишь убедиться, что ключ принят и модель существует.
_VERIFY_MAX_TOKENS = 1


class AiProviderError(Exception):
    """Провайдер отказал. user_message безопасен для показа пользователю."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


def _message_for_status(status: int) -> str:
    if status in (401, 403):
        return "Ключ не принят провайдером — проверь, что скопировал его целиком."
    if status == 402:
        return "На счету провайдера закончились средства."
    if status == 404:
        return "Провайдер не знает такой модели — проверь название."
    if status == 429:
        return "Слишком часто: провайдер ограничил частоту запросов. Попробуй через минуту."
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
        logger.info("ai_verify_rejected", status=response.status_code)
        raise AiProviderError(_message_for_status(response.status_code))
