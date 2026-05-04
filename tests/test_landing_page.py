"""Tests for the long marketing landing page."""

from httpx import AsyncClient


async def test_landing_renders_for_anon(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    body = response.text
    # Hero
    assert "Тудулист" in body or "тихий помощник" in body
    # All major sections present.
    assert 'id="features"' in body
    assert 'id="workflow"' in body
    assert 'id="pricing"' in body
    assert 'id="faq"' in body
    # CTA buttons.
    assert "/auth/register" in body
    assert "/auth/login" in body


async def test_landing_pricing_lists_three_tiers(client: AsyncClient) -> None:
    body = (await client.get("/")).text
    # Section heading + tier names.
    assert ">Free<" in body
    assert ">Pro<" in body or 'grad-text">Pro</h3>' in body
    assert ">Team<" in body
    # Trial promise + pricing markers.
    assert "14 дней Pro" in body or "14 дней" in body
    assert "199" in body
    assert "499" in body


async def test_landing_includes_help_link(client: AsyncClient) -> None:
    body = (await client.get("/")).text
    assert "/help" in body


async def test_landing_when_logged_in_redirects_to_app(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/", follow_redirects=False)
    assert response.status_code in (302, 303, 307)
    assert response.headers["location"].endswith("/app/today")
