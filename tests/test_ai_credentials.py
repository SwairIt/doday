"""Тесты этапа 1 ИИ-помощника: шифрование ключей, справочник, CRUD, API."""

from __future__ import annotations

import pytest

from app.ai.crypto import KEY_VERSION, AiKeyError, decrypt_api_key, encrypt_api_key, key_last4


def test_encrypt_decrypt_roundtrip() -> None:
    plain = "sk-test-abcdef1234567890"
    ciphertext = encrypt_api_key(plain)
    assert ciphertext != plain
    assert plain not in ciphertext
    assert decrypt_api_key(ciphertext) == plain


def test_encrypt_is_not_deterministic() -> None:
    """Fernet добавляет соль и метку времени — два шифрования дают разный текст."""
    plain = "sk-test-abcdef1234567890"
    assert encrypt_api_key(plain) != encrypt_api_key(plain)


def test_decrypt_rejects_garbage() -> None:
    with pytest.raises(AiKeyError):
        decrypt_api_key("не-шифротекст")


def test_decrypt_rejects_unknown_version() -> None:
    with pytest.raises(AiKeyError):
        decrypt_api_key(encrypt_api_key("sk-test"), version=999)


def test_key_last4() -> None:
    assert key_last4("sk-test-abcdef1234567890") == "7890"
    assert key_last4("abc") == "abc"


def test_key_version_is_current() -> None:
    assert KEY_VERSION == 1
