import asyncio
import base64
import json
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import MOCK_TOKEN_PREFIX
from app.api.chat import (
    _sse,
    get_calendar_client,
    get_clip_embedder,
    get_clip_store,
    get_complexity_strategy,
    get_external_client,
    get_local_client,
    get_rag_client,
    get_rag_client_admin,
    get_sales_catalog_client,
    get_scheduling_config,
    get_stt_client,
    get_tone_monitor_enabled,
)
from app.api.chat import router as chat_router
from app.db.models import Cliente, ClienteCompra, Conversa
from app.logging_config import ConversationIdFilter
from app.memory.store import listar_mensagens
from app.models.chat import CardAgendamento, CardCotacao, CardProduto, ChatDoneEventData
from app.rag.image_search import ImageSearchResult
from app.router.llm_client import LLMResponse, LLMStreamChunk
from app.router.rag_client import Document
from app.stt.whisper_client import SttIndisponivelError
from app.user_profile.classificacao import RESPOSTA_SO_EMAIL
from tests.conftest import _CommitFailingSession


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    eventos = []
    for bloco in body.split("\n\n"):
        if not bloco.strip():
            continue
        tipo = None
        dados = None
        for linha in bloco.split("\n"):
            if linha.startswith("event:"):
                tipo = linha[len("event:") :].strip()
            elif linha.startswith("data:"):
                dados = json.loads(linha[len("data:") :].strip())
        if tipo and dados is not None:
            eventos.append((tipo, dados))
    return eventos


def _find(eventos: list[tuple[str, dict]], tipo: str) -> dict:
    return next(dados for t, dados in eventos if t == tipo)


class _FakeLLMClient:
    def __init__(self, response: LLMResponse, vision_answer: str | None = None) -> None:
        self._response = response
        self.prompts: list[str] = []
        self._vision_answer = vision_answer
        self.vision_calls = 0
        self.temperature = None
        self.num_ctx = None
        self.top_p = None
        self.top_k = None
        self.repeat_penalty = None
        self.seed = None
        self.timeout_s = 30.0

    async def generate(self, prompt: str) -> LLMResponse:
        self.prompts.append(prompt)
        return self._response

    async def is_model_ready(self) -> bool:
        return True

    async def describe_image(self, image_bytes: bytes, prompt: str) -> str:
        self.vision_calls += 1
        # Sem resposta de visão configurada = comporta como modelo ausente.
        if self._vision_answer is None:
            from app.router.openrouter_client import VisionModelIndisponivelError

            raise VisionModelIndisponivelError("sem modelo de visão no teste")
        return self._vision_answer

    async def generate_stream(self, prompt: str):
        self.prompts.append(prompt)
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


class _FakeLLMClientComJev(_FakeLLMClient):
    """`_FakeLLMClient` com `classify_intent_jev` — para testar o caminho em
    que o Jev de fato responde (ao contrário do `_FakeLLMClient` puro, que
    não tem esse método e sempre degrada para a heurística dentro de
    `_classify_with_jev`). Ver Fix (revisão final, achado importante 1)."""

    def __init__(
        self,
        response: LLMResponse,
        jev_domain: str = "vendas",
        jev_confidence: float = 0.9,
        **kwargs,
    ) -> None:
        super().__init__(response, **kwargs)
        self._jev_domain = jev_domain
        self._jev_confidence = jev_confidence

    async def classify_intent_jev(self, message: str, recent_messages: list[str] | None = None):
        return self._jev_domain, self._jev_confidence


class _FakeClipStore:
    def __init__(self, results: list[ImageSearchResult] | None = None) -> None:
        self._results = results or []

    async def search_by_image(self, embedder, image_bytes, domain=None):
        return self._results


class _FakeRAGClient:
    def __init__(self, documents: list[Document] | None = None) -> None:
        self._documents = documents if documents is not None else []

    async def search(self, query: str, domain: str, **kwargs) -> list[Document]:
        return self._documents


class _FakeSttClient:
    def __init__(self, text: str = "", error: Exception | None = None) -> None:
        self._text = text
        self._error = error
        self.received_audio: list[bytes] = []

    async def transcribe(self, audio_bytes: bytes) -> str:
        self.received_audio.append(audio_bytes)
        if self._error is not None:
            raise self._error
        return self._text


class _SingleSessionMaker:
    """Fake de `db_sessionmaker` (achado no code-review, 2026-09-24: chat.py
    passou a abrir sua própria sessão via `request.app.state.db_sessionmaker`
    em vez de receber uma via `Depends`) — sempre devolve a MESMA sessão da
    fixture `db_session`, envolta num `async with` que não a fecha de
    verdade, pra permitir inspecionar o banco depois da requisição.
    """

    def __init__(self, session) -> None:
        self._session = session
        # Uma sessão só não aguenta uso simultâneo (a memória da conversa
        # grava enquanto a persistência do escalonamento roda em segundo
        # plano). Na aplicação cada `db_sessionmaker()` abre uma sessão
        # própria; aqui o lock faz os usos se revezarem.
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
def fakes(db_session):
    return {
        "local": _FakeLLMClient(LLMResponse(text="resposta local", total_duration_ms=10.0)),
        "external": _FakeLLMClient(LLMResponse(text="resposta externa", total_duration_ms=20.0)),
        "rag": _FakeRAGClient(documents=[Document(content="...", source="catalogo", score=0.9)]),
        "rag_admin": _FakeRAGClient(
            documents=[Document(content="...", source="admin_catalogo", score=0.9)]
        ),
        # MVP: STT não é exercitado por padrão nos testes que não enviam
        # `audio` — texto vazio nunca chega a ser usado nesses casos.
        "stt": _FakeSttClient(text=""),
        # Catálogo CLIP vazio por padrão — testes de identificação populam.
        "clip_store": _FakeClipStore(results=[]),
        "clip_embedder": object(),
        "db_session": db_session,
    }


