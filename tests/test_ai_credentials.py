"""Тесты этапа 1 ИИ-помощника: шифрование ключей, справочник, CRUD, API."""

from __future__ import annotations

from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import service as ai_service
from app.ai.client import AiProviderError, verify_key
from app.ai.crypto import KEY_VERSION, AiKeyError, decrypt_api_key, encrypt_api_key, key_last4
from app.ai.providers import CUSTOM_KEY, PROVIDER_BY_KEY, PROVIDERS, get_provider
from app.ai.service import UnknownProvider
from app.auth.models import User


def test_encrypt_decrypt_roundtrip() -> None:
    plain = "sk-test-abcdef1234567890"
    ciphertext = encrypt_api_key(plain)
    assert ciphertext != plain
    assert plain not in ciphertext
    assert decrypt_api_key(ciphertext) == plain


def test_encrypt_is_not_deterministic() -> None:
    """Fernet добавляет соль и метку времени — два шифрования дают разный текст."""
    plain = "sk-test-abcdef1234567890"
    assert encrypt_api_key(plain) != encrypt_api_key(plain)


def test_decrypt_rejects_garbage() -> None:
    with pytest.raises(AiKeyError):
        decrypt_api_key("не-шифротекст")


def test_decrypt_rejects_unknown_version() -> None:
    with pytest.raises(AiKeyError):
        decrypt_api_key(encrypt_api_key("sk-test"), version=999)


def test_key_last4() -> None:
    assert key_last4("sk-test-abcdef1234567890") == "7890"
    assert key_last4("abc") == "abc"


def test_key_version_is_current() -> None:
    assert KEY_VERSION == 1


def test_providers_have_required_fields() -> None:
    assert len(PROVIDERS) >= 3
    for p in PROVIDERS:
        assert p.key and p.title and p.hint
        if p.key != CUSTOM_KEY:
            assert p.base_url.startswith("https://")
            assert p.default_model


def test_provider_lookup() -> None:
    cloudru = get_provider("cloudru")
    assert cloudru is not None
    assert cloudru.base_url == "https://foundation-models.api.cloud.ru/v1"
    assert get_provider("нет-такого") is None
    assert set(PROVIDER_BY_KEY) == {p.key for p in PROVIDERS}


def test_custom_provider_has_no_fixed_url() -> None:
    custom = get_provider(CUSTOM_KEY)
    assert custom is not None
    assert custom.base_url == ""


# ── сервисный слой (нужна БД) ─────────────────────────────────────────────


@pytest_asyncio.fixture
async def ai_user_id(db_session: AsyncSession) -> UUID:
    """Отдельный пользователь под тесты ключей."""
    user = User(id=uuid4(), email=f"ai-{uuid4().hex[:8]}@test.local", password_hash="x")
    db_session.add(user)
    await db_session.commit()
    return user.id


async def test_upsert_and_get_credential(db_session: AsyncSession, ai_user_id: UUID) -> None:
    cred = await ai_service.upsert_credential(
        db_session, ai_user_id, provider="cloudru", api_key="sk-secret-1234"
    )
    assert cred.provider == "cloudru"
    assert cred.base_url == "https://foundation-models.api.cloud.ru/v1"
    assert cred.model == "ai-sage/GigaChat3-10B-A1.8B"
    assert cred.key_last4 == "1234"
    assert "sk-secret-1234" not in cred.key_ciphertext

    same = await ai_service.get_credential(db_session, ai_user_id)
    assert same is not None
    assert same.id == cred.id


async def test_upsert_replaces_existing(db_session: AsyncSession, ai_user_id: UUID) -> None:
    first = await ai_service.upsert_credential(
        db_session, ai_user_id, provider="cloudru", api_key="sk-first-1111"
    )
    first_id = first.id
    second = await ai_service.upsert_credential(
        db_session, ai_user_id, provider="mistral", api_key="sk-second-2222"
    )
    assert first_id == second.id, "один ключ на пользователя — запись обновляется"
    assert second.provider == "mistral"
    assert second.key_last4 == "2222"


def _resolves_to(monkeypatch: pytest.MonkeyPatch, ip: str) -> None:
    """Подменить резолвер: тесты не должны ходить в DNS."""
    monkeypatch.setattr(
        "app.ai.service.socket.getaddrinfo",
        lambda host, port: [(2, 1, 6, "", (ip, 0))],
    )


