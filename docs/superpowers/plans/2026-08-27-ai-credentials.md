# ИИ-помощник, этап 1: ключи и провайдеры — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Пользователь подключает свой ключ LLM-провайдера в настройках, ключ хранится зашифрованным, кнопка «Проверить» подтверждает, что ключ рабочий.

**Architecture:** Новый пакет `app/ai/` по образцу `app/school/` — модель, сервисный слой, роутер, схемы. Ключ шифруется Fernet с ключом, выведенным из `APP_SECRET_KEY` (тот же приём, что в `app/lessio/google_calendar.py`, но со своей солью и полем версии). Провайдеры описаны справочником, общение — по OpenAI-совместимому протоколу через `httpx`, без сторонних SDK.

**Tech Stack:** FastAPI 0.115, SQLAlchemy 2.0 async, Alembic, Pydantic v2, httpx, cryptography (Fernet + PBKDF2), pytest.

**Spec:** `docs/superpowers/specs/2026-08-26-ai-assistant-design.md`

## Global Constraints

- Python 3.12, весь код с аннотациями типов, проходит `mypy --strict`.
- Русские строки в модулях требуют записи в `[tool.ruff.lint.per-file-ignores]` (`RUF001`, `RUF002`, `RUF003`) — см. `pyproject.toml:176-182`.
- Роутеры не работают с ORM напрямую — только через `service.py` (паттерн `app/qa/router.py:6-8`).
- Ключ провайдера **никогда** не возвращается наружу: ни в API-ответе, ни в шаблоне, ни в логах, ни в тексте ошибки.
- Миграции: следующий номер — `0055`, `down_revision = "0054"`.
- Тесты используют фикстуры из `tests/conftest.py`: `client`, `logged_in_client`, `db_session`.
- Проверки перед коммитом: `uv run python -m ruff check . && uv run python -m ruff format --check . && uv run python -m mypy --strict app/ scripts/`.
- Коммиты `--no-verify` (pre-commit в этом окружении сломан), в теле сообщения указывать, что проверки прогнаны руками.
- Провайдеры (проверено 2026-08-27 запросами с этой машины):
  - Cloud.ru — `https://foundation-models.api.cloud.ru/v1`, модель по умолчанию `ai-sage/GigaChat3-10B-A1.8B`, эндпоинт `/models` открыт без ключа;
  - Mistral — `https://api.mistral.ai/v1`, модель по умолчанию `ministral-3-3b-2512`.

## Файловая структура

| Файл | Ответственность |
|---|---|
| `app/ai/__init__.py` | Докстрока пакета |
| `app/ai/crypto.py` | Шифрование/расшифровка ключей, версия ключа шифрования |
| `app/ai/providers.py` | Справочник провайдеров: адрес, модель по умолчанию, инструкция |
| `app/ai/models.py` | ORM `AiCredential` |
| `app/ai/schemas.py` | Pydantic-схемы запроса и ответа |
| `app/ai/service.py` | CRUD учётки, без HTTP |
| `app/ai/client.py` | HTTP к провайдеру: проверка ключа |
| `app/ai/router.py` | REST `/api/ai/credential` |
| `alembic/versions/0055_ai_credentials.py` | Таблица `ai_credentials` |
| `app/templates/app/settings.html` | Вкладка «ИИ-помощник» |
| `tests/test_ai_credentials.py` | Тесты всего этапа |

---

### Task 1: Шифрование ключей

**Files:**
- Create: `app/ai/__init__.py`, `app/ai/crypto.py`
- Test: `tests/test_ai_credentials.py`
- Modify: `pyproject.toml` (ruff per-file-ignores)

**Interfaces:**
- Consumes: `app.config.get_settings().app_secret_key`
- Produces:
  - `KEY_VERSION: int = 1`
  - `encrypt_api_key(plain: str) -> str`
  - `decrypt_api_key(ciphertext: str, version: int = KEY_VERSION) -> str`
  - `key_last4(plain: str) -> str`
  - `class AiKeyError(Exception)` — расшифровать не удалось

- [ ] **Step 1: Написать падающий тест**

Создать `tests/test_ai_credentials.py`:

```python
"""Тесты этапа 1 ИИ-помощника: шифрование ключей, справочник, CRUD, API."""

from __future__ import annotations

import pytest

from app.ai.crypto import KEY_VERSION, AiKeyError, decrypt_api_key, encrypt_api_key, key_last4


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
```

- [ ] **Step 2: Убедиться, что тест падает**

Run: `uv run python -m pytest tests/test_ai_credentials.py -q --noconftest`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ai'`

- [ ] **Step 3: Написать реализацию**

`app/ai/__init__.py`:

```python
"""ИИ-помощник Doday: подключение ключа провайдера и чат с моделью."""
```

`app/ai/crypto.py`:

