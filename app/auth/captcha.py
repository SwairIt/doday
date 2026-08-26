"""Яндекс SmartCaptcha — серверная проверка токена с формы регистрации.

Пока ключи не заданы в .env — капча выключена и verify() всегда пропускает,
чтобы регистрация работала как раньше. Fail-open: если сервис SmartCaptcha
недоступен (сеть/таймаут/5xx), тоже пропускаем — иначе временный сбой Яндекса
заблокировал бы всем регистрацию. Ботов в этот момент подстрахует honeypot.
"""

import httpx

from app.config import get_settings

VALIDATE_URL = "https://smartcaptcha.yandexcloud.net/validate"


def is_enabled() -> bool:
    """Настроена ли капча (заданы оба ключа)."""
    s = get_settings()
    return bool(s.smartcaptcha_client_key and s.smartcaptcha_server_key)


async def verify(token: str, ip: str | None) -> bool:
    """True, если проверка пройдена (человек) или капча выключена.

    :param token: значение поля ``smart-token`` из формы
    :param ip: IP клиента (Яндекс рекомендует передавать для точности)
    """
    if not is_enabled():
        return True
    if not token:
        return False
    s = get_settings()
    params = {"secret": s.smartcaptcha_server_key, "token": token}
    if ip:
        params["ip"] = ip
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(VALIDATE_URL, params=params)
    except Exception:
        return True  # сервис недоступен — не наказываем пользователя
    if resp.status_code != 200:
        return True
    try:
        return resp.json().get("status") == "ok"
    except Exception:
        return True
