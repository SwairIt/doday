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