async def test_custom_provider_requires_url_and_model(
    db_session: AsyncSession, ai_user_id: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    _resolves_to(monkeypatch, "93.184.216.34")
    cred = await ai_service.upsert_credential(
        db_session,
        ai_user_id,
        provider="custom",
        api_key="sk-custom-3333",
        base_url="https://example.test/v1",
        model="some-model",
    )
    assert cred.base_url == "https://example.test/v1"
    assert cred.model == "some-model"

    with pytest.raises(UnknownProvider):
        await ai_service.upsert_credential(
            db_session, ai_user_id, provider="custom", api_key="sk-x-4444"
        )


async def test_unknown_provider_rejected(db_session: AsyncSession, ai_user_id: UUID) -> None:
    with pytest.raises(UnknownProvider):
        await ai_service.upsert_credential(
            db_session, ai_user_id, provider="нет-такого", api_key="sk-x-5555"
        )


async def test_resolve_secret_returns_plain_key(db_session: AsyncSession, ai_user_id: UUID) -> None:
    await ai_service.upsert_credential(
        db_session, ai_user_id, provider="cloudru", api_key="sk-plain-9999"
    )
    resolved = await ai_service.resolve_secret(db_session, ai_user_id)
    assert resolved is not None
    base_url, api_key, model = resolved
    assert api_key == "sk-plain-9999"
    assert base_url.endswith("/v1")
    assert model


async def test_delete_credential(db_session: AsyncSession, ai_user_id: UUID) -> None:
    await ai_service.upsert_credential(
        db_session, ai_user_id, provider="cloudru", api_key="sk-del-4444"
    )
    assert await ai_service.delete_credential(db_session, ai_user_id) is True
    assert await ai_service.get_credential(db_session, ai_user_id) is None
    assert await ai_service.delete_credential(db_session, ai_user_id) is False


# ── проверка ключа у провайдера (без реальных запросов) ───────────────────


def _fake_post(status: int, body: object = None):
    """Подменяет httpx.AsyncClient.post фиксированным ответом."""

    async def post(self: object, url: str, **kwargs: object) -> httpx.Response:
        return httpx.Response(status, json=body or {"ok": True}, request=httpx.Request("POST", url))

    return post


async def test_verify_key_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        httpx.AsyncClient, "post", _fake_post(200, {"choices": [{"message": {"content": "ok"}}]})
    )
    await verify_key(base_url="https://x.test/v1", api_key="sk-1", model="m")


@pytest.mark.parametrize(
    ("status", "fragment"),
    [
        (401, "не принят"),
        (403, "не принят"),
        (402, "средства"),
        (404, "модели"),
        (429, "часто"),
        (500, "не отвечает"),
    ],
)
async def test_verify_key_maps_errors(
    monkeypatch: pytest.MonkeyPatch, status: int, fragment: str
) -> None:
    monkeypatch.setattr(httpx.AsyncClient, "post", _fake_post(status, {"error": "boom"}))
    with pytest.raises(AiProviderError) as exc:
        await verify_key(base_url="https://x.test/v1", api_key="sk-1", model="m")
    assert fragment in exc.value.user_message


async def test_verify_key_never_leaks_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx.AsyncClient, "post", _fake_post(401, {"error": "denied"}))
    with pytest.raises(AiProviderError) as exc:
        await verify_key(base_url="https://x.test/v1", api_key="sk-super-secret", model="m")
    assert "sk-super-secret" not in exc.value.user_message
    assert "sk-super-secret" not in str(exc.value)


async def test_verify_key_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(self: object, url: str, **kwargs: object) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout")

    monkeypatch.setattr(httpx.AsyncClient, "post", boom)
    with pytest.raises(AiProviderError) as exc:
        await verify_key(base_url="https://x.test/v1", api_key="sk-1", model="m")
    assert "не отвечает" in exc.value.user_message


# ── REST API ──────────────────────────────────────────────────────────────


async def test_providers_endpoint(logged_in_client: AsyncClient) -> None:
    r = await logged_in_client.get("/api/ai/providers")
    assert r.status_code == 200
    body = r.json()
    keys = {p["key"] for p in body}
    assert {"cloudru", "mistral", "custom"} <= keys
    assert all("hint" in p for p in body)


