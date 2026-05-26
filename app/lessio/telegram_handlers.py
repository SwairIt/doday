"""@LessioBot — handlers + post_init для bot worker'а.

Архитектура (см. app/telegram/bot.py):
- @DodayTaskBot и @LessioBot живут в одном worker-процессе через два
  Telegram Application'а в одном asyncio loop (gather в _run_both).
- `lessio_post_init` вызывается из `build_lessio_app()` и идемпотентно
  настраивает commands, description, short_description, menu-button.
  Каждый restart re-applies — безопасно.
- `register_handlers` маунтит все CommandHandler'ы + MessageHandler для
  /feedback-flow (catch-next-private-message).

Commands:
- /start [lessio_<slug>]  — приветствие; deeplink-payload `lessio_<slug>` от
  invite-ссылки tutor'а открывает booking-страницу клиента (web /u/<slug>).
- /menu                    — переоткрыть menu-button (если юзер скрыл).
- /help                    — список команд.
- /about                   — про сервис + ссылка на лендинг.
- /privacy                 — короткая privacy + ссылка на полную.
- /feedback                — попросить юзера написать сообщение, переслать
  его на admin_telegram_user_id.

Что НЕ здесь:
- PreCheckoutQueryHandler / SUCCESSFUL_PAYMENT — это handlers для Stars-flow.
  Когда Lessio начнёт выписывать tutor_pro_* / booking-invoices, эти handler'ы
  переиспользуются ИЗ @DodayTaskBot (общая логика через HMAC payload в
  app.billing.stars). Делаем это в отдельном чанке когда первый Stars-invoice
  для Lessio будет реально выписываться.
"""

from __future__ import annotations

import logging
from typing import Any

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Update,
    WebAppInfo,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import get_settings

logger = logging.getLogger("lessio.telegram")


# ── Тексты ────────────────────────────────────────────────────────────────

_WELCOME_TEXT = (
    "👋 Привет! Это <b>Lessio</b> — кабинет для онлайн-репетиторов, "
    "тренеров, коучей и психологов.\n\n"
    "📅 Клиент тапает по ссылке → выбирает время → платит → у тебя автоматически "
    "запись в календарь и деньги.\n\n"
    "✨ Без сайта, переводов на сбер и Excel-расписаний.\n\n"
    "Нажми кнопку ниже чтобы открыть кабинет."
)

_HELP_TEXT = (
    "<b>Что я умею</b>\n\n"
    "📝 /start — приветствие + кнопка кабинета\n"
    "🌐 /menu — переоткрыть кнопку «Открыть Lessio»\n"
    "ℹ️ /about — о проекте\n"
    "🔒 /privacy — политика конфиденциальности\n"
    "💬 /feedback — написать создателю\n\n"
    "Главная работа происходит в кабинете — открой его кнопкой ниже или "
    "командой /menu."
)

_ABOUT_TEXT = (
    '<b>Lessio</b> — один из проектов <a href="https://getdoday.ru">Doday Studio</a>.\n\n'
    "Создатель — Yaroslav (15 лет, разработчик Doday Tasks — ~400 активных юзеров).\n\n"
    "Идея: онлайн-учителя теряют часы в неделю на переписку «во вторник можно? "
    "переведите на сбер, чек скину завтра». Lessio закрывает это одной ссылкой.\n\n"
    'Открытый код: <a href="https://github.com/SwairIt">github.com/SwairIt</a>'
)

_PRIVACY_TEXT = (
    "🔒 <b>Что мы храним</b>:\n"
    "• Твой Telegram ID и имя (узнать тебя при следующем заходе)\n"
    "• Email и расписание (когда зарегистрируешься как репетитор)\n"
    "• Историю записей клиентов и оплаты (твой архив)\n\n"
    "<b>Что НЕ храним</b>:\n"
    "• Содержимое чатов с клиентами\n"
    "• Платёжные данные карт (всё через Telegram Stars — мы видим только сумму)\n\n"
    "<b>Удаление</b>: /feedback с просьбой «удалить все данные» → в течение 24ч.\n\n"
    "Полная версия: https://getdoday.ru/privacy"
)

_FEEDBACK_PROMPT = (
    "💬 Напиши одним сообщением что хочешь сказать. Бот перешлёт мне (Yaroslav), отвечу лично."
)

_FEEDBACK_FALLBACK_EMAIL = "doday.support@gmail.com"


# ── Commands list для setMyCommands ──────────────────────────────────────

_COMMANDS_RU: list[BotCommand] = [
    BotCommand("start", "Открыть Lessio"),
    BotCommand("menu", "Кнопка кабинета"),
    BotCommand("help", "Что я умею"),
    BotCommand("about", "О сервисе"),
    BotCommand("privacy", "Политика конфиденциальности"),
    BotCommand("feedback", "Написать создателю"),
]

