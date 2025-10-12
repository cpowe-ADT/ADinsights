from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
  model_config = SettingsConfigDict(env_file=".env", env_prefix="ADINSIGHTS_")

  database_url: str = "postgresql+asyncpg://analytics:analytics@db:5432/adinsights"
  llm_api_url: str = "http://llm:8000/v1/chat/completions"
  llm_api_key: str = "changeme"
  alert_email_recipients: list[str] = ["marketing-ops@example.com"]
  alert_slack_webhook: str | None = None
  refresh_interval_minutes: int = 15


@lru_cache
def get_settings() -> Settings:
  return Settings()
from typing import Any

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    app_name: str = "ADinsights Backend"
    environment: str = Field(default="development", env="ENVIRONMENT")
    database_url: str = Field(default="postgresql+psycopg2://user:password@localhost:5432/adinsights", env="DATABASE_URL")
    secret_key: str = Field(default="changeme", env="SECRET_KEY")
    access_token_expiry_minutes: int = Field(default=60 * 2, env="ACCESS_TOKEN_EXPIRY_MINUTES")
    refresh_token_expiry_days: int = Field(default=30, env="REFRESH_TOKEN_EXPIRY_DAYS")
    meta_client_id: str = Field(default="", env="META_CLIENT_ID")
    meta_client_secret: str = Field(default="", env="META_CLIENT_SECRET")
    google_ads_client_id: str = Field(default="", env="GOOGLE_ADS_CLIENT_ID")
    google_ads_client_secret: str = Field(default="", env="GOOGLE_ADS_CLIENT_SECRET")
    oauth_redirect_base_url: str = Field(default="http://localhost:8000", env="OAUTH_REDIRECT_BASE_URL")

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()  # type: ignore[arg-type]


SettingsType = Settings | Any
