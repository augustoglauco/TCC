import httpx
import pytest

from app.router.openrouter_client import OpenRouterClient


def _mock_transport(json_response: dict, status_code: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=json_response)

    return httpx.MockTransport(handler)


async def test_openrouter_client_parses_response_and_computes_cost():
    mock_response = {
        "choices": [{"message": {"content": "Olá!"}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
    }
    client = OpenRouterClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="test-key",
        model="anthropic/claude-3.5-haiku",
        timeout_s=30.0,
        price_per_1k_input_tokens=1.0,
        price_per_1k_output_tokens=2.0,
        client=httpx.AsyncClient(transport=_mock_transport(mock_response)),
    )

    result = await client.generate("oi")

    assert result.text == "Olá!"
    assert result.prompt_tokens == 100
    assert result.completion_tokens == 50
    assert result.load_duration_ms is None
    assert result.eval_duration_ms is None
    assert result.estimated_cost_usd == pytest.approx(0.1 * 1.0 + 0.05 * 2.0)


async def test_openrouter_client_raises_on_http_error():
    client = OpenRouterClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="test-key",
        model="anthropic/claude-3.5-haiku",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_transport({"error": "boom"}, status_code=401)),
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.generate("oi")