def _build_app(fakes: dict, complexity_strategy: str = "heuristic") -> FastAPI:
    app = FastAPI()
    app.include_router(chat_router)
    app.dependency_overrides[get_local_client] = lambda: fakes["local"]
    app.dependency_overrides[get_external_client] = lambda: fakes["external"]
    app.dependency_overrides[get_rag_client] = lambda: fakes["rag"]
    app.dependency_overrides[get_rag_client_admin] = lambda: fakes["rag_admin"]
    app.dependency_overrides[get_stt_client] = lambda: fakes["stt"]
    app.dependency_overrides[get_clip_store] = lambda: fakes["clip_store"]
    app.dependency_overrides[get_clip_embedder] = lambda: fakes["clip_embedder"]
    app.dependency_overrides[get_complexity_strategy] = lambda: complexity_strategy
    # `calendar_client`/`scheduling_config` ausentes (None) preserva o
    # comportamento pré-Task 11 destes testes: o gate de agendamento em
    # `orchestrator.handle_message` (Task 9) só entra no fluxo de coleta de
    # slots quando ambos não são None — como estes testes não exercitam esse
    # fluxo (são cobertos nos testes do orchestrator/scheduling), manter None
    # aqui evita mudar silenciosamente o que "domain == agendamento" significa
    # nas asserções abaixo (resposta normal do LLM, não o fluxo de booking).
    app.dependency_overrides[get_calendar_client] = lambda: None
    app.dependency_overrides[get_scheduling_config] = lambda: None
    app.dependency_overrides[get_sales_catalog_client] = lambda: None
    app.state.db_sessionmaker = _SingleSessionMaker(fakes["db_session"])
    # Limiares lidos via request.app.state no fluxo de identificação.
    app.state.image_internal_confidence = 0.30
    app.state.image_external_confidence = 0.80
    return app


@pytest.fixture
def client(fakes):
    app = _build_app(fakes)
    with TestClient(app) as test_client:
        yield test_client


def test_envia_mensagem_de_texto_simples(client):
    response = client.post("/api/chat/messages", json={"message": "quero agendar uma visita"})

    assert response.status_code == 200
    eventos = _parse_sse(response.text)
    tipos = [tipo for tipo, _ in eventos]
    assert tipos[0] == "conversation"
    assert tipos[-1] == "done"

    dados_conversation = _find(eventos, "conversation")
    conversation_id = dados_conversation["conversation_id"]
    assert isinstance(conversation_id, str) and conversation_id

    dados_done = _find(eventos, "done")
    assert dados_done["domain"] == "agendamento"
    assert dados_done["backend_used"] == "local"
    assert dados_done["escalation_reason"] == "nenhum"

    textos_token = [dados["text"] for tipo, dados in eventos if tipo == "token"]
    assert "".join(textos_token) == "resposta local"


def test_done_traz_fonte_e_score_de_cada_chunk_do_rag(fakes):
    fakes["rag"] = _FakeRAGClient(
        documents=[
            Document(content="Câmera VHD 5830.", source="catalogo_cameras.txt", score=0.91),
            Document(content="Garantia de 12 meses.", source="politica_garantia.pdf", score=0.72),
        ]
    )
    app = _build_app(fakes)
    with TestClient(app) as test_client:
        response = test_client.post("/api/chat/messages", json={"message": "qual o preço?"})

    dados_done = _find(_parse_sse(response.text), "done")
    assert dados_done["rag_chunks"] == [
        {"source": "catalogo_cameras.txt", "score": 0.91},
        {"source": "politica_garantia.pdf", "score": 0.72},
    ]


async def test_auth_token_admin_valido_usa_rag_client_admin(client, fakes):
    """Decisão de 2026-09-30 (docs/ARCHITECTURE.md §6): com um `auth_token`
    que o servidor confirma pertencer a uma sessão Admin, o chat busca no
    RAG completo (`rag_client_admin`), não na collection ativa comum."""
    sessao = fakes["db_session"]
    admin = Cliente(email="admin@example.com", nome="Admin")
    sessao.add(admin)
    await sessao.commit()
    await sessao.refresh(admin)

    resposta = client.post(
        "/api/chat/messages",
        json={"message": "qual o preço?", "auth_token": f"{MOCK_TOKEN_PREFIX}{admin.id}"},
    )

    dados_done = _find(_parse_sse(resposta.text), "done")
    assert dados_done["rag_chunks"] == [{"source": "admin_catalogo", "score": 0.9}]


async def test_auth_token_de_cliente_comum_nao_usa_rag_client_admin(client, fakes):
    """Um `auth_token` válido, mas de um cliente sem perfil Admin, não liga
    o modo admin — mesma proteção que `user_email` sozinho nunca teve."""
    sessao = fakes["db_session"]
    cliente = Cliente(email="visitante@example.com", nome="Visitante")
    sessao.add(cliente)
    await sessao.commit()
    await sessao.refresh(cliente)

    resposta = client.post(
        "/api/chat/messages",
        json={"message": "qual o preço?", "auth_token": f"{MOCK_TOKEN_PREFIX}{cliente.id}"},
    )

    dados_done = _find(_parse_sse(resposta.text), "done")
    assert dados_done["rag_chunks"] == [{"source": "catalogo", "score": 0.9}]


def test_user_email_admin_sozinho_nao_liga_modo_admin(client):
    """Nunca confiar em `user_email` (livre, nunca validado) para liberar o
    RAG completo — só `auth_token` verificado pode fazer isso."""
    resposta = client.post(
        "/api/chat/messages",
        json={"message": "qual o preço?", "user_email": "admin@example.com"},
    )

    dados_done = _find(_parse_sse(resposta.text), "done")
    assert dados_done["rag_chunks"] == [{"source": "catalogo", "score": 0.9}]


