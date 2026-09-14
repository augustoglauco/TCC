import pytest
from pydantic import ValidationError

from app.router.classifier import ClassificationResult, classify
from app.router.llm_client import LLMResponse


class _FakeLLMClient:
    def __init__(self, text: str) -> None:
        self._text = text

    async def generate(self, prompt: str) -> LLMResponse:
        return LLMResponse(text=self._text, total_duration_ms=10.0)


class _RaisingLLMClient:
    """Simula falha de infraestrutura do backend local dentro de `generate()`."""

    def __init__(self, exception: Exception) -> None:
        self._exception = exception

    async def generate(self, prompt: str) -> LLMResponse:
        raise self._exception


def _validation_error_do_ollama() -> ValidationError:
    """ValidationError igual à que `OllamaClient.generate()` levanta com payload inválido."""
    try:
        LLMResponse(text=None, total_duration_ms=None)  # type: ignore[arg-type]
    except ValidationError as exc:
        return exc
    raise AssertionError("esperava ValidationError")


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


async def test_classify_uses_llm_when_response_wrapped_in_markdown_code_fence():
    # Regressão: alguns modelos (ex.: gemma) envolvem o JSON pedido em um
    # bloco de código markdown mesmo quando instruídos a responder só com
    # JSON. Sem tratar isso, `json.loads` falha e a resposta correta do LLM
    # é descartada silenciosamente pelo fallback heurístico (ver classifier.py).
    llm_client = _FakeLLMClient(
        '```json\n{"domain": "agendamento", "complexity": "baixa", "confidence": 1.0}\n```'
    )

    result = await classify(
        "preciso mudar a data da minha consulta na loja para semana que vem",
        strategy="llm",
        llm_client=llm_client,
    )

    assert result == ClassificationResult(domain="agendamento", complexity="baixa", confidence=1.0)


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


async def test_classify_propaga_falha_de_conexao_do_llm_client():
    llm_client = _RaisingLLMClient(ConnectionError("ollama fora do ar"))

    with pytest.raises(ConnectionError):
        await classify("Qual a capital da França?", strategy="llm", llm_client=llm_client)


async def test_classify_propaga_validation_error_vinda_do_generate():
    # Regressão: `OllamaClient.generate()` levanta ValidationError quando o
    # Ollama devolve payload malformado. Isso é falha de infraestrutura do
    # backend local, não "LLM respondeu conteúdo não parseável" — não pode
    # ser engolido pelo fallback heurístico (que levaria a fora_escopo →
    # backend externo, ver spec §2.4).
    llm_client = _RaisingLLMClient(_validation_error_do_ollama())

    with pytest.raises(ValidationError):
        await classify("Qual a capital da França?", strategy="llm", llm_client=llm_client)


async def test_classify_ignora_acentos_ao_casar_palavras_chave():
    assert (await classify("qual o preco do produto?")).domain == "vendas"
    assert (await classify("nao funciona o aparelho")).domain == "suporte"
    assert (await classify("quero fazer a devolucao da compra")).domain == "atendimento"


async def test_classify_ignora_acentos_no_contexto_recente():
    result = await classify(
        "sim, pode ser",
        recent_messages=["Posso agendar uma visita para voce conhecer o showroom?"],
        strategy="heuristic",
    )

    assert result.domain == "agendamento"
