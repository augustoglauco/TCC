import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.chat import (
    get_complexity_strategy,
    get_external_client,
    get_local_client,
    get_rag_client,
    reset_conversation_history,
)
from app.api.chat import router as chat_router
from app.router.llm_client import LLMResponse
from app.router.rag_client import Document


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


@pytest.fixture
def fakes():
    return {
        "local": _FakeLLMClient(LLMResponse(text="resposta local", total_duration_ms=10.0)),
        "external": _FakeLLMClient(LLMResponse(text="resposta externa", total_duration_ms=20.0)),
        "rag": _FakeRAGClient(documents=[Document(content="...", source="catalogo", score=0.9)]),
    }


@pytest.fixture
def client(fakes):
    app = FastAPI()
    app.include_router(chat_router)
    app.dependency_overrides[get_local_client] = lambda: fakes["local"]
    app.dependency_overrides[get_external_client] = lambda: fakes["external"]
    app.dependency_overrides[get_rag_client] = lambda: fakes["rag"]
    app.dependency_overrides[get_complexity_strategy] = lambda: "heuristic"

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
    first = client.post(
        "/api/chat/messages", json={"message": "quero agendar uma visita"}
    ).json()
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
    isolated = client.post(
        "/api/chat/messages", json={"message": "pode ser amanhã às 10h"}
    ).json()
    assert isolated["domain"] == "fora_escopo"


def test_campo_de_audio_e_aceito_mas_ignorado(client, fakes):
    response = client.post(
        "/api/chat/messages",
        json={"message": "quero agendar uma visita", "audio": "base64-fake-audio"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["domain"] == "agendamento"
    # Nenhum prompt enviado ao LLM deve conter o payload de áudio — ele é
    # apenas aceito no schema, nunca processado (MVP: STT ainda não existe).
    assert all("base64-fake-audio" not in prompt for prompt in fakes["local"].prompts)


def test_dependencia_indisponivel_retorna_503():
    class _FailingLLMClient:
        async def generate(self, prompt: str) -> LLMResponse:
            raise ConnectionError("ollama fora do ar")

    app = FastAPI()
    app.include_router(chat_router)
    app.dependency_overrides[get_local_client] = lambda: _FailingLLMClient()
    app.dependency_overrides[get_external_client] = lambda: _FailingLLMClient()
    app.dependency_overrides[get_rag_client] = lambda: _FakeRAGClient()
    app.dependency_overrides[get_complexity_strategy] = lambda: "heuristic"

    reset_conversation_history()
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/chat/messages", json={"message": "quero agendar uma visita"}
        )
    reset_conversation_history()

    assert response.status_code == 503
