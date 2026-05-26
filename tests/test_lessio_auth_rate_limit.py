"""Lessio auth rate-limiting — защита от brute-force на login и spam-register."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.auth.rate_limit import reset_all


@pytest.fixture(autouse=True)
def _clear_limiter() -> None:
    """Reset in-memory limiter перед каждым тестом — иначе предыдущие
    провалы текут в следующий и счётчик «полнится» неожиданно."""
    reset_all()


async def test_login_rate_limit_kicks_in_after_10_attempts(client: AsyncClient) -> None:
    """10 неудачных попыток входа подряд → 11-я отвечает 429 вместо 401."""
    # Регистрируем юзера чтобы было кого «угадывать»
    await client.post(
        "/lessio/auth/register",
        data={"email": "rl_target@example.com", "password": "correct_pass_123"},
        follow_redirects=False,
    )
    await client.post("/lessio/auth/logout", follow_redirects=False)

    # 10 неудачных попыток — все должны давать 401
    for _ in range(10):
        resp = await client.post(
            "/lessio/auth/login",
            data={"email": "rl_target@example.com", "password": "wrong_password"},
            follow_redirects=False,
        )
        assert resp.status_code == 401

    # 11-я попытка — отбита лимитером
    resp = await client.post(
        "/lessio/auth/login",
        data={"email": "rl_target@example.com", "password": "wrong_password"},
        follow_redirects=False,
    )
    assert resp.status_code == 429
    assert "много" in resp.text.lower() or "Слишком" in resp.text


async def test_login_rate_limit_resets_on_successful_login(client: AsyncClient) -> None:
    """Успешный вход сбрасывает счётчик — после него снова доступно 10 попыток."""
    # Создаём юзера
    await client.post(
        "/lessio/auth/register",
        data={"email": "rl_reset@example.com", "password": "correct_pass_123"},
        follow_redirects=False,
    )
    await client.post("/lessio/auth/logout", follow_redirects=False)

    # 9 неудач
    for _ in range(9):
        await client.post(
            "/lessio/auth/login",
            data={"email": "rl_reset@example.com", "password": "wrong"},
            follow_redirects=False,
        )

    # Удачный вход — должен сбросить счётчик
    resp = await client.post(
        "/lessio/auth/login",
        data={"email": "rl_reset@example.com", "password": "correct_pass_123"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    await client.post("/lessio/auth/logout", follow_redirects=False)

    # Снова можем 10 неудачных подряд (счётчик пуст)
    for _ in range(10):
        resp = await client.post(
            "/lessio/auth/login",
            data={"email": "rl_reset@example.com", "password": "wrong"},
            follow_redirects=False,
        )
        assert resp.status_code == 401, "expected 401, limiter should have been reset"


async def test_register_rate_limit_kicks_in_after_5_attempts(client: AsyncClient) -> None:
    """5 регистраций с одного IP за минуту — 6-я отбита 429."""
    for i in range(5):
        resp = await client.post(
            "/lessio/auth/register",
            data={"email": f"rl_reg_{i}@example.com", "password": "strongpass123"},
            follow_redirects=False,
        )
        # Может быть 303 (успех) или 400 (email уже существует) — оба «не отбиты»
        assert resp.status_code in (302, 303, 400)
        # Logout чтобы не получить redirect на setup-profile из CurrentUser
        await client.post("/lessio/auth/logout", follow_redirects=False)

    # 6-я — отбита
    resp = await client.post(
        "/lessio/auth/register",
        data={"email": "rl_reg_blocked@example.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    assert resp.status_code == 429
    assert "много" in resp.text.lower() or "Слишком" in resp.text


async def test_login_rate_limit_isolates_by_email(client: AsyncClient) -> None:
    """Brute-force на одну почту не блокирует логин в другую с того же IP."""
    # Создаём двух юзеров
    await client.post(
        "/lessio/auth/register",
        data={"email": "alice_iso@example.com", "password": "correct_pass_123"},
        follow_redirects=False,
    )
    await client.post("/lessio/auth/logout", follow_redirects=False)
    await client.post(
        "/lessio/auth/register",
        data={"email": "bob_iso@example.com", "password": "correct_pass_123"},
        follow_redirects=False,
    )
    await client.post("/lessio/auth/logout", follow_redirects=False)

    # 10 неудач по Alice — её блокируем
    for _ in range(10):
        await client.post(
            "/lessio/auth/login",
            data={"email": "alice_iso@example.com", "password": "wrong"},
            follow_redirects=False,
        )

    # 11-я по Alice — 429
    resp = await client.post(
        "/lessio/auth/login",
        data={"email": "alice_iso@example.com", "password": "wrong"},
        follow_redirects=False,
    )
    assert resp.status_code == 429

    # Bob с того же IP — НЕ заблокирован (ключ другой)
    resp = await client.post(
        "/lessio/auth/login",
        data={"email": "bob_iso@example.com", "password": "wrong"},
        follow_redirects=False,
    )
    assert resp.status_code == 401, "limiter should isolate by email"