def test_chat_stream_router_provider_reflete_fallback_do_jev(fakes):
    # Fix (revisão final, achado importante 1) — REGRESSÃO: com
    # `intent_router_provider="jev_openrouter"` pedido, mas o
    # `_FakeLLMClient` de `fakes["external"]` sem `classify_intent_jev`, o
    # classificador degrada para a heurística local (`jev_falha_fallback`).
    # `router_provider` no `done` deve refletir o que REALMENTE aconteceu
    # ("heuristica_llm"), não o que foi pedido — antes do fix, este teste
    # esperava (incorretamente) "jev_openrouter" aqui.
    app = _build_app(fakes)
    app.state.intent_router_provider = "jev_openrouter"
    with TestClient(app) as test_client:
        response = test_client.post("/api/chat/messages", json={"message": "olá"})

    dados_done = _find(_parse_sse(response.text), "done")
    assert dados_done["router_provider"] == "heuristica_llm"


def test_chat_stream_router_provider_jev_quando_client_sucede(fakes):
    # Contraparte do teste acima: quando o Jev de fato responde,
    # `router_provider` no `done` deve ser "jev_openrouter".
    fakes["external"] = _FakeLLMClientComJev(
        LLMResponse(text="resposta externa", total_duration_ms=20.0)
    )
    app = _build_app(fakes)
    app.state.intent_router_provider = "jev_openrouter"
    with TestClient(app) as test_client:
        response = test_client.post("/api/chat/messages", json={"message": "olá"})

    dados_done = _find(_parse_sse(response.text), "done")
    assert dados_done["router_provider"] == "jev_openrouter"


def test_chat_stream_router_provider_default_sem_app_state(client):
    # `_build_app` (fixture `client`) não define `app.state.intent_router_provider`
    # — a dependência precisa cair no default "heuristica_llm" (getattr com
    # fallback), não estourar AttributeError.
    response = client.post("/api/chat/messages", json={"message": "olá"})

    dados_done = _find(_parse_sse(response.text), "done")
    assert dados_done["router_provider"] == "heuristica_llm"


class _ListaHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def test_logs_do_roteador_saem_com_o_conversation_id_da_requisicao(client):
    # Mesmo filtro que `configure_logging` pendura no handler de produção.
    handler = _ListaHandler()
    handler.addFilter(ConversationIdFilter())
    logger = logging.getLogger("app.router.orchestrator")
    nivel_anterior = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        client.post(
            "/api/chat/messages",
            json={"message": "quero agendar uma visita", "conversation_id": "conv-log-1"},
        )
    finally:
        logger.removeHandler(handler)
        logger.setLevel(nivel_anterior)

    decisoes = [r for r in handler.records if r.getMessage() == "router_decision"]
    assert len(decisoes) == 1
    assert decisoes[0].conversation_id == "conv-log-1"


def test_conversation_id_mantem_historico_entre_chamadas(client):
    first = client.post("/api/chat/messages", json={"message": "quero agendar uma visita"})
    conversation_id = _find(_parse_sse(first.text), "conversation")["conversation_id"]

    # Mensagem isolada e ambígua para o classificador por palavra-chave (não
    # casa nenhum domínio sozinha); só resolve para "agendamento" se o
    # histórico da mensagem anterior for repassado como contexto recente ao
    # orchestrator — é isso que este teste verifica.
    second = client.post(
        "/api/chat/messages",
        json={"message": "pode ser amanhã às 10h", "conversation_id": conversation_id},
    )
    eventos_second = _parse_sse(second.text)
    assert _find(eventos_second, "conversation")["conversation_id"] == conversation_id
    assert _find(eventos_second, "done")["domain"] == "agendamento"

    # Sem conversation_id (conversa nova), a mesma mensagem isolada cai em
    # fora_escopo por falta de contexto — prova de que o histórico é o que
    # muda o resultado, não a heurística da mensagem em si.
    isolated = client.post("/api/chat/messages", json={"message": "pode ser amanhã às 10h"})
    assert _find(_parse_sse(isolated.text), "done")["domain"] == "fora_escopo"


async def test_troca_fica_gravada_na_memoria_da_conversa(client, fakes):
    client.post(
        "/api/chat/messages",
        json={"message": "quero agendar uma visita", "conversation_id": "conv-memoria-1"},
    )

    mensagens = await listar_mensagens(fakes["db_session"], "conv-memoria-1")

    # Mensagem do cliente E resposta completa do assistente, com o domínio
    # da resposta (usado depois pela classificação do usuário, R10).
    assert [(m.papel, m.texto, m.dominio) for m in mensagens] == [
        ("cliente", "quero agendar uma visita", None),
        ("assistente", "resposta local", "agendamento"),
    ]


def test_get_conversa_devolve_o_historico_gravado(client):
    client.post(
        "/api/chat/messages",
        json={"message": "quero agendar uma visita", "conversation_id": "conv-get-1"},
    )

    resposta = client.get("/api/chat/conversations/conv-get-1")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["conversation_id"] == "conv-get-1"
    assert [(m["papel"], m["texto"], m["dominio"]) for m in corpo["mensagens"]] == [
        ("cliente", "quero agendar uma visita", None),
        ("assistente", "resposta local", "agendamento"),
    ]
    # E-mail e perfil do visitante (R10) não saem por este endpoint.
    assert set(corpo) == {"conversation_id", "resumo", "mensagens"}


