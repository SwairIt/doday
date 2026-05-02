"""Tests for email-sending helpers — SMTP call is mocked."""

from unittest.mock import AsyncMock, patch

from app.auth.email import send_verification_email


async def test_send_verification_email_calls_aiosmtplib() -> None:
    with patch("app.auth.email.aiosmtplib.send", new=AsyncMock()) as mock_send:
        await send_verification_email(
            to="kid@school.ru",
            verification_url="http://localhost:8000/auth/verify?token=abc123",
        )

    mock_send.assert_awaited_once()
    call = mock_send.await_args
    assert call is not None
    msg = call.args[0]
    assert msg["To"] == "kid@school.ru"
    assert "abc123" in msg.get_content()
    assert "Подтверждение" in msg["Subject"]