```python
"""Шифрование ключей LLM-провайдеров.

Ключ шифрования выводится из APP_SECRET_KEY через PBKDF2 — детерминированно,
поэтому переживает перезапуск процесса (деплой рестартует сервис на каждый
пуш). Соль своя, не общая с Lessio: у каждого назначения свой ключ, чтобы
компрометация одного не раскрывала другое.

KEY_VERSION хранится рядом с шифротекстом. Когда понадобится сменить схему
(другая соль, другой алгоритм), добавляется ветка в _fernet_for_version, а
старые записи продолжают читаться.
"""

from __future__ import annotations

import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import get_settings

KEY_VERSION = 1

_SALT_V1 = b"doday-ai-provider-key-v1"


class AiKeyError(Exception):
    """Ключ не удалось расшифровать: испорчен, чужой или неизвестной версии."""


def _fernet_for_version(version: int) -> Fernet:
    if version != KEY_VERSION:
        raise AiKeyError(f"неизвестная версия ключа шифрования: {version}")
    secret = (get_settings().app_secret_key or "doday-dev-fallback").encode("utf-8")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT_V1,
        iterations=100_000,
    )
    return Fernet(base64.urlsafe_b64encode(kdf.derive(secret)))


def encrypt_api_key(plain: str) -> str:
    """Зашифровать ключ провайдера для хранения в БД."""
    return _fernet_for_version(KEY_VERSION).encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_api_key(ciphertext: str, version: int = KEY_VERSION) -> str:
    """Расшифровать ключ. AiKeyError, если текст испорчен или версия чужая."""
    try:
        return _fernet_for_version(version).decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise AiKeyError("не удалось расшифровать ключ") from exc


def key_last4(plain: str) -> str:
    """Хвост ключа для показа в интерфейсе вместо самого ключа."""
    return plain[-4:] if len(plain) > 4 else plain
```

- [ ] **Step 4: Разрешить кириллицу в ruff**

В `pyproject.toml`, в блок `[tool.ruff.lint.per-file-ignores]` рядом со строками про `app/blog/*` добавить:

```toml
"app/ai/*" = ["RUF001", "RUF002", "RUF003"]                       # Russian docstrings/messages
"tests/test_ai_credentials.py" = ["RUF001", "RUF002", "RUF003"]
```

- [ ] **Step 5: Убедиться, что тесты проходят**

Run: `uv run python -m pytest tests/test_ai_credentials.py -q --noconftest`
Expected: PASS, 6 тестов

- [ ] **Step 6: Проверки и коммит**

```bash
uv run python -m ruff check app/ai tests/test_ai_credentials.py
uv run python -m ruff format --check app/ai tests/test_ai_credentials.py
uv run python -m mypy --strict app/ai
git add app/ai tests/test_ai_credentials.py pyproject.toml
git commit --no-verify -m "feat(ai): шифрование ключей LLM-провайдеров

Fernet с ключом из APP_SECRET_KEY через PBKDF2, своя соль (не общая с
Lessio), поле версии для будущей ротации. Проверки прогнаны руками."
```

---

### Task 2: Справочник провайдеров

**Files:**
- Create: `app/ai/providers.py`
- Test: `tests/test_ai_credentials.py` (дописать)

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Provider` с полями `key: str`, `title: str`, `base_url: str`, `default_model: str`, `signup_url: str`, `hint: str`
  - `PROVIDERS: tuple[Provider, ...]`
  - `PROVIDER_BY_KEY: dict[str, Provider]`
  - `get_provider(key: str) -> Provider | None`
  - `CUSTOM_KEY: str = "custom"`

- [ ] **Step 1: Написать падающий тест**

Дописать в `tests/test_ai_credentials.py`:

```python
from app.ai.providers import CUSTOM_KEY, PROVIDER_BY_KEY, PROVIDERS, get_provider


def test_providers_have_required_fields() -> None:
    assert len(PROVIDERS) >= 3
    for p in PROVIDERS:
        assert p.key and p.title and p.hint
        if p.key != CUSTOM_KEY:
            assert p.base_url.startswith("https://")
            assert p.default_model


def test_provider_lookup() -> None:
    assert get_provider("cloudru") is not None
    assert get_provider("cloudru").base_url == "https://foundation-models.api.cloud.ru/v1"
    assert get_provider("нет-такого") is None
    assert set(PROVIDER_BY_KEY) == {p.key for p in PROVIDERS}


def test_custom_provider_has_no_fixed_url() -> None:
    custom = get_provider(CUSTOM_KEY)
    assert custom is not None
    assert custom.base_url == ""
```

- [ ] **Step 2: Убедиться, что тест падает**

Run: `uv run python -m pytest tests/test_ai_credentials.py -q --noconftest`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ai.providers'`

- [ ] **Step 3: Написать реализацию**

`app/ai/providers.py`:

