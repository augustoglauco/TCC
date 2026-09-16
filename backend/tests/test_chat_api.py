import base64

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.chat import (
    get_complexity_strategy,
    get_external_client,
    get_local_client,
    get_rag_client,
    get_stt_client,
    reset_conversation_history,
)
from app.api.chat import router as chat_router
from app.router.llm_client import LLMResponse
from app.router.rag_client import Document
from app.stt.whisper_client import SttIndisponivelError


class _FakeLLMClient:
    def __init__(self, response: LLMResponse) -> None:
        self._response = response
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> LLMResponse:
        self.prompts.append(prompt)
        return self._response


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
    }


def _build_app(fakes: dict, complexity_strategy: str = "heuristic") -> FastAPI:
    app = FastAPI()
    app.include_router(chat_router)
    app.dependency_overrides[get_local_client] = lambda: fakes["local"]
    app.dependency_overrides[get_external_client] = lambda: fakes["external"]
    app.dependency_overrides[get_rag_client] = lambda: fakes["rag"]
    app.dependency_overrides[get_stt_client] = lambda: fakes["stt"]
    app.dependency_overrides[get_complexity_strategy] = lambda: complexity_strategy
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
    body = response.json()
    assert body["message"] == "resposta local"
    assert body["domain"] == "agendamento"
    assert body["backend_used"] == "local"
    assert body["escalation_reason"] == "nenhum"
    assert isinstance(body["conversation_id"], str) and body["conversation_id"]


def test_conversation_id_mantem_historico_entre_chamadas(client):
    first = client.post("/api/chat/messages", json={"message": "quero agendar uma visita"}).json()
    conversation_id = first["conversation_id"]

    # Mensagem isolada e ambígua para o classificador por palavra-chave (não
    # casa nenhum domínio sozinha); só resolve para "agendamento" se o
    # histórico da mensagem anterior for repassado como contexto recente ao
    # orchestrator — é isso que este teste verifica.
    second = client.post(
        "/api/chat/messages",
        json={"message": "pode ser amanhã às 10h", "conversation_id": conversation_id},
    ).json()

    assert second["conversation_id"] == conversation_id
    assert second["domain"] == "agendamento"

    # Sem conversation_id (conversa nova), a mesma mensagem isolada cai em
    # fora_escopo por falta de contexto — prova de que o histórico é o que
    # muda o resultado, não a heurística da mensagem em si.
    isolated = client.post("/api/chat/messages", json={"message": "pode ser amanhã às 10h"}).json()
    assert isolated["domain"] == "fora_escopo"


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
    body = response.json()
    assert body["domain"] == "agendamento"
    assert fakes["stt"].received_audio == [b"conteudo-de-audio-fake"]
    assert fakes["local"].prompts == ["quero agendar uma visita"]


def test_audio_transcrito_aparece_em_transcribed_message(client, fakes):
    fakes["stt"] = _FakeSttClient(text="quero agendar uma visita")
    client.app.dependency_overrides[get_stt_client] = lambda: fakes["stt"]
    audio_b64 = base64.b64encode(b"conteudo-de-audio-fake").decode()

    response = client.post("/api/chat/messages", json={"audio": audio_b64})

    assert response.status_code == 200
    body = response.json()
    assert body["transcribed_message"] == "quero agendar uma visita"
    assert body["domain"] == "agendamento"


def test_mensagem_de_texto_simples_nao_preenche_transcribed_message(client):
    response = client.post("/api/chat/messages", json={"message": "quero agendar uma visita"})

    assert response.status_code == 200
    assert response.json()["transcribed_message"] is None


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
    assert response.json()["domain"] == "agendamento"
    assert fakes["local"].prompts == ["quero agendar uma visita"]


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


def test_dependencia_indisponivel_retorna_503(fakes):
    class _FailingLLMClient:
        async def generate(self, prompt: str) -> LLMResponse:
            raise ConnectionError("ollama fora do ar")

    fakes["local"] = _FailingLLMClient()
    fakes["external"] = _FailingLLMClient()
    app = _build_app(fakes)

    reset_conversation_history()
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/chat/messages", json={"message": "quero agendar uma visita"}
        )
    reset_conversation_history()

    assert response.status_code == 503
