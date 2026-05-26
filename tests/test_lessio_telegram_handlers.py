"""@LessioBot handlers — /start + продуктовые команды (/menu /help /about /privacy /feedback)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.lessio.telegram_handlers import cmd_start, register_handlers


def _make_update(chat_id: int = 12345) -> Any:
    """Build a minimal stand-in for telegram.Update suitable for cmd_start."""
    reply = AsyncMock()
    message = SimpleNamespace(reply_text=reply)
    chat = SimpleNamespace(id=chat_id)
    return SimpleNamespace(message=message, effective_chat=chat)


async def test_cmd_start_sends_welcome_with_cta() -> None:
    update = _make_update()
    await cmd_start(update, SimpleNamespace())  # type: ignore[arg-type]
    update.message.reply_text.assert_awaited_once()
    text = update.message.reply_text.call_args.args[0]
    # Брендинг + CTA в тексте + наличие inline-кнопки с WebApp в reply_markup.
    assert "Lessio" in text
    # После запуска real-продукта welcome говорит про «кабинет», а не про waitlist.
    assert "кабинет" in text.lower()
    # HTML parse mode для жирного текста.
    kwargs = update.message.reply_text.call_args.kwargs
    assert kwargs.get("parse_mode") == "HTML"
    # Inline-кнопка с WebApp = /lessio (открывается прямо в Telegram WebView).
    markup = kwargs.get("reply_markup")
    assert markup is not None, "expected reply_markup with inline button"
    # Спускаемся до WebAppInfo URL — структура: [[InlineKeyboardButton(web_app=WebAppInfo(url=...))]]
    button = markup.inline_keyboard[0][0]
    assert button.web_app is not None
    assert button.web_app.url.endswith("/lessio")


async def test_cmd_start_ignores_missing_message() -> None:
    """Edge case — Telegram иногда шлёт update без message (edited_message etc).
    Хэндлер должен молча вернуться, не падать."""
    update = SimpleNamespace(message=None, effective_chat=None)
    # Не должно поднимать
    await cmd_start(update, SimpleNamespace())  # type: ignore[arg-type]


def test_register_handlers_adds_product_commands() -> None:
    """register_handlers подцепляет все продуктовые команды + message-handler."""
    added: list[Any] = []
    fake_app = SimpleNamespace(add_handler=lambda h: added.append(h))
    register_handlers(fake_app)  # type: ignore[arg-type]
    # /start /menu /help /about /privacy /feedback + on_feedback_message — итого 7
    assert len(added) >= 6, f"expected ≥6 handlers (commands + feedback), got {len(added)}"
    # Собираем имена команд из CommandHandler'ов
    all_commands: set[str] = set()
    for h in added:
        commands = getattr(h, "commands", None)
        if commands is not None:
            all_commands.update(str(c) for c in commands)
    for required in {"start", "menu", "help", "about", "privacy", "feedback"}:
        assert required in all_commands, f"command /{required} not registered"


@pytest.fixture(autouse=True)
def _no_warn_on_unraisable() -> None:
    """asyncio.AsyncMock сам по себе не выбрасывает unraisable — нет хуков."""
    return None
