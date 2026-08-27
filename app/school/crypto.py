"""Шифрование токенов школьных порталов.

`school_integrations.auth_token` — это `aupd_token` от dnevnik.mos.ru или
Школьного портала МО. Он живёт около десяти дней и даёт полный доступ к
дневнику ребёнка на портале: оценки, расписание, данные класса. Лежал он в
базе открытым текстом — с комментарием в модели «before going to prod this
column should be encrypted».

Схема та же, что у ключей ИИ (`app/ai/crypto.py`): Fernet, ключ выводится из
APP_SECRET_KEY через PBKDF2. Соль своя — компрометация одного назначения не
должна раскрывать другое.

Старые записи хранятся открытым текстом, поэтому `decrypt_token` возвращает
значение как есть, если это не наш шифротекст. При следующем сохранении
интеграции запись перешифруется.
"""

from __future__ import annotations

import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import get_settings

_SALT_V1 = b"doday-school-portal-token-v1"
_PREFIX = "enc1:"


def _fernet() -> Fernet:
    secret = (get_settings().app_secret_key or "doday-dev-fallback").encode("utf-8")
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=_SALT_V1, iterations=100_000)
    return Fernet(base64.urlsafe_b64encode(kdf.derive(secret)))


def encrypt_token(plain: str) -> str:
    """Зашифровать токен портала для хранения в БД."""
    return _PREFIX + _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_token(stored: str | None) -> str | None:
    """Достать токен из БД.

    Значение без нашего префикса — запись, сделанная до шифрования: отдаём
    как есть, иначе интеграция сломается у всех, кто её уже настроил.
    """
    if not stored:
        return None
    if not stored.startswith(_PREFIX):
        return stored
    try:
        return _fernet().decrypt(stored[len(_PREFIX) :].encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # Ключ приложения сменили — расшифровать нечем. Пусть интеграция
        # честно скажет «нет токена» и попросит подключить заново.
        return None
