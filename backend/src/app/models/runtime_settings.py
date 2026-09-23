"""Schemas Pydantic dos parâmetros de execução ajustáveis em runtime (além do
MVP) — mesmo padrão de `app.api.local_models` (só em memória, não persiste
entre restarts do processo). Ver decisão registrada em
docs/ARCHITECTURE.md §5.
"""

from typing import Literal

from pydantic import BaseModel, Field

IntentRouterProvider = Literal["heuristica_llm", "jev_openrouter"]


class RuntimeSettingsResponse(BaseModel):
    local_llm_temperature: float | None = Field(
        default=None, description="Temperatura do Ollama; null usa o default do próprio modelo."
    )
    local_llm_timeout_s: float = Field(
        ..., description="Timeout da chamada não-streaming ao Ollama (classificação)."
    )
    external_llm_timeout_s: float = Field(
        ..., description="Timeout da chamada não-streaming ao OpenRouter, quando escalada."
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
        default="heuristica_llm",
        description="Provedor ativo para classificação de intenção do roteador.",
    )


class RuntimeSettingsUpdateRequest(BaseModel):
    """Atualização parcial — só os campos enviados são alterados."""

    local_llm_temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    local_llm_timeout_s: float | None = Field(default=None, gt=0.0, le=300.0)
    external_llm_timeout_s: float | None = Field(default=None, gt=0.0, le=300.0)
    rag_search_domain_fallback: bool | None = None
    crawler_max_pages_default: int | None = Field(default=None, ge=1)
    crawler_confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    external_vision_model_name: str | None = None
    image_internal_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    image_external_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    intent_router_provider: IntentRouterProvider | None = None
