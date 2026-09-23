import pytest

from app.router.llm_client import LLMResponse
from app.router.tone_monitor import (
    ToneResult,
    analyze_tone,
    ja_escalada,
    marcar_escalada,
    reset_escalated_conversations,
)


class _FakeLLMClient:
    def __init__(self, response: LLMResponse | None = None, exception: Exception | None = None) -> None:
        self._response = response
        self._exception = exception
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> LLMResponse:
        self.prompts.append(prompt)
        if self._exception is not None:
            raise self._exception
        assert self._response is not None
        return self._response


class _FakeJevClient:
    def __init__(self, escalate: bool = False, confidence: float = 0.0, exception: Exception | None = None) -> None:
        self._escalate = escalate
        self._confidence = confidence
        self._exception = exception

    async def classify_tone_jev(self, message: str, recent_messages: list[str] | None = None):
        if self._exception is not None:
            raise self._exception
        return self._escalate, self._confidence


@pytest.mark.asyncio
async def test_heuristica_palavra_chave_de_insatisfacao_escala_sem_chamar_llm():
    llm = _FakeLLMClient()
    resultado = await analyze_tone(
        message="Isso é um absurdo, nunca mais compro nessa loja",
        recent_messages=[],
        strategy_provider="heuristica_llm",
        llm_client=llm,
        external_client=None,
    )
    assert resultado.escalate is True
    assert resultado.motivo == "insatisfacao"
    assert resultado.provider_efetivo == "heuristica_llm"
    assert llm.prompts == []


@pytest.mark.asyncio
async def test_heuristica_maiusculas_e_exclamacao_escala_como_urgencia():
    llm = _FakeLLMClient()
    resultado = await analyze_tone(
        message="PRECISO FALAR COM ALGUEM AGORA!!!",
        recent_messages=[],
        strategy_provider="heuristica_llm",
        llm_client=llm,
        external_client=None,
    )
    assert resultado.escalate is True
    assert resultado.motivo == "urgencia"
    assert llm.prompts == []


@pytest.mark.asyncio
async def test_mensagem_neutra_cai_no_fallback_llm_local():
    llm = _FakeLLMClient(
        LLMResponse(
            text='{"escalar": false, "motivo": null, "confianca": 0.1}', total_duration_ms=5.0
        )
    )
    resultado = await analyze_tone(
        message="Qual o horário de funcionamento da loja?",
        recent_messages=[],
        strategy_provider="heuristica_llm",
        llm_client=llm,
        external_client=None,
    )
    assert resultado.escalate is False
    assert resultado.motivo is None
    assert resultado.provider_efetivo == "heuristica_llm"
    assert len(llm.prompts) == 1


@pytest.mark.asyncio
async def test_fallback_llm_escala_quando_modelo_reporta_true():
    llm = _FakeLLMClient(
        LLMResponse(
            text='{"escalar": true, "motivo": "urgencia", "confianca": 0.8}', total_duration_ms=5.0
        )
    )
    resultado = await analyze_tone(
        message="Isso está demorando muito, quando vai resolver?",
        recent_messages=[],
        strategy_provider="heuristica_llm",
        llm_client=llm,
        external_client=None,
    )
    assert resultado.escalate is True
    assert resultado.motivo == "urgencia"
    assert resultado.confidence == 0.8


@pytest.mark.asyncio
async def test_fallback_llm_resposta_nao_parseavel_nao_escala():
    llm = _FakeLLMClient(LLMResponse(text="não é json", total_duration_ms=5.0))
    resultado = await analyze_tone(
        message="Mensagem ambígua qualquer",
        recent_messages=[],
        strategy_provider="heuristica_llm",
        llm_client=llm,
        external_client=None,
    )
    assert resultado.escalate is False
    assert resultado.provider_efetivo == "heuristica_llm"


@pytest.mark.asyncio
async def test_fallback_llm_motivo_invalido_degrada_com_validacao():
    # LLM hallucinates invalid motivo value (e.g., "raiva" instead of "urgencia"/"insatisfacao")
    llm = _FakeLLMClient(
        LLMResponse(
            text='{"escalar": true, "motivo": "raiva", "confianca": 0.8}', total_duration_ms=5.0
        )
    )
    resultado = await analyze_tone(
        message="Mensagem com tom inválido",
        recent_messages=[],
        strategy_provider="heuristica_llm",
        llm_client=llm,
        external_client=None,
    )
    # Should catch pydantic ValidationError (ValueError subclass) and degrade to safe default
    assert resultado.escalate is False
    assert resultado.motivo is None
    assert resultado.confidence == 0.0
    assert resultado.provider_efetivo == "heuristica_llm"


@pytest.mark.asyncio
async def test_fallback_jev_sucesso_usa_provider_jev_openrouter():
    llm = _FakeLLMClient()
    jev = _FakeJevClient(escalate=True, confidence=0.9)
    resultado = await analyze_tone(
        message="Mensagem ambígua qualquer",
        recent_messages=[],
        strategy_provider="jev_openrouter",
        llm_client=llm,
        external_client=jev,
    )
    assert resultado.escalate is True
    assert resultado.provider_efetivo == "jev_openrouter"
    assert resultado.confidence == 0.9
    assert llm.prompts == []


@pytest.mark.asyncio
async def test_fallback_jev_falha_degrada_para_heuristica_llm_sem_escalar():
    llm = _FakeLLMClient()
    jev = _FakeJevClient(exception=TimeoutError("timeout"))
    resultado = await analyze_tone(
        message="Mensagem ambígua qualquer",
        recent_messages=[],
        strategy_provider="jev_openrouter",
        llm_client=llm,
        external_client=jev,
    )
    assert resultado.escalate is False
    assert resultado.provider_efetivo == "heuristica_llm"


@pytest.mark.asyncio
async def test_fallback_jev_sem_client_valido_degrada():
    llm = _FakeLLMClient()
    resultado = await analyze_tone(
        message="Mensagem ambígua qualquer",
        recent_messages=[],
        strategy_provider="jev_openrouter",
        llm_client=llm,
        external_client=None,
    )
    assert resultado.escalate is False
    assert resultado.provider_efetivo == "heuristica_llm"


def test_estado_de_conversa_marcar_e_consultar_escalada():
    reset_escalated_conversations()
    assert ja_escalada("conv-1") is False
    marcar_escalada("conv-1")
    assert ja_escalada("conv-1") is True
    assert ja_escalada("conv-2") is False
    reset_escalated_conversations()
    assert ja_escalada("conv-1") is False
