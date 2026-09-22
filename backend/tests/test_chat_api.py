import base64
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.chat import (
    get_calendar_client,
    get_clip_embedder,
    get_clip_store,
    get_complexity_strategy,
    get_external_client,
    get_local_client,
    get_rag_client,
    get_scheduling_config,
    get_stt_client,
    reset_conversation_history,
)
from app.api.chat import router as chat_router
from app.rag.image_search import ImageSearchResult
from app.router.llm_client import LLMResponse, LLMStreamChunk
from app.router.rag_client import Document
from app.stt.whisper_client import SttIndisponivelError


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


class _FakeClipStore:
    def __init__(self, results: list[ImageSearchResult] | None = None) -> None:
        self._results = results or []

    async def search_by_image(self, embedder, image_bytes, domain=None):
        return self._results


class _FakeRAGClient:
    def __init__(self, documents: list[Document] | None = None) -> None:
        self._documents = documents if documents is not None else []

    async def search(self, query: str, domain: str) -> list[Document]:
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


@pytest.fixture
def fakes():
    return {
        "local": _FakeLLMClient(LLMResponse(text="resposta local", total_duration_ms=10.0)),
        "external": _FakeLLMClient(LLMResponse(text="resposta externa", total_duration_ms=20.0)),
        "rag": _FakeRAGClient(documents=[Document(content="...", source="catalogo", score=0.9)]),
        # MVP: STT não é exercitado por padrão nos testes que não enviam
        # `audio` — texto vazio nunca chega a ser usado nesses casos.
        "stt": _FakeSttClient(text=""),
        # Catálogo CLIP vazio por padrão — testes de identificação populam.
        "clip_store": _FakeClipStore(results=[]),
        "clip_embedder": object(),
    }


def _build_app(fakes: dict, complexity_strategy: str = "heuristic") -> FastAPI:
    app = FastAPI()
    app.include_router(chat_router)
    app.dependency_overrides[get_local_client] = lambda: fakes["local"]
    app.dependency_overrides[get_external_client] = lambda: fakes["external"]
    app.dependency_overrides[get_rag_client] = lambda: fakes["rag"]
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
    # Limiares lidos via request.app.state no fluxo de identificação.
    app.state.image_internal_confidence = 0.30
    app.state.image_external_confidence = 0.80
    return app


@pytest.fixture
def client(fakes):
    app = _build_app(fakes)

    reset_conversation_history()
    with TestClient(app) as test_client:
        yield test_client
    reset_conversation_history()


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
    reset_conversation_history()
    with TestClient(app) as test_client:
        response = test_client.post("/api/chat/messages", json={"message": "qual o preço?"})

    dados_done = _find(_parse_sse(response.text), "done")
    assert dados_done["rag_chunks"] == [
        {"source": "catalogo_cameras.txt", "score": 0.91},
        {"source": "politica_garantia.pdf", "score": 0.72},
    ]


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


def test_audio_e_transcrito_e_usado_como_mensagem(client, fakes):
    # A mensagem de texto ("ignorado") não deveria chegar ao LLM: quando há
    # áudio, o texto transcrito é a mensagem efetiva (ver comentário MVP em
    # `app.api.chat.send_message`).
    fakes["stt"] = _FakeSttClient(text="quero agendar uma visita")
    client.app.dependency_overrides[get_stt_client] = lambda: fakes["stt"]
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

    reset_conversation_history()
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/chat/messages",
            json={"message": "quero agendar uma visita", "audio": audio_b64},
        )
    reset_conversation_history()

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

    reset_conversation_history()
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/chat/messages", json={"message": "quero agendar uma visita"}
        )
    reset_conversation_history()

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

    reset_conversation_history()
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/chat/messages", json={"message": "quero agendar uma visita"}
        )
    reset_conversation_history()

    assert response.status_code == 200
    eventos = _parse_sse(response.text)
    assert eventos[-1][0] == "error"
    assert "temporariamente indisponível" in eventos[-1][1]["detail"]