def test_get_conversa_devolve_as_metricas_de_cada_resposta(client):
    envio = client.post(
        "/api/chat/messages",
        json={"message": "quero agendar uma visita", "conversation_id": "conv-met-1"},
    )
    done = _find(_parse_sse(envio.text), "done")

    cliente, assistente = client.get("/api/chat/conversations/conv-met-1").json()["mensagens"]

    # As métricas gravadas são o próprio evento `done` — o painel ⚙️
    # reaparece igual nas mensagens recarregadas.
    assert assistente["metricas"] == done
    assert assistente["metricas"]["perfil_usuario"] == "lead"
    assert cliente["metricas"] is None


def test_get_conversa_inexistente_da_404(client):
    assert client.get("/api/chat/conversations/nao-existe").status_code == 404


def test_get_conversa_com_banco_fora_do_ar_da_503(fakes):
    class _SessaoQueFalha:
        def __call__(self):
            return self

        async def __aenter__(self):
            raise ConnectionError("postgres fora do ar")

        async def __aexit__(self, *exc_info) -> bool:
            return False

    app = _build_app(fakes)
    app.state.db_sessionmaker = _SessaoQueFalha()
    with TestClient(app) as client:
        assert client.get("/api/chat/conversations/conv-x").status_code == 503


def test_deletar_conversa_limpa_mensagens_e_retorna_204(client):
    msg_resp = client.post(
        "/api/chat/messages", json={"message": "Olá", "conversation_id": "conv-del-1"}
    )
    assert msg_resp.status_code == 200

    del_resp = client.delete("/api/chat/conversations/conv-del-1")
    assert del_resp.status_code == 204

    get_resp = client.get("/api/chat/conversations/conv-del-1")
    assert get_resp.status_code == 200
    assert get_resp.json()["mensagens"] == []
    assert get_resp.json()["resumo"] is None


def test_deletar_conversa_inexistente_da_404(client):
    assert client.delete("/api/chat/conversations/nao-existe").status_code == 404


def test_done_traz_o_perfil_lead_por_intencao_de_compra(client):
    resposta = client.post("/api/chat/messages", json={"message": "quero agendar uma visita"})

    done = _find(_parse_sse(resposta.text), "done")
    assert (done["perfil_usuario"], done["perfil_motivo"]) == ("lead", "intenção de compra")


async def test_done_traz_o_perfil_cliente_pelo_email_da_base(client, fakes):
    sessao = fakes["db_session"]
    ana = Cliente(email="ana.recorrente@example.com", nome="Ana")
    sessao.add(ana)
    await sessao.flush()
    agora = datetime.now(UTC)
    sessao.add_all(
        [
            ClienteCompra(
                cliente_id=ana.id,
                quantidade=1,
                valor_total=Decimal("100"),
                comprado_em=agora - timedelta(days=dias),
            )
            for dias in (30, 90)
        ]
    )
    await sessao.commit()

    resposta = client.post(
        "/api/chat/messages",
        json={"message": "meu gerador não funciona, meu e-mail é ana.recorrente@example.com"},
    )

    done = _find(_parse_sse(resposta.text), "done")
    assert done["perfil_usuario"] == "cliente"
    # Com o e-mail na própria mensagem, o assistente não é instruído a pedi-lo.
    assert "e-mail usado na compra" not in fakes["local"].prompts[-1]


def test_pos_venda_sem_email_instrui_o_assistente_a_pedir(client, fakes):
    client.post("/api/chat/messages", json={"message": "meu gerador não funciona"})

    assert "e-mail usado na compra" in fakes["local"].prompts[-1]


async def test_resumo_da_conversa_entra_no_prompt(client, fakes):
    fakes["db_session"].add(Conversa(id="conv-resumo-1", resumo="Cliente quer 2 geradores GD-15."))
    await fakes["db_session"].commit()

    client.post(
        "/api/chat/messages",
        json={"message": "quero agendar uma visita", "conversation_id": "conv-resumo-1"},
    )

    assert "Resumo da conversa até aqui" in fakes["local"].prompts[-1]
    assert "Cliente quer 2 geradores GD-15." in fakes["local"].prompts[-1]


def test_banco_fora_do_ar_nao_derruba_a_resposta(fakes, caplog):
    class _SessaoQueFalha:
        def __call__(self):
            return self

        async def __aenter__(self):
            raise ConnectionError("postgres fora do ar")

        async def __aexit__(self, *exc_info) -> bool:
            return False

    app = _build_app(fakes)
    app.state.db_sessionmaker = _SessaoQueFalha()
    with caplog.at_level(logging.WARNING, logger="app.api.chat"):
        with TestClient(app) as client:
            response = client.post(
                "/api/chat/messages", json={"message": "quero agendar uma visita"}
            )

    eventos = _parse_sse(response.text)
    assert "".join(dados["text"] for tipo, dados in eventos if tipo == "token") == (
        "resposta local"
    )
    assert _find(eventos, "done")["domain"] == "agendamento"
    # Uma linha ao carregar o contexto e outra ao gravar a troca.
    operacoes = [
        r.router["operacao"] for r in caplog.records if r.getMessage() == "memoria_indisponivel"
    ]
    assert operacoes == ["carregar", "registrar"]


