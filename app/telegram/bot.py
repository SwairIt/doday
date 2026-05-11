"""Telegram bot worker — long-running polling loop.

Запускается отдельно от uvicorn:
    .venv/bin/python -m app.telegram.bot

На проде — systemd-сервис /etc/systemd/system/doday-bot.service с
restart-on-failure. BOT_TOKEN из app/.env (settings.telegram_bot_token).

Команды:
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

import logging
import socket
from datetime import UTC, datetime, timedelta
from datetime import time as dtime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# SQLAlchemy mapper-warmup: relationship строки вроде `order_by="Label.name"`
# eval'ятся лениво и требуют чтобы все классы были загружены в registry до
# первого query. uvicorn это делает через include_router → импорт routers →
# импорт moduls. У бота нет роутеров, поэтому импортируем модели явно.
import app.auth.models
import app.comments.models
import app.custom_filters.models
import app.habits.models
import app.labels.models
import app.links.models
import app.mood.models
import app.pomodoro.models
import app.projects.models
import app.reminders.models
import app.school.models
import app.sections.models
import app.tasks.models
import app.telegram.models
import app.user_templates.models  # noqa: F401
from app.auth.models import User
from app.config import get_settings
from app.quickadd.parser import parse_quick_add
from app.tasks.models import Task, TaskPriority
from app.tasks.service import create_task
from app.telegram.service import complete_link, get_user_by_chat, unlink

logger = logging.getLogger("doday.telegram")


def _force_ipv4_resolve() -> None:
    """Monkey-patch socket.getaddrinfo → AF_INET only.

    На проде systemd-resolved отдаёт только AAAA для api.telegram.org, и httpx
    висит 30s на недоступной IPv6-сети. Force-IPv4 убирает баг без sudo-правки
    /etc/hosts.

    Caveat: getaddrinfo поддерживает family и позиционно (3-й аргумент после
    host, port), и через kwargs. Httpx передаёт family позиционно — поэтому
    переписывание kwargs['family'] вызывает TypeError "multiple values for
    family". Обрабатываем оба варианта и трогаем family только если оригинал
    был AF_UNSPEC (0).
    """
    orig = socket.getaddrinfo

    def _ipv4_only(host: Any, *args: Any, **kwargs: Any) -> Any:
        args_list = list(args)
        # args = (port, family, type, proto, flags) — family это args_list[1]
        if len(args_list) >= 2:
            if args_list[1] == 0:
                args_list[1] = socket.AF_INET
        elif kwargs.get("family", 0) == 0:
            kwargs["family"] = socket.AF_INET
        return orig(host, *args_list, **kwargs)

    socket.getaddrinfo = _ipv4_only


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

    Также проверяет что юзер на Pro-тарифе. Если trial кончился — добрая
    подсказка вместо тихого молчания."""
    from app.billing.service import has_pro_features

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
    if not has_pro_features(user):
        await _reply(
            update,
            "Telegram-бот доступен в Pro-подписке. Trial закончился, и сейчас "
            "у тебя Free-тариф. Подключи Pro → бот снова заработает: "
            "https://getdoday.ru/pricing",
        )
        return None
    return user


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Юзер пишет /start или /start <token> через deeplink."""
    args = context.args or []
    chat = update.effective_chat
    if chat is None:
        return
    if not args:
        await _reply(
            update,
            "Привет, я бот *Doday* — добавляю задачи в твой список из чата.\n\n"
            "Чтобы привязать аккаунт, открой Doday → Профиль → Telegram → "
            "нажми «Подключить». Получишь ссылку с токеном.",
            markdown=True,
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
    await _reply(
        update,
        f"✓ Готово, ты привязан как *{user.email}*.\n\n"
        "Команды:\n"
        "/add `купить молоко завтра !!! @дом` — задача\n"
        "/today — задачи на сегодня\n"
        "/upcoming — на 7 дней\n"
        "/done — закрытые сегодня\n"
        "/help — полная справка",
        markdown=True,
    )


async def cmd_help(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply(
        update,
        "Команды:\n\n"
        "*/add <текст>*  — добавить задачу. Парсер понимает:\n"
        "  • Даты: «сегодня», «завтра», «пн», «через 3 дня», «15 декабря»\n"
        "  • Приоритет: «!» = P4 ... «!!!!» = P1\n"
        "  • Лейблы: «@дом», «@работа»\n"
        "  • Проект: «#учёба»\n"
        "  Пример: `/add Сходить в зал завтра !!! @спорт`\n\n"
        "*/today* — просроченные + сегодняшние\n"
        "*/upcoming* — следующие 7 дней\n"
        "*/done* — последние 5 закрытых сегодня\n"
        "*/unlink* — отвязать этот чат от Doday-аккаунта",
        markdown=True,
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
    """Открыть Mini App инлайн-кнопкой. Подсказка-fallback если у юзера
    клиент не поддерживает inline-WebApp (старые версии Telegram)."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

    if update.message is None:
        return
    settings = get_settings()
    base = settings.app_base_url or "https://getdoday.ru"
    webapp_url = base.rstrip("/") + "/miniapp/"
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Открыть Doday", web_app=WebAppInfo(url=webapp_url))]]
    )
    await update.message.reply_text(
        "Тапни кнопку ниже — откроется Doday прямо в Telegram.",
        reply_markup=keyboard,
    )


async def on_unknown_text(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Любой текст без / — короткая подсказка."""
    if update.message is None or update.message.text is None:
        return
    await _reply(
        update,
        "Я понимаю команды через /. Самое полезное:\n"
        "/app — открыть Mini App\n"
        "/add <текст> — добавить задачу\n"
        "/today — что на сегодня\n"
        "/help — все команды",
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


def build_app() -> Application[Any, Any, Any, Any, Any, Any]:
    # IPv4-only DNS — должен сработать ДО первого httpx.AsyncClient.
    _force_ipv4_resolve()
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан в .env — bot worker не стартует")
    application: Application[Any, Any, Any, Any, Any, Any] = (
        Application.builder().token(settings.telegram_bot_token).build()
    )
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("app", cmd_app))
    application.add_handler(CommandHandler("add", cmd_add))
    application.add_handler(CommandHandler("today", cmd_today))
    application.add_handler(CommandHandler("upcoming", cmd_upcoming))
    application.add_handler(CommandHandler("done", cmd_done))
    application.add_handler(CommandHandler("unlink", cmd_unlink))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_unknown_text))

    # Post-init: при старте бота
    #   1. ставим default chat menu button → WebApp Mini App;
    #   2. регистрируем команды через setMyCommands → юзер видит подсказки при "/";
    # Обе операции идемпотентны, переживают перезапуск.
    async def _post_init(app: Application[Any, Any, Any, Any, Any, Any]) -> None:
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

    application.post_init = _post_init

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


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
    )
    logger.info("starting Doday Telegram bot...")
    app = build_app()
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
