"""Telegram bot worker — long-running polling loop для двух ботов.

Запускается отдельно от uvicorn:
    .venv/bin/python -m app.telegram.bot

На проде — systemd-сервис /etc/systemd/system/doday-bot.service с
restart-on-failure. Один процесс держит **два Telegram Application'а** в
одном asyncio loop через `asyncio.gather`:

- **@DodayTaskBot** (settings.telegram_bot_token) — Doday Tasks: /add, /today,
  /done, /upcoming, /help, /app, /unlink. Stars payments для pro_* продуктов.
- **@LessioBot** (settings.lessio_bot_token, OPTIONAL) — Lessio: на текущей
  фазе валидации только /start с CTA на waitlist. Если LESSIO_BOT_TOKEN пуст —
  Lessio Application не создаётся, worker крутит только Doday. После waitlist'а
  ≥100 здесь добавятся /start lessio_<slug>, /cabinet и Stars handlers для
  tutor_pro_* — handler-функции pre_checkout / successful_payment унифицированы
  через HMAC payload (см. app.billing.stars).

Команды Doday Tasks:
- /start [token]   — приветствие; если токен — привязать к Doday-аккаунту
- /help            — список команд
- /add <текст>     — создать задачу (через quickadd-парсер: даты, приоритеты,
  лейблы, проекты)
- /today           — задачи на сегодня + просрочка
- /upcoming        — следующие 7 дней
- /done            — последние 5 закрытых сегодня
- /unlink          — отвязать чат
"""

from __future__ import annotations

import asyncio
import logging
import socket
from datetime import UTC, datetime, timedelta
from datetime import time as dtime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

# SQLAlchemy mapper-warmup: relationship строки вроде `order_by="Label.name"`
# eval'ятся лениво и требуют чтобы все классы были загружены в registry до
# первого query. uvicorn это делает через include_router → импорт routers →
# импорт moduls. У бота нет роутеров, поэтому импортируем модели явно.
import app.auth.models
import app.comments.models
import app.labels.models
import app.pomodoro.models
import app.projects.models
import app.reminders.models
import app.school.models
import app.sections.models
import app.tasks.models
import app.telegram.models  # noqa: F401 — mapper warmup
from app.auth.models import User
from app.config import get_settings
from app.quickadd.parser import parse_quick_add
from app.tasks.models import Task, TaskPriority
from app.tasks.service import create_task
from app.telegram.service import complete_link, get_user_by_chat, unlink

logger = logging.getLogger("doday.telegram")


# Hardcoded IPv4 Telegram API. systemd-resolved отдаёт только AAAA, а
# IPv6-сеть из прода не маршрутизируется. У Telegram несколько A-записей,
# но **с нашего сервера маршрут есть только к части DC** —
# остальные отвечают SYN-SENT (asymmetric routing / firewall провайдера).
# Поэтому жёстко список IP: httpx попробует по порядку, если первый failed —
# следующий. Без этого httpx random'но выбирает один и виснет на connect timeout.
#
# Состав списка проверен 2026-05-25 с dev-машины (оба отдают 302 на GET /):
# - 149.154.166.110 — current A-record (Google DNS + Cloudflare DNS)
# - 149.154.167.220 — старый hardcoded, всё ещё отвечает с dev
#
# Если оба не доступны с прод-сервера → это сетевой блок (RKN / провайдер /
# MTU / firewall), не stale-IP. Тогда фикс через MTProxy или HTTP-прокси,
# не через обновление этого списка. См. memory feedback_telegram_api_infra_debt.
_TELEGRAM_API_IPS = ("149.154.166.110", "149.154.167.220")
_FORCED_HOSTS = {"api.telegram.org"}


