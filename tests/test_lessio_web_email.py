"""Email-templates render smoke (без SMTP — aiosmtplib.send замокан)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from app.lessio.email import (
    send_booking_emails,
    send_cancellation_email,
    send_reminder_email,
)


def _booking_stub() -> object:
    class B:
        client_full_name = "Тест Клиент"
        client_email = "stub@example.com"
        starts_at = datetime(2026, 6, 8, 14, 0, tzinfo=UTC)
        duration_minutes = 60
        manage_token = "x" * 48
        meeting_url = "https://meet.example/abc"
        notes = None

    return B()


def _tutor_stub() -> object:
    class T:
        display_name = "Tutor Test"
        slug = "tutor_test"
        notification_email = "tutor@example.com"
        default_meeting_url_template = None

    return T()


@patch("app.lessio.email.aiosmtplib.send", new_callable=AsyncMock)
async def test_send_booking_emails_renders_both(mock_send: AsyncMock) -> None:
    await send_booking_emails(
        booking=_booking_stub(),  # type: ignore[arg-type]
        tutor=_tutor_stub(),  # type: ignore[arg-type]
        service_title="Английский 60 мин",
    )
    assert mock_send.await_count == 2


@patch("app.lessio.email.aiosmtplib.send", new_callable=AsyncMock)
async def test_send_cancellation_to_client_when_by_tutor(mock_send: AsyncMock) -> None:
    await send_cancellation_email(
        booking=_booking_stub(),  # type: ignore[arg-type]
        tutor=_tutor_stub(),  # type: ignore[arg-type]
        by="tutor",
        service_title="Y",
    )
    args = mock_send.await_args
    msg = args.args[0]
    assert msg["To"] == "stub@example.com"


@patch("app.lessio.email.aiosmtplib.send", new_callable=AsyncMock)
async def test_send_reminder_returns_true_on_success(mock_send: AsyncMock) -> None:
    ok = await send_reminder_email(
        booking=_booking_stub(),  # type: ignore[arg-type]
        tutor=_tutor_stub(),  # type: ignore[arg-type]
        service_title="Y",
        hours=24,
    )
    assert ok is True
    assert mock_send.await_count == 1


@patch(
    "app.lessio.email.aiosmtplib.send",
    new_callable=AsyncMock,
    side_effect=RuntimeError("SMTP down"),
)
async def test_send_reminder_returns_false_on_smtp_failure(mock_send: AsyncMock) -> None:
    ok = await send_reminder_email(
        booking=_booking_stub(),  # type: ignore[arg-type]
        tutor=_tutor_stub(),  # type: ignore[arg-type]
        service_title="Y",
        hours=1,
    )
    assert ok is False
