"""Tests for auth Pydantic schemas (input validation, no DB required)."""

import pytest
from pydantic import ValidationError

from app.auth.schemas import LoginIn, RegisterIn


def test_register_in_lowercases_email() -> None:
    payload = RegisterIn(email="MIXED@School.RU", password="strongpass123")
    assert payload.email == "mixed@school.ru"


def test_register_in_strips_whitespace_in_email() -> None:
    payload = RegisterIn(email="  kid@school.ru  ", password="strongpass123")
    assert payload.email == "kid@school.ru"


def test_register_in_rejects_short_password() -> None:
    with pytest.raises(ValidationError):
        RegisterIn(email="kid@school.ru", password="short")


def test_register_in_rejects_invalid_email() -> None:
    with pytest.raises(ValidationError):
        RegisterIn(email="not-an-email", password="strongpass123")


def test_login_in_lowercases_email() -> None:
    payload = LoginIn(email="USER@DOMAIN.COM", password="anything")
    assert payload.email == "user@domain.com"
