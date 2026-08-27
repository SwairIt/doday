"""Справочник LLM-провайдеров.

Все перечисленные говорят по OpenAI-совместимому протоколу, поэтому код
общения один: различаются только адрес, имя модели и то, где взять ключ.

Список нарочно короткий и проверенный. Каждый адрес проверен запросом
с российского адреса 2026-08-27: провайдер должен отвечать ошибкой ключа
(400/401), а не блокировкой. Groq, OpenRouter, Cerebras и Nebius на такой
запрос отвечают 403 «access denied» — из России они недоступны, и в списке
им делать нечего: пользователь получил бы ключ, а чат бы не заработал.

Формат ключа мы нигде не проверяем и не должны: он разный и меняется. У
Google AI Studio сейчас выдаются ключи вида AQ.Ab…, раньше были AIza…; у
Yandex Cloud — AQVN…; у большинства остальных — sk-…. Принят ключ или нет,
говорит сам провайдер.

Про Gemini. Его условия требуют, чтобы API пользовался человек 18 лет и
старше, и запрещают строить на нём сервисы для младшей аудитории. У нас
ключ подключает сам пользователь и только после того, как подтвердит
возраст на экране согласия (см. `ai_terms_accepted_at`), — то есть с
Gemini общается он сам и своим ключом, а не Doday за него.
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
        key="gemini",
        title="Google Gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        default_model="gemini-3.6-flash",
        signup_url="https://aistudio.google.com/apikey",
        hint=(
            "Бесплатный ключ выдают сразу, карта не нужна. Нужен аккаунт Google. "
            "Модели у них меняются часто — если ответит «нет такой модели», "
            "поменяй её в шапке чата."
        ),
        price="бесплатно",
        key_looks_like="AQ.Ab… или AIza…",
        steps=(
            "Открой aistudio.google.com/apikey и войди в аккаунт Google.",
            "Нажми «Create API key» — ключ появится сразу, платить ничего не нужно.",
            "Скопируй ключ целиком и вставь в поле ниже — формат бывает разный.",
            "Нажми «Сохранить ключ» — мы проверим его коротким запросом к провайдеру.",
        ),
    ),
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
        key="mistral",
        title="Mistral",
        base_url="https://api.mistral.ai/v1",
        default_model="ministral-3-3b-2512",
        signup_url="https://console.mistral.ai/api-keys",
        hint="Европейский провайдер, есть бесплатный тариф с ограничением частоты.",
        price="есть бесплатный тариф",
        key_looks_like="строка из 32 символов",
        steps=(
            "Зарегистрируйся на console.mistral.ai (нужен телефон для подтверждения).",
            "Открой раздел API Keys и нажми «Create new key».",
            "Скопируй ключ — второй раз его не покажут.",
            "Вставь в поле ниже и сохрани.",
        ),
    ),
    Provider(
        key="deepseek",
        title="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        default_model="deepseek-chat",
        signup_url="https://platform.deepseek.com/api_keys",
        hint="Дёшево даже по сравнению с остальными, отвечает по-русски хорошо.",
        price="по карте, около 1 ₽ за длинный ответ",
        key_looks_like="sk-…",
        steps=(
            "Зарегистрируйся на platform.deepseek.com.",
            "Пополни баланс — минимальная сумма небольшая, её хватит надолго.",
            "Открой API keys и нажми «Create new API key».",
            "Скопируй ключ (начинается на sk-) и вставь в поле ниже.",
        ),
    ),
    Provider(
        key="together",
        title="Together AI",
        base_url="https://api.together.xyz/v1",
        default_model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
        signup_url="https://api.together.ai/settings/api-keys",
        hint="Много открытых моделей. При регистрации дают стартовый баланс.",
        price="стартовый баланс бесплатно",
        key_looks_like="длинная строка из букв и цифр",
        steps=(
            "Зарегистрируйся на together.ai.",
            "Открой Settings → API Keys и скопируй ключ, он создаётся сам.",
            "Вставь ключ в поле ниже.",
            "Если хочешь другую модель — впиши её название в поле «Модель».",
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
        hint="Подойдёт любой провайдер, который умеет /chat/completions.",
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
