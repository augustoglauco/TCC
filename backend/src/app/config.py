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
    # MVP: sem default fixado — `None` mantém o comportamento de sempre
    # (usa a temperatura padrão do próprio modelo no Ollama, sem mandar
    # `options.temperature`). Ajustável em runtime via
    # `PUT /api/admin/runtime-settings` (ver `app/api/runtime_settings.py`).
    local_llm_temperature: float | None = None

    # MVP: tamanho fixo por config, sem troca automática por VRAM disponível
    # em runtime (ver docs/ARCHITECTURE.md §7).
    stt_model_size: str = "small"

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    # Default da lib qdrant-client é 5s; em dev (WSL2), resolver "localhost"
    # às vezes demora mais que isso (ver `app/rag/qdrant_client.py`).
    qdrant_timeout_s: float = 10.0
    # MVP: desligado por padrão — o comportamento documentado em
    # docs/ARCHITECTURE.md (RAG vazio para o domínio → escala pro modelo
    # externo) depende da busca filtrada por domínio poder retornar vazio de
    # verdade. Ligar isso faz `search()` reforçar com uma segunda busca SEM
    # filtro de domínio quando a filtrada não acha nada — sacrifica o
    # isolamento entre domínios (pode trazer conteúdo de outro domínio) e
    # corrompe esse sinal de escalonamento (a busca quase nunca fica vazia).
    # Existe como flag para comparação/experimento (ver
    # `app.rag.qdrant_client.QdrantRAGClient.search`), não como recomendação.
    rag_search_domain_fallback: bool = False

    postgres_dsn: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/assistente"

    # MVP: disco local gerenciado pelo processo do backend, sem object
    # storage — coerente com o ambiente de desenvolvimento único deste
    # protótipo de TCC (ver
    # docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §3).
    rag_uploads_dir: str = "./data/rag_uploads"

    google_calendar_credentials_path: str = "./secrets/google_calendar_credentials.json"
    google_calendar_calendar_id: str = "primary"

    mcp_b2b_host: str = "0.0.0.0"
    mcp_b2b_port: int = 8100

    # MVP: origem única do frontend em dev — sem lista configurável por
    # ambiente/parceiro (isso seria necessário para um deploy real, R2/R9).
    cors_allowed_origin: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