def _force_ipv4_resolve() -> None:
    """Подменяем resolve для api.telegram.org на hardcoded IPv4.

    Патчим на двух уровнях:
      1. socket.getaddrinfo — sync-резолв (curl-like usage, sync libs).
      2. asyncio.BaseEventLoop.getaddrinfo — async-резолв (httpx → httpcore
         → anyio идут через event-loop.getaddrinfo, а НЕ socket.getaddrinfo).
         Без этого пункта монке-патч на socket бесполезен внутри ptb.

    Почему так: stub-resolver systemd-resolved отдаёт только AAAA для
    api.telegram.org (политика провайдера), а IPv6-сеть оттуда не
    маршрутизируется — httpx виснет на 30s connect-timeout, бот молча
    падает. Hardcoded IP — единственный путь без sudo /etc/hosts.

    **Override**: можно отключить через настройку `DISABLE_TELEGRAM_IPV4_PATCH=1`
    в .env — нужно когда конкретный hardcoded IP перестал отвечать (Telegram
    периодически ротирует DC IP-адреса). Без патча уйдёт обычный системный DNS,
    и если провайдер сейчас отдаёт работающий IPv4 (или маршрут до IPv6 починили) —
    бот заработает.

    Все остальные хосты резолвятся как было — мы не ломаем прочий outbound.
    """
    if get_settings().disable_telegram_ipv4_patch:
        logger.info(
            "DISABLE_TELEGRAM_IPV4_PATCH set — skipping hardcoded api.telegram.org resolver"
        )
        return

    import asyncio.base_events

    sync_orig = socket.getaddrinfo

    def _v4_sync(host: Any, *args: Any, **kwargs: Any) -> Any:
        if host in _FORCED_HOSTS:
            port = args[0] if args else kwargs.get("port", 0)
            return [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in _TELEGRAM_API_IPS
            ]
        return sync_orig(host, *args, **kwargs)

    socket.getaddrinfo = _v4_sync

    async_orig = asyncio.base_events.BaseEventLoop.getaddrinfo

    async def _v4_async(self: Any, host: Any, port: Any = 0, *args: Any, **kwargs: Any) -> Any:
        if host in _FORCED_HOSTS:
            return [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in _TELEGRAM_API_IPS
            ]
        return await async_orig(self, host, port, *args, **kwargs)

    asyncio.base_events.BaseEventLoop.getaddrinfo = _v4_async  # type: ignore[method-assign]


# Single async engine + sessionmaker reused across handlers — bot долгоживущий.
_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _engine, _sessionmaker
    if _sessionmaker is None:
        _engine = create_async_engine(
            get_settings().database_url,
            connect_args={"server_settings": {"timezone": "UTC"}},
        )
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _sessionmaker


async def _reply(update: Update, text: str, *, markdown: bool = False) -> None:
    """Helper — reply to incoming message, скрывает None-проверки."""
    if update.message is None:
        logger.warning("update without message: %s", update)
        return
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN if markdown else None)


async def _get_user_or_prompt(update: Update, session: AsyncSession) -> User | None:
    """Find linked user by chat_id. If not linked — prompt to /start <token>.

    Раньше тут стояла жёсткая `has_pro_features` проверка — бот считался
    Pro-only фичей. Это противоречило public messaging «в бета-режиме
    всё бесплатно для всех», поэтому юзеры с истёкшим trial писали боту
    и получали «бот доступен в Pro» — выглядело как сломанный бот.

    Теперь бот доступен ВСЕМ привязанным юзерам. Если в будущем появится
    Pro-only специфичная команда (например /digest-config), её можно
    залочить отдельной проверкой внутри handler'а — а базовые /add /today
    /upcoming /done /unlink работают всегда.
    """
    chat = update.effective_chat
    if chat is None:
        return None
    user = await get_user_by_chat(session, chat.id)
    if user is None:
        await _reply(
            update,
            "Чат не привязан к аккаунту Doday.\n\n"
            "Открой Doday → Профиль → Telegram → нажми «Подключить» — "
            "получишь ссылку которая привяжет нас.",
        )
        return None
    return user


