import json
import logging

import pytest

from app.logging_config import JsonFormatter
from app.models.chat import RagChunkMetric
from app.router.llm_client import LLMResponse, LLMStreamChunk
from app.router.orchestrator import (
    ExternalBackendIndisponivelError,
    LocalBackendIndisponivelError,
    RouterDecision,
    StatusEvent,
    TokenEvent,
    handle_message,
)
from app.router.rag_client import Document, RAGConnectionError


class _FakeLLMClient:
    def __init__(
        self,
        response: LLMResponse | None = None,
        exception: Exception | None = None,
        model_ready: bool = True,
        model_ready_exception: Exception | None = None,
    ) -> None:
        self._response = response
        self._exception = exception
        self._model_ready = model_ready
        self._model_ready_exception = model_ready_exception
        self.calls = 0
        self.last_prompt: str | None = None

    async def generate(self, prompt: str) -> LLMResponse:
        self.calls += 1
        self.last_prompt = prompt
        if self._exception is not None:
            raise self._exception
        assert self._response is not None
        return self._response

    async def is_model_ready(self) -> bool:
        if self._model_ready_exception is not None:
            raise self._model_ready_exception
        return self._model_ready

    async def generate_stream(self, prompt: str):
        self.calls += 1
        self.last_prompt = prompt
        if self._exception is not None:
            raise self._exception
        assert self._response is not None
        if self._response.text:
            yield LLMStreamChunk(text=self._response.text)
        yield LLMStreamChunk(
            done=True,
            prompt_tokens=self._response.prompt_tokens,
            completion_tokens=self._response.completion_tokens,
            total_duration_ms=self._response.total_duration_ms,
            load_duration_ms=self._response.load_duration_ms,
            prompt_eval_duration_ms=self._response.prompt_eval_duration_ms,
            eval_duration_ms=self._response.eval_duration_ms,
            estimated_cost_usd=self._response.estimated_cost_usd,
            model_name=self._response.model_name,
        )


class _FakeRAGClient:
    def __init__(
        self,
        documents: list[Document] | None = None,
        documents_sequence: list[list[Document]] | None = None,
        exception: Exception | None = None,
    ) -> None:
        self._documents = documents if documents is not None else []
        self._documents_sequence = documents_sequence
        self._exception = exception
        self.queries: list[str] = []

    async def search(self, query: str, domain: str) -> list[Document]:
        self.queries.append(query)
        if self._exception is not None:
            raise self._exception
        if self._documents_sequence is not None:
            index = len(self.queries) - 1
            if index < len(self._documents_sequence):
                return self._documents_sequence[index]
            return self._documents_sequence[-1]
        return self._documents


def _resposta_local() -> LLMResponse:
    return LLMResponse(text="resposta local", total_duration_ms=100.0)


def _resposta_externa() -> LLMResponse:
    return LLMResponse(text="resposta externa", total_duration_ms=200.0)


async def _coletar_eventos(message, **kwargs):
    return [evento async for evento in handle_message(message, **kwargs)]


async def test_agendamento_sempre_local():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient()

    eventos = await _coletar_eventos(
        "quero agendar uma visita",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )
    decisao = eventos[-1]
    assert isinstance(decisao, RouterDecision)

    assert decisao.domain == "agendamento"
    assert decisao.backend_escolhido == "local"
    assert decisao.motivo_escalonamento == "nenhum"
    assert local_client.calls == 1
    assert external_client.calls == 0


async def test_ttft_usa_prompt_eval_duration_nao_load_duration():
    # `load_duration` é o tempo de carregar o MODELO na memória (~0 após o
    # primeiro uso) — não deve ser usado como TTFT. `prompt_eval_duration` é
    # o proxy correto (tempo de processar o prompt antes de gerar tokens).
    resposta = LLMResponse(
        text="resposta local",
        completion_tokens=100,
        total_duration_ms=2500.0,
        load_duration_ms=500.0,
        prompt_eval_duration_ms=150.0,
        eval_duration_ms=1800.0,
    )
    local_client = _FakeLLMClient(response=resposta)
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient()

    eventos = await _coletar_eventos(
        "quero agendar uma visita",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )
    decisao = eventos[-1]
    assert isinstance(decisao, RouterDecision)

    assert decisao.ttft_ms == 150.0
    # TPS usa eval_duration (geração pura): 100 tokens / 1.8s = 55.56
    assert decisao.tps == pytest.approx(55.56, abs=0.01)


async def test_fora_escopo_sempre_externo_sem_tentar_rag():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(exception=RAGConnectionError("não deveria ser chamado"))

    eventos = await _coletar_eventos(
        "Qual a capital da França?",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )
    decisao = eventos[-1]
    assert isinstance(decisao, RouterDecision)

    assert decisao.domain == "fora_escopo"
    assert decisao.backend_escolhido == "externo"
    assert decisao.motivo_escalonamento == "fora_escopo"
    assert local_client.calls == 0
    assert external_client.calls == 1