```python
"""Справочник LLM-провайдеров.

Все перечисленные говорят по OpenAI-совместимому протоколу, поэтому код
общения один, различаются только адрес и имя модели. Адреса и модели
проверены запросами 2026-08-27.

Gemini сознательно отсутствует: его условия запрещают использование в
сервисах, направленных на аудиторию младше 18 лет, а Doday — сервис для
школьников. Технически ключ Gemini можно ввести через «custom», но
инструкцию под него мы не даём.
"""

from __future__ import annotations

from dataclasses import dataclass

CUSTOM_KEY = "custom"


@dataclass(frozen=True)
class Provider:
    key: str
    title: str
    base_url: str
    default_model: str
    signup_url: str
    hint: str


PROVIDERS: tuple[Provider, ...] = (
    Provider(
        key="cloudru",
        title="Cloud.ru",
        base_url="https://foundation-models.api.cloud.ru/v1",
        default_model="ai-sage/GigaChat3-10B-A1.8B",
        signup_url="https://cloud.ru/products/evolution-foundation-models",
        hint=(
            "Российские серверы, оплата картой от 100 ₽. Зарегистрируйся, "
            "создай сервисный аккаунт и выпусти API-ключ."
        ),
    ),
    Provider(
        key="mistral",
        title="Mistral",
        base_url="https://api.mistral.ai/v1",
        default_model="ministral-3-3b-2512",
        signup_url="https://console.mistral.ai/",
        hint="Зарегистрируйся и создай ключ в разделе API Keys.",
    ),
    Provider(
        key=CUSTOM_KEY,
        title="Другой (OpenAI-совместимый)",
        base_url="",
        default_model="",
        signup_url="",
        hint="Укажи адрес API и название модели вручную.",
    ),
)

PROVIDER_BY_KEY: dict[str, Provider] = {p.key: p for p in PROVIDERS}


def get_provider(key: str) -> Provider | None:
    return PROVIDER_BY_KEY.get(key)
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `uv run python -m pytest tests/test_ai_credentials.py -q --noconftest`
Expected: PASS, 9 тестов

- [ ] **Step 5: Проверки и коммит**

```bash
uv run python -m ruff check app/ai tests/test_ai_credentials.py
uv run python -m ruff format --check app/ai tests/test_ai_credentials.py
uv run python -m mypy --strict app/ai
git add app/ai/providers.py tests/test_ai_credentials.py
git commit --no-verify -m "feat(ai): справочник LLM-провайдеров

Cloud.ru, Mistral и произвольный OpenAI-совместимый адрес. Gemini не
включён: его условия запрещают сервисы для аудитории младше 18 лет.
Проверки прогнаны руками."
```

---

### Task 3: Модель и миграция

**Files:**
- Create: `app/ai/models.py`, `alembic/versions/0055_ai_credentials.py`
- Modify: `tests/conftest.py` (импорт модели, чтобы `create_all` увидел таблицу)

**Interfaces:**
- Produces: `class AiCredential(Base)` с полями `id`, `user_id`, `provider`, `base_url`, `model`, `key_ciphertext`, `key_version`, `key_last4`, `created_at`, `updated_at`

- [ ] **Step 1: Написать модель**

`app/ai/models.py`:

```python
"""ORM ключей LLM-провайдеров. Один ключ на пользователя."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AiCredential(Base):
    """Ключ доступа пользователя к LLM-провайдеру.

    Сам ключ лежит только в зашифрованном виде (app/ai/crypto.py). В
    интерфейс отдаётся key_last4, по которому владелец узнаёт свой ключ,
    но который бесполезен для постороннего.
    """

    __tablename__ = "ai_credentials"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    key_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    key_last4: Mapped[str] = mapped_column(String(8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
```

- [ ] **Step 2: Написать миграцию**

`alembic/versions/0055_ai_credentials.py`:

```python
"""ai_credentials — ключи LLM-провайдеров пользователей

Один ключ на пользователя, сам ключ хранится зашифрованным (Fernet),
рядом лежит версия схемы шифрования для будущей ротации.

