import httpx
import pytest

from app.router.ollama_client import OllamaClient


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