_COMMANDS_EN: list[BotCommand] = [
    BotCommand("start", "Open Lessio"),
    BotCommand("menu", "Cabinet button"),
    BotCommand("help", "What I can do"),
    BotCommand("about", "About"),
    BotCommand("privacy", "Privacy policy"),
    BotCommand("feedback", "Contact creator"),
]

# Короткое описание — показывается в профиле бота под именем. ≤ 120 chars.
_SHORT_DESCRIPTION_RU = (
    "Записи и оплата для онлайн-репетиторов, тренеров, коучей. Без сайта, в Telegram."
)

# Длинное описание — на экране пустого чата (до первого /start). ≤ 512 chars.
_DESCRIPTION_RU = (
    "👋 Lessio — кабинет для онлайн-репетиторов, тренеров, коучей и психологов.\n\n"
    "📅 Клиент тапает → выбирает время → платит → у тебя запись в календарь и деньги.\n\n"
    "✨ Без сайта, переводов на сбер и Excel.\n\n"
    "Открой меню снизу слева ↓"
)


# ── Клавиатура с WebApp-кнопкой ──────────────────────────────────────────


def _open_lessio_keyboard() -> InlineKeyboardMarkup:
    """Inline-кнопка «🚀 Открыть Lessio» → WebApp `/lessio`.

    Тот же URL используется menu-button'ом (см. lessio_post_init). Landing на
    `/lessio` редиректит залогиненных юзеров в `/lessio/app/today`, не залогиненных
    — на `/lessio/auth/login`.
    """
    base = (get_settings().app_base_url or "https://getdoday.ru").rstrip("/")
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🚀 Открыть Lessio", web_app=WebAppInfo(url=f"{base}/lessio"))]]
    )


def _open_booking_keyboard(slug: str) -> InlineKeyboardMarkup:
    """Inline-кнопка для invite-deeplink: открывает публичную страницу tutor'а.

    Tutor шерит `t.me/LessioBot?start=lessio_<slug>` → клиент жмёт Start → бот
    отдаёт сюда → WebApp открывает `/u/<slug>` (публичная страница с booking).
    """
    base = (get_settings().app_base_url or "https://getdoday.ru").rstrip("/")
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Открыть запись", web_app=WebAppInfo(url=f"{base}/u/{slug}"))]]
    )


# ── post_init: setMyCommands + descriptions + menu button ───────────────


async def lessio_post_init(application: Application[Any, Any, Any, Any, Any, Any]) -> None:
    """Idempotent setup. Re-applied on every worker restart.

    Что ставит:
    - commands per-locale (ru + en fallback)
    - short_description (≤ 120 chars, в профиле бота)
    - description (≤ 512 chars, экран пустого чата)
    - default chat menu button → WebApp `/lessio`

    Что НЕ ставит (только через @BotFather руками):
    - name (/setname)
    - profile picture (/setuserpic)
    """
    bot = application.bot
    base = (get_settings().app_base_url or "https://getdoday.ru").rstrip("/")
    webapp_url = f"{base}/lessio"

    # 1. Commands (per-locale). Fallback (no language_code) — для языков кроме ru.
    try:
        await bot.set_my_commands(_COMMANDS_RU, language_code="ru")
        await bot.set_my_commands(_COMMANDS_EN)
        logger.info("Lessio commands registered (ru + en fallback)")
    except BadRequest as exc:
        logger.warning("Lessio set_my_commands failed: %s", exc)

    # 2. Short description (≤120 chars)
    try:
        await bot.set_my_short_description(
            short_description=_SHORT_DESCRIPTION_RU, language_code="ru"
        )
    except BadRequest as exc:
        logger.warning("Lessio set_my_short_description failed: %s", exc)

    # 3. Long description (≤512 chars)
    try:
        await bot.set_my_description(description=_DESCRIPTION_RU, language_code="ru")
    except BadRequest as exc:
        logger.warning("Lessio set_my_description failed: %s", exc)

    # 4. Menu button → WebApp /lessio
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Открыть Lessio", web_app=WebAppInfo(url=webapp_url))
        )
        logger.info("Lessio menu button set to %s", webapp_url)
    except BadRequest as exc:
        logger.warning("Lessio set_chat_menu_button failed: %s", exc)


