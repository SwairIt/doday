"""Валидация Telegram WebApp initData по HMAC-SHA256 c bot-token.

Telegram отдаёт каждому Mini App при открытии querystring `initData` со
всеми полями + полем `hash` (HMAC-SHA256 от data-check-string ключом
HMAC-SHA256("WebAppData", bot_token)). Сервер проверяет hash → значит
initData реально пришло от Telegram-клиента, а не подделано.

Документация: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl

# Reject initData старше 24 часов — типичная защита от replay-атак.
# Telegram сам не ограничивает срок, это наш policy.
INIT_DATA_MAX_AGE = timedelta(hours=24)


def _build_data_check_string(pairs: list[tuple[str, str]]) -> str:
    """key=value\nkey=value\n... отсортированно по ключу, без 'hash'."""
    filtered = sorted((k, v) for k, v in pairs if k != "hash")
    return "\n".join(f"{k}={v}" for k, v in filtered)


def _compute_hash(data_check_string: str, bot_token: str) -> str:
    """HMAC-SHA256 c key=HMAC-SHA256('WebAppData', bot_token)."""
    secret = hmac.new(
        key=b"WebAppData", msg=bot_token.encode("utf-8"), digestmod=hashlib.sha256
    ).digest()
    return hmac.new(
        key=secret, msg=data_check_string.encode("utf-8"), digestmod=hashlib.sha256
    ).hexdigest()


def validate_init_data(init_data: str, bot_token: str) -> dict[str, Any] | None:
    """Парсит initData, проверяет HMAC, возвращает разобранные поля или None.

    Поле `user` (если есть) дополнительно парсится из JSON — оно содержит
    Telegram user_id, first_name, language_code и т.д.

    Возвращает None если:
    - hash отсутствует или не совпадает (подделка / wrong bot_token)
    - auth_date старше INIT_DATA_MAX_AGE (replay-атака)
    - querystring невалидный

    Никогда не raise — возвращает None, caller сам решает 401 или прочее.
    """
    if not init_data or not bot_token:
        return None
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        return None
    fields = dict(pairs)
    received_hash = fields.get("hash")
    if not received_hash:
        return None

    expected_hash = _compute_hash(_build_data_check_string(pairs), bot_token)
    if not hmac.compare_digest(received_hash, expected_hash):
        return None

    auth_date_str = fields.get("auth_date")
    if not auth_date_str or not auth_date_str.isdigit():
        return None
    auth_date = datetime.fromtimestamp(int(auth_date_str), tz=UTC)
    if datetime.now(UTC) - auth_date > INIT_DATA_MAX_AGE:
        return None

    # Парсим nested user-объект если есть (Telegram кодирует его JSON-строкой).
    if "user" in fields:
        try:
            fields["user"] = json.loads(fields["user"])
        except (json.JSONDecodeError, TypeError):
            return None

    return fields


def get_telegram_user_id(parsed_init_data: dict[str, Any]) -> int | None:
    """Возвращает Telegram user_id из распарсенного initData или None."""
    user = parsed_init_data.get("user")
    if not isinstance(user, dict):
        return None
    user_id = user.get("id")
    if not isinstance(user_id, int):
        return None
    return user_id
