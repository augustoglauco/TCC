import pytest

from app.router.classifier import ClassificationResult, classify
from app.router.llm_client import LLMResponse


class _FakeLLMClient:
    def __init__(self, text: str) -> None:
        self._text = text

    async def generate(self, prompt: str) -> LLMResponse:
        return LLMResponse(text=self._text, total_duration_ms=10.0)


async def test_classify_matches_domain_by_keyword():
    result = await classify("Qual o preço desse produto?")

    assert result.domain == "vendas"
    assert result.complexity == "baixa"


async def test_classify_detects_alta_complexity_by_length():
    mensagem_longa = "Preciso de um orçamento detalhado. " * 10
    result = await classify(mensagem_longa)

    assert result.domain == "vendas"
    assert result.complexity == "alta"


async def test_classify_fallback_to_fora_escopo_when_heuristic_inconclusive():
    result = await classify("Qual a capital da França?", strategy="heuristic")

    assert result.domain == "fora_escopo"


async def test_classify_uses_recent_messages_for_context_in_heuristic_fallback():
    result = await classify(
        "sim, pode ser",
        recent_messages=["Posso agendar uma visita para você conhecer o showroom?"],
        strategy="heuristic",
    )

    assert result.domain == "agendamento"


async def test_classify_uses_llm_when_keywords_inconclusive_and_strategy_llm():
    llm_client = _FakeLLMClient('{"domain": "suporte", "complexity": "alta", "confidence": 0.9}')

    result = await classify(
        "Qual a capital da França?",
        strategy="llm",
        llm_client=llm_client,
    )

    assert result == ClassificationResult(domain="suporte", complexity="alta", confidence=0.9)


async def test_classify_falls_back_to_heuristic_when_llm_returns_invalid_json():
    llm_client = _FakeLLMClient("isso não é json")

    result = await classify(
        "Qual a capital da França?",
        strategy="llm",
        llm_client=llm_client,
    )

    assert result.domain == "fora_escopo"


async def test_classify_falls_back_to_heuristic_when_llm_returns_valid_json_non_object():
    llm_client = _FakeLLMClient("42")

    result = await classify(
        "Qual a capital da França?",
        strategy="llm",
        llm_client=llm_client,
    )

    assert result.domain == "fora_escopo"


async def test_classify_raises_when_strategy_llm_without_client():
    with pytest.raises(ValueError):
        await classify("Qual a capital da França?", strategy="llm")
