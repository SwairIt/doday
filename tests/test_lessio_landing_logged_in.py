"""Lessio landing + marketing-страницы: header показывает «В кабинет» для логиненных
вместо «Войти / Стать репетитором». Hero CTA тоже динамичен.

Регрессия от user'feedback'а 2026-05-26: «когда вошёл и вышел в лендинг,
всё равно показывает Войти/Стать репетитором — хотя должно быть В кабинет».
"""

from __future__ import annotations

from httpx import AsyncClient


async def test_landing_anon_shows_register_cta(client: AsyncClient) -> None:
    """Без сессии — должно быть «Войти / Стать репетитором»."""
    resp = await client.get("/lessio")
    assert resp.status_code == 200
    body = resp.text
    # Header — стандартные CTA для анонима
    assert "Стать репетитором" in body
    assert "/lessio/auth/login" in body
    assert "/lessio/auth/register" in body
    # Hero — «Создать страницу бесплатно»
    assert "Создать страницу бесплатно" in body


async def test_landing_logged_in_shows_cabinet_button(client: AsyncClient) -> None:
    """С сессией — header должен показать «В кабинет» + «Выйти», скрыть Войти/Стать."""
    # Регистрируем юзера — он автоматически залогинен
    await client.post(
        "/lessio/auth/register",
        data={"email": "land_logged@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    # Открываем /lessio лендинг
    resp = await client.get("/lessio")
    assert resp.status_code == 200
    body = resp.text
    # Должен быть «В кабинет» + «Выйти»
    assert "В кабинет" in body
    assert "/lessio/app/today" in body
    assert "Выйти" in body
    assert "/lessio/auth/logout" in body
    # И hero — «Открыть мой кабинет» вместо «Создать страницу бесплатно»
    assert "Открыть мой кабинет" in body
    # Final CTA — «С возвращением 👋»
    assert "С возвращением" in body


async def test_marketing_pages_show_cabinet_when_logged_in(client: AsyncClient) -> None:
    """/lessio/blog и /lessio/dlya-* тоже должны показать «В кабинет» через _base_marketing."""
    await client.post(
        "/lessio/auth/register",
        data={"email": "mp_logged@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    for path in ("/lessio/blog", "/lessio/help", "/lessio/dlya-repetitorov"):
        resp = await client.get(path)
        assert resp.status_code == 200, f"{path}: HTTP {resp.status_code}"
        body = resp.text
        # Header должен показать «В кабинет» (через partial _base_marketing.html)
        assert "В кабинет" in body, f"{path}: header не показывает «В кабинет»"


async def test_marketing_anon_shows_login_cta(client: AsyncClient) -> None:
    """/lessio/blog, /lessio/help, /lessio/dlya-* без сессии — «Войти / Начать»."""
    for path in ("/lessio/blog", "/lessio/help", "/lessio/dlya-repetitorov"):
        resp = await client.get(path)
        assert resp.status_code == 200
        body = resp.text
        assert "Войти" in body, f"{path}: header не показывает «Войти»"
        assert "/lessio/auth/login" in body


async def test_logo_single_source_truth(client: AsyncClient) -> None:
    """Логотип одинаков везде — gradient-square с «L» + текст «Lessio»."""
    for path in ("/lessio", "/lessio/blog", "/lessio/help", "/lessio/dlya-repetitorov"):
        resp = await client.get(path)
        assert resp.status_code == 200
        body = resp.text
        # Старый ✦-вариант должен исчезнуть с marketing-страниц
        assert "✦ Lessio" not in body, f"{path}: остался старый ✦-логотип"
        # Новый gradient-square должен быть
        assert "from-violet-500 to-pink-500" in body, f"{path}: нет gradient-логотипа"


async def test_logout_from_landing_works(client: AsyncClient) -> None:
    """Кнопка «Выйти» на лендинге должна работать."""
    await client.post(
        "/lessio/auth/register",
        data={"email": "logout_test@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    # POST на logout
    resp = await client.post("/lessio/auth/logout", follow_redirects=False)
    assert resp.status_code in (302, 303)
    # После logout — landing снова показывает анон-CTA
    resp = await client.get("/lessio")
    body = resp.text
    assert "Стать репетитором" in body
    assert "В кабинет" not in body
