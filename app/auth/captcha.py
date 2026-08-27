"""Google reCAPTCHA (v2 «я не робот») — серверная проверка токена с формы.

Пока ключи не заданы в .env — капча выключена и verify() всегда пропускает,
чтобы регистрация работала как раньше. Fail-open: если сервис reCAPTCHA
недоступен (сеть/таймаут/5xx), тоже пропускаем — иначе временный сбой Google
заблокировал бы всем регистрацию. Ботов в этот момент подстрахует honeypot.
"""

import httpx

from app.config import get_settings

VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


def is_enabled() -> bool:
    """Настроена ли капча (заданы оба ключа)."""
    s = get_settings()
    return bool(s.recaptcha_site_key and s.recaptcha_secret_key)


async def verify(token: str, ip: str | None) -> bool:
    """True, если проверка пройдена (человек) или капча выключена.

    :param token: значение поля ``g-recaptcha-response`` из формы
    :param ip: IP клиента (передаём в remoteip для точности)
    """
    if not is_enabled():
        return True
    if not token:
        return False
    s = get_settings()
    data = {"secret": s.recaptcha_secret_key, "response": token}
    if ip:
        data["remoteip"] = ip
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(VERIFY_URL, data=data)
    except Exception:
        return True  # сервис недоступен — не наказываем пользователя
    if resp.status_code != 200:
        return True
    try:
        # .json() отдаёт Any — приводим результат к bool явно.
        return bool(resp.json().get("success") is True)
    except Exception:
        return True