Revision ID: 0055
Revises: 0054
"""

import sqlalchemy as sa
from alembic import op

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.String(length=255), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("key_ciphertext", sa.Text(), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("key_last4", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_ai_credentials_user"),
    )
    op.create_index("ix_ai_credentials_user_id", "ai_credentials", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_credentials_user_id", table_name="ai_credentials")
    op.drop_table("ai_credentials")
```

- [ ] **Step 3: Зарегистрировать модель в conftest**

В `tests/conftest.py` найти блок импортов моделей (строки 20-43) и добавить рядом с остальными:

```python
import app.ai.models  # noqa: F401
```

- [ ] **Step 4: Применить миграцию и проверить обратимость**

```bash
uv run python -m alembic upgrade head
uv run python -m alembic downgrade -1
uv run python -m alembic upgrade head
```
Expected: все три команды без ошибок; таблица `ai_credentials` существует после последней.

- [ ] **Step 5: Проверки и коммит**

```bash
uv run python -m ruff check app/ai alembic/versions/0055_ai_credentials.py
uv run python -m ruff format --check app/ai alembic/versions/0055_ai_credentials.py
uv run python -m mypy --strict app/ai
git add app/ai/models.py alembic/versions/0055_ai_credentials.py tests/conftest.py
git commit --no-verify -m "feat(ai): таблица ai_credentials

Один ключ на пользователя, шифротекст + версия схемы шифрования + хвост
ключа для интерфейса. Обратимость миграции проверена. Проверки прогнаны
руками."
```

---

### Task 4: Сервисный слой

**Files:**
- Create: `app/ai/service.py`
- Test: `tests/test_ai_credentials.py` (дописать)

**Interfaces:**
- Consumes: `AiCredential`, `encrypt_api_key`, `key_last4`, `decrypt_api_key`, `get_provider`, `CUSTOM_KEY`
- Produces:
  - `async def get_credential(session, user_id) -> AiCredential | None`
  - `async def upsert_credential(session, user_id, *, provider, api_key, model=None, base_url=None) -> AiCredential`
  - `async def delete_credential(session, user_id) -> bool`
  - `async def resolve_secret(session, user_id) -> tuple[str, str, str] | None` — `(base_url, api_key, model)` для запроса к провайдеру
  - `class UnknownProvider(Exception)`

- [ ] **Step 1: Написать падающий тест**

Дописать в `tests/test_ai_credentials.py`:

```python
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import service as ai_service
from app.ai.service import UnknownProvider


async def test_upsert_and_get_credential(db_session: AsyncSession, user_id_fixture) -> None:
    cred = await ai_service.upsert_credential(
        db_session, user_id_fixture, provider="cloudru", api_key="sk-secret-1234"
    )
    assert cred.provider == "cloudru"
    assert cred.base_url == "https://foundation-models.api.cloud.ru/v1"
    assert cred.model == "ai-sage/GigaChat3-10B-A1.8B"
    assert cred.key_last4 == "1234"
    assert "sk-secret-1234" not in cred.key_ciphertext

    same = await ai_service.get_credential(db_session, user_id_fixture)
    assert same is not None
    assert same.id == cred.id


async def test_upsert_replaces_existing(db_session: AsyncSession, user_id_fixture) -> None:
    first = await ai_service.upsert_credential(
        db_session, user_id_fixture, provider="cloudru", api_key="sk-first-1111"
    )
    second = await ai_service.upsert_credential(
        db_session, user_id_fixture, provider="mistral", api_key="sk-second-2222"
    )
    assert first.id == second.id, "один ключ на пользователя — запись обновляется"
    assert second.provider == "mistral"
    assert second.key_last4 == "2222"


async def test_custom_provider_requires_url_and_model(
    db_session: AsyncSession, user_id_fixture
) -> None:
    cred = await ai_service.upsert_credential(
        db_session,
        user_id_fixture,
        provider="custom",
        api_key="sk-custom-3333",
        base_url="https://example.test/v1",
        model="some-model",
    )
    assert cred.base_url == "https://example.test/v1"
    assert cred.model == "some-model"


async def test_unknown_provider_rejected(db_session: AsyncSession, user_id_fixture) -> None:
    with pytest.raises(UnknownProvider):
        await ai_service.upsert_credential(
            db_session, user_id_fixture, provider="нет-такого", api_key="sk-x"
        )


async def test_resolve_secret_returns_plain_key(
    db_session: AsyncSession, user_id_fixture
) -> None:
    await ai_service.upsert_credential(
        db_session, user_id_fixture, provider="cloudru", api_key="sk-plain-9999"
    )
    resolved = await ai_service.resolve_secret(db_session, user_id_fixture)
    assert resolved is not None
    base_url, api_key, model = resolved
    assert api_key == "sk-plain-9999"
    assert base_url.endswith("/v1")
    assert model


async def test_delete_credential(db_session: AsyncSession, user_id_fixture) -> None:
    await ai_service.upsert_credential(
        db_session, user_id_fixture, provider="cloudru", api_key="sk-del-4444"
    )
    assert await ai_service.delete_credential(db_session, user_id_fixture) is True
    assert await ai_service.get_credential(db_session, user_id_fixture) is None
    assert await ai_service.delete_credential(db_session, user_id_fixture) is False
```

Фикстура `user_id_fixture` — создаёт пользователя и возвращает его id. Дописать в тот же файл:

```python
import pytest_asyncio

from app.auth.models import User


@pytest_asyncio.fixture
async def user_id_fixture(db_session: AsyncSession):
    user = User(id=uuid4(), email=f"ai-{uuid4().hex[:8]}@test.local", password_hash="x")
    db_session.add(user)
    await db_session.commit()
    return user.id
```

- [ ] **Step 2: Убедиться, что тест падает**

Run: `uv run python -m pytest tests/test_ai_credentials.py -q -k credential`
(эти тесты требуют БД — запускать с conftest, то есть без `--noconftest`)
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ai.service'`

- [ ] **Step 3: Написать реализацию**

`app/ai/service.py`:

```python
"""CRUD ключей провайдеров. HTTP-запросов здесь нет — только БД и шифрование."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.crypto import KEY_VERSION, decrypt_api_key, encrypt_api_key, key_last4
from app.ai.models import AiCredential
from app.ai.providers import CUSTOM_KEY, get_provider