async def test_credential_crud_via_api(logged_in_client: AsyncClient) -> None:
    assert (await logged_in_client.get("/api/ai/credential")).json() is None

    r = await logged_in_client.put(
        "/api/ai/credential",
        json={"provider": "cloudru", "api_key": "sk-api-5678"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "cloudru"
    assert body["key_last4"] == "5678"
    assert "api_key" not in body
    assert "sk-api-5678" not in r.text

    assert (await logged_in_client.get("/api/ai/credential")).json()["key_last4"] == "5678"
    assert (await logged_in_client.delete("/api/ai/credential")).status_code == 204
    assert (await logged_in_client.get("/api/ai/credential")).json() is None


async def test_credential_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/ai/credential")).status_code == 401


async def test_unknown_provider_returns_400(logged_in_client: AsyncClient) -> None:
    r = await logged_in_client.put(
        "/api/ai/credential", json={"provider": "нет-такого", "api_key": "sk-12345678"}
    )
    assert r.status_code == 400


async def test_verify_endpoint(
    logged_in_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await logged_in_client.put(
        "/api/ai/credential", json={"provider": "cloudru", "api_key": "sk-verify-7777"}
    )

    async def ok(**kwargs: object) -> None:
        return None

    monkeypatch.setattr("app.ai.router.verify_key", ok)
    r = await logged_in_client.post("/api/ai/credential/verify")
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    async def fail(**kwargs: object) -> None:
        raise AiProviderError("Ключ не принят провайдером — проверь, что скопировал его целиком.")

    monkeypatch.setattr("app.ai.router.verify_key", fail)
    r = await logged_in_client.post("/api/ai/credential/verify")
    assert r.status_code == 400
    assert "не принят" in r.json()["detail"]


async def test_settings_page_has_ai_section(logged_in_client: AsyncClient) -> None:
    html = (await logged_in_client.get("/app/settings")).text
    assert "ИИ-помощник" in html
    assert "/api/ai/providers" in html
    assert "/api/ai/credential" in html
    # шифротекст и сам ключ не должны попадать в разметку
    assert "key_ciphertext" not in html


async def test_verify_key_400_with_key_marker_reads_as_bad_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cloud.ru на неверный ключ отвечает 400, а не 401 — проверено вживую."""
    monkeypatch.setattr(
        httpx.AsyncClient,
        "post",
        _fake_post(400, {"code": "InvalidArgument", "message": "invalid api key secret"}),
    )
    with pytest.raises(AiProviderError) as exc:
        await verify_key(base_url="https://x.test/v1", api_key="sk-1", model="m")
    assert "не принят" in exc.value.user_message


async def test_verify_key_400_without_key_marker_points_at_url_and_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx.AsyncClient, "post", _fake_post(400, {"message": "bad request"}))
    with pytest.raises(AiProviderError) as exc:
        await verify_key(base_url="https://x.test/v1", api_key="sk-1", model="m")
    assert "адрес API" in exc.value.user_message


# ── свой провайдер не должен вести во внутреннюю сеть ─────────────────────


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",  # сам сервер
        "10.0.0.5",  # локальная сеть
        "192.168.33.3",  # панель хостинга
        "172.16.4.4",
        "169.254.169.254",  # метадата облака
    ],
)
async def test_custom_provider_rejects_internal_address(
    db_session: AsyncSession, ai_user_id: UUID, monkeypatch: pytest.MonkeyPatch, ip: str
) -> None:
    """Адрес, по которому потом ходит наш сервер, — это SSRF, если он внутренний.

    Проверялась только схема https://, так что «свой провайдер» работал
    сканером внутренней сети: коды ответа у нас разные для 401/404/429.
    """
    _resolves_to(monkeypatch, ip)
    with pytest.raises(UnknownProvider):
        await ai_service.upsert_credential(
            db_session,
            ai_user_id,
            provider="custom",
            api_key="sk-ssrf-9999",
            base_url="https://internal.example/v1",
            model="m",
        )


async def test_known_provider_does_not_resolve_dns(
    db_session: AsyncSession, ai_user_id: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Для провайдеров из справочника адрес наш, ходить в DNS незачем."""

    def boom(host: str, port: object) -> object:
        raise AssertionError("резолвер не должен вызываться")

    monkeypatch.setattr("app.ai.service.socket.getaddrinfo", boom)
    cred = await ai_service.upsert_credential(
        db_session, ai_user_id, provider="mistral", api_key="sk-known-1111"
    )
    assert cred.provider == "mistral"


# ── справочник провайдеров ────────────────────────────────────────────────


def test_gemini_is_available() -> None:
    """Ключ Gemini бесплатный и выдаётся сразу — это самый простой путь для
    пользователя, поэтому он должен быть в списке, а не только через «свой»."""
    gemini = get_provider("gemini")
    assert gemini is not None
    assert gemini.base_url == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert gemini.default_model.startswith("gemini")
    assert "aistudio.google.com" in gemini.signup_url


def test_every_provider_explains_how_to_get_a_key() -> None:
    """Жалоба была ровно про это: «нифига непонятно, как подключать»."""
    for provider in PROVIDERS:
        assert len(provider.steps) >= 3, provider.key
        assert all(step.strip() for step in provider.steps), provider.key
        assert provider.price.strip(), provider.key
        assert provider.key_looks_like.strip(), provider.key
        assert provider.hint.strip(), provider.key


def test_known_providers_have_url_and_model() -> None:
    for provider in PROVIDERS:
        if provider.key == CUSTOM_KEY:
            continue
        assert provider.base_url.startswith("https://"), provider.key
        assert not provider.base_url.endswith("/"), provider.key
        assert provider.default_model, provider.key
        assert provider.signup_url.startswith("https://"), provider.key


def test_blocked_from_russia_providers_are_absent() -> None:
    """Groq, OpenRouter, Cerebras и Nebius на запрос с российского адреса
    отвечают 403 «access denied». Ключ бы выдали, а чат бы не заработал."""
    urls = " ".join(p.base_url for p in PROVIDERS)
    for host in ("groq.com", "openrouter.ai", "cerebras.ai", "nebius"):
        assert host not in urls


async def test_gemini_credential_saves(db_session: AsyncSession, ai_user_id: UUID) -> None:
    cred = await ai_service.upsert_credential(
        db_session, ai_user_id, provider="gemini", api_key="AIzaSyTestKey1234567890"
    )
    assert cred.provider == "gemini"
    assert cred.base_url == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert cred.key_last4 == "7890"


async def test_providers_endpoint_returns_steps(logged_in_client: AsyncClient) -> None:
    rows = (await logged_in_client.get("/api/ai/providers")).json()
    by_key = {r["key"]: r for r in rows}
    assert "gemini" in by_key
    assert len(by_key["gemini"]["steps"]) >= 3
    assert by_key["gemini"]["price"]


async def test_settings_page_shows_instructions(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/settings")).text
    assert "Как получить ключ" in body
    assert 'id="ai"' in body


async def test_yandex_is_available_and_needs_folder_id(
    db_session: AsyncSession, ai_user_id: UUID
) -> None:
    """Ключ Yandex Cloud начинается на AQVN — его тоже надо уметь подключить.

    Название модели у них содержит ID каталога, поэтому в поле стоит заглушка:
    уехав как есть, она дала бы невнятную ошибку провайдера.
    """
    yandex = get_provider("yandex")
    assert yandex is not None
    assert yandex.base_url == "https://llm.api.cloud.yandex.net/v1"
    assert "ID-КАТАЛОГА" in yandex.default_model

    with pytest.raises(UnknownProvider):
        await ai_service.upsert_credential(
            db_session, ai_user_id, provider="yandex", api_key="AQVNtest1234567890"
        )

    cred = await ai_service.upsert_credential(
        db_session,
        ai_user_id,
        provider="yandex",
        api_key="AQVNtest1234567890",
        model="gpt://b1gtestfolder/yandexgpt-lite/latest",
    )
    assert cred.model == "gpt://b1gtestfolder/yandexgpt-lite/latest"


def test_key_format_is_never_validated() -> None:
    """Ключи выглядят по-разному: AQ.Ab у Google (раньше был AIza), AQVN у
    Yandex, sk- у прочих.

    Проверять формат нельзя — принимаем любой, а прав он или нет, скажет
    сам провайдер.
    """
    from app.ai.schemas import CredentialIn

    for key in ("AQ.Ab8RN6abcdef123", "AIzaSyABC1234567890", "AQVNabcdef1234567890", "sk-1234"):
        assert CredentialIn(provider="custom", api_key=key).api_key == key