def _miniapp_keyboard() -> Any:
    """Inline-клавиатура с одной кнопкой → Mini App. Юзер открывает Doday
    прямо внутри Telegram."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

    base = get_settings().app_base_url or "https://getdoday.ru"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🚀 Открыть Doday", web_app=WebAppInfo(url=base.rstrip("/") + "/miniapp/")
                )
            ]
        ]
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Юзер пишет /start или /start <token> через deeplink."""
    args = context.args or []
    chat = update.effective_chat
    if chat is None or update.message is None:
        return
    if not args:
        await update.message.reply_text(
            "👋 *Привет! Я Doday — твой to-do прямо в Telegram.*\n\n"
            "📱 Тапни кнопку ниже — откроется Mini App: задачи, проекты, Pomodoro, "
            "статистика, всё прямо в чате.\n\n"
            "Или используй команды:\n"
            "/add — быстро добавить задачу\n"
            "/today — что на сегодня\n"
            "/help — полная справка",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_miniapp_keyboard(),
        )
        return
    token = args[0]
    sm = _get_sessionmaker()
    async with sm() as session:
        user = await complete_link(session, token, chat.id)
    if user is None:
        await _reply(
            update,
            "Этот токен не подходит — он либо уже использован, либо устарел.\n"
            "Сгенерируй новый в Doday → Профиль → Telegram.",
        )
        return
    await update.message.reply_text(
        f"✅ *Готово, ты привязан как `{user.email}`*\n\n"
        "Теперь бот может добавлять задачи, присылать напоминания и утренний дайджест.\n"
        "Открой Mini App кнопкой ниже — там удобнее, чем в чате.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_miniapp_keyboard(),
    )


