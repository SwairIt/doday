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