def test_audio_e_transcrito_e_usado_como_mensagem(client, fakes):
    # A mensagem de texto ("ignorado") não deveria chegar ao LLM: quando há
    # áudio, o texto transcrito é a mensagem efetiva (ver comentário MVP em
    # `app.api.chat.send_message`).
    fakes["stt"] = _FakeSttClient(text="quero agendar uma visita")
    client.app.dependency_overrides[get_stt_client] = lambda: fakes["stt"]
    # Monitor de Tom (R8) também chamaria local_client.generate() (fallback
    # heuristica_llm) para a mensagem sem sinal heurístico forte, inflando a
    # contagem de prompts verificada abaixo — desligado aqui para isolar
    # especificamente o comportamento de transcrição de áudio que este teste
    # valida (mesmo padrão usado em test_orchestrator.py, Task 6).
    client.app.dependency_overrides[get_tone_monitor_enabled] = lambda: False
    audio_b64 = base64.b64encode(b"conteudo-de-audio-fake").decode()

    response = client.post(
        "/api/chat/messages",
        json={"message": "ignorado", "audio": audio_b64},
    )

    assert response.status_code == 200
    eventos = _parse_sse(response.text)
    assert _find(eventos, "done")["domain"] == "agendamento"
    assert fakes["stt"].received_audio == [b"conteudo-de-audio-fake"]
    # O prompt agora inclui o playbook do domínio (Fase 3); o que importa
    # aqui é que a mensagem efetiva seja a transcrição, não o texto "ignorado".
    assert len(fakes["local"].prompts) == 1
    assert "quero agendar uma visita" in fakes["local"].prompts[0]
    assert "ignorado" not in fakes["local"].prompts[0]


def test_audio_transcrito_aparece_em_transcription_event(client, fakes):
    fakes["stt"] = _FakeSttClient(text="quero agendar uma visita")
    client.app.dependency_overrides[get_stt_client] = lambda: fakes["stt"]
    audio_b64 = base64.b64encode(b"conteudo-de-audio-fake").decode()

    response = client.post("/api/chat/messages", json={"audio": audio_b64})

    assert response.status_code == 200
    eventos = _parse_sse(response.text)
    assert _find(eventos, "transcription")["transcribed_message"] == "quero agendar uma visita"
    assert _find(eventos, "done")["domain"] == "agendamento"


def test_mensagem_de_texto_simples_nao_gera_transcription_event(client):
    response = client.post("/api/chat/messages", json={"message": "quero agendar uma visita"})

    assert response.status_code == 200
    eventos = _parse_sse(response.text)
    tipos = [tipo for tipo, _ in eventos]
    assert "transcription" not in tipos


def test_sem_message_e_sem_audio_retorna_422(client):
    response = client.post("/api/chat/messages", json={})

    assert response.status_code == 422


def test_audio_sem_fala_e_sem_message_retorna_422(client, fakes):
    fakes["stt"] = _FakeSttClient(text="")
    client.app.dependency_overrides[get_stt_client] = lambda: fakes["stt"]
    audio_b64 = base64.b64encode(b"audio-sem-fala-reconhecivel").decode()

    response = client.post("/api/chat/messages", json={"audio": audio_b64})

    assert response.status_code == 422


def test_audio_transcrito_vazio_cai_de_volta_para_mensagem_de_texto(client, fakes):
    fakes["stt"] = _FakeSttClient(text="")
    client.app.dependency_overrides[get_stt_client] = lambda: fakes["stt"]
    # Monitor de Tom (R8) também chamaria local_client.generate() (fallback
    # heuristica_llm) para a mensagem sem sinal heurístico forte, inflando a
    # contagem de prompts verificada abaixo — desligado aqui para isolar
    # especificamente o comportamento de fallback de transcrição vazia que
    # este teste valida (mesmo padrão usado em test_orchestrator.py, Task 6).
    client.app.dependency_overrides[get_tone_monitor_enabled] = lambda: False
    audio_b64 = base64.b64encode(b"audio-sem-fala-reconhecivel").decode()

    response = client.post(
        "/api/chat/messages",
        json={"message": "quero agendar uma visita", "audio": audio_b64},
    )

    assert response.status_code == 200
    eventos = _parse_sse(response.text)
    assert _find(eventos, "done")["domain"] == "agendamento"
    # Transcrição vazia → cai de volta para a mensagem de texto, que agora
    # aparece dentro do prompt com o playbook do domínio (Fase 3).
    assert len(fakes["local"].prompts) == 1
    assert "quero agendar uma visita" in fakes["local"].prompts[0]


def test_audio_base64_invalido_retorna_400(client):
    response = client.post(
        "/api/chat/messages",
        json={"message": "quero agendar uma visita", "audio": "isto-nao-e-base64!!!"},
    )

    assert response.status_code == 400


def test_stt_indisponivel_retorna_503(fakes):
    fakes["stt"] = _FakeSttClient(error=SttIndisponivelError("modelo não carregou"))
    app = _build_app(fakes)
    audio_b64 = base64.b64encode(b"audio").decode()
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/chat/messages",
            json={"message": "quero agendar uma visita", "audio": audio_b64},
        )

    assert response.status_code == 503


class _FakeLLMClientNaoCarregado(_FakeLLMClient):
    """`is_model_ready` sempre `False` — força o evento `status` do orchestrator."""

    async def is_model_ready(self) -> bool:
        return False


def test_modelo_nao_carregado_gera_evento_status(fakes):
    fakes["local"] = _FakeLLMClientNaoCarregado(
        LLMResponse(text="resposta local", total_duration_ms=10.0)
    )
    app = _build_app(fakes)
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/chat/messages", json={"message": "quero agendar uma visita"}
        )

    assert response.status_code == 200
    assert "event: status" in response.text
    eventos = _parse_sse(response.text)
    assert _find(eventos, "status")["status"] == "carregando_modelo"


def test_dependencia_indisponivel_gera_evento_de_erro(fakes):
    class _FailingLLMClient:
        async def generate(self, prompt: str) -> LLMResponse:
            raise ConnectionError("ollama fora do ar")

        async def is_model_ready(self) -> bool:
            return True

        async def generate_stream(self, prompt: str):
            raise ConnectionError("ollama fora do ar")
            yield  # pragma: no cover - necessário para ser um async generator

    fakes["local"] = _FailingLLMClient()
    fakes["external"] = _FailingLLMClient()
    app = _build_app(fakes)
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/chat/messages", json={"message": "quero agendar uma visita"}
        )

    assert response.status_code == 200
    eventos = _parse_sse(response.text)
    assert eventos[-1][0] == "error"
    assert "temporariamente indisponível" in eventos[-1][1]["detail"]


