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


class _FakeOpenRouterJevClient:
    def __init__(self, domain: str = "vendas", confidence: float = 0.9, fail: bool = False):
        self.domain = domain
        self.confidence = confidence
        self.fail = fail

    async def classify_intent_jev(self, message: str, recent_messages: list[str] | None = None):
        if self.fail:
            raise RuntimeError("Conexão com OpenRouter falhou")
        return self.domain, self.confidence


async def test_classify_com_jev_sucesso():
    fake_client = _FakeOpenRouterJevClient(domain="vendas", confidence=0.92)
    result = await classify(
        message="Quero saber o valor do plano",
        provider="jev_openrouter",
        external_client=fake_client,
    )
    assert result.domain == "vendas"
    assert result.confidence == 0.92
    assert result.complexity == "baixa"
    # Fix (revisão final, achado importante 1): sucesso do Jev deve marcar
    # o provedor efetivo como "jev_openrouter" — é este campo (não o
    # parâmetro `provider` pedido pelo chamador) que o orchestrator usa para
    # popular `RouterDecision.router_provider`.
    assert result.provider_efetivo == "jev_openrouter"


async def test_classify_com_jev_fallback_em_falha():
    fake_client = _FakeOpenRouterJevClient(fail=True)
    # Deve degradar para a heurística sem estourar exceção
    result = await classify(
        message="Qual o preço desse produto?",
        provider="jev_openrouter",
        external_client=fake_client,
    )
    # Heurística reconhece "preço" como vendas. Confidence fixo em 0.3: o
    # fallback do Jev cai em `_classify_heuristic_fallback` (não no
    # short-circuit de match direto de `classify()`, que usaria 0.6).
    assert result.domain == "vendas"
    assert result.confidence == 0.3
    # Fix (revisão final, achado importante 1): mesmo com `provider`
    # pedido="jev_openrouter", a falha degrada o campo `provider_efetivo`
    # para "heuristica_llm" — é o que aconteceu de fato, não o que foi
    # pedido. Regressão específica do bug corrigido nesta rodada: sem isso,
    # a telemetria (RouterDecision/ChatDoneEventData) atribuiria ao Jev uma
    # resposta que na verdade veio da heurística local.
    assert result.provider_efetivo == "heuristica_llm"


async def test_classify_com_jev_sem_external_client_cai_para_heuristica():
    result = await classify(
        message="Qual o preço desse produto?",
        provider="jev_openrouter",
        external_client=None,
    )
    assert result.domain == "vendas"
    assert result.confidence == 0.3
    assert result.provider_efetivo == "heuristica_llm"


async def test_classify_com_jev_client_sem_metodo_cai_para_heuristica():
    class _ClienteIncompativel:
        pass

    result = await classify(
        message="Qual o preço desse produto?",
        provider="jev_openrouter",
        external_client=_ClienteIncompativel(),
    )
    assert result.domain == "vendas"
    assert result.confidence == 0.3
    assert result.provider_efetivo == "heuristica_llm"
