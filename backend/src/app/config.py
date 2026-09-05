from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    local_model_base_url: str = "http://localhost:11434"
    local_model_name: str = "llama3.1:8b"

    external_model_base_url: str = "https://api.openai.com/v1"
    external_model_api_key: str = "changeme"
    external_model_name: str = "gpt-4o-mini"

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    postgres_dsn: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/assistente"

    google_calendar_credentials_path: str = "./secrets/google_calendar_credentials.json"
    google_calendar_calendar_id: str = "primary"

    mcp_b2b_host: str = "0.0.0.0"
    mcp_b2b_port: int = 8100


@lru_cache
def get_settings() -> Settings:
    return Settings()
