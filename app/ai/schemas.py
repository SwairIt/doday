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
    price: str
    key_looks_like: str
    steps: list[str]


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


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


class ChatStateOut(BaseModel):
    """Всё, что нужно странице чата при открытии."""

    terms_accepted: bool
    has_credential: bool
    provider: str
    model: str
    used_today: int
    daily_limit: int
    messages: list[MessageOut]
    templates: list[dict[str, str]]


class ModelIn(BaseModel):
    """Смена модели без повторного ввода ключа."""

    model: str = Field(min_length=1, max_length=128)


class AskIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    # Задача, к которой привязана ветка переписки.
    task_id: str | None = None
    # Задачи, приложенные к вопросу как контекст: «что делать сначала»,
    # «сколько это займёт». Историю не разделяют, только уходят модели.
    task_ids: list[str] = Field(default_factory=list, max_length=5)
