"""Ponto de entrada da API FastAPI do backend (`uvicorn app.main:app`)."""

import asyncio
from contextlib import asynccontextmanager
import inspect
import logging
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin_atendimento import router as admin_atendimento_router
from app.api.admin_charts import router as admin_charts_router
from app.api.admin_metrics import router as admin_metrics_router
from app.api.admin_pedidos_conversao import router as admin_pedidos_router
from app.api.admin_products import router as admin_products_router
from app.api.agendamentos import router as agendamentos_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.crawler import router as crawler_router
from app.api.image_search import router as image_search_router
from app.api.local_models import router as local_models_router
from app.api.model_catalog import router as model_catalog_router
from app.api.orders import router as orders_router
from app.api.products import router as products_router
from app.api.rag import router as rag_router
from app.api.rag_collections import router as rag_collections_router
from app.api.rag_playground import router as rag_playground_router
from app.api.runtime_settings import router as runtime_settings_router
from app.api.tom_escalonamentos import router as tom_escalonamentos_router
from app.api.uploads import router as uploads_router
from app.config import get_settings
from app.db.engine import create_db_engine, create_session_factory
from app.db.settings import get_all_app_settings
from app.logging_config import configure_logging
from app.mcp_client.google_calendar import GoogleCalendarMCPClient
from app.models.runtime_settings import DEFAULT_INTENT_ROUTER_PROVIDER
from app.rag.active_collection_client import ActiveCollectionRagClient
from app.rag.admin_all_collections_client import AdminAllCollectionsRagClient
from app.rag.clip_embedder import ClipEmbedder
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.image_search import ClipImageStore
from app.rag.qdrant_client import QdrantRAGClient
from app.router.ollama_client import OllamaClient
from app.router.openrouter_client import OpenRouterClient
from app.router.sales_catalog import SalesCatalogClient
from app.router.scheduling import SchedulingConfig
from app.services.chat_closure_service import inactivity_closure_worker
from app.stt.whisper_client import WhisperSttClient

logger = logging.getLogger(__name__)


