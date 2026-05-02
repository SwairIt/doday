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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
