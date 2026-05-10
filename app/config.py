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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