async def test_email_e_guardado_mesmo_quando_o_llm_falha(fakes):
    # Cenário real do teste local (R9, 2026-09-25): o modelo externo deu 429
    # e o e-mail da mensagem se perdia junto com a resposta.
    class _FailingLLMClient:
        async def generate(self, prompt: str) -> LLMResponse:
            raise ConnectionError("429 Too Many Requests")

        async def is_model_ready(self) -> bool:
            return True

        async def generate_stream(self, prompt: str):
            raise ConnectionError("429 Too Many Requests")
            yield  # pragma: no cover - necessário para ser um async generator

    fakes["local"] = _FailingLLMClient()
    fakes["external"] = _FailingLLMClient()
    app = _build_app(fakes)
    with TestClient(app) as test_client:
        resposta = test_client.post(
            "/api/chat/messages",
            json={
                "message": "Quero trocar uma peça, meu e-mail é carla.antiga@example.com",
                "conversation_id": "conv-email-falha",
            },
        )

    assert _parse_sse(resposta.text)[-1][0] == "error"
    conversa = await fakes["db_session"].get(Conversa, "conv-email-falha")
    assert conversa.email == "carla.antiga@example.com"


def test_mensagem_so_com_email_tem_resposta_fixa_sem_llm(client, fakes):
    resposta = client.post(
        "/api/chat/messages",
        json={"message": "Sou bruno.unico@example.com", "conversation_id": "conv-so-email"},
    )

    eventos = _parse_sse(resposta.text)
    texto = "".join(dados["text"] for tipo, dados in eventos if tipo == "token")
    assert texto == RESPOSTA_SO_EMAIL
    done = _find(eventos, "done")
    assert (done["backend_used"], done["domain"]) == ("resposta_fixa", "atendimento")
    # Nenhum LLM chamado (nem classificador, nem monitor de tom, nem resposta).
    assert fakes["local"].prompts == []
    assert fakes["external"].prompts == []
    # A troca fica no histórico, como qualquer outra.
    historico = client.get("/api/chat/conversations/conv-so-email").json()["mensagens"]
    assert [m["texto"] for m in historico] == ["Sou bruno.unico@example.com", RESPOSTA_SO_EMAIL]


def test_email_ja_informado_nao_e_pedido_de_novo_no_pos_venda(client, fakes):
    client.post(
        "/api/chat/messages",
        json={"message": "meu e-mail é ana.recorrente@example.com", "conversation_id": "conv-e1"},
    )

    client.post(
        "/api/chat/messages",
        json={"message": "meu gerador não funciona", "conversation_id": "conv-e1"},
    )

    assert "e-mail usado na compra" not in fakes["local"].prompts[-1]


def test_mensagem_com_sinal_forte_emite_evento_escalonamento_antes_do_done(client):
    from app.router.tone_monitor import reset_escalated_conversations

    reset_escalated_conversations()
    response = client.post(
        "/api/chat/messages",
        json={"message": "Isso é um absurdo, nunca mais compro nessa loja!"},
    )

    assert response.status_code == 200
    eventos = _parse_sse(response.text)
    tipos = [tipo for tipo, _ in eventos]
    assert "escalonamento" in tipos
    assert tipos.index("escalonamento") < tipos.index("done")
    escalonamento = _find(eventos, "escalonamento")
    assert escalonamento["motivo"] == "insatisfacao"
    assert isinstance(escalonamento["confianca"], float)


def test_mensagem_neutra_nao_emite_evento_escalonamento(client):
    from app.router.tone_monitor import reset_escalated_conversations

    reset_escalated_conversations()
    response = client.post(
        "/api/chat/messages", json={"message": "Qual o horário de funcionamento?"}
    )

    assert response.status_code == 200
    eventos = _parse_sse(response.text)
    tipos = [tipo for tipo, _ in eventos]
    assert "escalonamento" not in tipos


async def test_escalonamento_e_persistido_no_banco(fakes, monkeypatch):
    from app.router.tone_monitor import reset_escalated_conversations

    # A persistência agora roda em background (`asyncio.create_task`,
    # achado no code-review) numa sessão PRÓPRIA — não mais a mesma sessão
    # de teste usada em outros pontos. `TestClient` roda a app numa thread/
    # loop separada (portal do anyio); uma task de background disparada de
    # lá e ainda em execução quando o teste (rodando no loop do
    # pytest-asyncio) volta a tocar a MESMA sessão já causou
    # `PendingRollbackError` (`AsyncSession` não é segura entre loops/
    # threads diferentes). Em vez de reproduzir esse cross-loop na
    # verificação, este teste substitui `criar_escalonamento` por um
    # espião — confirma que a persistência é *chamada* com os dados
    # certos, sem depender de mexer na sessão SQLite fora do loop onde ela
    # foi criada (a gravação de verdade em si já é coberta por
    # test_tone_monitor.py).
    chamadas: list[dict] = []

    async def _criar_escalonamento_espiao(session, **kwargs):
        chamadas.append(kwargs)

    monkeypatch.setattr("app.api.chat.criar_escalonamento", _criar_escalonamento_espiao)

    reset_escalated_conversations()
    app = _build_app(fakes)
    with TestClient(app) as client:
        response = client.post(
            "/api/chat/messages",
            json={"message": "Isso é um absurdo, nunca mais compro nessa loja!"},
        )
    assert response.status_code == 200

    # A task de background pode ainda não ter rodado quando a resposta HTTP
    # volta — espera curta para dar chance dela terminar.
    for _ in range(50):
        if chamadas:
            break
        await asyncio.sleep(0.01)

    assert len(chamadas) == 1
    assert chamadas[0]["mensagem"] == "Isso é um absurdo, nunca mais compro nessa loja!"
    assert chamadas[0]["motivo"] == "insatisfacao"
    assert chamadas[0]["provider_efetivo"] == "heuristica_llm"


