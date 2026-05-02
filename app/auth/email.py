"""Email sending. Uses aiosmtplib; tests mock the underlying SMTP call."""

from email.message import EmailMessage

import aiosmtplib

from app.config import get_settings


async def send_verification_email(*, to: str, verification_url: str) -> None:
    settings = get_settings()
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = "Подтверждение почты — SchoolTodo"
    msg.set_content(
        "Привет!\n\n"
        f"Подтверди свою почту, перейдя по ссылке:\n{verification_url}\n\n"
        "Если ты не регистрировался — просто проигнорируй это письмо.\n"
    )

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username or None,
        password=settings.smtp_password or None,
        start_tls=False,
    )
