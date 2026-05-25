"""@LessioBot handlers — validation phase: только /start с CTA на waitlist.

Архитектура (см. app/telegram/bot.py):
- @DodayTaskBot и @LessioBot живут в одном worker-процессе через два
  Telegram Application'а в одном asyncio loop (gather в main()).
- Здесь только handlers Lessio. Stars-payment handlers (pre_checkout / successful)
  подключаются позже, в MVP-фазе — пока никаких invoices Lessio не выписывает.

После прохождения waitlist'а (≥100 подписок на 2026-06-01) добавятся:
- /start lessio_<tutor_slug> — клиент пришёл по invite-ссылке репетитора,
  отвечаем inline-кнопкой `web_app` URL = /lessio/miniapp/book/<slug>
- /cabinet — открыть Mini App кабинета репетитора (/lessio/miniapp/cabinet)
- PreCheckoutQueryHandler + SUCCESSFUL_PAYMENT MessageHandler — переиспользуем
  on_pre_checkout_query / on_successful_payment из app.telegram.bot (общая
  логика через HMAC payload в app.billing.stars).
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

logger = logging.getLogger("lessio.telegram")


_WELCOME_TEXT = (
    "👋 Привет! Это <b>Lessio</b> — Telegram-кабинет для репетиторов и онлайн-тренеров.\n\n"
    "Клиент тапает → выбирает время → платит через Telegram Stars → "
    "у тебя автоматически запись в календарь и деньги.\n\n"
    "🚧 <b>Сейчас собираю waitlist.</b> Если 100 репетиторов подпишутся за неделю — "
    "запускаю MVP. Если нет — переключаюсь на другую идею.\n\n"
    '👉 Оставь email на <a href="https://getdoday.ru/lessio">getdoday.ru/lessio</a> — '
    "напишу лично в Telegram когда будет первая версия.\n\n"
    "<i>Если ты не репетитор — посмотри другие проекты студии: "
    '<a href="https://getdoday.ru/">getdoday.ru</a></i>'
)


async def cmd_start(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message + CTA на waitlist. Игнорирует payload `/start <args>` —
    deeplink-handling добавится в MVP-фазе."""
    if update.message is None:
        return
    await update.message.reply_text(
        _WELCOME_TEXT,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=False,
    )
    logger.info(
        "/start from chat_id=%s", update.effective_chat.id if update.effective_chat else "?"
    )


def register_handlers(application: Application) -> None:  # type: ignore[type-arg]
    """Mount Lessio handlers on the given Application. Called from app/telegram/bot.py."""
    application.add_handler(CommandHandler("start", cmd_start))
