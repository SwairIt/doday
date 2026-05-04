"""Tests for the redesigned auth pages — show/hide password, strength meter,
caps-lock detector, marketing side-panel."""

from httpx import AsyncClient


async def test_login_page_has_polish_features(client: AsyncClient) -> None:
    body = (await client.get("/auth/login")).text
    # Show/hide password toggle present.
    assert "showPwd" in body
    assert "Показать пароль" in body or "Скрыть пароль" in body
    # Caps-lock detector wired.
    assert "capsOn" in body
    assert "Caps Lock" in body
    # Email live validation.
    assert "validateEmail" in body
    # Marketing side panel.
    assert "Pomodoro-таймер" in body or "marketing" in body.lower() or "🎯" in body
    # Forgot password link.
    assert "/auth/forgot" in body
    # Two-column grid.
    assert "md:grid-cols-2" in body


async def test_register_page_has_strength_meter(client: AsyncClient) -> None:
    body = (await client.get("/auth/register")).text
    assert "Надёжность пароля" in body
    # All four password requirements rendered.
    assert "8+ символов" in body
    assert "Буквы Aa" in body
    assert "Цифра" in body
    assert "Спецсимвол" in body
    # Strength scoring helper.
    assert "scoreLabel" in body
    # Trial promise on the marketing side.
    assert "14 дней" in body


async def test_register_page_has_show_hide_and_caps(client: AsyncClient) -> None:
    body = (await client.get("/auth/register")).text
    assert "showPwd" in body
    assert "capsOn" in body


async def test_login_page_keeps_csrf_safe_target(client: AsyncClient) -> None:
    body = (await client.get("/auth/login")).text
    assert 'action="/auth/login"' in body
    assert 'method="post"' in body


async def test_auth_pages_link_to_each_other(client: AsyncClient) -> None:
    login = (await client.get("/auth/login")).text
    register = (await client.get("/auth/register")).text
    assert "/auth/register" in login
    assert "/auth/login" in register
