import json

import httpx
import pytest

from app.router.ollama_client import LocalModel, OllamaClient, PullProgressLine


def _mock_transport(json_response: dict, status_code: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=json_response)

    return httpx.MockTransport(handler)


async def test_ollama_client_parses_response():
    mock_response = {
        "response": "Olá!",
        "prompt_eval_count": 12,
        "eval_count": 34,
        "total_duration": 2_500_000_000,
        "load_duration": 500_000_000,
        "prompt_eval_duration": 200_000_000,
        "eval_duration": 1_800_000_000,
    }
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_transport(mock_response)),
    )

    result = await client.generate("oi")

    assert result.text == "Olá!"
    assert result.prompt_tokens == 12
    assert result.completion_tokens == 34
    assert result.total_duration_ms == 2500.0
    assert result.load_duration_ms == 500.0
    assert result.prompt_eval_duration_ms == 200.0
    assert result.eval_duration_ms == 1800.0
    assert result.estimated_cost_usd == 0.0


async def test_ollama_client_raises_on_http_error():
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_transport({"error": "boom"}, status_code=500)),
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.generate("oi")


async def test_model_property_e_setter():
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_transport({})),
    )

    assert client.model == "llama3.1:8b"

    client.model = "qwen2.5:7b"

    assert client.model == "qwen2.5:7b"


async def test_list_local_models_mapeia_a_resposta_do_ollama():
    mock_response = {
        "models": [
            {
                "name": "llama3.1:8b",
                "model": "llama3.1:8b",
                "modified_at": "2026-09-01T10:00:00Z",
                "size": 4_920_000_000,
                "digest": "sha256:abc",
                "details": {},
                "capabilities": ["completion"],
            },
            {
                "name": "qwen2.5:7b",
                "model": "qwen2.5:7b",
                "modified_at": "2026-08-15T09:00:00Z",
                "size": 4_100_000_000,
                "digest": "sha256:def",
                "details": {},
                "capabilities": ["completion"],
            },
        ]
    }
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_transport(mock_response)),
    )

    modelos = await client.list_local_models()

    assert modelos == [
        LocalModel(
            name="llama3.1:8b", size_bytes=4_920_000_000, modified_at="2026-09-01T10:00:00Z"
        ),
        LocalModel(name="qwen2.5:7b", size_bytes=4_100_000_000, modified_at="2026-08-15T09:00:00Z"),
    ]


async def test_list_local_models_vazio_retorna_lista_vazia():
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_transport({"models": []})),
    )

    assert await client.list_local_models() == []


def _mock_streaming_transport(lines: list[str], status_code: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        body = "\n".join(lines).encode()
        return httpx.Response(status_code, content=body)

    return httpx.MockTransport(handler)


async def test_pull_model_streaming_gera_uma_linha_por_status():
    lines = [
        json.dumps({"status": "pulling manifest"}),
        json.dumps(
            {
                "status": "pulling sha256:abc",
                "digest": "sha256:abc",
                "total": 1000,
                "completed": 500,
            }
        ),
        json.dumps(
            {
                "status": "pulling sha256:abc",
                "digest": "sha256:abc",
                "total": 1000,
                "completed": 1000,
            }
        ),
        json.dumps({"status": "success"}),
    ]
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_streaming_transport(lines)),
    )

    progresso = [linha async for linha in client.pull_model_streaming("llama3.1:8b")]

    assert len(progresso) == 4
    assert progresso[0] == PullProgressLine(
        status="pulling manifest", digest=None, total=None, completed=None, error=None
    )
    assert progresso[1] == PullProgressLine(
        status="pulling sha256:abc", digest="sha256:abc", total=1000, completed=500, error=None
    )
    assert progresso[3] == PullProgressLine(
        status="success", digest=None, total=None, completed=None, error=None
    )


async def test_pull_model_streaming_repassa_linha_de_erro():
    lines = [
        json.dumps({"status": "pulling manifest"}),
        json.dumps({"error": "pull model manifest: file does not exist"}),
    ]
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_streaming_transport(lines)),
    )

    progresso = [linha async for linha in client.pull_model_streaming("nome-invalido")]

    assert progresso[-1].error == "pull model manifest: file does not exist"


async def test_is_model_ready_true_quando_modelo_esta_na_lista_do_ps():
    mock_response = {
        "models": [
            {"name": "outro-modelo:8b"},
            {"name": "llama3.1:8b"},
        ]
    }
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_transport(mock_response)),
    )

    assert await client.is_model_ready() is True


async def test_is_model_ready_false_quando_modelo_nao_esta_na_lista_do_ps():
    mock_response = {"models": [{"name": "outro-modelo:8b"}]}
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_transport(mock_response)),
    )

    assert await client.is_model_ready() is False


async def test_is_model_ready_false_quando_lista_vazia():
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_transport({"models": []})),
    )

    assert await client.is_model_ready() is False