async def test_rag_vazio_escala_para_externo():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(documents=[])

    eventos = await _coletar_eventos(
        "Qual o preço desse produto?",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )
    decisao = eventos[-1]
    assert isinstance(decisao, RouterDecision)

    assert decisao.domain == "vendas"
    assert decisao.backend_escolhido == "externo"
    assert decisao.motivo_escalonamento == "rag_vazio"


async def test_rag_vazio_sem_historico_nao_tenta_de_novo():
    # Primeira mensagem da conversa (recent_messages vazio) — não há
    # contexto pra concatenar, então só uma busca deve ocorrer (mesmo
    # comportamento de antes desta mudança).
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(documents=[])

    eventos = await _coletar_eventos(
        "Qual o preço desse produto?",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )
    decisao = eventos[-1]
    assert isinstance(decisao, RouterDecision)

    assert decisao.motivo_escalonamento == "rag_vazio"
    assert rag_client.queries == ["Qual o preço desse produto?"]


async def test_rag_vazio_com_historico_tenta_de_novo_com_contexto_e_acha():
    # Mensagem de acompanhamento ("quais outras opções?") sozinha não bate
    # com nada no RAG — a segunda tentativa, com o histórico concatenado,
    # encontra o documento e mantém a resposta local (regressão do bug
    # relatado: "perguntei sobre câmeras, [...] perguntei sobre outras
    # opções e ele simplesmente roteou para externo").
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    documento = Document(content="câmera VHD 5830", source="catalogo", score=0.8)
    rag_client = _FakeRAGClient(documents_sequence=[[], [documento]])

    # MVP: precisa de uma palavra-chave (aqui "produto") pra classificação
    # heurística acertar o domínio "vendas" sem depender de uma chamada real
    # de LLM — o ponto do teste é o fallback de RAG, não o classificador.
    eventos = await _coletar_eventos(
        "quais outras opções de produto vocês têm?",
        recent_messages=["você teria alguma câmera de boa resolução?"],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )
    decisao = eventos[-1]
    assert isinstance(decisao, RouterDecision)

    assert decisao.backend_escolhido == "local"
    assert decisao.motivo_escalonamento == "nenhum"
    assert rag_client.queries == [
        "quais outras opções de produto vocês têm?",
        "você teria alguma câmera de boa resolução?\nquais outras opções de produto vocês têm?",
    ]


async def test_rag_com_resultado_na_primeira_busca_nao_tenta_de_novo():
    # Busca direta já encontrou algo — não deve concatenar o histórico e
    # gastar uma segunda busca (evita diluir o embedding sem necessidade).
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    documento = Document(content="...", source="catalogo", score=0.9)
    rag_client = _FakeRAGClient(documents=[documento])

    eventos = await _coletar_eventos(
        "Qual o preço desse produto?",
        recent_messages=["mensagem anterior qualquer"],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )
    decisao = eventos[-1]
    assert isinstance(decisao, RouterDecision)

    assert decisao.motivo_escalonamento == "nenhum"
    assert rag_client.queries == ["Qual o preço desse produto?"]


async def test_rag_com_resultado_e_complexidade_baixa_fica_local():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(documents=[Document(content="...", source="catalogo", score=0.9)])

    eventos = await _coletar_eventos(
        "Qual o preço desse produto?",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )
    decisao = eventos[-1]
    assert isinstance(decisao, RouterDecision)

    assert decisao.backend_escolhido == "local"
    assert decisao.motivo_escalonamento == "nenhum"
    assert decisao.rag_chunks == [RagChunkMetric(source="catalogo", score=0.9)]


