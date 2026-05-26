"""Compose and send the morning digest email.

`gather_tasks_for(session, user)` returns three lists:
    (overdue, today, tomorrow)
sorted by priority then due_at. `compose_subject/text/html` build the letter
body. `send_morning_digest` ties it together and writes
`users.morning_digest_last_sent_at` on success. `send_morning_digests_for_all_users`
is the cron entry-point — iterates over opt-in users and returns a count.
"""

from datetime import UTC, date, datetime, time, timedelta
from email.message import EmailMessage
from html import escape

import aiosmtplib
from sqlalchemy import and_, asc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.config import get_settings
from app.tasks.models import Task

_DIGEST_MOTIVATIONAL = "Полезно начать с того что просрочено — потом дальше будет легче."


async def gather_tasks_for(
    session: AsyncSession, user: User, *, now: datetime | None = None
) -> tuple[list[Task], list[Task], list[Task]]:
    """Return (overdue, today, tomorrow_first_3) for user, sorted by priority+date."""
    now = now or datetime.now(UTC)
    today_start = datetime.combine(now.date(), time.min, tzinfo=UTC)
    tomorrow_start = today_start + timedelta(days=1)
    after_tomorrow_start = today_start + timedelta(days=2)

    base_filter = and_(
        Task.user_id == user.id,
        Task.is_completed.is_(False),
        Task.deleted_at.is_(None),
        Task.due_at.is_not(None),
    )

    overdue_stmt = (
        select(Task)
        .where(base_filter, Task.due_at < today_start)
        .order_by(asc(Task.priority), asc(Task.due_at))
    )
    today_stmt = (
        select(Task)
        .where(base_filter, Task.due_at >= today_start, Task.due_at < tomorrow_start)
        .order_by(asc(Task.priority), asc(Task.due_at))
    )
    tomorrow_stmt = (
        select(Task)
        .where(base_filter, Task.due_at >= tomorrow_start, Task.due_at < after_tomorrow_start)
        .order_by(asc(Task.priority), asc(Task.due_at))
        .limit(3)
    )

    overdue = list((await session.execute(overdue_stmt)).scalars().all())
    today_tasks = list((await session.execute(today_stmt)).scalars().all())
    tomorrow = list((await session.execute(tomorrow_stmt)).scalars().all())
    return overdue, today_tasks, tomorrow


def _format_date_ru(d: date) -> str:
    months = (
        "января",
        "февраля",
        "марта",
        "апреля",
        "мая",
        "июня",
        "июля",
        "августа",
        "сентября",
        "октября",
        "ноября",
        "декабря",
    )
    return f"{d.day} {months[d.month - 1]}"


def compose_subject(today: date, total: int) -> str:
    """e.g. «Twoy plan na 9 мая: 7 задач» — short, clear, no spam markers."""
    suffix = "задач"
    if total % 10 == 1 and total % 100 != 11:
        suffix = "задача"
    elif 2 <= total % 10 <= 4 and not (12 <= total % 100 <= 14):
        suffix = "задачи"
    return f"План на {_format_date_ru(today)}: {total} {suffix}"


def _task_line_text(task: Task) -> str:
    prio_marker = {
        "p1": "🔴",
        "p2": "🟠",
        "p3": "🔵",
        "p4": "  ",
    }.get(task.priority.value, "  ")
    return f"  {prio_marker}  {task.title}"


def _task_line_html(task: Task) -> str:
    prio_color = {
        "p1": "#ef4444",
        "p2": "#f59e0b",
        "p3": "#3b82f6",
        "p4": "#94a3b8",
    }.get(task.priority.value, "#94a3b8")
    title = escape(task.title)
    return (
        f'<li style="padding:8px 0;border-bottom:1px solid #ede9fe;font-size:14px;'
        f'color:#1a1230;line-height:1.5;">'
        f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
        f'background:{prio_color};margin-right:10px;vertical-align:middle;"></span>'
        f"{title}</li>"
    )


def compose_text(
    user: User,
    today: date,
    overdue: list[Task],
    today_tasks: list[Task],
    tomorrow: list[Task],
    *,
    base_url: str,
) -> str:
    parts = [f"План на {_format_date_ru(today)}", "", _DIGEST_MOTIVATIONAL, ""]

    if overdue:
        parts.append(f"⚠ Просрочено · {len(overdue)}")
        parts.extend(_task_line_text(t) for t in overdue)
        parts.append("")
    if today_tasks:
        parts.append(f"📅 Сегодня · {len(today_tasks)}")
        parts.extend(_task_line_text(t) for t in today_tasks)
        parts.append("")
    if tomorrow:
        parts.append(f"🔮 Завтра (первые {len(tomorrow)})")
        parts.extend(_task_line_text(t) for t in tomorrow)
        parts.append("")

    parts.append(f"Открыть Doday: {base_url}/doday/app/today")
    parts.append("")
    parts.append(f"Отписаться: {base_url}/doday/app/settings (раздел Уведомления)")
    return "\n".join(parts)


