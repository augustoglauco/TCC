"""Ponto de entrada da API FastAPI do backend (`uvicorn app.main:app`)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.config import get_settings
from app.logging_config import configure_logging
from app.router.ollama_client import OllamaClient
from app.router.openrouter_client import OpenRouterClient
from app.router.rag_client import NullRAGClient


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="Assistente Multimodal — Backend", version="0.1.0")

    # MVP: libera só a origem do frontend de dev — sem lista por
    # ambiente/parceiro (ver docs/FRONTEND.md).
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
    )
    app.state.external_client = OpenRouterClient(
        base_url=settings.external_model_base_url,
        api_key=settings.external_model_api_key,
        model=settings.external_model_name,
        timeout_s=settings.external_llm_timeout_s,
        price_per_1k_input_tokens=settings.external_model_price_per_1k_input_tokens,
        price_per_1k_output_tokens=settings.external_model_price_per_1k_output_tokens,
    )
    # MVP: RAG real (Qdrant) ainda não implementado — entra na Fase 2, junto
    # da ingestão de PDFs/textos (ver docs/ROADMAP.md).
    app.state.rag_client = NullRAGClient()
    app.state.complexity_strategy = settings.router_complexity_strategy

    app.include_router(chat_router)

    return app


app = create_app()
