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
import app.projects.models
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


async def on_unknown_text(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Любой текст без / — короткая подсказка."""
    if update.message is None or update.message.text is None:
        return
    await _reply(
        update,
        "Я понимаю команды через /. Самое полезное:\n"
        "/add <текст> — добавить задачу\n"
        "/today — что на сегодня\n"
        "/help — все команды",
    )


def build_app() -> Application[Any, Any, Any, Any, Any, Any]:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан в .env — bot worker не стартует")
    application: Application[Any, Any, Any, Any, Any, Any] = (
        Application.builder().token(settings.telegram_bot_token).build()
    )
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("add", cmd_add))
    application.add_handler(CommandHandler("today", cmd_today))
    application.add_handler(CommandHandler("upcoming", cmd_upcoming))
    application.add_handler(CommandHandler("done", cmd_done))
    application.add_handler(CommandHandler("unlink", cmd_unlink))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_unknown_text))
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
