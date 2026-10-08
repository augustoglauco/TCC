import asyncio
from datetime import UTC, datetime
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin_metrics import router as admin_metrics_router
from app.api.rag_dependencies import get_db_session
from app.db.models import Conversa, ConversaMensagem, IngestionCostEvent
from app.router.llm_client import LLMResponse
from app.rag.crawler_classifier import classify_page


class _SingleSessionMaker:
    def __init__(self, session) -> None:
        self._session = session
        self._lock = asyncio.Lock()

    def __call__(self):
        return self

    async def __aenter__(self):
        await self._lock.acquire()
        return self._session

    async def __aexit__(self, *exc_info) -> bool:
        self._lock.release()
        return False


@pytest.fixture
def test_client(db_session):
    app = FastAPI()
    app.include_router(admin_metrics_router)
    app.state.db_sessionmaker = _SingleSessionMaker(db_session)
    app.dependency_overrides[get_db_session] = lambda: db_session
    with TestClient(app) as client:
        yield client


class _MockCrawlerLLM:
    def __init__(self, text: str, prompt_tokens: int, completion_tokens: int, cost: float):
        self.response = LLMResponse(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_duration_ms=150.0,
            cost_prompt_usd=cost * 0.7,
            cost_completion_usd=cost * 0.3,
            estimated_cost_usd=cost,
            model_name="openai/gpt-4o-mini",
        )

    async def generate(self, prompt: str) -> LLMResponse:
        return self.response


# MVP/telemetria: a extração de catálogo por visão (`extract_page_products_vision`)
# usava `_MockVisionClient` + `record_ingestion_cost` aqui, mas migrou para o
# ledger unificado `registrar_uso_ia` (item D, pontos 3a-3b, 2026-10-08) —
# migração sem dual-write, decisão do usuário de não preservar os dados
# antigos. A cobertura equivalente agora vive em
# `tests/test_catalog_extractor.py`
# (`test_extract_page_products_vision_interna_registra_uso_ia` /
# `..._externa_registra_uso_ia`).


@pytest.mark.asyncio
async def test_crawler_records_ingestion_cost_event(db_session):
    mock_llm = _MockCrawlerLLM(
        text='{"domain": "vendas", "confidence": 0.95}',
        prompt_tokens=500,
        completion_tokens=20,
        cost=0.0008,
    )
    classification = await classify_page(
        mock_llm,
        "Texto de produtos e promoções",
        source_identifier="https://exemplo.com.br/promos",
        session=db_session,
    )
    assert classification.domain == "vendas"
    assert classification.confidence == 0.95

    await db_session.commit()


@pytest.mark.asyncio
async def test_admin_metrics_aggregates_ingestion_and_chat_costs(test_client, db_session, admin_headers):
    agora = datetime.now(UTC)

    # 1. Chat encerrado ($0.0010)
    conversa = Conversa(
        id="conv-metrics-ingest-1",
        status="encerrada",
        encerrada_em=agora,
        motivo_encerramento="manual_usuario",
    )
    db_session.add(conversa)
    msg = ConversaMensagem(
        conversa_id=conversa.id,
        papel="assistente",
        texto="Olá! Como posso ajudar?",
        criada_em=agora,
        metricas={
            "backend_used": "externo",
            "prompt_tokens": 800,
            "completion_tokens": 100,
            "cost_prompt_usd": 0.0008,
            "cost_completion_usd": 0.0002,
            "estimated_cost_usd": 0.0010,
        },
    )
    db_session.add(msg)

    # 2. IngestionCostEvent: Crawler ($0.0008)
    evt_crawler = IngestionCostEvent(
        source_type="crawler",
        source_identifier="https://exemplo.com/sobre",
        model_name="openai/gpt-4o-mini",
        prompt_tokens=500,
        completion_tokens=20,
        cost_prompt_usd=0.0005,
        cost_completion_usd=0.0003,
        total_cost_usd=0.0008,
        criado_em=agora,
    )

    # 3. IngestionCostEvent: Catálogo Visão ($0.0022)
    evt_catalog = IngestionCostEvent(
        source_type="catalog_extractor",
        source_identifier="catalogo.pdf#p1",
        model_name="google/gemini-flash-1.5",
        prompt_tokens=1400,
        completion_tokens=80,
        cost_prompt_usd=0.0018,
        cost_completion_usd=0.0004,
        total_cost_usd=0.0022,
        criado_em=agora,
    )
    db_session.add_all([evt_crawler, evt_catalog])
    await db_session.commit()

    response = test_client.get(
        "/api/admin/metrics/tokens-and-costs?period=today", headers=admin_headers
    )
    assert response.status_code == 200
    data = response.json()
    summary = data["summary"]

    # Chat metrics
    assert summary["total_closed_chats"] == 1
    assert summary["total_cost_usd"] == 0.0010

    # Ingestion metrics
    assert summary["total_ingestion_calls"] == 2
    assert summary["total_ingestion_tokens"] == 2000  # (500+20) + (1400+80)
    assert summary["total_ingestion_cost_usd"] == 0.0030  # 0.0008 + 0.0022

    # Grand total (Chat + Ingestion)
    assert summary["grand_total_cost_usd"] == 0.0040  # 0.0010 + 0.0030

    # Daily breakdown
    daily = data["daily_breakdown"][0]
    assert daily["closed_chats_count"] == 1
    # Consolidado do dia = Atendimento (0.0010) + Ingestão (0.0030), sem
    # sobreposição — achado de 2026-10-05: antes não somava Ingestão aqui,
    # apesar do tooltip do frontend já afirmar que incluía.
    assert daily["total_cost_usd"] == 0.0040
    assert daily["ingestion_calls_count"] == 2
    assert daily["ingestion_tokens"] == 2000
    assert daily["ingestion_cost_usd"] == 0.0030


# Removidos em 2026-10-08: três testes que cobriam exclusivamente o caminho
# antigo de `extract_page_products_vision` via `record_ingestion_cost`
# (sessionmaker global sem `session`, estimativa de tokens por tamanho de
# texto quando a API de visão não reporta uso, e `extract_catalog_stream`
# persistindo em `IngestionCostEvent`) — removido na migração para
# `registrar_uso_ia` (item D, pontos 3a-3b); a estimativa LOCAL por tamanho
# de texto que existia dentro de `extract_page_products_vision` contrariava
# a semântica `None`=não-capturado do ledger novo e por isso não foi
# portada. Isso cobre só a estimativa local dessa função: a mesma fabricação
# ainda pode ocorrer uma camada acima, em
# `OpenRouterClient.describe_image` (app/router/openrouter_client.py),
# quando a API de visão externa não reporta uso real — gap conhecido, fora
# do escopo deste item (compartilhado com código do item B), candidato a
# revisão no item E ou em follow-up dedicado. Ver
# `tests/test_catalog_extractor.py` para a cobertura atual.
