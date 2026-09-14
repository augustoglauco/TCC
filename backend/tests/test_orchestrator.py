import json
import logging

import pytest

from app.logging_config import JsonFormatter
from app.router.llm_client import LLMResponse
from app.router.orchestrator import (
    ExternalBackendIndisponivelError,
    LocalBackendIndisponivelError,
    handle_message,
)
from app.router.rag_client import Document, RAGConnectionError


class _FakeLLMClient:
    def __init__(
        self, response: LLMResponse | None = None, exception: Exception | None = None
    ) -> None:
        self._response = response
        self._exception = exception
        self.calls = 0
        self.last_prompt: str | None = None

    async def generate(self, prompt: str) -> LLMResponse:
        self.calls += 1
        self.last_prompt = prompt
        if self._exception is not None:
            raise self._exception
        assert self._response is not None
        return self._response


class _FakeRAGClient:
    def __init__(
        self, documents: list[Document] | None = None, exception: Exception | None = None
    ) -> None:
        self._documents = documents if documents is not None else []
        self._exception = exception

    async def search(self, query: str, domain: str) -> list[Document]:
        if self._exception is not None:
            raise self._exception
        return self._documents


def _resposta_local() -> LLMResponse:
    return LLMResponse(text="resposta local", total_duration_ms=100.0)


def _resposta_externa() -> LLMResponse:
    return LLMResponse(text="resposta externa", total_duration_ms=200.0)


async def test_agendamento_sempre_local():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient()

    decisao = await handle_message(
        "quero agendar uma visita",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )

    assert decisao.domain == "agendamento"
    assert decisao.backend_escolhido == "local"
    assert decisao.motivo_escalonamento == "nenhum"
    assert local_client.calls == 1
    assert external_client.calls == 0


async def test_fora_escopo_sempre_externo_sem_tentar_rag():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(exception=RAGConnectionError("não deveria ser chamado"))

    decisao = await handle_message(
        "Qual a capital da França?",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )

    assert decisao.domain == "fora_escopo"
    assert decisao.backend_escolhido == "externo"
    assert decisao.motivo_escalonamento == "fora_escopo"
    assert local_client.calls == 0
    assert external_client.calls == 1


async def test_rag_vazio_escala_para_externo():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(documents=[])

    decisao = await handle_message(
        "Qual o preço desse produto?",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )

    assert decisao.domain == "vendas"
    assert decisao.backend_escolhido == "externo"
    assert decisao.motivo_escalonamento == "rag_vazio"


async def test_rag_com_resultado_e_complexidade_baixa_fica_local():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(documents=[Document(content="...", source="catalogo", score=0.9)])

    decisao = await handle_message(
        "Qual o preço desse produto?",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )

    assert decisao.backend_escolhido == "local"
    assert decisao.motivo_escalonamento == "nenhum"


async def test_documento_recuperado_pelo_rag_e_injetado_no_prompt_do_llm():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    documento = Document(
        content="O gerador GD-30 tem potência de 30 kVA.",
        source="catalogo_geradores.txt",
        score=0.9,
    )
    rag_client = _FakeRAGClient(documents=[documento])

    await handle_message(
        "Qual o preço do gerador GD-30?",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )

    assert local_client.calls == 1
    assert documento.content in local_client.last_prompt
    assert "Qual o preço do gerador GD-30?" in local_client.last_prompt


async def test_rag_vazio_nao_injeta_contexto_prompt_e_a_mensagem_original():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(documents=[])

    await handle_message(
        "Qual o preço desse produto?",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )

    # Sem documentos, o prompt enviado ao LLM é a própria mensagem do
    # cliente — sem o texto de instrução extra do `_build_prompt`.
    assert external_client.last_prompt == "Qual o preço desse produto?"


async def test_rag_com_resultado_e_complexidade_alta_escala_para_externo():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(documents=[Document(content="...", source="catalogo", score=0.9)])

    mensagem_longa = "Preciso de um orçamento detalhado. " * 10 + " qual o preço?"

    decisao = await handle_message(
        mensagem_longa,
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )

    assert decisao.backend_escolhido == "externo"
    assert decisao.motivo_escalonamento == "complexidade_alta"


async def test_rag_indisponivel_propaga_erro_sem_fallback_para_externo():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(exception=RAGConnectionError("qdrant fora do ar"))

    with pytest.raises(RAGConnectionError):
        await handle_message(
            "Qual o preço desse produto?",
            recent_messages=[],
            local_client=local_client,
            external_client=external_client,
            rag_client=rag_client,
            complexity_strategy="heuristic",
        )

    assert external_client.calls == 0


async def test_ollama_indisponivel_nao_faz_fallback_para_externo():
    local_client = _FakeLLMClient(exception=ConnectionError("ollama fora do ar"))
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient()

    with pytest.raises(LocalBackendIndisponivelError):
        await handle_message(
            "quero agendar uma visita",
            recent_messages=[],
            local_client=local_client,
            external_client=external_client,
            rag_client=rag_client,
            complexity_strategy="heuristic",
        )

    assert external_client.calls == 0


async def test_falha_do_local_na_classificacao_llm_nao_faz_fallback_para_externo():
    # Regressão: com strategy="llm" o classificador chama o backend local.
    # Se o Ollama estiver fora do ar, isso é falha de infraestrutura local e
    # deve virar LocalBackendIndisponivelError — nunca degradar em silêncio
    # para fora_escopo (que rotearia para o backend externo).
    local_client = _FakeLLMClient(exception=ConnectionError("ollama fora do ar"))
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient()

    with pytest.raises(LocalBackendIndisponivelError):
        await handle_message(
            "Qual a capital da França?",
            recent_messages=[],
            local_client=local_client,
            external_client=external_client,
            rag_client=rag_client,
            complexity_strategy="llm",
        )

    assert external_client.calls == 0


async def test_log_de_decisao_tem_campos_json_de_primeiro_nivel(caplog):
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient()

    with caplog.at_level(logging.INFO, logger="app.router.orchestrator"):
        await handle_message(
            "quero agendar uma visita",
            recent_messages=[],
            local_client=local_client,
            external_client=external_client,
            rag_client=rag_client,
            complexity_strategy="heuristic",
        )

    registros = [r for r in caplog.records if r.getMessage() == "router_decision"]
    assert len(registros) == 1

    payload = json.loads(JsonFormatter().format(registros[0]))

    assert payload["message"] == "router_decision"
    assert payload["domain"] == "agendamento"
    assert payload["backend_escolhido"] == "local"
    assert payload["motivo_escalonamento"] == "nenhum"
    assert payload["custo_estimado_usd"] == 0.0
    assert payload["latencia_ms"] == 100.0


def test_json_formatter_nao_deixa_extra_sobrescrever_campos_base():
    record = logging.LogRecord(
        name="app.router.orchestrator",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="router_decision",
        args=(),
        exc_info=None,
    )
    record.router = {"message": "invasor", "level": "invasor", "domain": "vendas"}

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "router_decision"
    assert payload["level"] == "INFO"
    assert payload["domain"] == "vendas"


async def test_openrouter_indisponivel_propaga_erro():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(exception=ConnectionError("openrouter fora do ar"))
    rag_client = _FakeRAGClient()

    with pytest.raises(ExternalBackendIndisponivelError):
        await handle_message(
            "Qual a capital da França?",
            recent_messages=[],
            local_client=local_client,
            external_client=external_client,
            rag_client=rag_client,
            complexity_strategy="heuristic",
        )
