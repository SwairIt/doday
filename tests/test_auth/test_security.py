"""Tests for password hashing and email-verification tokens (no DB required)."""

import pytest

from app.auth.security import (
    InvalidToken,
    create_email_verification_token,
    hash_password,
    verify_email_verification_token,
    verify_password,
)


def test_hash_password_returns_argon2_hash() -> None:
    hashed = hash_password("hunter2")
    assert hashed.startswith("$argon2")
    assert hashed != "hunter2"


def test_verify_password_correct() -> None:
    hashed = hash_password("hunter2")
    assert verify_password("hunter2", hashed) is True


def test_verify_password_wrong() -> None:
    hashed = hash_password("hunter2")
    assert verify_password("wrong", hashed) is False


def test_each_hash_is_unique_due_to_salt() -> None:
    h1 = hash_password("hunter2")
    h2 = hash_password("hunter2")
    assert h1 != h2


def test_email_verification_round_trip() -> None:
    token = create_email_verification_token("user-id-123")
    assert isinstance(token, str)
    assert len(token) > 20
    assert verify_email_verification_token(token) == "user-id-123"


def test_email_verification_garbage_raises() -> None:
    with pytest.raises(InvalidToken):
        verify_email_verification_token("not-a-real-token")


def test_email_verification_expired_raises() -> None:
    # max_age=-1 means "any age greater than -1 is too old", i.e., always expired.
    token = create_email_verification_token("user-id-123")
    with pytest.raises(InvalidToken):
        verify_email_verification_token(token, max_age=-1)
