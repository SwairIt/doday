"""Preserve the public landing's content and optional video playback contract."""

import re

from httpx import AsyncClient


async def test_landing_keeps_every_existing_section(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    sections = set(re.findall(r'<section[^>]+id="([^"]+)"', response.text))
    assert {
        "features",
        "school",
        "workflow",
        "pricing",
        "screenshots",
        "comparison",
        "testimonials",
        "three-steps",
        "blog",
        "ecosystem",
        "faq",
        "updates",
    } <= sections
    assert "Боева Лариса Владимировна" in response.text
    assert "/auth/register" in response.text
    assert "/auth/login" in response.text
    assert "дней Pro в подарок" not in response.text


async def test_landing_video_requires_a_user_action(client: AsyncClient) -> None:
    body = (await client.get("/")).text
    video = re.search(r"<video\b([^>]+)>", body)
    assert video is not None
    assert 'preload="none"' in video[1]
    assert "autoplay" not in video[1]
    assert "controls" in video[1]
    assert "playsinline" in video[1]
    assert 'data-src="/static/landing/doday-in-action.mp4"' in video[1]
    assert '<source src="/static/landing/doday-in-action.mp4"' not in body
    assert "<noscript>" in body
    assert "/static/landing/demo.vtt" in body
    assert "particles_fx" not in body


async def test_demo_video_supports_partial_download(client: AsyncClient) -> None:
    response = await client.get(
        "/static/landing/doday-in-action.mp4", headers={"Range": "bytes=0-31"}
    )
    assert response.status_code == 206
    assert response.headers["content-type"] == "video/mp4"
    assert response.headers["content-range"].startswith("bytes 0-31/")
    assert len(response.content) == 32
    assert b"ftyp" in response.content
