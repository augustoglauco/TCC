"""Ponto de entrada da API FastAPI do backend (`uvicorn app.main:app`)."""

from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.crawler import router as crawler_router
from app.api.image_search import router as image_search_router
from app.api.local_models import router as local_models_router
from app.api.rag import router as rag_router
from app.api.rag_collections import router as rag_collections_router
from app.api.rag_playground import router as rag_playground_router
from app.api.runtime_settings import router as runtime_settings_router
from app.config import get_settings
from app.db.engine import create_db_engine, create_session_factory
from app.logging_config import configure_logging
from app.mcp_client.google_calendar import GoogleCalendarMCPClient
from app.rag.active_collection_client import ActiveCollectionRagClient
from app.rag.clip_embedder import ClipEmbedder
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.image_search import ClipImageStore
from app.rag.qdrant_client import QdrantRAGClient
from app.router.ollama_client import OllamaClient
from app.router.openrouter_client import OpenRouterClient
from app.router.scheduling import SchedulingConfig
from app.stt.whisper_client import WhisperSttClient


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="Assistente Multimodal — Backend", version="0.1.0")

    # MVP: libera só a origem do frontend de dev — sem lista por
    # ambiente/parceiro (ver docs/FRONTEND.md). Configurável via
    # CORS_ALLOWED_ORIGIN em .env (padrão: http://localhost:3001, a porta do
    # frontend Next.js) — não hardcode outras origens aqui, isso desliga o
    # controle que a settings deveria ter.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_allowed_origin],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Clientes de infraestrutura como singletons por processo — reaproveitados
    # entre requisições (mesmo padrão usado pelos testes do orchestrator).
    app.state.local_client = OllamaClient(
        base_url=settings.local_model_base_url,
        model=settings.local_model_name,
        timeout_s=settings.local_llm_timeout_s,
        temperature=settings.local_llm_temperature,
    )
    app.state.external_client = OpenRouterClient(
        base_url=settings.external_model_base_url,
        api_key=settings.external_model_api_key,
        model=settings.external_model_name,
        timeout_s=settings.external_llm_timeout_s,
        price_per_1k_input_tokens=settings.external_model_price_per_1k_input_tokens,
        price_per_1k_output_tokens=settings.external_model_price_per_1k_output_tokens,
        vision_model=settings.external_vision_model_name,
    )

    # Gerenciador de modelos locais (além do MVP — ver
    # docs/superpowers/specs/2026-09-16-local-model-manager-design.md).
    # Progresso de download em memória, por nome de modelo — nunca
    # persistido, reseta a cada restart do processo.
    app.state.model_pull_progress = {}

    # RAG real via Qdrant (R4, Fase 2), evoluído para múltiplas collections
    # configuráveis (Entregas B+C+D, além do MVP — ver
    # docs/superpowers/specs/2026-09-15-rag-collections-config-design.md).
    # `qdrant_client`/`embedder_registry` são de baixo nível (usados pelos
    # endpoints administrativos de `app.api.rag`/`rag_collections`/
    # `rag_playground`); `rag_client` é o adapter que resolve a collection
    # ativa a cada busca, consumido pelo orchestrator via `app.api.chat`.
    app.state.qdrant_client = QdrantRAGClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        timeout_s=settings.qdrant_timeout_s,
        search_domain_fallback=settings.rag_search_domain_fallback,
    )
    app.state.embedder_registry = EmbedderRegistry()
    app.state.rag_uploads_dir = Path(settings.rag_uploads_dir)
    app.state.crawler_max_pages_default = settings.crawler_max_pages
    app.state.crawler_confidence_threshold = settings.crawler_confidence_threshold
    # Cliente HTTP dedicado ao crawler (spec
    # docs/superpowers/specs/2026-09-19-crawler-paginas-design.md) — separado
    # de `external_client`/`local_client`, que são clientes de LLM, não de
    # fetch de páginas arbitrárias.
    app.state.crawler_http_client = httpx.AsyncClient()

    # Primeiro uso real do Postgres do projeto (registro de documentos do
    # RAG, além do MVP — ver docs/ARCHITECTURE.md §5). Engine criado
    # explicitamente aqui (não via singleton global), mesmo padrão dos
    # outros clientes de infraestrutura desta função.
    db_engine = create_db_engine(settings.postgres_dsn)
    app.state.db_sessionmaker = create_session_factory(db_engine)

    app.state.rag_client = ActiveCollectionRagClient(
        qdrant=app.state.qdrant_client,
        session_factory=app.state.db_sessionmaker,
        embedders=app.state.embedder_registry,
    )

    # CLIP para busca multimodal por imagem (R6, Fase 3) — singleton lazy,
    # mesmo padrão dos outros clientes de infraestrutura.
    app.state.clip_embedder = ClipEmbedder()
    app.state.clip_image_store = ClipImageStore(app.state.qdrant_client.async_client)

    app.state.complexity_strategy = settings.router_complexity_strategy
    # Limiares do fluxo de identificação de produto por imagem (R6, Fase 3),
    # ajustáveis em runtime via PUT /api/admin/runtime-settings. O
    # `external_vision_model_name` vive no OpenRouterClient (`vision_model`).
    app.state.image_internal_confidence = settings.image_internal_confidence
    app.state.image_external_confidence = settings.image_external_confidence
    # MVP: modelo carregado sob demanda (lazy) na mesma GPU do modelo local de
    # chat — contenção de VRAM entre os dois é um risco conhecido (ver
    # docs/ARCHITECTURE.md §7).
    app.state.stt_client = WhisperSttClient(model_size=settings.stt_model_size)

    # MCP do Google Calendar (R11, Fase 4A) — carregamento de
    # credenciais/refresh token é lazy (só no primeiro uso real), então
    # construir o cliente aqui não exige que os arquivos já existam em todo
    # ambiente de dev (ver
    # docs/superpowers/specs/2026-09-21-agendamento-mcp-calendar-design.md §3).
    app.state.calendar_client = GoogleCalendarMCPClient(
        credentials_path=settings.google_calendar_credentials_path,
        token_path=settings.google_calendar_token_path,
        calendar_id=settings.google_calendar_calendar_id,
    )
    app.state.scheduling_config = SchedulingConfig(
        timezone=settings.agendamento_timezone,
        expediente_dias=settings.agendamento_expediente_dias,
        expediente_inicio=settings.agendamento_expediente_inicio,
        expediente_fim=settings.agendamento_expediente_fim,
    )

    app.include_router(chat_router)
    app.include_router(crawler_router)
    app.include_router(image_search_router)
    app.include_router(local_models_router)
    app.include_router(rag_router)
    app.include_router(rag_collections_router)
    app.include_router(rag_playground_router)
    app.include_router(runtime_settings_router)

    return app


app = create_app()
