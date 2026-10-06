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
from app.catalog_extractor.extractor import extract_page_products_vision
from app.router.openrouter_client import VisionResult


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


class _MockVisionClient:
    def __init__(self, result: str, prompt_tokens: int, completion_tokens: int, cost: float):
        self.result = VisionResult(result)
        self.result.prompt_tokens = prompt_tokens
        self.result.completion_tokens = completion_tokens
        self.result.cost_prompt_usd = cost * 0.8
        self.result.cost_completion_usd = cost * 0.2
        self.result.estimated_cost_usd = cost
        self.result.model_name = "google/gemma-4-31b-it:free"

    async def describe_image(self, image_bytes: bytes, prompt: str) -> VisionResult:
        return self.result


@pytest.mark.asyncio
async def test_crawler_and_catalog_record_ingestion_cost_events(db_session):
    # 1. Test crawler classification records cost event
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

    # 2. Test catalog extractor records vision cost event
    mock_vision = _MockVisionClient(
        result='[{"nome": "Câmera IP", "preco": 299.90}]',
        prompt_tokens=1400,
        completion_tokens=80,
        cost=0.0022,
    )
    products = await extract_page_products_vision(
        b"fake-bytes",
        mock_vision,
        source_identifier="catalogo_2026.pdf#p1",
        session=db_session,
    )
    assert len(products) == 1
    assert products[0]["nome"] == "Câmera IP"

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


@pytest.mark.asyncio
async def test_catalog_extractor_records_cost_without_session_using_global_sessionmaker(db_session):
    from app.services.ingestion_metrics import set_global_sessionmaker
    set_global_sessionmaker(_SingleSessionMaker(db_session))

    mock_vision = _MockVisionClient(
        result='[{"nome": "Inversor Solar 3kW", "preco": 1850.00}]',
        prompt_tokens=900,
        completion_tokens=60,
        cost=0.0015,
    )

    products = await extract_page_products_vision(
        b"fake-bytes-no-session",
        mock_vision,
        source_identifier="painel_solar.jpg",
    )
    assert len(products) == 1
    assert products[0]["nome"] == "Inversor Solar 3kW"

    from sqlalchemy import select
    stmt = select(IngestionCostEvent).where(IngestionCostEvent.source_identifier == "painel_solar.jpg")
    res = await db_session.execute(stmt)
    evt = res.scalar_one()
    assert evt.source_type == "catalog_extractor"
    assert evt.prompt_tokens == 900
    assert evt.completion_tokens == 60
    assert evt.total_cost_usd == 0.0015


@pytest.mark.asyncio
async def test_catalog_extractor_estimates_tokens_when_model_usage_is_missing(db_session):
    mock_vision = _MockVisionClient(
        result='[{"nome": "Módulo Fotovoltaico", "preco": 600.00}]',
        prompt_tokens=0,
        completion_tokens=0,
        cost=0.0,
    )

    products = await extract_page_products_vision(
        b"fake-bytes",
        mock_vision,
        prompt="Extraia produtos desta imagem em formato JSON",
        source_identifier="foto_sem_usage.jpg",
        session=db_session,
    )
    assert len(products) == 1

    from sqlalchemy import select
    stmt = select(IngestionCostEvent).where(IngestionCostEvent.source_identifier == "foto_sem_usage.jpg")
    res = await db_session.execute(stmt)
    evt = res.scalar_one()
    assert evt.prompt_tokens >= 500
    assert evt.completion_tokens > 0


@pytest.mark.asyncio
async def test_extract_catalog_stream_single_image_records_cost(tmp_path, db_session):
    from app.catalog_extractor.extractor import extract_catalog_stream

    mock_vision = _MockVisionClient(
        result='[{"nome": "Controlador MPPT", "preco": 420.00}]',
        prompt_tokens=1100,
        completion_tokens=70,
        cost=0.002,
    )

    sessionmaker = _SingleSessionMaker(db_session)
    events = []
    async for ev in extract_catalog_stream(
        files=[("controlador.jpg", b"fake-jpg-content")],
        provider="external",
        fallback_external=True,
        temp_dir=tmp_path,
        vision_client=mock_vision,
        session_factory=sessionmaker,
    ):
        events.append(ev)

    assert len(events) >= 2

    from sqlalchemy import select
    stmt = select(IngestionCostEvent).where(IngestionCostEvent.source_identifier == "controlador.jpg")
    res = await db_session.execute(stmt)
    evt = res.scalar_one()
    assert evt.source_type == "catalog_extractor"
    assert evt.prompt_tokens == 1100
    assert evt.completion_tokens == 70
    assert evt.total_cost_usd == 0.002
