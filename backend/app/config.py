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
