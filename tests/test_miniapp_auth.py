"""Tests for Telegram Mini App initData validation + /miniapp/auth endpoint.

Документация формата:
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from urllib.parse import urlencode

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import RegisterIn
from app.auth.service import register_user
from app.config import get_settings
from app.miniapp.auth import (
    INIT_DATA_MAX_AGE,
    get_telegram_user_id,
    validate_init_data,
)
from app.telegram.models import TelegramLink

BOT_TOKEN = "8761474413:TEST_TOKEN_FOR_HMAC_NOT_REAL"


def _make_init_data(
    *,
    bot_token: str = BOT_TOKEN,
    auth_date: int | None = None,
    user: dict | None = None,
    extra: dict | None = None,
    bad_hash: bool = False,
) -> str:
    """Build a valid (or intentionally invalid) initData querystring."""
    if auth_date is None:
        auth_date = int(time.time())
    if user is None:
        user = {"id": 12345, "first_name": "Test", "language_code": "ru"}
    fields: dict[str, str] = {
        "auth_date": str(auth_date),
        "query_id": "AAH-test-id",
        "user": json.dumps(user, separators=(",", ":")),
    }
    if extra:
        fields.update(extra)

    # Build data-check-string sorted by key, без hash
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    hsh = hmac.new(secret, data_check.encode("utf-8"), hashlib.sha256).hexdigest()
    if bad_hash:
        hsh = "0" * 64
    fields["hash"] = hsh
    return urlencode(fields)


# --- pure-function tests ----------------------------------------------------


def test_validate_init_data_valid() -> None:
    init = _make_init_data()
    parsed = validate_init_data(init, BOT_TOKEN)
    assert parsed is not None
    assert parsed["auth_date"]
    assert isinstance(parsed["user"], dict)
    assert parsed["user"]["id"] == 12345


def test_validate_init_data_bad_hash_rejected() -> None:
    init = _make_init_data(bad_hash=True)
    assert validate_init_data(init, BOT_TOKEN) is None


def test_validate_init_data_wrong_bot_token_rejected() -> None:
    init = _make_init_data(bot_token=BOT_TOKEN)
    assert validate_init_data(init, "OTHER_TOKEN") is None


def test_validate_init_data_stale_auth_date_rejected() -> None:
    stale = int(time.time()) - int(INIT_DATA_MAX_AGE.total_seconds()) - 60
    init = _make_init_data(auth_date=stale)
    assert validate_init_data(init, BOT_TOKEN) is None


def test_validate_init_data_empty_inputs() -> None:
    assert validate_init_data("", BOT_TOKEN) is None
    assert validate_init_data("foo=bar", "") is None


def test_validate_init_data_no_hash_field() -> None:
    fields = {"auth_date": str(int(time.time())), "user": '{"id":1}'}
    assert validate_init_data(urlencode(fields), BOT_TOKEN) is None


def test_get_telegram_user_id_extracts_int() -> None:
    parsed = {"user": {"id": 7777, "first_name": "X"}}
    assert get_telegram_user_id(parsed) == 7777


def test_get_telegram_user_id_no_user() -> None:
    assert get_telegram_user_id({}) is None
    assert get_telegram_user_id({"user": "not-a-dict"}) is None
    assert get_telegram_user_id({"user": {"first_name": "X"}}) is None


# --- /miniapp/auth endpoint tests -------------------------------------------


async def test_auth_endpoint_invalid_init_data_returns_401(
    client: AsyncClient, monkeypatch: object
) -> None:
    """Bad HMAC → 401 invalid_init_data."""
    s = get_settings()
    s.telegram_bot_token = BOT_TOKEN
    try:
        bad = _make_init_data(bad_hash=True)
        r = await client.post("/miniapp/auth", json={"init_data": bad})
        assert r.status_code == 401
        assert r.json() == {"error": "invalid_init_data"}
    finally:
        s.telegram_bot_token = ""


async def test_auth_endpoint_no_bot_token_returns_503(client: AsyncClient) -> None:
    """Если на сервере не настроен бот — 503."""
    s = get_settings()
    s.telegram_bot_token = ""
    init = _make_init_data()
    r = await client.post("/miniapp/auth", json={"init_data": init})
    assert r.status_code == 503
    assert r.json() == {"error": "bot_not_configured"}


async def test_auth_endpoint_unlinked_user_returns_need_link(client: AsyncClient) -> None:
    """Validatable initData, но chat_id не привязан → 401 need_link."""
    s = get_settings()
    s.telegram_bot_token = BOT_TOKEN
    try:
        init = _make_init_data(user={"id": 99999, "first_name": "X"})
        r = await client.post("/miniapp/auth", json={"init_data": init})
        assert r.status_code == 401
        body = r.json()
        assert body == {"need_link": True, "telegram_user_id": 99999}
    finally:
        s.telegram_bot_token = ""


async def test_auth_endpoint_linked_user_sets_session(
    db_session: AsyncSession, client: AsyncClient
) -> None:
    """Привязанный user_id → 200 + session-cookie проставлена."""
    s = get_settings()
    s.telegram_bot_token = BOT_TOKEN
    try:
        user = await register_user(
            db_session, RegisterIn(email="ma1@test.com", password="strongpass123")
        )
        user.email_verified_at = datetime.now(UTC)
        link = TelegramLink(user_id=user.id, chat_id=55555, link_token=None)
        link.linked_at = datetime.now(UTC)
        db_session.add(link)
        await db_session.commit()

        init = _make_init_data(user={"id": 55555, "first_name": "Linked"})
        r = await client.post("/miniapp/auth", json={"init_data": init})
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert r.json()["user_id"] == str(user.id)
        # Session cookie должна быть выставлена
        assert any(c.name == "session" for c in client.cookies.jar)
    finally:
        s.telegram_bot_token = ""
