from datetime import timedelta

import pytest

from app.router.llm_client import LLMResponse
from app.router.tone_monitor import (
    analyze_tone,
    criar_escalonamento,
    ja_escalada,
    listar_escalonamentos,
    marcar_escalada,
    reset_escalated_conversations,
)


class _FakeLLMClient:
    def __init__(
        self, response: LLMResponse | None = None, exception: Exception | None = None
    ) -> None:
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
    def __init__(
        self,
        escalate: bool = False,
        confidence: float = 0.0,
        exception: Exception | None = None,
    ) -> None:
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
async def test_heuristica_processar_pagamento_nao_escala_como_falso_positivo():
    # Achado na revisão final (item 2, problema A): "processar" sozinho
    # (substring sem âncora) casava com português comercial neutro. Este
    # caso não deve bater a heurística — precisa cair no fallback LLM (que
    # aqui responde escalar=false).
    llm = _FakeLLMClient(
        LLMResponse(
            text='{"escalar": false, "motivo": null, "confianca": 0.05}', total_duration_ms=5.0
        )
    )
    resultado = await analyze_tone(
        message="Vocês conseguem processar o pagamento no cartão?",
        recent_messages=[],
        strategy_provider="heuristica_llm",
        llm_client=llm,
        external_client=None,
    )
    assert len(llm.prompts) == 1  # heurística não deve ter escalado sozinha
    assert resultado.escalate is False


@pytest.mark.asyncio
async def test_heuristica_processar_pedido_nao_escala_como_falso_positivo():
    llm = _FakeLLMClient(
        LLMResponse(
            text='{"escalar": false, "motivo": null, "confianca": 0.05}', total_duration_ms=5.0
        )
    )
    resultado = await analyze_tone(
        message="Quanto tempo leva para processar meu pedido?",
        recent_messages=[],
        strategy_provider="heuristica_llm",
        llm_client=llm,
        external_client=None,
    )
    assert len(llm.prompts) == 1
    assert resultado.escalate is False


@pytest.mark.asyncio
async def test_heuristica_processar_nota_fiscal_nao_escala_como_falso_positivo():
    llm = _FakeLLMClient(
        LLMResponse(
            text='{"escalar": false, "motivo": null, "confianca": 0.05}', total_duration_ms=5.0
        )
    )
    resultado = await analyze_tone(
        message="Preciso processar a nota fiscal desse pedido, pode ajudar?",
        recent_messages=[],
        strategy_provider="heuristica_llm",
        llm_client=llm,
        external_client=None,
    )
    assert len(llm.prompts) == 1
    assert resultado.escalate is False


@pytest.mark.asyncio
async def test_heuristica_ameaca_juridica_explicita_ainda_escala_como_insatisfacao():
    # Forma inequívoca ("vou processar" / "processar vocês") continua
    # escalando sem chamar o LLM, como antes.
    llm = _FakeLLMClient()
    resultado = await analyze_tone(
        message="Vou processar vocês na justiça por isso",
        recent_messages=[],
        strategy_provider="heuristica_llm",
        llm_client=llm,
        external_client=None,
    )
    assert resultado.escalate is True
    assert resultado.motivo == "insatisfacao"
    assert llm.prompts == []


@pytest.mark.asyncio
async def test_heuristica_sku_curto_maiusculo_nao_escala_como_falso_positivo():
    # Achado na revisão final (item 2, problema B): um código de produto
    # curto colado na conversa batia o limiar de caracteres/proporção
    # maiúscula sem ser, de fato, uma frase em caixa alta. Com o requisito
    # adicional de >= 3 palavras, este caso deve cair no fallback LLM.
    llm = _FakeLLMClient(
        LLMResponse(
            text='{"escalar": false, "motivo": null, "confianca": 0.05}', total_duration_ms=5.0
        )
    )
    resultado = await analyze_tone(
        message="SKU ABCD-1234-EFGH",
        recent_messages=[],
        strategy_provider="heuristica_llm",
        llm_client=llm,
        external_client=None,
    )
    assert len(llm.prompts) == 1
    assert resultado.escalate is False


@pytest.mark.asyncio
async def test_heuristica_frase_longa_em_caixa_alta_ainda_escala_como_urgencia():
    # Frase real de várias palavras em caixa alta continua sendo lida como
    # sinal estrutural de urgência (sem depender de "!!!").
    llm = _FakeLLMClient()
    resultado = await analyze_tone(
        message="ISSO AQUI NUNCA FUNCIONA DIREITO",
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
async def test_fallback_llm_erro_de_conexao_degrada_sem_propagar():
    # Achado na integração da Task 7 (chat.py): antes do fix, uma
    # ConnectionError do backend local (ex.: Ollama fora do ar) durante o
    # fallback heuristica_llm propagava crua em vez de degradar como já
    # acontece para JSON não-parseável — violando a mesma promessa de
    # "nunca derruba a mensagem do usuário" que _analyze_with_jev já cumpre
    # com seu `except Exception` (ver docstring de ToneResult).
    llm = _FakeLLMClient(exception=ConnectionError("ollama fora do ar"))
    resultado = await analyze_tone(
        message="Mensagem ambígua qualquer",
        recent_messages=[],
        strategy_provider="heuristica_llm",
        llm_client=llm,
        external_client=None,
    )
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


@pytest.mark.asyncio
async def test_criar_escalonamento_persiste_e_retorna_o_registro(db_session):
    registro = await criar_escalonamento(
        db_session,
        conversation_id="conv-1",
        mensagem="preciso falar com um atendente AGORA",
        motivo="urgencia",
        confianca=0.9,
        provider_efetivo="heuristica_llm",
    )

    assert registro.id is not None
    assert registro.conversation_id == "conv-1"
    assert registro.motivo == "urgencia"


@pytest.mark.asyncio
async def test_criar_escalonamento_trunca_mensagem_muito_longa(db_session):
    mensagem_longa = "x" * 5000

    registro = await criar_escalonamento(
        db_session,
        conversation_id="conv-1",
        mensagem=mensagem_longa,
        motivo="urgencia",
        confianca=0.9,
        provider_efetivo="heuristica_llm",
    )

    assert len(registro.mensagem) == 2000


@pytest.mark.asyncio
async def test_listar_escalonamentos_ordena_mais_recente_primeiro(db_session):
    primeiro = await criar_escalonamento(
        db_session,
        conversation_id="conv-a",
        mensagem="primeira",
        motivo="urgencia",
        confianca=0.9,
        provider_efetivo="heuristica_llm",
    )
    # Empurra o primeiro registro 1s pro passado em vez de dormir o teste —
    # server_default=now() do SQLite só tem precisão de segundo, então dois
    # inserts no mesmo segundo empatariam sem isso (achado na revisão final).
    primeiro.criado_em -= timedelta(seconds=1)
    await db_session.commit()
    await criar_escalonamento(
        db_session,
        conversation_id="conv-b",
        mensagem="segunda",
        motivo="insatisfacao",
        confianca=0.8,
        provider_efetivo="jev_openrouter",
    )

    resultado = await listar_escalonamentos(db_session)

    assert [r.conversation_id for r in resultado] == ["conv-b", "conv-a"]


@pytest.mark.asyncio
async def test_listar_escalonamentos_respeita_limit(db_session):
    for i in range(3):
        await criar_escalonamento(
            db_session,
            conversation_id=f"conv-{i}",
            mensagem="msg",
            motivo="urgencia",
            confianca=0.5,
            provider_efetivo="heuristica_llm",
        )

    resultado = await listar_escalonamentos(db_session, limit=2)

    assert len(resultado) == 2