def test_falha_ao_persistir_escalonamento_nao_derruba_o_stream(fakes):
    # Achado crítico da revisão final (item 1): antes do fix em
    # `app.api.chat`, uma exceção em `criar_escalonamento` (ex.: commit
    # falhando por instabilidade do Postgres) propagava crua de dentro de
    # `event_stream()` e matava a conexão SSE inteira DEPOIS do evento
    # `escalonamento` já ter sido enviado — sem `token`, sem `done`, sem
    # `error`. Aqui simulamos essa falha com `_CommitFailingSession` (mesmo
    # padrão usado em test_rag_api.py) e garantimos que o stream ainda
    # termina normalmente com `token` e `done`.
    from app.router.tone_monitor import reset_escalated_conversations

    reset_escalated_conversations()
    fakes["db_session"] = _CommitFailingSession(fakes["db_session"])
    app = _build_app(fakes)
    with TestClient(app) as client:
        response = client.post(
            "/api/chat/messages",
            json={"message": "Isso é um absurdo, nunca mais compro nessa loja!"},
        )

    assert response.status_code == 200
    eventos = _parse_sse(response.text)
    tipos = [tipo for tipo, _ in eventos]
    assert "escalonamento" in tipos
    assert "token" in tipos
    assert tipos[-1] == "done"


def test_app_state_sem_db_sessionmaker_nao_derruba_o_stream(fakes):
    # Achado no code-review (2026-09-24, dois agentes independentes): o fix
    # acima protege só a chamada a criar_escalonamento(), mas
    # `request.app.state.db_sessionmaker` era lido no PONTO DE CHAMADA (uma
    # expressão síncrona, fora de qualquer try/except) ao montar os
    # argumentos de `asyncio.create_task`. Se esse atributo não existisse
    # (app.state incompleto), o AttributeError propagava cru e matava o
    # stream — o mesmo bug de novo, por uma rota diferente. Aqui simulamos
    # exatamente isso: um app cujo `app.state` não tem `db_sessionmaker`
    # nenhum.
    from app.router.tone_monitor import reset_escalated_conversations

    reset_escalated_conversations()
    app = _build_app(fakes)
    del app.state.db_sessionmaker
    with TestClient(app) as client:
        response = client.post(
            "/api/chat/messages",
            json={"message": "Isso é um absurdo, nunca mais compro nessa loja!"},
        )

    assert response.status_code == 200
    eventos = _parse_sse(response.text)
    tipos = [tipo for tipo, _ in eventos]
    assert "escalonamento" in tipos
    assert "token" in tipos
    assert tipos[-1] == "done"


async def test_usuario_autenticado_recebe_historico_compras_no_prompt(client, fakes):
    sessao = fakes["db_session"]
    ana = Cliente(email="ana.recorrente@example.com", nome="Ana")
    sessao.add(ana)
    await sessao.flush()
    sessao.add(
        ClienteCompra(
            cliente_id=ana.id,
            quantidade=1,
            valor_total=Decimal("18500.00"),
            comprado_em=datetime.now(UTC) - timedelta(days=20),
        )
    )
    await sessao.commit()

    resposta = client.post(
        "/api/chat/messages",
        json={
            "message": "que compras fiz?",
            "conversation_id": "conv-auth-test-1",
            "user_email": "ana.recorrente@example.com",
        },
    )
    assert resposta.status_code == 200
    ultimo_prompt = fakes["local"].prompts[-1]
    assert "[Dados do Cliente e Histórico de Compras]:" in ultimo_prompt
    assert "Histórico de Compras e Pedidos Realizados:" in ultimo_prompt
    assert "- Nome do cliente: Ana" in ultimo_prompt


async def test_usuario_deslogado_recebe_apenas_tipo_cliente_sem_compras(client, fakes):
    sessao = fakes["db_session"]
    ana = Cliente(email="ana.recorrente@example.com", nome="Ana")
    sessao.add(ana)
    await sessao.flush()
    sessao.add(
        ClienteCompra(
            cliente_id=ana.id,
            quantidade=1,
            valor_total=Decimal("18500.00"),
            comprado_em=datetime.now(UTC) - timedelta(days=20),
        )
    )
    await sessao.commit()

    # Usuário cita o e-mail no texto mas NÃO está autenticado (user_email ausente)
    resposta = client.post(
        "/api/chat/messages",
        json={
            "message": "sou ana.recorrente@example.com, que compras fiz?",
            "conversation_id": "conv-unauth-test-1",
        },
    )
    assert resposta.status_code == 200
    ultimo_prompt = fakes["local"].prompts[-1]
    assert "[Perfil do Visitante no Chat (Não Autenticado)]:" in ultimo_prompt
    assert "Tipo de cliente:" in ultimo_prompt
    assert "NÃO AUTENTICADO" in ultimo_prompt
    assert "Histórico de Compras e Pedidos Realizados:" not in ultimo_prompt
    assert "18500" not in ultimo_prompt