# ── Handlers ──────────────────────────────────────────────────────────────


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome + WebApp button.

    Поддерживает deeplink `t.me/LessioBot?start=lessio_<slug>`: tutor шерит ссылку
    с клиентом, бот ловит и отдаёт inline-button с публичной booking-страницей
    `/u/<slug>` внутри WebApp.
    """
    if update.message is None:
        return

    args = context.args or []
    payload = args[0] if args else ""

    if payload.startswith("lessio_"):
        slug = payload.removeprefix("lessio_")
        # Минимальная санитизация — slug-формат уже проверяется на backend'е при
        # резолве, тут просто отрубаем явно мусорное. На дальние строки Telegram
        # сам ограничит payload до 64 символов.
        if slug and all(c.isalnum() or c in "-_" for c in slug):
            await update.message.reply_text(
                "📅 Запишитесь к репетитору — откроется страница с расписанием:",
                reply_markup=_open_booking_keyboard(slug),
                disable_web_page_preview=True,
            )
            chat_id = update.effective_chat.id if update.effective_chat else None
            logger.info("/start deeplink lessio_<slug> from chat_id=%s slug=%r", chat_id, slug)
            return
        logger.warning("/start with invalid deeplink slug ignored: %r", payload)

    await update.message.reply_text(
        _WELCOME_TEXT,
        parse_mode=ParseMode.HTML,
        reply_markup=_open_lessio_keyboard(),
        disable_web_page_preview=True,
    )
    chat_id = update.effective_chat.id if update.effective_chat else None
    logger.info("/start from chat_id=%s payload=%r", chat_id, payload)


async def cmd_menu(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Переоткрыть menu-button, если юзер случайно скрыл."""
    if update.message is None:
        return
    await update.message.reply_text(
        "👉 Нажми кнопку ниже чтобы открыть кабинет:",
        reply_markup=_open_lessio_keyboard(),
    )


async def cmd_help(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(
        _HELP_TEXT,
        parse_mode=ParseMode.HTML,
        reply_markup=_open_lessio_keyboard(),
    )


async def cmd_about(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(_ABOUT_TEXT, parse_mode=ParseMode.HTML)


async def cmd_privacy(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(_PRIVACY_TEXT, parse_mode=ParseMode.HTML)


# /feedback — простой sink через context.user_data. Юзер пишет /feedback,
# бот просит сообщение. Следующее текстовое сообщение в private chat ловит
# `on_feedback_message` и пересылает админу.

_FEEDBACK_AWAITING_KEY = "lessio_feedback_awaiting"


async def cmd_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    if context.user_data is not None:
        context.user_data[_FEEDBACK_AWAITING_KEY] = True
    await update.message.reply_text(_FEEDBACK_PROMPT)


async def on_feedback_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch private text-message — пересылает админу если в feedback-mode,
    иначе показывает friendly fallback с menu-кнопкой.

    Catch-all для текста в private chat (filter в register_handlers). Так что
    помимо feedback-flow это ещё и «непонятная команда» обработчик: юзер
    написал произвольный текст → отвечаем подсказкой + WebApp-кнопкой.
    """
    if update.message is None:
        return

    in_feedback_mode = context.user_data is not None and context.user_data.pop(
        _FEEDBACK_AWAITING_KEY, False
    )

    if not in_feedback_mode:
        # Юзер написал текст вне feedback-flow — friendly fallback.
        await update.message.reply_text(
            "Я понимаю команды через /. Самое удобное — открыть кабинет кнопкой ниже "
            "или командой /menu. Список команд — /help.",
            reply_markup=_open_lessio_keyboard(),
        )
        return

    settings = get_settings()
    admin_id = settings.admin_telegram_user_id
    if not admin_id:
        await update.message.reply_text(
            f"⚠️ Не настроен админ-канал. Напиши на {_FEEDBACK_FALLBACK_EMAIL}"
        )
        return

    sender = update.effective_user
    sender_label = (
        f"@{sender.username}"
        if sender and sender.username
        else (f"id={sender.id}" if sender else "unknown")
    )
    text_in = update.message.text or "(пустое сообщение)"
    try:
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"📬 Lessio feedback от {sender_label}:\n\n{text_in}",
        )
        await update.message.reply_text("✅ Отправил. Спасибо!")
    except Exception as exc:
        logger.exception("Lessio feedback forward failed: %s", exc)
        await update.message.reply_text(
            f"⚠️ Не удалось переслать. Напиши на {_FEEDBACK_FALLBACK_EMAIL}"
        )


# ── Registration ──────────────────────────────────────────────────────────


def register_handlers(application: Application[Any, Any, Any, Any, Any, Any]) -> None:
    """Mount all Lessio handlers. Called from app/telegram/bot.py build_lessio_app()."""
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("menu", cmd_menu))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("about", cmd_about))
    application.add_handler(CommandHandler("privacy", cmd_privacy))
    application.add_handler(CommandHandler("feedback", cmd_feedback))

    # Catch-all для следующего private-message после /feedback.
    # Filter ChatType.PRIVATE — чтобы НЕ ловить сообщения если бота добавили
    # в группу. Filter ~filters.COMMAND — чтобы не пересекаться с CommandHandler'ами.
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, on_feedback_message
        )
    )