class UnknownProvider(Exception):
    """Провайдер отсутствует в справочнике."""


async def get_credential(session: AsyncSession, user_id: UUID) -> AiCredential | None:
    result = await session.execute(
        select(AiCredential).where(AiCredential.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def upsert_credential(
    session: AsyncSession,
    user_id: UUID,
    *,
    provider: str,
    api_key: str,
    model: str | None = None,
    base_url: str | None = None,
) -> AiCredential:
    """Создать или заменить ключ пользователя.

    Для известного провайдера адрес и модель берутся из справочника, если не
    заданы явно. Для «custom» и то и другое обязательно.
    """
    known = get_provider(provider)
    if known is None:
        raise UnknownProvider(f"неизвестный провайдер: {provider}")

    resolved_url = (base_url or known.base_url).strip()
    resolved_model = (model or known.default_model).strip()
    if provider == CUSTOM_KEY and (not resolved_url or not resolved_model):
        raise UnknownProvider("для своего провайдера нужны адрес API и название модели")
    if not resolved_url.startswith("https://"):
        raise UnknownProvider("адрес API должен начинаться с https://")

    existing = await get_credential(session, user_id)
    if existing is None:
        existing = AiCredential(user_id=user_id)
        session.add(existing)

    existing.provider = provider
    existing.base_url = resolved_url
    existing.model = resolved_model
    existing.key_ciphertext = encrypt_api_key(api_key)
    existing.key_version = KEY_VERSION
    existing.key_last4 = key_last4(api_key)
    await session.commit()
    await session.refresh(existing)
    return existing


async def delete_credential(session: AsyncSession, user_id: UUID) -> bool:
    """Удалить ключ. True, если было что удалять."""
    result = await session.execute(
        delete(AiCredential).where(AiCredential.user_id == user_id)
    )
    await session.commit()
    return bool(result.rowcount)


async def resolve_secret(
    session: AsyncSession, user_id: UUID
) -> tuple[str, str, str] | None:
    """Данные для запроса к провайдеру: (base_url, api_key, model).

    Возвращает расшифрованный ключ — вызывающий обязан не логировать его и
    не отдавать наружу.
    """
    cred = await get_credential(session, user_id)
    if cred is None:
        return None
    return cred.base_url, decrypt_api_key(cred.key_ciphertext, cred.key_version), cred.model
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `uv run python -m pytest tests/test_ai_credentials.py -q`
Expected: PASS, все тесты (включая ранее написанные)

- [ ] **Step 5: Проверки и коммит**

```bash
uv run python -m ruff check app/ai tests/test_ai_credentials.py
uv run python -m ruff format --check app/ai tests/test_ai_credentials.py
uv run python -m mypy --strict app/ai
git add app/ai/service.py tests/test_ai_credentials.py
git commit --no-verify -m "feat(ai): сервисный слой ключей провайдеров

Один ключ на пользователя, upsert заменяет запись; для своего провайдера
адрес и модель обязательны, адрес только https. Проверки прогнаны руками."
```

---

### Task 5: Проверка ключа у провайдера

**Files:**
- Create: `app/ai/client.py`
- Test: `tests/test_ai_credentials.py` (дописать)

**Interfaces:**
- Produces:
  - `async def verify_key(*, base_url: str, api_key: str, model: str, timeout_s: float = 20.0) -> None` — успех = вернулась без исключения
  - `class AiProviderError(Exception)` с полем `user_message: str`

- [ ] **Step 1: Написать падающий тест**

Дописать в `tests/test_ai_credentials.py`:

```python
import httpx

from app.ai.client import AiProviderError, verify_key


async def test_verify_key_success(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_post(self, url, **kwargs):  # noqa: ANN001, ANN202
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    await verify_key(base_url="https://x.test/v1", api_key="sk-1", model="m")


@pytest.mark.parametrize(
    ("status", "fragment"),
    [(401, "не принят"), (403, "не принят"), (402, "средства"), (429, "часто"), (500, "не отвечает")],
)
async def test_verify_key_maps_errors(
    monkeypatch: pytest.MonkeyPatch, status: int, fragment: str
) -> None:
    async def fake_post(self, url, **kwargs):  # noqa: ANN001, ANN202
        return httpx.Response(status, json={"error": "boom"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(AiProviderError) as exc:
        await verify_key(base_url="https://x.test/v1", api_key="sk-1", model="m")
    assert fragment in exc.value.user_message


async def test_verify_key_never_leaks_key(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_post(self, url, **kwargs):  # noqa: ANN001, ANN202
        return httpx.Response(401, text="denied", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(AiProviderError) as exc:
        await verify_key(base_url="https://x.test/v1", api_key="sk-super-secret", model="m")
    assert "sk-super-secret" not in exc.value.user_message
    assert "sk-super-secret" not in str(exc.value)


async def test_verify_key_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_post(self, url, **kwargs):  # noqa: ANN001, ANN202
        raise httpx.ConnectTimeout("timeout")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(AiProviderError) as exc:
        await verify_key(base_url="https://x.test/v1", api_key="sk-1", model="m")
    assert "не отвечает" in exc.value.user_message
```

- [ ] **Step 2: Убедиться, что тест падает**

Run: `uv run python -m pytest tests/test_ai_credentials.py -q -k verify`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ai.client'`

- [ ] **Step 3: Написать реализацию**

`app/ai/client.py`:

```python
"""HTTP-общение с LLM-провайдером по OpenAI-совместимому протоколу.

Ключ пользователя нигде не логируется и не попадает в текст ошибки: сообщения
для пользователя собираются из фиксированных фраз, а не из ответа провайдера.
"""

from __future__ import annotations

import httpx
import structlog

logger = structlog.get_logger(__name__)

# Один токен — нам нужно лишь убедиться, что ключ принят и модель существует.
_VERIFY_MAX_TOKENS = 1


class AiProviderError(Exception):
    """Провайдер отказал. user_message безопасен для показа пользователю."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


def _message_for_status(status: int) -> str:
    if status in (401, 403):
        return "Ключ не принят провайдером — проверь, что скопировал его целиком."
    if status == 402:
        return "На счету провайдера закончились средства."
    if status == 404:
        return "Провайдер не знает такой модели — проверь название."
    if status == 429:
        return "Слишком часто: провайдер ограничил частоту запросов. Попробуй через минуту."
    return "Провайдер не отвечает. Попробуй позже."


async def verify_key(
    *, base_url: str, api_key: str, model: str, timeout_s: float = 20.0
) -> None:
    """Сделать минимальный запрос и убедиться, что ключ рабочий.

    Возвращается молча при успехе, иначе AiProviderError.
    """
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "max_tokens": _VERIFY_MAX_TOKENS,
        "messages": [{"role": "user", "content": "ping"}],
    }
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.post(
                url, json=payload, headers={"Authorization": f"Bearer {api_key}"}
            )
    except httpx.HTTPError as exc:
        logger.warning("ai_verify_transport_error", error=type(exc).__name__)
        raise AiProviderError("Провайдер не отвечает. Попробуй позже.") from exc

    if response.status_code >= 400:
        logger.info("ai_verify_rejected", status=response.status_code)
        raise AiProviderError(_message_for_status(response.status_code))
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `uv run python -m pytest tests/test_ai_credentials.py -q`
Expected: PASS

- [ ] **Step 5: Проверки и коммит**

```bash
uv run python -m ruff check app/ai tests/test_ai_credentials.py
uv run python -m ruff format --check app/ai tests/test_ai_credentials.py
uv run python -m mypy --strict app/ai
git add app/ai/client.py tests/test_ai_credentials.py
git commit --no-verify -m "feat(ai): проверка ключа у провайдера

Минимальный запрос на 1 токен, понятные сообщения по кодам ответа, ключ
не попадает ни в лог, ни в текст ошибки. Проверки прогнаны руками."
```

---

### Task 6: REST API

**Files:**
- Create: `app/ai/schemas.py`, `app/ai/router.py`
- Modify: `app/main.py` (импорт и `include_router`)
- Test: `tests/test_ai_credentials.py` (дописать)

**Interfaces:**
- Consumes: `ai_service`, `verify_key`, `PROVIDERS`
- Produces маршруты:
  - `GET /api/ai/providers` → `list[ProviderOut]`
  - `GET /api/ai/credential` → `CredentialOut | null`
  - `PUT /api/ai/credential` (тело `CredentialIn`) → `CredentialOut`
  - `DELETE /api/ai/credential` → `204`
  - `POST /api/ai/credential/verify` → `{"ok": true}` либо `400` с `detail`

- [ ] **Step 1: Написать падающий тест**

Дописать в `tests/test_ai_credentials.py`:

```python
from httpx import AsyncClient


async def test_providers_endpoint(logged_in_client: AsyncClient) -> None:
    r = await logged_in_client.get("/api/ai/providers")
    assert r.status_code == 200
    keys = {p["key"] for p in r.json()}
    assert {"cloudru", "mistral", "custom"} <= keys
    assert all("hint" in p for p in r.json())


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
        "/api/ai/credential", json={"provider": "нет-такого", "api_key": "sk-1"}
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
        from app.ai.client import AiProviderError

        raise AiProviderError("Ключ не принят провайдером — проверь, что скопировал его целиком.")

    monkeypatch.setattr("app.ai.router.verify_key", fail)
    r = await logged_in_client.post("/api/ai/credential/verify")
    assert r.status_code == 400
    assert "не принят" in r.json()["detail"]
```

- [ ] **Step 2: Убедиться, что тест падает**

Run: `uv run python -m pytest tests/test_ai_credentials.py -q -k "api or providers"`
Expected: FAIL — 404 на `/api/ai/providers`

- [ ] **Step 3: Написать схемы**

`app/ai/schemas.py`:

```python
"""Схемы API ИИ-помощника. Ключ принимаем, но никогда не отдаём."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProviderOut(BaseModel):
    key: str
    title: str
    base_url: str
    default_model: str
    signup_url: str
    hint: str


class CredentialIn(BaseModel):
    provider: str = Field(max_length=32)
    api_key: str = Field(min_length=8, max_length=512)
    model: str | None = Field(default=None, max_length=128)
    base_url: str | None = Field(default=None, max_length=255)


class CredentialOut(BaseModel):
    provider: str
    base_url: str
    model: str
    key_last4: str
```

- [ ] **Step 4: Написать роутер**

`app/ai/router.py`:

```python
"""REST ИИ-помощника: справочник провайдеров и ключ пользователя."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Response, status

from app.ai import service as ai_service
from app.ai.client import AiProviderError, verify_key
from app.ai.providers import PROVIDERS
from app.ai.schemas import CredentialIn, CredentialOut, ProviderOut
from app.ai.service import UnknownProvider
from app.auth.deps import DbSession, RequiredUser

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/providers", response_model=list[ProviderOut])
async def list_providers(user: RequiredUser) -> list[ProviderOut]:
    return [ProviderOut(**asdict(p)) for p in PROVIDERS]


@router.get("/credential", response_model=CredentialOut | None)
async def read_credential(user: RequiredUser, session: DbSession) -> CredentialOut | None:
    cred = await ai_service.get_credential(session, user.id)
    if cred is None:
        return None
    return CredentialOut(
        provider=cred.provider,
        base_url=cred.base_url,
        model=cred.model,
        key_last4=cred.key_last4,
    )


@router.put("/credential", response_model=CredentialOut)
async def save_credential(
    payload: CredentialIn, user: RequiredUser, session: DbSession
) -> CredentialOut:
    try:
        cred = await ai_service.upsert_credential(
            session,
            user.id,
            provider=payload.provider,
            api_key=payload.api_key,
            model=payload.model,
            base_url=payload.base_url,
        )
    except UnknownProvider as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return CredentialOut(
        provider=cred.provider,
        base_url=cred.base_url,
        model=cred.model,
        key_last4=cred.key_last4,
    )


@router.delete("/credential", status_code=status.HTTP_204_NO_CONTENT)
async def remove_credential(user: RequiredUser, session: DbSession) -> Response:
    await ai_service.delete_credential(session, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/credential/verify")
async def check_credential(user: RequiredUser, session: DbSession) -> dict[str, bool]:
    resolved = await ai_service.resolve_secret(session, user.id)
    if resolved is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ключ не подключён")
    base_url, api_key, model = resolved
    try:
        await verify_key(base_url=base_url, api_key=api_key, model=model)
    except AiProviderError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.user_message) from exc
    return {"ok": True}
```

- [ ] **Step 5: Подключить роутер**

В `app/main.py` рядом с другими импортами роутеров добавить:

```python
from app.ai.router import router as ai_router
```

и рядом с `app.include_router(blog_router)`:

```python
app.include_router(ai_router)
```

- [ ] **Step 6: Убедиться, что тесты проходят**

Run: `uv run python -m pytest tests/test_ai_credentials.py -q`
Expected: PASS

- [ ] **Step 7: Проверки и коммит**

```bash
uv run python -m ruff check app tests/test_ai_credentials.py
uv run python -m ruff format --check app tests/test_ai_credentials.py
uv run python -m mypy --strict app/ai
git add app/ai tests/test_ai_credentials.py app/main.py
git commit --no-verify -m "feat(ai): API ключа провайдера

GET providers, CRUD ключа и проверка его у провайдера. Ключ принимается,
но не возвращается ни в одном ответе. Проверки прогнаны руками."
```

---

### Task 7: Экран настроек

**Files:**
- Modify: `app/templates/app/settings.html`
- Test: `tests/test_ai_credentials.py` (дописать)

**Interfaces:**
- Consumes: `/api/ai/providers`, `/api/ai/credential`, `/api/ai/credential/verify`

- [ ] **Step 1: Написать падающий тест**

Дописать в `tests/test_ai_credentials.py`:

```python
async def test_settings_page_has_ai_section(logged_in_client: AsyncClient) -> None:
    html = (await logged_in_client.get("/app/settings")).text
    assert "ИИ-помощник" in html
    assert "/api/ai/providers" in html
    assert "/api/ai/credential" in html
    # ключ не должен рендериться на страницу ни при каких условиях
    assert "key_ciphertext" not in html
```

- [ ] **Step 2: Убедиться, что тест падает**

Run: `uv run python -m pytest tests/test_ai_credentials.py -q -k settings_page`
Expected: FAIL — «ИИ-помощник» не найден

- [ ] **Step 3: Добавить секцию в настройки**

В `app/templates/app/settings.html` рядом с блоком школьных интеграций (около строки 660, где `x-data` со списком `integrations`) добавить новую карточку. Разметка в стиле проекта — `.card`, `.btn-primary`, `.btn-ghost`, `.input`:

```html
<div class="card p-6" x-data="aiCredential()" x-init="load()">
  <h2 class="text-lg font-semibold mb-1">ИИ-помощник</h2>
  <p class="text-sm text-[var(--text-muted)] mb-4">
    Подключи свой ключ — и сможешь спрашивать модель прямо в задачах.
    Ключ хранится в зашифрованном виде и никому не показывается.
  </p>

  <template x-if="current">
    <div class="flex items-center gap-3 mb-4 text-sm">
      <span class="px-2 py-1 rounded bg-[var(--surface-2)]" x-text="current.provider"></span>
      <span class="text-[var(--text-muted)]">ключ ····<span x-text="current.key_last4"></span></span>
      <button class="btn-ghost !py-1 !px-3 text-sm" @click="verify()">Проверить</button>
      <button class="btn-ghost !py-1 !px-3 text-sm" @click="remove()">Удалить</button>
    </div>
  </template>

  <div class="space-y-3">
    <select class="input w-full" x-model="form.provider">
      <template x-for="p in providers" :key="p.key">
        <option :value="p.key" x-text="p.title"></option>
      </template>
    </select>

    <p class="text-xs text-[var(--text-muted)]" x-text="hint()"></p>

    <template x-if="form.provider === 'custom'">
      <div class="space-y-3">
        <input class="input w-full" placeholder="https://адрес-api/v1" x-model="form.base_url">
        <input class="input w-full" placeholder="название модели" x-model="form.model">
      </div>
    </template>

    <input class="input w-full" type="password" placeholder="Ключ провайдера" x-model="form.api_key">
    <button class="btn-primary" @click="save()" :disabled="busy">Сохранить ключ</button>
    <p class="text-sm" :class="ok ? 'text-emerald-400' : 'text-rose-400'" x-text="message"></p>
  </div>
</div>

<script>
  function aiCredential() {
    return {
      providers: [], current: null, busy: false, ok: true, message: '',
      form: { provider: 'cloudru', api_key: '', model: '', base_url: '' },
      async load() {
        const [pr, cr] = await Promise.all([
          fetch('/api/ai/providers', {credentials: 'include'}),
          fetch('/api/ai/credential', {credentials: 'include'}),
        ]);
        if (pr.ok) this.providers = await pr.json();
        if (cr.ok) this.current = await cr.json();
        if (this.current) this.form.provider = this.current.provider;
      },
      hint() {
        const p = this.providers.find(x => x.key === this.form.provider);
        return p ? p.hint : '';
      },
      async save() {
        this.busy = true; this.message = '';
        const r = await fetch('/api/ai/credential', {
          method: 'PUT', credentials: 'include',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(this.form),
        });
        this.busy = false;
        this.ok = r.ok;
        if (r.ok) {
          this.current = await r.json();
          this.form.api_key = '';
          this.message = 'Ключ сохранён';
        } else {
          this.message = (await r.json()).detail || 'Не удалось сохранить';
        }
      },
      async verify() {
        this.busy = true; this.message = 'Проверяю…';
        const r = await fetch('/api/ai/credential/verify', {method: 'POST', credentials: 'include'});
        this.busy = false;
        this.ok = r.ok;
        this.message = r.ok ? 'Ключ рабочий' : (await r.json()).detail;
      },
      async remove() {
        await fetch('/api/ai/credential', {method: 'DELETE', credentials: 'include'});
        this.current = null; this.message = 'Ключ удалён'; this.ok = true;
      },
    };
  }
</script>
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `uv run python -m pytest tests/test_ai_credentials.py -q`
Expected: PASS

- [ ] **Step 5: Проверить линтер шаблонов**

Run: `uv run python scripts/lint_templates.py`
Expected: `0 error(s)`. Если ругается на длинный inline-скрипт (`long-inline-script` — предупреждение, не ошибка), оставить как есть.

- [ ] **Step 6: Проверки и коммит**

```bash
uv run python -m ruff check app tests/test_ai_credentials.py
uv run python -m ruff format --check app tests/test_ai_credentials.py
uv run python -m mypy --strict app/ai
uv run python scripts/lint_templates.py
git add app/templates/app/settings.html tests/test_ai_credentials.py
git commit --no-verify -m "feat(ai): экран подключения ключа в настройках

Выбор провайдера с подсказкой, поля для своего адреса и модели, кнопки
проверки и удаления. Ключ вводится, но обратно не показывается — только
последние 4 символа. Проверки прогнаны руками."
```

---

## Проверка этапа целиком

- [ ] `uv run python -m pytest tests/test_ai_credentials.py -q` — все тесты зелёные
- [ ] `uv run python -m pytest -q` — весь набор не сломан
- [ ] `uv run python -m mypy --strict app/ scripts/` — чисто
- [ ] `uv run python -m ruff check . && uv run python -m ruff format --check .` — чисто
- [ ] Ручная проверка на локальном сервере: открыть `/app/settings`, увидеть блок «ИИ-помощник», сохранить произвольный ключ, нажать «Проверить» (ожидаемо получить «Ключ не принят провайдером» — ключ фиктивный), удалить.
- [ ] `git log --oneline` — семь коммитов этапа на месте
