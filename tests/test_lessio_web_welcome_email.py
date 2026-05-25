"""Welcome email после регистрации tutor'а — фаер в setup-profile (не в register, т.к. там
ещё нет профиля, slug, и т.д.)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@patch("app.lessio.email.send_welcome_email", new_callable=AsyncMock, return_value=True)
async def test_setup_profile_sends_welcome_email(
    mock_send: AsyncMock, client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.post(
        "/lessio/auth/register",
        data={"email": "wel@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    await client.post(
        "/lessio/app/setup-profile",
        data={
            "slug": "welcome_t",
            "display_name": "Welcome Test",
            "niche": "english",
        },
        follow_redirects=False,
    )
    mock_send.assert_awaited_once()
    kwargs = mock_send.await_args.kwargs
    assert kwargs["to"] == "wel@e.com"
    assert kwargs["tutor"].slug == "welcome_t"


@patch("app.lessio.email.aiosmtplib.send", new_callable=AsyncMock)
async def test_welcome_email_renders_template(mock_send: AsyncMock) -> None:
    """Smoke: send_welcome_email рендерит без ошибок Jinja."""
    from app.lessio.email import send_welcome_email

    class TutorStub:
        slug = "render_test"
        display_name = "Render Test"
        niche = "english"
        avatar_emoji = "👨‍🏫"

    ok = await send_welcome_email(to="render@e.com", tutor=TutorStub())  # type: ignore[arg-type]
    assert ok is True
    mock_send.assert_awaited_once()