async def test_logout_em_conversa_existente_remove_compras_do_prompt(client, fakes):
    sessao = fakes["db_session"]
    ana = Cliente(email="ana.recorrente@example.com", nome="Ana")
    sessao.add(ana)
    await sessao.flush()
    sessao.add(
        ClienteCompra(
            cliente_id=ana.id,
            quantidade=1,
            valor_total=Decimal("18500.00"),
            comprado_em=datetime.now(UTC) - timedelta(days=20),
        )
    )
    await sessao.commit()

    # 1. Usuário logado manda mensagem
    client.post(
        "/api/chat/messages",
        json={
            "message": "quais são minhas compras?",
            "conversation_id": "conv-logout-fluxo",
            "user_email": "ana.recorrente@example.com",
        },
    )
    assert "[Dados do Cliente e Histórico de Compras]:" in fakes["local"].prompts[-1]

    # 2. Usuário desloga e manda nova mensagem na mesma conversa sem user_email
    client.post(
        "/api/chat/messages",
        json={
            "message": "que compras fiz?",
            "conversation_id": "conv-logout-fluxo",
        },
    )
    ultimo_prompt = fakes["local"].prompts[-1]
    assert "Histórico de Compras e Pedidos Realizados:" not in ultimo_prompt
    assert "[Perfil do Visitante no Chat (Não Autenticado)]:" in ultimo_prompt


async def test_login_no_meio_da_conversa_mantem_contexto_e_habilita_compras(client, fakes):
    sessao = fakes["db_session"]
    ana = Cliente(email="ana.recorrente@example.com", nome="Ana")
    sessao.add(ana)
    await sessao.flush()
    sessao.add(
        ClienteCompra(
            cliente_id=ana.id,
            quantidade=1,
            valor_total=Decimal("18500.00"),
            comprado_em=datetime.now(UTC) - timedelta(days=20),
        )
    )
    await sessao.commit()

    # 1. Usuário pergunta sem login prévio (anônimo)
    client.post(
        "/api/chat/messages",
        json={
            "message": "quais foram as minhas compras?",
            "conversation_id": "conv-login-mid",
        },
    )
    primeiro_prompt = fakes["local"].prompts[-1]
    assert "Histórico de Compras e Pedidos Realizados:" not in primeiro_prompt

    # 2. Usuário efetua login e envia nova mensagem na MESMA conversa com user_email
    client.post(
        "/api/chat/messages",
        json={
            "message": "agora estou logado, pode listar minhas compras?",
            "conversation_id": "conv-login-mid",
            "user_email": "ana.recorrente@example.com",
        },
    )
    segundo_prompt = fakes["local"].prompts[-1]
    assert "[Dados do Cliente e Histórico de Compras]:" in segundo_prompt
    assert "Histórico de Compras e Pedidos Realizados:" in segundo_prompt
    assert "- Nome do cliente: Ana" in segundo_prompt
    # Conversa preservou o histórico recente anterior
    conversa_history = client.get("/api/chat/conversations/conv-login-mid").json()["mensagens"]
    mensagens_textos = [m["texto"] for m in conversa_history]
    assert "quais foram as minhas compras?" in mensagens_textos
    assert "agora estou logado, pode listar minhas compras?" in mensagens_textos


async def test_usuario_autenticado_com_conversa_anterior_injeta_contexto_anterior_no_prompt(
    client, fakes
):
    sessao = fakes["db_session"]
    # Cria uma conversa passada para Ana com resumo
    conversa_passada = Conversa(
        id="conv-passada-1",
        email="ana.recorrente@example.com",
        resumo="Cliente comprou um gerador GD-15 e tirou dúvidas de garantia.",
        mensagens_resumidas=6,
    )
    sessao.add(conversa_passada)
    await sessao.commit()

    # Ana inicia uma conversa nova autenticada
    client.post(
        "/api/chat/messages",
        json={
            "message": "Olá, queria saber se há novidades sobre garantia.",
            "conversation_id": "conv-nova-2",
            "user_email": "ana.recorrente@example.com",
        },
    )

    todos_os_prompts = fakes["local"].prompts + fakes["external"].prompts
    prompt_com_contexto = next(
        (p for p in todos_os_prompts if "Contexto da conversa anterior do cliente" in p), None
    )
    assert prompt_com_contexto is not None
    assert "Cliente comprou um gerador GD-15 e tirou dúvidas de garantia." in prompt_com_contexto


@pytest.mark.parametrize(
    "card",
    [
        CardProduto(
            produto_id=1, nome="Gerador Diesel GD-15", preco=Decimal("24900.00"), estoque_total=8
        ),
        CardCotacao(
            produto_id=1,
            nome="Gerador Diesel GD-15",
            quantidade=2,
            preco_unitario=Decimal("24900.00"),
            percentual_desconto=Decimal("10"),
            subtotal=Decimal("44820.00"),
        ),
        CardAgendamento(
            data_hora_inicio=datetime(2026, 10, 1, 14, 30, tzinfo=UTC),
            data_hora_fim=datetime(2026, 10, 1, 15, 30, tzinfo=UTC),
            google_event_link="https://calendar.google.com/evt1",
        ),
    ],
)
def test_done_event_com_card_serializa_decimal_e_datetime_como_json(card):
    # Regressão: `Decimal`/`datetime` (campos dos 3 cards) não são
    # serializáveis por `json.dumps` no modo "python" do Pydantic
    # (`model_dump()` puro) — precisa de `model_dump(mode="json")`, que
    # converte ambos para string. Sem isso, o evento SSE `done` quebraria a
    # cada card (bug pego só neste teste, não nos de `test_orchestrator.py`,
    # que verificam o objeto Python, nunca o `json.dumps` de verdade).
    done_data = ChatDoneEventData(
        domain="vendas",
        backend_used="local",
        escalation_reason="nenhum",
        card=card,
    )

    bloco_sse = _sse("done", done_data.model_dump(mode="json"))

    tipo, dados = _parse_sse(bloco_sse)[0]
    assert tipo == "done"
    assert dados["card"]["tipo"] == card.tipo