async def test_documento_recuperado_pelo_rag_e_injetado_no_prompt_do_llm():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    documento = Document(
        content="O gerador GD-30 tem potência de 30 kVA.",
        source="catalogo_geradores.txt",
        score=0.9,
    )
    rag_client = _FakeRAGClient(documents=[documento])

    await _coletar_eventos(
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

    await _coletar_eventos(
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

    eventos = await _coletar_eventos(
        mensagem_longa,
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )
    decisao = eventos[-1]
    assert isinstance(decisao, RouterDecision)

    assert decisao.backend_escolhido == "externo"
    assert decisao.motivo_escalonamento == "complexidade_alta"


async def test_rag_indisponivel_propaga_erro_sem_fallback_para_externo():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(exception=RAGConnectionError("qdrant fora do ar"))

    with pytest.raises(RAGConnectionError):
        await _coletar_eventos(
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
        await _coletar_eventos(
            "quero agendar uma visita",
            recent_messages=[],
            local_client=local_client,
            external_client=external_client,
            rag_client=rag_client,
            complexity_strategy="heuristic",
        )

    assert external_client.calls == 0


async def test_falha_de_rede_em_is_model_ready_vira_local_backend_indisponivel():
    # Regressão: `is_model_ready()` faz uma chamada de rede (ex.: GET
    # /api/ps do Ollama) tão sujeita a falha de infraestrutura quanto
    # `generate_stream` — antes da correção, uma falha aqui propagava crua
    # em vez de virar LocalBackendIndisponivelError (e, no endpoint HTTP, em
    # vez de virar o evento SSE `error`).
    local_client = _FakeLLMClient(
        response=_resposta_local(), model_ready_exception=ConnectionError("ollama fora do ar")
    )
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient()

    with pytest.raises(LocalBackendIndisponivelError):
        await _coletar_eventos(
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
        await _coletar_eventos(
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
        await _coletar_eventos(
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


async def test_generate_stream_sem_chunk_final_vira_local_backend_indisponivel():
    # Regressão: se `generate_stream` esgotar sem nunca emitir um chunk
    # `done=True` (ex.: Ollama fecha a conexão no meio do cold-start), antes
    # da correção isso escapava como `AssertionError` cru em vez de virar
    # `LocalBackendIndisponivelError` (e, no endpoint HTTP, o evento SSE
    # `error`).
    class _StreamSemChunkFinal:
        def __init__(self) -> None:
            self.calls = 0

        async def is_model_ready(self) -> bool:
            return True

        async def generate_stream(self, prompt: str):
            self.calls += 1
            yield LLMStreamChunk(text="parcial")
            return
            yield  # pragma: no cover - nunca alcançado, só p/ ser async generator

    local_client = _StreamSemChunkFinal()
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient()

    with pytest.raises(LocalBackendIndisponivelError):
        await _coletar_eventos(
            "quero agendar uma visita",
            recent_messages=[],
            local_client=local_client,
            external_client=external_client,
            rag_client=rag_client,
            complexity_strategy="heuristic",
        )

    assert external_client.calls == 0


async def test_openrouter_indisponivel_propaga_erro():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(exception=ConnectionError("openrouter fora do ar"))
    rag_client = _FakeRAGClient()

    with pytest.raises(ExternalBackendIndisponivelError):
        await _coletar_eventos(
            "Qual a capital da França?",
            recent_messages=[],
            local_client=local_client,
            external_client=external_client,
            rag_client=rag_client,
            complexity_strategy="heuristic",
        )


async def test_modelo_local_nao_carregado_emite_status_antes_dos_tokens():
    local_client = _FakeLLMClient(response=_resposta_local(), model_ready=False)
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient()

    eventos = await _coletar_eventos(
        "quero agendar uma visita",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )

    assert isinstance(eventos[0], StatusEvent)
    assert eventos[0].status == "carregando_modelo"


async def test_modelo_local_ja_carregado_nao_emite_status():
    local_client = _FakeLLMClient(response=_resposta_local(), model_ready=True)
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient()

    eventos = await _coletar_eventos(
        "quero agendar uma visita",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )

    assert not any(isinstance(e, StatusEvent) for e in eventos)


async def test_modelo_carrega_durante_classificacao_llm_ainda_assim_emite_status():
    # Reproduz o bug relatado pelo usuário: com strategy="llm", quando a
    # mensagem é ambígua para o classificador por palavra-chave,
    # `classify()` chama `local_client.generate()` (bloqueante) — no Ollama
    # real, é essa chamada (não a geração da resposta em si) que
    # efetivamente paga o cold-start do modelo. Antes desta correção, o
    # único check de `is_model_ready()` ficava logo antes de
    # `generate_stream`, ou seja, DEPOIS do cold-start já ter acontecido em
    # silêncio durante a classificação — o evento `status` nunca era
    # emitido, mesmo a espera real tendo ocorrido (é o que o Fake abaixo
    # simula: `is_model_ready` só volta a `True` depois da primeira
    # chamada, igual o Ollama depois que `generate()` carrega o modelo).
    class _FakeLLMClientCargaNaClassificacao(_FakeLLMClient):
        async def is_model_ready(self) -> bool:
            return self.calls > 0

    local_client = _FakeLLMClientCargaNaClassificacao(
        response=LLMResponse(
            text='{"domain": "suporte", "complexity": "baixa", "confidence": 0.9}',
            total_duration_ms=100.0,
        )
    )
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(documents=[Document(content="...", source="catalogo", score=0.9)])

    eventos = await _coletar_eventos(
        "Qual a capital da França?",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="llm",
    )

    assert isinstance(eventos[0], StatusEvent)
    assert eventos[0].status == "carregando_modelo"


async def test_tokens_emitidos_em_ordem_e_resposta_final_e_a_concatenacao():
    local_client = _FakeLLMClient(response=LLMResponse(text="Boa tarde!", total_duration_ms=50.0))
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient()

    eventos = await _coletar_eventos(
        "quero agendar uma visita",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )

    tokens = [e for e in eventos if isinstance(e, TokenEvent)]
    assert len(tokens) == 1
    assert tokens[0].text == "Boa tarde!"
    assert eventos[-1].resposta == "Boa tarde!"
