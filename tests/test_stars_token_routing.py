"""Stars — выбор bot token по product_code (Doday vs Lessio split)."""

from __future__ import annotations

import pytest

from app.billing.stars import StarsError, _bot_token_for_product
from app.config import get_settings


@pytest.fixture
def stash_tokens() -> tuple[str, str]:
    """Сохранить текущие токены, чтобы тест мог их перезаписать."""
    settings = get_settings()
    saved = (settings.telegram_bot_token, settings.lessio_bot_token)
    yield saved  # type: ignore[misc]
    settings.telegram_bot_token, settings.lessio_bot_token = saved


def test_doday_product_routes_to_doday_token(stash_tokens: tuple[str, str]) -> None:
    settings = get_settings()
    settings.telegram_bot_token = "doday-token"
    settings.lessio_bot_token = "lessio-token"
    assert _bot_token_for_product("pro_1m") == "doday-token"
    assert _bot_token_for_product("pro_12m") == "doday-token"
    assert _bot_token_for_product("pro_forever") == "doday-token"
    assert _bot_token_for_product("family_1m") == "doday-token"
    assert _bot_token_for_product("family_12m") == "doday-token"


def test_lessio_product_routes_to_lessio_token(stash_tokens: tuple[str, str]) -> None:
    settings = get_settings()
    settings.telegram_bot_token = "doday-token"
    settings.lessio_bot_token = "lessio-token"
    assert _bot_token_for_product("tutor_pro_1m") == "lessio-token"
    assert _bot_token_for_product("tutor_pro_12m") == "lessio-token"
    assert _bot_token_for_product("tutor_pro_forever") == "lessio-token"


def test_lessio_token_empty_raises(stash_tokens: tuple[str, str]) -> None:
    """Lessio-продукт без LESSIO_BOT_TOKEN — explicit error, не fallback на Doday."""
    settings = get_settings()
    settings.telegram_bot_token = "doday-token"
    settings.lessio_bot_token = ""
    with pytest.raises(StarsError, match="LESSIO_BOT_TOKEN"):
        _bot_token_for_product("tutor_pro_1m")


def test_doday_token_empty_raises(stash_tokens: tuple[str, str]) -> None:
    settings = get_settings()
    settings.telegram_bot_token = ""
    settings.lessio_bot_token = "lessio-token"
    with pytest.raises(StarsError, match="TELEGRAM_BOT_TOKEN"):
        _bot_token_for_product("pro_1m")
