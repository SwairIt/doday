"""Шифрование ключей LLM-провайдеров.

Ключ шифрования выводится из APP_SECRET_KEY через PBKDF2 — детерминированно,
поэтому переживает перезапуск процесса (деплой рестартует сервис на каждый
пуш). Соль своя, не общая с Lessio: у каждого назначения свой ключ, чтобы
компрометация одного не раскрывала другое.

KEY_VERSION хранится рядом с шифротекстом. Когда понадобится сменить схему
(другая соль, другой алгоритм), добавляется ветка в _fernet_for_version, а
старые записи продолжают читаться.
"""

from __future__ import annotations

import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import get_settings

KEY_VERSION = 1

_SALT_V1 = b"doday-ai-provider-key-v1"


class AiKeyError(Exception):
    """Ключ не удалось расшифровать: испорчен, чужой или неизвестной версии."""


def _fernet_for_version(version: int) -> Fernet:
    if version != KEY_VERSION:
        raise AiKeyError(f"неизвестная версия ключа шифрования: {version}")
    secret = (get_settings().app_secret_key or "doday-dev-fallback").encode("utf-8")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT_V1,
        iterations=100_000,
    )
    return Fernet(base64.urlsafe_b64encode(kdf.derive(secret)))


def encrypt_api_key(plain: str) -> str:
    """Зашифровать ключ провайдера для хранения в БД."""
    return _fernet_for_version(KEY_VERSION).encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_api_key(ciphertext: str, version: int = KEY_VERSION) -> str:
    """Расшифровать ключ. AiKeyError, если текст испорчен или версия чужая."""
    try:
        return _fernet_for_version(version).decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise AiKeyError("не удалось расшифровать ключ") from exc


def key_last4(plain: str) -> str:
    """Хвост ключа для показа в интерфейсе вместо самого ключа."""
    return plain[-4:] if len(plain) > 4 else plain
