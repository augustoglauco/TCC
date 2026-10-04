"""Schemas Pydantic dos parâmetros de execução ajustáveis em runtime (além do
MVP). Alterações via `PUT /api/admin/runtime-settings` ficam em memória
(`app.state`) E são persistidas na tabela `app_settings` do Postgres
(`app.db.settings`), restauradas automaticamente no boot do backend — ver
decisão de 2026-10-03 registrada em docs/ARCHITECTURE.md §5 (achado da
revisão de 2026-10-04: este docstring ainda descrevia o comportamento
anterior à persistência, só em memória).
"""

from typing import Literal

from pydantic import BaseModel, Field

IntentRouterProvider = Literal["heuristica", "heuristica_llm", "jev_openrouter"]
# Único ponto de definição do default — reaproveitado em app/router/,
# app/api/ e app/main.py em vez de repetir a string-mágica "heuristica_llm"
# em ~10 lugares (achado da revisão final do branch do Jev).
DEFAULT_INTENT_ROUTER_PROVIDER: IntentRouterProvider = "heuristica_llm"

ToneMonitorProvider = Literal["heuristica_llm", "jev_openrouter"]
# Mesmo padrão de DEFAULT_INTENT_ROUTER_PROVIDER acima — único ponto de
# definição do default do Monitor de Tom (R8, Fase 4B).
DEFAULT_TONE_MONITOR_PROVIDER: ToneMonitorProvider = "heuristica_llm"


class RuntimeSettingsResponse(BaseModel):
    local_llm_temperature: float | None = Field(
        default=None, description="Temperatura do Ollama; null usa o default do próprio modelo."
    )
    local_llm_num_ctx: int | None = Field(
        default=None, description="Tamanho da janela de contexto em tokens do Ollama (num_ctx)."
    )
    local_llm_top_p: float | None = Field(
        default=None, description="Nucleus sampling do Ollama (top_p, 0.0 a 1.0)."
    )
    local_llm_top_k: int | None = Field(
        default=None, description="Top-k sampling do Ollama (top_k, 1 a 500)."
    )
    local_llm_repeat_penalty: float | None = Field(
        default=None, description="Penalidade de repetição do Ollama (repeat_penalty, 0.0 a 3.0)."
    )
    local_llm_seed: int | None = Field(
        default=None, description="Semente aleatória do Ollama para geracao reproduzivel (seed)."
    )
    local_llm_timeout_s: float = Field(
        ..., description="Timeout da chamada não-streaming ao Ollama (classificação)."
    )
    external_llm_timeout_s: float = Field(
        ..., description="Timeout da chamada não-streaming ao OpenRouter, quando escalada."
    )
    rag_top_k: int = Field(
        default=3, description="Quantidade de trechos de documentos buscados no Qdrant (top-k)."
    )
    rag_score_threshold: float = Field(
        default=0.35, description="Limiar mínimo de similaridade vetorial no Qdrant (0.0 a 1.0)."
    )
    rag_search_domain_fallback: bool = Field(
        ...,
        description="Se a busca do RAG refaz sem filtro de domínio quando a filtrada vem vazia.",
    )
    crawler_max_pages_default: int = Field(
        ...,
        description=(
            "Teto default de páginas por execução do crawler, pré-preenche o form do admin."
        ),
    )
    crawler_confidence_threshold: float = Field(
        ...,
        description=(
            "Limiar de confiança do classificador do crawler: acima ingere direto, "
            "abaixo vai pra fila de revisão."
        ),
    )
    external_model_name: str = Field(
        ...,
        description="Modelo LLM de texto via OpenRouter ativo para inferência externa.",
    )
    external_vision_model_name: str = Field(
        ...,
        description=(
            "Modelo de visão via OpenRouter para identificação de imagem "
            '(formato "provider/model"); vazio desliga o fallback externo.'
        ),
    )
    image_internal_confidence: float = Field(
        ...,
        description="Limiar de aceite do catálogo interno (CLIP) na identificação de imagem.",
    )
    image_external_confidence: float = Field(
        ...,
        description="Confiança mínima reportada pelo modelo de visão externo para aceitar.",
    )
    intent_router_provider: IntentRouterProvider = Field(
        default=DEFAULT_INTENT_ROUTER_PROVIDER,
        description="Provedor ativo para classificação de intenção do roteador.",
    )
    tone_monitor_enabled: bool = Field(
        ...,
        description=(
            "Liga/desliga o Monitor de Tom (R8) — heurística e fallback nunca rodam quando false."
        ),
    )
    tone_monitor_provider: ToneMonitorProvider = Field(
        default=DEFAULT_TONE_MONITOR_PROVIDER,
        description=(
            "Provedor do fallback ambíguo do Monitor de Tom quando a heurística não encontra "
            "sinal forte."
        ),
    )
    local_llm_keep_alive: str = Field(
        default="-1",
        description="Tempo de retenção na VRAM do Ollama (-1=permanente, 5m=padrão, 0=descarrega)",
    )
    local_llm_warmup_on_startup: bool = Field(
        default=True,
        description="Se pré-carrega o modelo local na VRAM ao inicializar o backend.",
    )
    local_model_loaded: bool = Field(
        default=False,
        description="Se o modelo ativo está atualmente residente na VRAM do Ollama.",
    )
    local_model_vram_bytes: int | None = Field(
        default=None,
        description="Quantidade de bytes de VRAM alocados para o modelo ativo no Ollama.",
    )


class RuntimeSettingsUpdateRequest(BaseModel):
    """Atualização parcial — só os campos enviados são alterados."""

    local_llm_temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    local_llm_num_ctx: int | None = Field(default=None, ge=512, le=131072)
    local_llm_top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    local_llm_top_k: int | None = Field(default=None, ge=1, le=500)
    local_llm_repeat_penalty: float | None = Field(default=None, ge=0.0, le=3.0)
    local_llm_seed: int | None = Field(default=None)
    local_llm_timeout_s: float | None = Field(default=None, gt=0.0, le=300.0)
    external_llm_timeout_s: float | None = Field(default=None, gt=0.0, le=300.0)
    rag_top_k: int | None = Field(default=None, ge=1, le=20)
    rag_score_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    rag_search_domain_fallback: bool | None = None
    crawler_max_pages_default: int | None = Field(default=None, ge=1)
    crawler_confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    external_model_name: str | None = None
    external_vision_model_name: str | None = None
    image_internal_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    image_external_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    intent_router_provider: IntentRouterProvider | None = None
    tone_monitor_enabled: bool | None = None
    tone_monitor_provider: ToneMonitorProvider | None = None
    local_llm_keep_alive: str | None = None
    local_llm_warmup_on_startup: bool | None = None
