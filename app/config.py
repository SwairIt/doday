"""Application settings loaded from .env via pydantic-settings v2."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_env: str = "dev"
    app_secret_key: str = Field(min_length=32)
    app_base_url: str = "http://localhost:8000"
    log_level: str = "INFO"

    database_url: str
    test_database_url: str = ""  # tests only; empty in production

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@schooltodo.local"
    smtp_start_tls: bool = False  # set true for real providers like Resend/Brevo on port 587

    # Yandex.Metrika counter ID (числовой — например 12345678).
    # Empty в dev — скрипт не подключается. Задаётся в .env прода.
    ya_metrika_id: str = ""

    # IndexNow API key (16+ hex chars). Должен также быть размещён на
    # https://getdoday.ru/<key>.txt — endpoint в app.main отдаёт его автоматически.
    # Empty → ping no-op. Используется Lessio при создании tutor-профиля.
    indexnow_key: str = ""

    # Google OAuth для Lessio Calendar busy-times sync (опционально).
    # Регистрация: https://console.cloud.google.com/apis/credentials
    # Scopes: https://www.googleapis.com/auth/calendar.readonly
    # Redirect URI в Google Cloud: https://getdoday.ru/lessio/oauth/google/callback
    # Empty → /lessio/app/settings скрывает «Подключить Google Calendar».
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""

    # Secret token for /api/digest/cron-trigger — prod cron passes it in
    # X-Cron-Token header, missing/wrong header → 403. Empty in dev disables
    # the endpoint (returns 503 with a hint to set the env var).
    cron_token: str = ""

    # Secret token for /api/admin/complaints.json — Claude / operator can curl
    # admin data without juggling session cookies. X-Admin-Token header must
    # match. Empty in dev disables (503 with hint).
    admin_token: str = ""

    # Telegram bot — задачи через чат-команды /add /today /done /upcoming.
    # TOKEN получается у @BotFather, USERNAME — bot's @username (без @).
    # Если оба пустые — endpoint /api/profile/telegram-link работает с
    # placeholder URL, бот-воркер не запустится.
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""

    # Когда True — bot worker пропускает hardcoded-IPv4 monkey-patch resolver для
    # api.telegram.org (см. app/telegram/bot.py:_force_ipv4_resolve). Нужно когда
    # hardcoded IP перестал отвечать (Telegram ротирует DC адреса) или сетевой блок
    # бьёт по конкретным IP. Без патча bot использует системный DNS.
    disable_telegram_ipv4_patch: bool = False

    # Когда True — bot worker НЕ запускает @DodayTaskBot Application. Полезно для
    # local-dev запуска ТОЛЬКО Lessio bot — избегаем конкуренции за getUpdates на
    # prod @DodayTaskBot polling (Telegram запрещает два long-poll'а на одном
    # токене). Дефолт — False (Doday запускается как обычно).
    disable_doday_bot: bool = False

    # HTTP/SOCKS5/HTTPS-прокси для всех Telegram API запросов из bot worker.
    # На проде RKN/провайдер блокируют исходящий доступ к api.telegram.org —
    # даже с обновлёнными IP TLS-handshake таймаутит. python-telegram-bot
    # async-арх не работает с monkey-patch'ингом DNS (uvloop игнорирует
    # BaseEventLoop.getaddrinfo override). Решение — прокси.
    #
    # Поддерживаются:
    # - HTTP-proxy: http://USER:PASS@HOST:PORT
    # - SOCKS5: socks5://USER:PASS@HOST:PORT (нужен `uv add httpx[socks]`)
    #
    # Если пусто — bot ходит напрямую (на dev обычно работает, на проде —
    # таймаутит). Когда непусто — bot подключается через прокси, патч resolver'а
    # не нужен (прокси сам резолвит).
    telegram_proxy_url: str = ""

    # Lessio bot — отдельный @LessioBot для brand-separation от @DodayTaskBot.
    # Worker процесс один и тот же (app/telegram/bot.py main()), но Application'ов
    # два — крутятся в одном asyncio loop через gather. Если LESSIO_BOT_TOKEN пуст
    # (validation phase до 2026-06-01 готов к этапу или просто Lessio выключен) —
    # Lessio Application не создаётся, Doday bot работает как раньше. Stars-invoice
    # для tutor_pro_* продуктов выписываются на этом боте, потому что Stars-выручка
    # привязана к боту-источнику createInvoiceLink.
    lessio_bot_token: str = ""
    lessio_bot_username: str = ""

    # Beta-flag: если True — все юзеры получают Pro-фичи независимо от tier.
    # Раннее grandfather-обещание: «всё бесплатно сейчас, ранним юзерам Pro
    # останется навсегда когда введём оплату». Снимается в один клик в .env
    # когда придёт время монетизации (для НОВЫХ юзеров; ранних — отдельно).
    beta_free_for_all: bool = False

    # Sentry error-tracking. Если DSN пустой — init пропускается, ничего не
    # ломается. environment различает prod/dev в дашборде. release — pin'ит
    # версию приложения чтобы видеть когда регрессия появилась.
    sentry_dsn: str = ""
    sentry_environment: str = "dev"
    sentry_traces_sample_rate: float = 0.1
    sentry_release: str = "0.1.0"

    # Public Telegram-канал для community/анонсов. Если пустой — ссылка в
    # футере не показывается. Формат: «https://t.me/dodayru» или просто
    # «@dodayru» (template нормализует).
    telegram_channel_url: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