def _apply_runtime_settings(app: FastAPI, settings_dict: dict[str, Any]) -> None:
    local_client = getattr(app.state, "local_client", None)
    external_client = getattr(app.state, "external_client", None)
    qdrant_client = getattr(app.state, "qdrant_client", None)

    if local_client is not None:
        if "local_llm_temperature" in settings_dict:
            local_client.temperature = settings_dict["local_llm_temperature"]
        if "local_llm_num_ctx" in settings_dict:
            local_client.num_ctx = settings_dict["local_llm_num_ctx"]
        if "local_llm_top_p" in settings_dict:
            local_client.top_p = settings_dict["local_llm_top_p"]
        if "local_llm_top_k" in settings_dict:
            local_client.top_k = settings_dict["local_llm_top_k"]
        if "local_llm_repeat_penalty" in settings_dict:
            local_client.repeat_penalty = settings_dict["local_llm_repeat_penalty"]
        if "local_llm_seed" in settings_dict:
            local_client.seed = settings_dict["local_llm_seed"]
        if "local_llm_timeout_s" in settings_dict:
            local_client.timeout_s = settings_dict["local_llm_timeout_s"]
        if "local_llm_keep_alive" in settings_dict:
            local_client.keep_alive = str(settings_dict["local_llm_keep_alive"])

    if external_client is not None:
        if "external_llm_timeout_s" in settings_dict:
            external_client.timeout_s = settings_dict["external_llm_timeout_s"]
        if "external_model_name" in settings_dict:
            external_client.model = settings_dict["external_model_name"]
        if "external_vision_model_name" in settings_dict:
            external_client.vision_model = settings_dict["external_vision_model_name"]

    if qdrant_client is not None:
        if "rag_search_domain_fallback" in settings_dict:
            qdrant_client.search_domain_fallback = bool(settings_dict["rag_search_domain_fallback"])

    if "rag_top_k" in settings_dict:
        app.state.rag_top_k = settings_dict["rag_top_k"]
    if "rag_score_threshold" in settings_dict:
        app.state.rag_score_threshold = settings_dict["rag_score_threshold"]
    if "crawler_max_pages_default" in settings_dict:
        app.state.crawler_max_pages_default = settings_dict["crawler_max_pages_default"]
    if "crawler_confidence_threshold" in settings_dict:
        app.state.crawler_confidence_threshold = settings_dict["crawler_confidence_threshold"]
    if "image_internal_confidence" in settings_dict:
        app.state.image_internal_confidence = settings_dict["image_internal_confidence"]
    if "image_external_confidence" in settings_dict:
        app.state.image_external_confidence = settings_dict["image_external_confidence"]
    if "intent_router_provider" in settings_dict:
        app.state.intent_router_provider = settings_dict["intent_router_provider"]
    if "tone_monitor_enabled" in settings_dict:
        app.state.tone_monitor_enabled = settings_dict["tone_monitor_enabled"]
    if "tone_monitor_provider" in settings_dict:
        app.state.tone_monitor_provider = settings_dict["tone_monitor_provider"]
    if "local_llm_warmup_on_startup" in settings_dict:
        app.state.local_llm_warmup_on_startup = bool(settings_dict["local_llm_warmup_on_startup"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    session_factory = getattr(app.state, "db_sessionmaker", None)
    if session_factory is not None:
        try:
            async with session_factory() as session:
                persisted = await get_all_app_settings(session)
                _apply_runtime_settings(app, persisted)
        except Exception as exc:
            logger.warning("Falha ao carregar configurações persistidas do banco no startup: %s", exc)

    closure_worker_task = None
    if session_factory is not None:
        closure_worker_task = asyncio.create_task(
            inactivity_closure_worker(session_factory, interval_seconds=300, timeout_minutes=30)
        )

    if getattr(app.state, "local_llm_warmup_on_startup", True):
        local_client = getattr(app.state, "local_client", None)
        if (
            local_client
            and hasattr(local_client, "preload")
            and inspect.iscoroutinefunction(local_client.preload)
            and str(getattr(local_client, "keep_alive", "-1")) != "0"
        ):
            logger.info("Disparando warmup do modelo local (%s) na VRAM...", getattr(local_client, "model", ""))
            asyncio.create_task(local_client.preload())

    yield

    if closure_worker_task is not None:
        closure_worker_task.cancel()
        try:
            await closure_worker_task
        except asyncio.CancelledError:
            pass

    crawler_http_client = getattr(app.state, "crawler_http_client", None)
    if crawler_http_client and not crawler_http_client.is_closed:
        await crawler_http_client.aclose()
    catalog_client = getattr(app.state, "model_catalog_http_client", None)
    if catalog_client and not catalog_client.is_closed:
        await catalog_client.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Assistente Multimodal — Backend",
        version="0.1.0",
        lifespan=lifespan,
    )

    # MVP: libera as origens do frontend de dev (lista, ver
    # Settings.cors_allowed_origins) — sem lista por ambiente/parceiro
    # (ver docs/FRONTEND.md). Configurável via CORS_ALLOWED_ORIGIN em .env
    # (padrão: http://localhost:3001, a porta do frontend Next.js;
    # separado por vírgula para mais de uma origem) — não hardcode outras
    # origens aqui, isso desliga o controle que a settings deveria ter.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
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
        num_ctx=settings.local_llm_num_ctx,
        top_p=settings.local_llm_top_p,
        top_k=settings.local_llm_top_k,
        repeat_penalty=settings.local_llm_repeat_penalty,
        seed=settings.local_llm_seed,
        keep_alive=settings.local_llm_keep_alive,
    )
    app.state.local_llm_warmup_on_startup = settings.local_llm_warmup_on_startup
    app.state.external_client = OpenRouterClient(
        base_url=settings.external_model_base_url,
        api_key=settings.external_model_api_key,
        model=settings.external_model_name,
        timeout_s=settings.external_llm_timeout_s,
        price_per_1k_input_tokens=settings.external_model_price_per_1k_input_tokens,
        price_per_1k_output_tokens=settings.external_model_price_per_1k_output_tokens,
        vision_model=settings.external_vision_model_name,
        price_per_1k_vision_input_tokens=settings.external_vision_model_price_per_1k_input_tokens,
        price_per_1k_vision_output_tokens=settings.external_vision_model_price_per_1k_output_tokens,
        jev_model=settings.jev_model_name,
        jev_timeout_s=settings.jev_timeout_s,
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
    app.state.product_images_dir = Path(settings.product_images_dir)
    app.state.product_images_dir.mkdir(parents=True, exist_ok=True)
    (app.state.product_images_dir / "temp").mkdir(parents=True, exist_ok=True)
    app.state.crawler_max_pages_default = settings.crawler_max_pages
    app.state.crawler_confidence_threshold = settings.crawler_confidence_threshold
    # Cliente HTTP dedicado ao crawler (spec
    # docs/superpowers/specs/2026-09-19-crawler-paginas-design.md) — separado
    # de `external_client`/`local_client`, que são clientes de LLM, não de
    # fetch de páginas arbitrárias.
    app.state.crawler_http_client = httpx.AsyncClient()

    # Cliente HTTP dedicado às fontes públicas de características de
    # modelo (OpenRouter/Hugging Face, além do MVP — ver
    # docs/superpowers/specs/2026-10-03-caracteristicas-modelo-hover-
    # design.md) — separado dos demais clientes HTTP por propósito.
    app.state.model_catalog_http_client = httpx.AsyncClient()

    # Primeiro uso real do Postgres do projeto (registro de documentos do
    # RAG, além do MVP — ver docs/ARCHITECTURE.md §5). Engine criado
    # explicitamente aqui (não via singleton global), mesmo padrão dos
    # outros clientes de infraestrutura desta função.
    db_engine = create_db_engine(settings.postgres_dsn)
    app.state.db_sessionmaker = create_session_factory(db_engine)
    from app.services.ingestion_metrics import set_global_sessionmaker
    set_global_sessionmaker(app.state.db_sessionmaker)

    app.state.rag_client = ActiveCollectionRagClient(
        qdrant=app.state.qdrant_client,
        session_factory=app.state.db_sessionmaker,
        embedders=app.state.embedder_registry,
    )
    # Modo admin do chat (decisão de 2026-09-30, docs/ARCHITECTURE.md §6): o
    # Admin, confirmado por `auth_token` (ver `app.api.auth.verificar_admin_por_token`
    # em `app.api.chat`), busca em todo o RAG em vez de só a collection ativa.
    app.state.rag_client_admin = AdminAllCollectionsRagClient(
        qdrant=app.state.qdrant_client,
        session_factory=app.state.db_sessionmaker,
        embedders=app.state.embedder_registry,
    )

    # Orquestrador como integrador do MCP B2B em Vendas (R12, Fase 5) — ver
    # docs/superpowers/specs/2026-09-24-orquestrador-mcp-b2b-vendas-design.md.
    # Chama app.db.catalog diretamente (mesmo processo), não abre uma
    # conexão MCP real contra o mcp-b2b-server separado (spec §4).
    app.state.sales_catalog_client = SalesCatalogClient(app.state.db_sessionmaker)

    # CLIP para busca multimodal por imagem (R6, Fase 3) — singleton lazy,
    # mesmo padrão dos outros clientes de infraestrutura.
    app.state.clip_embedder = ClipEmbedder(timeout_s=settings.clip_timeout_s)
    app.state.clip_image_store = ClipImageStore(app.state.qdrant_client.async_client)

    app.state.complexity_strategy = settings.router_complexity_strategy
    # Limiares do fluxo de identificação de produto por imagem (R6, Fase 3),
    # ajustáveis em runtime via PUT /api/admin/runtime-settings. O
    # `external_vision_model_name` vive no OpenRouterClient (`vision_model`).
    app.state.image_internal_confidence = settings.image_internal_confidence
    app.state.image_external_confidence = settings.image_external_confidence
    app.state.rag_top_k = settings.rag_top_k
    app.state.rag_score_threshold = settings.rag_score_threshold
    app.state.rag_download_confidence_threshold = settings.rag_download_confidence_threshold
    app.state.intent_router_provider = DEFAULT_INTENT_ROUTER_PROVIDER
    # Monitor de Tom (R8, Fase 4B) — diferente de intent_router_provider
    # acima, aqui o valor inicial vem de settings/env (TONE_MONITOR_ENABLED/
    # TONE_MONITOR_PROVIDER), não de uma constante fixa: a spec pede default
    # configurável por ambiente (docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md §7).
    app.state.tone_monitor_enabled = settings.tone_monitor_enabled
    app.state.tone_monitor_provider = settings.tone_monitor_provider
    # MVP: modelo carregado sob demanda (lazy) na mesma GPU do modelo local de
    # chat — contenção de VRAM entre os dois é um risco conhecido (ver
    # docs/ARCHITECTURE.md §7).
    app.state.stt_client = WhisperSttClient(model_size=settings.stt_model_size)

    # MCP do Google Calendar (R11, Fase 4A) — servidor de terceiro
    # `calendar-mcp-server` rodando localmente, autenticação gerenciada por
    # ele mesmo (ver docs/ARCHITECTURE.md §5, decisão revista 2026-09-23).
    # Conexão MCP só é aberta no primeiro uso real, então construir o
    # cliente aqui não exige que o servidor já esteja no ar em todo
    # ambiente de dev.
    app.state.calendar_client = GoogleCalendarMCPClient(
        mcp_server_url=settings.calendar_mcp_url,
        calendar_id=settings.google_calendar_calendar_id,
        timeout_s=settings.calendar_mcp_timeout_s,
    )
    app.state.scheduling_config = SchedulingConfig(
        timezone=settings.agendamento_timezone,
        expediente_dias=settings.agendamento_expediente_dias,
        expediente_inicio=settings.agendamento_expediente_inicio,
        expediente_fim=settings.agendamento_expediente_fim,
    )

    app.include_router(chat_router)
    app.include_router(admin_atendimento_router)
    app.include_router(admin_pedidos_router)
    app.include_router(admin_charts_router)
    app.include_router(admin_metrics_router)
    app.include_router(crawler_router)
    app.include_router(image_search_router)
    app.include_router(local_models_router)
    app.include_router(model_catalog_router)
    app.include_router(rag_router)
    app.include_router(rag_collections_router)
    app.include_router(rag_playground_router)
    app.include_router(runtime_settings_router)
    app.include_router(tom_escalonamentos_router)
    app.include_router(uploads_router)
    app.include_router(admin_products_router)
    app.include_router(auth_router)
    app.include_router(products_router)
    app.include_router(orders_router)
    app.include_router(agendamentos_router)

    return app


app = create_app()