def compose_html(
    user: User,
    today: date,
    overdue: list[Task],
    today_tasks: list[Task],
    tomorrow: list[Task],
    *,
    base_url: str,
) -> str:
    motivational_line = escape(_DIGEST_MOTIVATIONAL)
    today_str = _format_date_ru(today)

    def section(title: str, tasks: list[Task]) -> str:
        if not tasks:
            return ""
        items = "".join(_task_line_html(t) for t in tasks)
        return (
            f'<h2 style="margin:24px 0 8px 0;font-size:14px;font-weight:700;'
            f'text-transform:uppercase;letter-spacing:.08em;color:#7c3aed;">'
            f"{escape(title)}</h2>"
            f'<ul style="list-style:none;margin:0;padding:0;">{items}</ul>'
        )

    overdue_block = section(f"Просрочено · {len(overdue)}", overdue)
    today_block = section(f"Сегодня · {len(today_tasks)}", today_tasks)
    tomorrow_block = section(f"Завтра — первые {len(tomorrow)}", tomorrow)

    return f"""\
<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>План на {today_str} — Doday</title>
</head>
<body style="margin:0;padding:0;background:#faf5ff;\
font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Inter,Arial,sans-serif;\
color:#1a1230;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:#faf5ff;min-height:100vh;">
<tr><td align="center" style="padding:32px 16px 16px 16px;">

  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="560"
         style="max-width:560px;width:100%;background:#ffffff;border-radius:20px;
                box-shadow:0 12px 40px -16px rgba(124,58,237,.25);overflow:hidden;">
    <tr>
      <td style="background:linear-gradient(135deg,#7c3aed 0%,#a855f7 50%,#d946ef 100%);
                 padding:24px 32px;text-align:left;">
        <div style="display:inline-block;color:#fff;font-weight:800;font-size:14px;
                    letter-spacing:.3px;opacity:.85;">✦ Doday</div>
        <h1 style="margin:6px 0 0 0;font-size:24px;font-weight:800;color:#fff;
                   line-height:1.25;">План на {today_str}</h1>
      </td>
    </tr>
    <tr>
      <td style="padding:24px 32px 8px 32px;">
        <p style="margin:0;font-size:14px;line-height:1.55;color:#4a4170;">
          {motivational_line}
        </p>
        {overdue_block}
        {today_block}
        {tomorrow_block}
        <table role="presentation" cellpadding="0" cellspacing="0" border="0"
               style="margin:28px auto 8px auto;">
        <tr><td align="center" bgcolor="#7c3aed"
                style="border-radius:12px;
                       background:linear-gradient(135deg,#7c3aed 0%,#d946ef 100%);">
          <a href="{base_url}/doday/app/today"
             style="display:inline-block;padding:12px 28px;font-size:14px;font-weight:700;
                    color:#ffffff;text-decoration:none;letter-spacing:.2px;
                    border-radius:12px;">
            Открыть Doday →
          </a>
        </td></tr>
        </table>
      </td>
    </tr>
    <tr>
      <td style="padding:16px 32px 24px 32px;text-align:center;
                 border-top:1px solid #ede9fe;">
        <p style="margin:0;font-size:11px;color:#9890b8;line-height:1.5;">
          Получаешь это письмо потому что включил утренний дайджест.
          <a href="{base_url}/doday/app/settings" style="color:#a78bfa;text-decoration:underline;">
            Отписаться можно в Настройках
          </a> · одна галка.
        </p>
      </td>
    </tr>
  </table>

</td></tr>
</table>
</body>
</html>"""


async def send_morning_digest(
    session: AsyncSession, user: User, *, now: datetime | None = None
) -> bool:
    """Send the digest to a single user. Returns True if sent, False if skipped.

    Skips when there are no tasks at all (overdue+today+tomorrow == 0) — letters
    with «у тебя ничего» are demotivating; we'd rather stay silent.
    """
    settings = get_settings()
    now = now or datetime.now(UTC)

    overdue, today_tasks, tomorrow = await gather_tasks_for(session, user, now=now)
    total = len(overdue) + len(today_tasks) + len(tomorrow)
    if total == 0:
        return False

    base_url = settings.app_base_url.rstrip("/")
    today_local = now.date()
    subject = compose_subject(today_local, total)
    text = compose_text(user, today_local, overdue, today_tasks, tomorrow, base_url=base_url)
    html = compose_html(user, today_local, overdue, today_tasks, tomorrow, base_url=base_url)

    msg = EmailMessage()
    msg["From"] = f"Doday <{settings.smtp_from}>"
    msg["To"] = user.email
    msg["Subject"] = subject
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username or None,
        password=settings.smtp_password or None,
        start_tls=settings.smtp_start_tls,
    )

    user.morning_digest_last_sent_at = now
    await session.commit()
    return True


async def send_morning_digests_for_all_users(
    session: AsyncSession, *, now: datetime | None = None
) -> dict[str, int]:
    """Cron entry-point. Iterates over opt-in users and sends each digest.

    Dedupes by `morning_digest_last_sent_at` >= start of today (UTC) — if the
    cron fires twice on the same day for any reason, we skip already-sent ones.

    Returns {sent: N, skipped_already: N, skipped_empty: N, errored: N}.
    """
    now = now or datetime.now(UTC)
    today_start = datetime.combine(now.date(), time.min, tzinfo=UTC)

    stmt = select(User).where(
        User.morning_digest_enabled.is_(True),
        User.email_verified_at.is_not(None),
        or_(
            User.morning_digest_last_sent_at.is_(None),
            User.morning_digest_last_sent_at < today_start,
        ),
    )
    users = list((await session.execute(stmt)).scalars().all())

    counters = {
        "sent": 0,
        "skipped_already": 0,
        "skipped_empty": 0,
        "skipped_free": 0,
        "errored": 0,
    }

    # Defence-in-depth: opt-in flag uses Pro-gate в profile/router, но если юзер
    # был на trial и opt-in включил, потом trial закончился — флаг остался True.
    # Здесь дополнительно проверяем effective_tier — если уже не Pro, не шлём.
    from app.billing.service import has_pro_features

    for user in users:
        if not has_pro_features(user):
            counters["skipped_free"] += 1
            continue
        try:
            sent = await send_morning_digest(session, user, now=now)
            if sent:
                counters["sent"] += 1
            else:
                counters["skipped_empty"] += 1
        except Exception:
            counters["errored"] += 1
            await session.rollback()

    return counters
