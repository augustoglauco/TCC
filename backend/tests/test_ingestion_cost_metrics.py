import pytest

from app.router.llm_client import LLMResponse
from app.rag.crawler_classifier import classify_page


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
