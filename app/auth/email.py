"""Email sending — branded HTML letters via aiosmtplib.

Sends multipart/alternative: text/plain fallback + an inline-styled HTML body.
Inline CSS is mandatory because Gmail (and almost every other client) strips
<style> blocks. Layout is tables-based for legacy clients (Outlook, Yandex Mail).
"""

from email.message import EmailMessage

import aiosmtplib

from app.config import get_settings


def _render_html(verification_url: str) -> str:
    """Build the verification email body. Inline CSS only; tables for layout."""
    return f"""\
<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Подтверждение почты — Doday</title>
</head>
<body style="margin:0;padding:0;background:#0d0820;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Inter,Arial,sans-serif;color:#1a1230;">

<!-- Outer wrapper that gives the dark background even in clients that ignore body bg -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:radial-gradient(circle at top right,#2e1065 0%,#0d0820 60%);min-height:100vh;">
<tr><td align="center" style="padding:40px 16px 20px 16px;">

  <!-- Brand -->
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:24px;">
  <tr><td>
    <div style="display:inline-block;background:linear-gradient(135deg,#7c3aed 0%,#d946ef 100%);
                color:#fff;font-weight:800;font-size:22px;letter-spacing:.3px;
                padding:10px 18px;border-radius:14px;
                box-shadow:0 8px 30px -8px rgba(124,58,237,.6);">
      ✦ Doday
    </div>
  </td></tr>
  </table>

  <!-- Main card -->
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="560"
         style="max-width:560px;width:100%;background:#ffffff;border-radius:24px;
                box-shadow:0 30px 80px -20px rgba(124,58,237,.45);overflow:hidden;">

    <!-- Gradient header strip -->
    <tr>
      <td style="background:linear-gradient(135deg,#7c3aed 0%,#a855f7 50%,#d946ef 100%);
                 height:6px;font-size:0;line-height:0;">&nbsp;</td>
    </tr>

    <tr>
      <td style="padding:48px 48px 32px 48px;text-align:center;">

        <!-- Hero emoji on a gradient halo -->
        <div style="display:inline-block;width:88px;height:88px;border-radius:50%;
                    background:linear-gradient(135deg,#ede9fe 0%,#fce7f3 100%);
                    line-height:88px;font-size:42px;margin-bottom:20px;">
          ✉️
        </div>

        <h1 style="margin:0 0 12px 0;font-size:28px;font-weight:800;
                   color:#1a1230;line-height:1.25;">
          Подтверди почту
          <br><span style="background:linear-gradient(135deg,#7c3aed 0%,#d946ef 100%);
                          -webkit-background-clip:text;background-clip:text;
                          color:transparent;">— и ты внутри</span>
        </h1>

        <p style="margin:0 0 32px 0;font-size:16px;line-height:1.55;color:#4a4170;">
          Спасибо что выбрал <strong>Doday</strong>! Один клик
          по кнопке внизу — и можно начинать раскладывать дела
          по полочкам.
        </p>

        <!-- CTA button — bulletproof tabled button for legacy clients -->
        <table role="presentation" cellpadding="0" cellspacing="0" border="0"
               style="margin:0 auto 28px auto;">
        <tr><td align="center" bgcolor="#7c3aed"
                style="border-radius:14px;
                       background:linear-gradient(135deg,#7c3aed 0%,#d946ef 100%);
                       box-shadow:0 12px 32px -8px rgba(124,58,237,.5);">
          <a href="{verification_url}"
             style="display:inline-block;padding:16px 40px;font-size:16px;font-weight:700;
                    color:#ffffff;text-decoration:none;letter-spacing:.2px;
                    border-radius:14px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Inter,Arial,sans-serif;">
            ✓ Подтвердить почту
          </a>
        </td></tr>
        </table>

        <p style="margin:0 0 8px 0;font-size:13px;color:#6b6587;">
          Кнопка не работает? Скопируй ссылку:
        </p>
        <p style="margin:0;font-size:12px;line-height:1.4;
                  word-break:break-all;color:#7c3aed;">
          <a href="{verification_url}" style="color:#7c3aed;text-decoration:underline;">
            {verification_url}
          </a>
        </p>

      </td>
    </tr>

    <!-- Feature strip — three quick "what's inside" tiles -->
    <tr>
      <td style="padding:0 48px 32px 48px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td width="33%" align="center" style="padding:16px 8px;background:#faf5ff;border-radius:12px;">
            <div style="font-size:24px;margin-bottom:4px;">📅</div>
            <div style="font-size:12px;font-weight:600;color:#4a4170;">Календарь</div>
            <div style="font-size:11px;color:#6b6587;">+ помодоро</div>
          </td>
          <td width="2%">&nbsp;</td>
          <td width="33%" align="center" style="padding:16px 8px;background:#faf5ff;border-radius:12px;">
            <div style="font-size:24px;margin-bottom:4px;">🌌</div>
            <div style="font-size:12px;font-weight:600;color:#4a4170;">Граф связей</div>
            <div style="font-size:11px;color:#6b6587;">как в Obsidian</div>
          </td>
          <td width="2%">&nbsp;</td>
          <td width="33%" align="center" style="padding:16px 8px;background:#faf5ff;border-radius:12px;">
            <div style="font-size:24px;margin-bottom:4px;">🎯</div>
            <div style="font-size:12px;font-weight:600;color:#4a4170;">Привычки</div>
            <div style="font-size:11px;color:#6b6587;">+ стрики</div>
          </td>
        </tr>
        </table>
      </td>
    </tr>

    <tr>
      <td style="padding:0 48px 40px 48px;text-align:center;">
        <p style="margin:0;font-size:13px;line-height:1.5;color:#6b6587;">
          Не регистрировался? Спокойно проигнорируй это письмо —
          никаких аккаунтов без подтверждения мы не создаём.
        </p>
      </td>
    </tr>
  </table>

  <!-- Footer -->
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="560"
         style="max-width:560px;width:100%;margin-top:24px;">
  <tr><td align="center" style="padding:0 16px 32px 16px;">
    <p style="margin:0 0 8px 0;font-size:12px;color:#9890b8;">
      <a href="https://getdoday.ru/" style="color:#a78bfa;text-decoration:none;">getdoday.ru</a>
      &nbsp;·&nbsp;
      <a href="https://getdoday.ru/help" style="color:#a78bfa;text-decoration:none;">Помощь</a>
      &nbsp;·&nbsp;
      <a href="https://getdoday.ru/privacy" style="color:#a78bfa;text-decoration:none;">Приватность</a>
    </p>
    <p style="margin:0;font-size:11px;color:#6b6587;">
      Doday — бесплатный туду-лист без рекламы и без слежки. Сделано в России.
    </p>
  </td></tr>
  </table>

</td></tr>
</table>

</body>
</html>"""


def _render_text(verification_url: str) -> str:
    """Plain-text fallback for clients that don't render HTML (rare, but exists)."""
    return (
        "Привет!\n\n"
        "Спасибо что выбрал Doday — бесплатный туду-лист без рекламы.\n\n"
        f"Подтверди свою почту по ссылке:\n{verification_url}\n\n"
        "Если ты не регистрировался — просто проигнорируй это письмо.\n\n"
        "—\n"
        "Doday · https://getdoday.ru/\n"
    )


async def send_verification_email(*, to: str, verification_url: str) -> None:
    settings = get_settings()
    msg = EmailMessage()
    msg["From"] = f"Doday <{settings.smtp_from}>"
    msg["To"] = to
    msg["Subject"] = "Подтверди почту — добро пожаловать в Doday ✨"
    # set_content sets text/plain; add_alternative attaches html with the right
    # MIME structure (multipart/alternative).
    msg.set_content(_render_text(verification_url))
    msg.add_alternative(_render_html(verification_url), subtype="html")

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username or None,
        password=settings.smtp_password or None,
        start_tls=settings.smtp_start_tls,
    )
