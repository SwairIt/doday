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
    # Subject mentions verification; works for both "Подтверди" and "Подтверждение".
    assert "Подтверди" in msg["Subject"]
    # Multipart now: plain-text + html. Both must carry the verification URL.
    bodies = [
        part.get_content() for part in msg.walk() if not part.is_multipart()
    ]
    assert any("abc123" in b for b in bodies), bodies
    # And the HTML part contains the brand.
    assert any("Doday" in b for b in bodies)
