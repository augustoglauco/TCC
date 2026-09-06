from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    local_model_base_url: str = "http://localhost:11434"
    local_model_name: str = "llama3.1:8b"

    external_model_base_url: str = "https://openrouter.ai/api/v1"
    external_model_api_key: str = "changeme"
    # MVP: sem default fixado — decidir o modelo (formato "provider/model" do
    # OpenRouter, ex.: "anthropic/claude-3.5-haiku") na hora do benchmark real
    # (ver docs/superpowers/specs/2026-09-05-roteador-basico-design.md §6).
    external_model_name: str = ""
    external_model_price_per_1k_input_tokens: float = 0.0
    external_model_price_per_1k_output_tokens: float = 0.0

    # Tipado como Literal para falhar na carga das settings (erro claro) em vez
    # de estourar um ValueError obscuro dentro do classificador em runtime.
    router_complexity_strategy: Literal["heuristic", "llm"] = "heuristic"
    local_llm_timeout_s: float = 30.0
    external_llm_timeout_s: float = 30.0

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
