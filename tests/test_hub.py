"""Витрина студии переехала на /all и поддомен all.getdoday.ru.

Корень `/` теперь принадлежит продукту Doday Tasks (лендинг), поэтому все
проверки витрины ходят на `/all`.
"""

from httpx import AsyncClient


async def test_hub_renders_for_anon(client: AsyncClient) -> None:
    """Аноним видит витрину с карточками продуктов."""
    response = await client.get("/all", follow_redirects=False)
    assert response.status_code == 200
    body = response.text
    assert "Doday" in body
    assert "Мини-продукты" in body
    # Витрина на поддомене, поэтому ссылки на продукты — АБСОЛЮТНЫЕ на основной
    # домен: относительный /pdd/ увёл бы на all.getdoday.ru/pdd/ (дубль).
    assert 'href="https://getdoday.ru/"' in body  # лендинг Doday Tasks
    assert 'href="https://getdoday.ru/lessio"' in body
    assert 'href="https://getdoday.ru/game"' in body
    assert 'href="https://getdoday.ru/taptower"' in body
    assert "/auth/login" in body
    assert "/auth/register" in body


async def test_hub_does_not_redirect_logged_in(logged_in_client: AsyncClient) -> None:
    """Витрина доступна и залогиненным — это витрина студии, а не приложение."""
    response = await logged_in_client.get("/all", follow_redirects=False)
    assert response.status_code == 200
    assert "К задачам" in response.text


async def test_hub_links_to_github_and_email(client: AsyncClient) -> None:
    """В подвале витрины — контакты студии."""
    body = (await client.get("/all")).text
    assert "github.com/SwairIt/doday" in body
    assert "doday.support@gmail.com" in body


async def test_root_serves_product_landing(client: AsyncClient) -> None:
    """Корень домена теперь отдаёт лендинг продукта, а не витрину."""
    body = (await client.get("/")).text
    # Лендинг тудушки, не витрина студии.
    assert "Мини-продукты" not in body
