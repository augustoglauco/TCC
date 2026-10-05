import pytest
from unittest.mock import AsyncMock, patch
import httpx
from app.router.openrouter_client import OpenRouterClient, VisionResult

@pytest.mark.asyncio
async def test_describe_image_calculates_segregated_costs_and_usage():
    mock_response = httpx.Response(
        status_code=200,
        json={
            "choices": [{"message": {"content": '{"produto": "Câmera IP", "confianca": 0.9}'}}],
            "usage": {
                "prompt_tokens": 1200,
                "completion_tokens": 80,
                "total_tokens": 1280
            }
        },
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    )

    client = OpenRouterClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="mock-key",
        model="google/gemini-2.5-flash",
        vision_model="google/gemma-4-31b-it:free",
        timeout_s=10.0,
        price_per_1k_input_tokens=0.001,
        price_per_1k_output_tokens=0.002,
        price_per_1k_vision_input_tokens=0.005,
        price_per_1k_vision_output_tokens=0.015,
    )

    with patch.object(client._client, "post", AsyncMock(return_value=mock_response)):
        dummy_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        res = await client.describe_image(dummy_png, "Identifique")

        assert isinstance(res, str)
        assert isinstance(res, VisionResult)
        assert '{"produto": "Câmera IP"' in res
        assert res.prompt_tokens == 1200
        assert res.completion_tokens == 80
        assert res.total_tokens == 1280
        assert pytest.approx(res.cost_prompt_usd, 0.00001) == (1200 / 1000.0) * 0.005
        assert pytest.approx(res.cost_completion_usd, 0.00001) == (80 / 1000.0) * 0.015
        assert pytest.approx(res.estimated_cost_usd, 0.00001) == 0.0072
        assert res.model_name == "google/gemma-4-31b-it:free"

@pytest.mark.asyncio
async def test_describe_image_handles_missing_usage():
    mock_response = httpx.Response(
        status_code=200,
        json={
            "choices": [{"message": {"content": "Identificação sem usage"}}],
        },
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    )

    client = OpenRouterClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="mock-key",
        model="google/gemini-2.5-flash",
        vision_model="google/gemma-4-31b-it:free",
        timeout_s=10.0,
    )

    with patch.object(client._client, "post", AsyncMock(return_value=mock_response)):
        dummy_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        res = await client.describe_image(dummy_png, "Identifique")

        assert isinstance(res, str)
        assert isinstance(res, VisionResult)
        assert res == "Identificação sem usage"
        assert res.prompt_tokens is None
        assert res.completion_tokens is None
        assert res.cost_prompt_usd == 0.0
        assert res.cost_completion_usd == 0.0
        assert res.estimated_cost_usd == 0.0
