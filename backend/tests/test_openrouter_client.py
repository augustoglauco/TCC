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


async def test_is_model_ready_sempre_true():
    client = OpenRouterClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="chave-fake",
        model="anthropic/claude-3.5-haiku",
        timeout_s=30.0,
    )

    assert await client.is_model_ready() is True


def _mock_sse_transport(lines: list[str], status_code: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        body = "\n\n".join(lines).encode() + b"\n\n"
        return httpx.Response(
            status_code, content=body, headers={"content-type": "text/event-stream"}
        )

    return httpx.MockTransport(handler)


async def test_generate_stream_emite_delta_de_conteudo_e_chunk_final_com_usage():
    from app.router.llm_client import LLMStreamChunk

    lines = [
        'data: {"choices":[{"delta":{"content":"Olá"}}]}',
        'data: {"choices":[{"delta":{"content":", tudo bem?"}}]}',
        'data: {"choices":[{"delta":{}}],"usage":{"prompt_tokens":12,"completion_tokens":34}}',
        "data: [DONE]",
    ]
    client = OpenRouterClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="chave-fake",
        model="anthropic/claude-3.5-haiku",
        timeout_s=30.0,
        price_per_1k_input_tokens=1.0,
        price_per_1k_output_tokens=2.0,
        client=httpx.AsyncClient(transport=_mock_sse_transport(lines)),
    )

    chunks = [chunk async for chunk in client.generate_stream("oi")]

    assert len(chunks) == 3
    assert chunks[0] == LLMStreamChunk(text="Olá")
    assert chunks[1] == LLMStreamChunk(text=", tudo bem?")
    assert chunks[2].done is True
    assert chunks[2].prompt_tokens == 12
    assert chunks[2].completion_tokens == 34
    # custo: 12/1000*1.0 + 34/1000*2.0 = 0.012 + 0.068 = 0.08
    assert chunks[2].estimated_cost_usd == pytest.approx(0.08)
    assert chunks[2].model_name == "anthropic/claude-3.5-haiku"


async def test_generate_stream_sintetiza_chunk_final_se_provedor_nunca_manda_usage():
    from app.router.llm_client import LLMStreamChunk

    # Provedor agregado pelo OpenRouter que ignora `stream_options.include_usage`
    # — o stream termina em [DONE] sem nenhum chunk trazer `usage`.
    lines = [
        'data: {"choices":[{"delta":{"content":"oi"}}]}',
        "data: [DONE]",
    ]
    client = OpenRouterClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="chave-fake",
        model="anthropic/claude-3.5-haiku",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_sse_transport(lines)),
    )

    chunks = [chunk async for chunk in client.generate_stream("oi")]

    assert len(chunks) == 2
    assert chunks[0] == LLMStreamChunk(text="oi")
    assert chunks[1].done is True
    assert chunks[1].prompt_tokens is None
    assert chunks[1].completion_tokens is None
    assert chunks[1].model_name == "anthropic/claude-3.5-haiku"
