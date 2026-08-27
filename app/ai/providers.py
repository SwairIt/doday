"""Справочник LLM-провайдеров.

Все перечисленные говорят по OpenAI-совместимому протоколу, поэтому код
общения один: различаются только адрес, имя модели и то, где взять ключ.

В списке только российские провайдеры, и это решение не техническое, а
юридическое. Запрос к зарубежному провайдеру — это трансграничная передача
персональных данных: текст вопроса пользователя уходит за пределы РФ. Она
требует отдельного уведомления в Роскомнадзор (ч. 3 ст. 12 152-ФЗ), а у нас
аудитория несовершеннолетняя, то есть внимание регулятора выше среднего.
Пока это не оформлено — зарубежных провайдеров в списке нет.

Технически они работали по-разному: Groq, OpenRouter, Cerebras и Nebius
вообще отвечают из России 403 «access denied», а Google с рабочим ключом —
«User location is not supported». Mistral, DeepSeek, Together и io.net
отвечали нормально, но это ничего не меняет: см. выше про трансграничную
передачу.

Формат ключа мы нигде не проверяем и не должны: он разный и меняется. У
Google AI Studio сейчас выдаются ключи вида AQ.Ab…, раньше были AIza…; у
Yandex Cloud — AQVN…; у большинства остальных — sk-…. Принят ключ или нет,
говорит сам провайдер.

Урок на будущее: проверка адреса заведомо неверным ключом не доказывает,
что провайдер работает. Google на невалидный ключ отвечает про ключ и
только с рабочим — про страну.
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
    # Во сколько обойдётся: показывается плашкой рядом с названием.
    price: str
    # Как выглядит ключ — чтобы человек понял, то ли он скопировал.
    key_looks_like: str
    # Пошаговая инструкция. Показывается прямо в настройках: жалоба
    # «нифига непонятно как подключать» была именно про её отсутствие.
    steps: tuple[str, ...]


PROVIDERS: tuple[Provider, ...] = (
    Provider(
        key="cloudru",
        title="Cloud.ru",
        base_url="https://foundation-models.api.cloud.ru/v1",
        default_model="ai-sage/GigaChat3-10B-A1.8B",
        signup_url="https://cloud.ru/products/evolution-foundation-models",
        hint="Российские серверы и оплата рублями с карты. Модели GigaChat и Qwen.",
        price="по карте, от 100 ₽",
        key_looks_like="длинная строка из букв и цифр",
        steps=(
            "Зарегистрируйся на cloud.ru и подтверди почту.",
            "В консоли открой Evolution Foundation Models и включи сервис.",
            "Создай сервисный аккаунт, затем выпусти для него API-ключ.",
            "Скопируй ключ и вставь в поле ниже.",
        ),
    ),
    Provider(
        key="yandex",
        title="Yandex Foundation Models",
        base_url="https://llm.api.cloud.yandex.net/v1",
        default_model="gpt://ID-КАТАЛОГА/yandexgpt-lite/latest",
        signup_url="https://console.yandex.cloud/",
        hint=(
            "Российские серверы. Ключ начинается на AQVN. Название модели "
            "содержит ID каталога — его надо подставить самому."
        ),
        price="по карте, рубли",
        key_looks_like="AQVN…",
        steps=(
            "В консоли console.yandex.cloud создай сервисный аккаунт и дай ему "
            "роль ai.languageModels.user.",
            "Нажми «Создать новый ключ» → «API-ключ». Скопируй его, он начинается на AQVN.",
            "Скопируй ID каталога — он в адресной строке консоли и выглядит как b1g….",
            "В поле «Модель» замени ID-КАТАЛОГА на свой: gpt://b1g…/yandexgpt-lite/latest",
        ),
    ),
    Provider(
        key="proxyapi",
        title="ProxyAPI",
        base_url="https://api.proxyapi.ru/openai/v1",
        default_model="gpt-4o-mini",
        signup_url="https://proxyapi.ru/",
        hint="Российский посредник: даёт доступ к моделям OpenAI за рубли.",
        price="по карте, рубли",
        key_looks_like="sk-…",
        steps=(
            "Зарегистрируйся на proxyapi.ru.",
            "Пополни баланс картой.",
            "В личном кабинете скопируй API-ключ.",
            "Вставь его в поле ниже.",
        ),
    ),
    Provider(
        key=CUSTOM_KEY,
        title="Другой (OpenAI-совместимый)",
        base_url="",
        default_model="",
        signup_url="",
        hint=(
            "Подойдёт любой провайдер, который умеет /chat/completions. "
            "Выбирай российского: запрос к зарубежному — это передача данных "
            "за границу, и отвечать за неё будешь ты сам."
        ),
        price="как у выбранного провайдера",
        key_looks_like="как выдал провайдер",
        steps=(
            "Возьми у провайдера адрес API — тот, что заканчивается на /v1.",
            "Узнай точное название модели: провайдеры пишут его в документации.",
            "Заполни оба поля и вставь ключ.",
            "Адрес должен начинаться с https:// и вести в интернет, а не во внутреннюю сеть.",
        ),
    ),
)

PROVIDER_BY_KEY: dict[str, Provider] = {p.key: p for p in PROVIDERS}


def get_provider(key: str) -> Provider | None:
    return PROVIDER_BY_KEY.get(key)
