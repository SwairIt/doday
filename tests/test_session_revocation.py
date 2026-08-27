"""Смена пароля должна выкидывать все остальные сессии.

Сессия живёт в подписанной cookie, серверного хранилища нет — отозвать её
раньше было нечем: угнанная cookie работала две недели независимо от того,
сменил ли владелец пароль.
"""

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.db import get_session
from app.main import app


async def _second_device(db_session: AsyncSession) -> AsyncClient:
    """Второй вход тем же аккаунтом — «угнанная» cookie в отдельной банке."""

    async def override() -> object:
        yield db_session

    app.dependency_overrides[get_session] = override
    ac = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    r = await ac.post(
        "/auth/login",
        data={"email": "logged-in@example.com", "password": "strongpass123"},
    )
    assert r.status_code == 303
    return ac


async def test_password_change_kills_other_sessions(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    stolen = await _second_device(db_session)
    assert (await stolen.get("/api/tasks")).status_code == 200

    r = await logged_in_client.post(
        "/api/profile/password",
        data={"current_password": "strongpass123", "new_password": "brandnewpass456"},
    )
    assert r.status_code == 200, r.text

    # Чужая сессия больше не работает…
    assert (await stolen.get("/api/tasks")).status_code == 401
    # …а та, из которой меняли пароль, продолжает.
    assert (await logged_in_client.get("/api/tasks")).status_code == 200
    await stolen.aclose()
    app.dependency_overrides.clear()


async def test_old_cookie_without_epoch_still_works(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    """Cookie, выданные до появления поля, номера поколения не содержат —
    выкладка не должна разлогинивать весь сайт."""
    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    assert user.session_epoch == 0
    assert (await logged_in_client.get("/api/tasks")).status_code == 200


async def test_password_change_is_rate_limited(logged_in_client: AsyncClient) -> None:
    """Перебор текущего пароля с угнанной сессии + argon2 на 64 МБ = дешёвый DoS."""
    codes = []
    for _ in range(7):
        r = await logged_in_client.post(
            "/api/profile/password",
            data={"current_password": "wrong-guess", "new_password": "whatever12345"},
        )
        codes.append(r.status_code)
    assert 429 in codes
