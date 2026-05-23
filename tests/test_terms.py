"""Integration tests for the /terms public-offer page and the legal-requisites
footer that ЮKassa / T-Bank inspect when reviewing the application."""

from httpx import AsyncClient


async def test_terms_renders(client: AsyncClient) -> None:
    response = await client.get("/terms")
    assert response.status_code == 200
    # Key facts the payment processor looks for in the offer.
    assert "Условия использования" in response.text
    assert "Самозанятый" in response.text or "самозанятый" in response.text
    assert "550149009405" in response.text  # ИНН
    assert "Боев Ярослав Дмитриевич" in response.text
    # Price + a digital-delivery clause.
    assert "199" in response.text and "299" in response.text
    assert "цифров" in response.text.lower() or "моментально" in response.text


async def test_public_footer_shows_requisites_on_landing(client: AsyncClient) -> None:
    body = (await client.get("/")).text
    assert "550149009405" in body
    assert "Самозанятый" in body or "самозанятый" in body
    assert "/terms" in body  # link to offer is in the footer


async def test_public_footer_shows_requisites_on_privacy(client: AsyncClient) -> None:
    body = (await client.get("/privacy")).text
    assert "550149009405" in body
    assert "/terms" in body


async def test_public_footer_shows_requisites_on_pricing(client: AsyncClient) -> None:
    body = (await client.get("/pricing")).text
    assert "550149009405" in body
    assert "/terms" in body