async def cmd_help(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(
        "*Doday — команды:*\n\n"
        "*/app* — открыть Mini App (всё там)\n"
        "*/add* `<текст>` — добавить задачу. Парсер понимает:\n"
        "  • Даты: «сегодня», «завтра», «пн», «через 3 дня», «15 декабря»\n"
        "  • Приоритет: «!» = P4 ... «!!!!» = P1\n"
        "  • Лейблы: «@дом», «@работа»\n"
        "  • Проект: «#учёба»\n"
        "  Пример: `/add Сходить в зал завтра !!! @спорт`\n\n"
        "*/today* — просроченные + сегодняшние\n"
        "*/upcoming* — следующие 7 дней\n"
        "*/done* — последние 5 закрытых сегодня\n"
        "*/unlink* — отвязать этот чат от аккаунта",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_miniapp_keyboard(),
    )


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw = " ".join(context.args or []).strip()
    if not raw:
        await _reply(
            update,
            "После /add нужен текст. Пример: `/add Купить молоко завтра !!! @дом`",
            markdown=True,
        )
        return
    sm = _get_sessionmaker()
    async with sm() as session:
        user = await _get_user_or_prompt(update, session)
        if user is None:
            return
        parsed = parse_quick_add(raw)
        task = await create_task(
            session,
            user.id,
            title=parsed.title,
            due_at=parsed.due_at,
            due_date_only=parsed.due_at is not None,
            priority=parsed.priority,
            recurrence=parsed.recurrence,
        )
        msg = f"✓ Добавлено: *{task.title}*"
        if task.due_at:
            msg += f" · {task.due_at.strftime('%d.%m')}"
        if task.priority != TaskPriority.P4:
            msg += f" · !{task.priority.value[1:]}"
        await _reply(update, msg, markdown=True)


def _format_task_line(t: Task) -> str:
    prio_emoji = {"p1": "🔴", "p2": "🟠", "p3": "🔵", "p4": "  "}.get(t.priority.value, "  ")
    date_str = ""
    if t.due_at:
        if t.due_date_only:
            date_str = f" · {t.due_at.strftime('%d.%m')}"
        else:
            date_str = f" · {t.due_at.strftime('%d.%m %H:%M')}"
    return f"{prio_emoji} {t.title}{date_str}"


async def cmd_today(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    sm = _get_sessionmaker()
    async with sm() as session:
        user = await _get_user_or_prompt(update, session)
        if user is None:
            return
        now = datetime.now(UTC)
        today_end = datetime.combine(now.date(), dtime.max, tzinfo=UTC)
        stmt = (
            select(Task)
            .where(
                Task.user_id == user.id,
                Task.is_completed.is_(False),
                Task.deleted_at.is_(None),
                Task.due_at.is_not(None),
                Task.due_at <= today_end,
            )
            .order_by(Task.due_at)
            .limit(20)
        )
        rows = list((await session.execute(stmt)).scalars().all())
        if not rows:
            await _reply(update, "Сегодня всё чисто. Используй /add чтобы что-то запланировать.")
            return
        lines = ["*На сегодня и просрочка:*\n"]
        lines.extend(_format_task_line(t) for t in rows)
        await _reply(update, "\n".join(lines), markdown=True)


async def cmd_upcoming(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    sm = _get_sessionmaker()
    async with sm() as session:
        user = await _get_user_or_prompt(update, session)
        if user is None:
            return
        now = datetime.now(UTC)
        in_a_week = now + timedelta(days=7)
        stmt = (
            select(Task)
            .where(
                Task.user_id == user.id,
                Task.is_completed.is_(False),
                Task.deleted_at.is_(None),
                Task.due_at.is_not(None),
                Task.due_at >= now,
                Task.due_at <= in_a_week,
            )
            .order_by(Task.due_at)
            .limit(20)
        )
        rows = list((await session.execute(stmt)).scalars().all())
        if not rows:
            await _reply(update, "На неделю ничего не запланировано.")
            return
        lines = ["*На 7 дней:*\n"]
        lines.extend(_format_task_line(t) for t in rows)
        await _reply(update, "\n".join(lines), markdown=True)


async def cmd_done(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    sm = _get_sessionmaker()
    async with sm() as session:
        user = await _get_user_or_prompt(update, session)
        if user is None:
            return
        today_start = datetime.combine(datetime.now(UTC).date(), dtime.min, tzinfo=UTC)
        stmt = (
            select(Task)
            .where(
                Task.user_id == user.id,
                Task.is_completed.is_(True),
                Task.completed_at.is_not(None),
                Task.completed_at >= today_start,
            )
            .order_by(desc(Task.completed_at))
            .limit(5)
        )
        rows = list((await session.execute(stmt)).scalars().all())
        if not rows:
            await _reply(update, "Сегодня ещё ничего не закрыто.")
            return
        lines = ["*Закрыто сегодня:*\n"]
        lines.extend(f"✓ {t.title}" for t in rows)
        await _reply(update, "\n".join(lines), markdown=True)


async def cmd_unlink(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    sm = _get_sessionmaker()
    async with sm() as session:
        user = await _get_user_or_prompt(update, session)
        if user is None:
            return
        await unlink(session, user.id)
        await _reply(
            update,
            "Чат отвязан. Команды больше не работают. Заново подключиться "
            "можно из Doday → Профиль → Telegram.",
        )


async def cmd_app(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Открыть Mini App инлайн-кнопкой."""
    if update.message is None:
        return
    await update.message.reply_text(
        "📱 Тапни кнопку ниже — Doday откроется прямо в Telegram.",
        reply_markup=_miniapp_keyboard(),
    )


async def on_pre_checkout_query(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Telegram waits up to 10s for our ok/error answer before charging.

    We verify the signed payload + amount sanity; on mismatch, answer with a
    user-facing reason so Telegram cancels the purchase before deducting Stars.
    """
    from app.billing.stars import validate_pre_checkout

    query = update.pre_checkout_query
    if query is None:
        return
    ok, reason, _product = validate_pre_checkout(query.invoice_payload, query.total_amount)
    try:
        if ok:
            await query.answer(ok=True)
        else:
            await query.answer(ok=False, error_message=reason or "Платёж отклонён")
    except Exception as e:
        logger.error("pre_checkout answer failed: %s", e)


async def on_successful_payment(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """SuccessfulPayment update → credit user (idempotent), thank them, log."""
    from app.billing.stars import apply_successful_payment

    if update.message is None or update.message.successful_payment is None:
        return
    sp = update.message.successful_payment
    sm = _get_sessionmaker()
    async with sm() as session:
        try:
            payment = await apply_successful_payment(
                session,
                telegram_payment_charge_id=sp.telegram_payment_charge_id,
                provider_payment_charge_id=sp.provider_payment_charge_id,
                payload=sp.invoice_payload,
                stars_amount=sp.total_amount,
            )
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.exception("apply_successful_payment failed: %s", e)
            await _reply(
                update,
                "⚠ Платёж получен, но не смог обновить тариф автоматически. "
                "Напиши на doday.support@gmail.com — выручим вручную.",
            )
            return
    if payment is None:
        await _reply(
            update,
            "⚠ Платёж получен, но я не смог распознать счёт. "
            "Это значит данные были изменены посередине — напиши в поддержку.",
        )
        return
    from app.billing.products import get_product

    product = get_product(payment.product_code)
    msg_lines = [
        "✅ *Платёж принят*",
        "",
        f"Тариф: *{product.title if product else payment.product_code}*",
        f"Списано: *{payment.stars_amount} ⭐*",
    ]
    if product and product.duration_months is None:
        msg_lines.append("Подписка: *навсегда*")
    elif product and product.duration_months:
        msg_lines.append(f"Подписка: на *{product.duration_months} мес*")
    msg_lines.append("")
    msg_lines.append("Открой Doday — все Pro-функции уже доступны.")
    await _reply(update, "\n".join(msg_lines), markdown=True)


async def on_unknown_text(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Любой текст без / — короткая подсказка."""
    if update.message is None or update.message.text is None:
        return
    await update.message.reply_text(
        "Я понимаю команды через /. Самое удобное — открыть Mini App.",
        reply_markup=_miniapp_keyboard(),
    )


async def _job_check_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    """ε N3 cron-tick: проверить approaching reminders → отправить ТГ-сообщения."""
    sm = _get_sessionmaker()
    async with sm() as session:
        from app.reminders.service import list_due, mark_sent
        from app.telegram.service import get_link_for_user

        due = await list_due(session)
        for rem in due:
            link = await get_link_for_user(session, rem.user_id)
            if link is None or link.chat_id is None:
                # юзер ещё не привязал TG — пропускаем, но всё равно mark sent
                # чтобы не спамить попытками
                await mark_sent(session, rem.id)
                continue
            # Подтянем title задачи
            task = (
                await session.execute(
                    select(Task.title, Task.is_completed).where(Task.id == rem.task_id)
                )
            ).first()
            if task is None or task[1]:
                # Задача удалена/закрыта — silence
                await mark_sent(session, rem.id)
                continue
            text = f"🔔 Напоминание:\n*{task[0]}*"
            try:
                await context.bot.send_message(
                    chat_id=link.chat_id, text=text, parse_mode=ParseMode.MARKDOWN
                )
                await mark_sent(session, rem.id)
            except Exception as e:
                logger.warning("Failed to send reminder %s: %s", rem.id, e)


async def _job_morning_digest(context: ContextTypes.DEFAULT_TYPE) -> None:
    """ε N4: каждое утро 09:00 МСК (06:00 UTC) — short digest активных задач."""
    from datetime import UTC, datetime
    from datetime import time as dtime

    from app.auth.models import User
    from app.telegram.models import TelegramLink

    sm = _get_sessionmaker()
    async with sm() as session:
        rows = await session.execute(
            select(User, TelegramLink)
            .join(TelegramLink, TelegramLink.user_id == User.id)
            .where(TelegramLink.chat_id.is_not(None))
        )
        today_date = datetime.now(UTC).date()
        today_end = datetime.combine(today_date, dtime.max, tzinfo=UTC)
        for user, link in rows.all():
            tasks_q = await session.execute(
                select(Task)
                .where(
                    Task.user_id == user.id,
                    Task.is_completed.is_(False),
                    Task.deleted_at.is_(None),
                    Task.due_at.is_not(None),
                    Task.due_at <= today_end,
                )
                .order_by(Task.priority, Task.due_at)
                .limit(10)
            )
            tasks = list(tasks_q.scalars().all())
            if not tasks:
                continue
            lines = [f"🌅 *Доброе утро!* На сегодня {len(tasks)} задач:\n"]
            for t in tasks[:5]:
                prio_emoji = {"p1": "🔥", "p2": "⚡", "p3": "💧", "p4": "•"}.get(
                    t.priority.value, "•"
                )
                lines.append(f"{prio_emoji} {t.title}")
            if len(tasks) > 5:
                lines.append(f"\n…и ещё {len(tasks) - 5}")
            try:
                await context.bot.send_message(
                    chat_id=link.chat_id, text="\n".join(lines), parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.warning("Failed to send morning digest to %s: %s", link.chat_id, e)


def build_doday_app() -> Application[Any, Any, Any, Any, Any, Any]:
    """Build @DodayTaskBot Application (full Doday Tasks feature set + Stars).

    Raises RuntimeError if TELEGRAM_BOT_TOKEN is empty — caller in `_run_both`
    catches this and continues with Lessio only (graceful per-bot degradation).
    """
    # IPv4-only DNS — должен сработать ДО первого httpx.AsyncClient.
    _force_ipv4_resolve()
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN empty — Doday bot disabled")

    async def _post_init(app: Application[Any, Any, Any, Any, Any, Any]) -> None:
        """Post-init: chat menu button + setMyCommands. Идемпотентно."""
        from telegram import BotCommand, MenuButtonWebApp, WebAppInfo

        base = settings.app_base_url or "https://getdoday.ru"
        webapp_url = base.rstrip("/") + "/miniapp/"
        try:
            await app.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="Doday", web_app=WebAppInfo(url=webapp_url))
            )
            logger.info("default chat menu button set to %s", webapp_url)
        except Exception as e:
            logger.warning("failed to set default menu button: %s", e)

        commands = [
            BotCommand("app", "Открыть Mini App"),
            BotCommand("add", "Добавить задачу: /add купить молоко завтра !!! @дом"),
            BotCommand("today", "Задачи на сегодня + просрочка"),
            BotCommand("upcoming", "Задачи на 7 дней"),
            BotCommand("done", "Что закрыто сегодня"),
            BotCommand("help", "Справка по командам"),
            BotCommand("unlink", "Отвязать этот чат"),
        ]
        try:
            await app.bot.set_my_commands(commands)
            logger.info("registered %d bot commands", len(commands))
        except Exception as e:
            logger.warning("failed to set commands: %s", e)

    builder = Application.builder().token(settings.telegram_bot_token).post_init(_post_init)
    if settings.telegram_proxy_url:
        # python-telegram-bot v21: .proxy(url) для get_me/sendMessage и
        # .get_updates_proxy(url) для long-poll'а getUpdates. Без второго
        # polling может всё равно идти напрямую → таймаут.
        builder = builder.proxy(settings.telegram_proxy_url).get_updates_proxy(
            settings.telegram_proxy_url
        )
        logger.info("Doday bot using proxy: %s", settings.telegram_proxy_url.split("@")[-1])
    application: Application[Any, Any, Any, Any, Any, Any] = builder.build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("app", cmd_app))
    application.add_handler(CommandHandler("add", cmd_add))
    application.add_handler(CommandHandler("today", cmd_today))
    application.add_handler(CommandHandler("upcoming", cmd_upcoming))
    application.add_handler(CommandHandler("done", cmd_done))
    application.add_handler(CommandHandler("unlink", cmd_unlink))
    # Stars payment flow — handlers MUST run before the catch-all text handler.
    application.add_handler(PreCheckoutQueryHandler(on_pre_checkout_query))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, on_successful_payment))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_unknown_text))

    # ε N3+N4: JobQueue cron-tasks для reminders + morning digest.
    # JobQueue запускается автоматически с run_polling если установлен extra.
    if application.job_queue is not None:
        # Каждую минуту проверять reminders
        application.job_queue.run_repeating(
            _job_check_reminders, interval=60, first=10, name="check_reminders"
        )
        # Каждый день 06:00 UTC (≈09:00 МСК) — morning digest.
        from datetime import time as dtime

        application.job_queue.run_daily(
            _job_morning_digest,
            time=dtime(hour=6, minute=0, tzinfo=UTC),
            name="morning_digest",
        )
        logger.info("JobQueue tasks scheduled: check_reminders (1 min), morning_digest (06:00 UTC)")
    else:
        logger.warning("JobQueue not available — reminders/digest cron disabled")

    return application


def build_lessio_app() -> Application[Any, Any, Any, Any, Any, Any] | None:
    """Build @LessioBot Application.

    Returns None if LESSIO_BOT_TOKEN is empty (Lessio bot disabled). Returning
    None — not raising — keeps the worker process running just Doday in graceful
    degradation mode. Token can be added later via .env edit + systemctl restart
    doday-bot, no code redeploy needed.

    post_init + handlers — в app.lessio.telegram_handlers (commands ru/en,
    short_description, description, menu button, /menu /help /about /privacy
    /feedback + deeplink lessio_<slug>).
    """
    settings = get_settings()
    if not settings.lessio_bot_token:
        logger.info("LESSIO_BOT_TOKEN empty — @LessioBot disabled, running only Doday")
        return None

    from app.lessio.telegram_handlers import lessio_post_init

    builder = Application.builder().token(settings.lessio_bot_token).post_init(lessio_post_init)
    if settings.telegram_proxy_url:
        builder = builder.proxy(settings.telegram_proxy_url).get_updates_proxy(
            settings.telegram_proxy_url
        )
        logger.info("Lessio bot using proxy: %s", settings.telegram_proxy_url.split("@")[-1])
    application: Application[Any, Any, Any, Any, Any, Any] = builder.build()
    from app.lessio.telegram_handlers import register_handlers as register_lessio_handlers

    register_lessio_handlers(application)
    # Stars-payment handlers — те же что у @DodayTaskBot. Общая логика через
    # HMAC-signed payload в app.billing.stars: payload содержит product_code +
    # user_id + nonce + signature, обработчик ровно один. Если tutor_pro_*
    # invoice выписан через lessio_bot_token — pre_checkout и SuccessfulPayment
    # прилетят на @LessioBot Application; без этих handler'ов это silent fail.
    application.add_handler(PreCheckoutQueryHandler(on_pre_checkout_query))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, on_successful_payment))
    return application


async def _run_both() -> None:
    """Start Doday + (optional) Lessio Application'ы в одном asyncio loop.

    Каждый бот начинает независимо: если Doday Application упал на initialize()
    (Telegram API timeout, invalid token, network — обычно инфра-причины), это
    НЕ должно блокировать Lessio bot и наоборот. Изолированный try/except на
    каждый startup, лог ошибки + продолжаем.

    Не используем `Application.run_polling()` — он сам управляет loop'ом и
    несовместим с gather'ом. Вместо этого ручная связка initialize/start/
    updater.start_polling + бесконечное ожидание `asyncio.Event()` пока процесс
    не получит SIGTERM от systemd.
    """
    doday_app: Application[Any, Any, Any, Any, Any, Any] | None
    if get_settings().disable_doday_bot:
        logger.info("DISABLE_DODAY_BOT set — skipping @DodayTaskBot Application (local-dev mode)")
        doday_app = None
    else:
        try:
            doday_app = build_doday_app()
        except RuntimeError as exc:
            logger.warning("Doday Application build failed: %s — running without Doday bot", exc)
            doday_app = None

    lessio_app = build_lessio_app()

    doday_updater = None
    if doday_app is not None:
        try:
            doday_updater = doday_app.updater
            if doday_updater is None:
                raise RuntimeError("Doday Application.updater is None — builder misconfigured")
            await doday_app.initialize()
            await doday_app.start()
            await doday_updater.start_polling(allowed_updates=Update.ALL_TYPES)
            # post_init НЕ вызывается автоматически при ручном initialize/start —
            # это делает только Application.run_polling(). Вызываем вручную.
            if doday_app.post_init is not None:
                await doday_app.post_init(doday_app)
            logger.info("Doday bot polling started")
        except Exception as exc:
            logger.error("Doday bot failed to start: %s — continuing with Lessio only", exc)
            # Don't try to shutdown a half-initialized app; just drop the reference.
            doday_app = None
            doday_updater = None

    lessio_updater = None
    if lessio_app is not None:
        try:
            lessio_updater = lessio_app.updater
            if lessio_updater is None:
                raise RuntimeError("Lessio Application.updater is None — builder misconfigured")
            await lessio_app.initialize()
            await lessio_app.start()
            await lessio_updater.start_polling(allowed_updates=Update.ALL_TYPES)
            if lessio_app.post_init is not None:
                await lessio_app.post_init(lessio_app)
            logger.info("Lessio bot polling started")
        except Exception as exc:
            logger.error("Lessio bot failed to start: %s — continuing with Doday only", exc)
            lessio_app = None
            lessio_updater = None

    if doday_app is None and lessio_app is None:
        logger.error("Both bots failed to start — exiting worker (watchdog will retry)")
        return

    # Wait until the worker is killed (systemd SIGTERM → CancelledError below).
    stop_event = asyncio.Event()
    try:
        await stop_event.wait()
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("shutdown signal received, stopping bots…")
    finally:
        if lessio_app is not None and lessio_updater is not None:
            try:
                await lessio_updater.stop()
                await lessio_app.stop()
                await lessio_app.shutdown()
            except Exception as exc:
                logger.warning("Lessio shutdown error: %s", exc)
        if doday_app is not None and doday_updater is not None:
            try:
                await doday_updater.stop()
                await doday_app.stop()
                await doday_app.shutdown()
            except Exception as exc:
                logger.warning("Doday shutdown error: %s", exc)


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
    )
    logger.info("starting Telegram bot worker (Doday + optional Lessio)…")
    asyncio.run(_run_both())


if __name__ == "__main__":
    main()
