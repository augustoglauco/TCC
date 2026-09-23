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

    # --- Identificação de produto por imagem (R6, Fase 3) ---
    # Fluxo: imagem espontânea = identificação (padrão); OCR só quando o
    # sistema solicita comprovante (ver docs/ARCHITECTURE.md §4). Os três
    # parâmetros abaixo têm default aqui só para popular o frontend; são
    # ajustáveis em runtime via PUT /api/admin/runtime-settings.
    # Modelo de visão via OpenRouter (formato "provider/model", ex.:
    # "openai/gpt-4o-mini"). Vazio = fallback externo indisponível (o motor
    # responde "não identificado" em vez de chamar o externo).
    external_vision_model_name: str = ""
    # Limiar alto de aceite do catálogo interno (CLIP): melhor score >= este
    # valor aceita o interno sem chamar o externo.
    image_internal_confidence: float = 0.30
    # Confiança mínima que o modelo de visão externo precisa reportar para o
    # resultado ser aceito.
    image_external_confidence: float = 0.80

    # Provedor alternativo do classificador de intenção (além do MVP, ver
    # docs/ARCHITECTURE.md §5, decisão 2026-09-23). Reaproveita
    # external_model_api_key/external_model_base_url (mesma conta OpenRouter).
    # O til em "~typesafe/jev-latest" é parte do slug do modelo, não um
    # artefato de URL — sem ele o OpenRouter devolve 400 "Model ... does not
    # exist" (achado na verificação E2E da Task 6, confirmado com chamada
    # real à API).
    jev_model_name: str = "~typesafe/jev-latest"
    # Orçamento de timeout próprio do Jev, menor que o do LLM de chat externo
    # (achado da revisão final) — evita que um travamento na chamada custe
    # até external_llm_timeout_s (30s default) ao visitante antes do
    # fallback gracioso disparar.
    jev_timeout_s: float = 10.0

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

    # MVP: teto default (não rígido — o form do admin pode pedir mais por
    # execução, ver `app.api.crawler`) de páginas por execução do crawler de
    # páginas (R4). Ajustável em runtime via `PUT /api/admin/runtime-settings`
    # (ver docs/superpowers/specs/2026-09-19-crawler-paginas-design.md).
    crawler_max_pages: int = 20
    # Limiar de confiança do classificador de domínio do crawler:
    # `confidence >= limiar` ingere direto, abaixo vai pra fila de revisão
    # manual. Ajustável em runtime via `PUT /api/admin/runtime-settings`.
    crawler_confidence_threshold: float = 0.7

    # URL do servidor MCP de terceiro `calendar-mcp-server` (pacote PyPI,
    # https://github.com/deciduus/calendar-mcp), rodando localmente via
    # `calendar-mcp-server serve --transport http --port 8090` — substitui o
    # MCP oficial do Google (`calendarmcp.googleapis.com`), que está em
    # Developer Preview e não aceita contas Gmail pessoais (achado em
    # docs/ARCHITECTURE.md §5, 2026-09-23). Autenticação OAuth é gerenciada
    # pelo próprio `calendar-mcp-server` (`calendar-mcp-server auth`), não
    # por este backend.
    calendar_mcp_url: str = "http://127.0.0.1:8090/mcp"
    google_calendar_calendar_id: str = "primary"

    # --- Validação de horário do agendamento (R11, Fase 4A) ---
    agendamento_timezone: str = "America/Sao_Paulo"
    agendamento_expediente_dias: str = "seg-sex"
    agendamento_expediente_inicio: str = "09:00"
    agendamento_expediente_fim: str = "18:00"

    mcp_b2b_host: str = "0.0.0.0"
    mcp_b2b_port: int = 8100

    # MVP: origem única do frontend em dev — sem lista configurável por
    # ambiente/parceiro (isso seria necessário para um deploy real, R2/R9).
    cors_allowed_origin: str = "http://localhost:3001"


@lru_cache
def get_settings() -> Settings:
    return Settings()
