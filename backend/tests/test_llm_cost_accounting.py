import pytest
from app.router.openrouter_client import OpenRouterClient
from app.router.llm_client import LLMResponse, LLMStreamChunk
from app.models.chat import ChatDoneEventData

def test_openrouter_segregated_cost_calculation():
    client = OpenRouterClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="mock-key",
        model="google/gemini-2.5-flash",
        timeout_s=10.0,
        price_per_1k_input_tokens=0.001,  # $0.001 per 1k input
        price_per_1k_output_tokens=0.003, # $0.003 per 1k output
    )
    cost_prompt, cost_completion, cost_total = client._custo_detalhado(prompt_tokens=1000, completion_tokens=2000)
    assert pytest.approx(cost_prompt, 0.00001) == 0.001
    assert pytest.approx(cost_completion, 0.00001) == 0.006
    assert pytest.approx(cost_total, 0.00001) == 0.007

def test_openrouter_handles_none_tokens():
    client = OpenRouterClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="mock-key",
        model="google/gemini-2.5-flash",
        timeout_s=10.0,
        price_per_1k_input_tokens=0.001,
        price_per_1k_output_tokens=0.003,
    )
    cost_prompt, cost_completion, cost_total = client._custo_detalhado(prompt_tokens=None, completion_tokens=None)
    assert cost_prompt == 0.0
    assert cost_completion == 0.0
    assert cost_total == 0.0

def test_llm_response_and_chunk_have_segregated_costs():
    resp = LLMResponse(
        text="teste",
        prompt_tokens=100,
        completion_tokens=50,
        total_duration_ms=120.0,
        cost_prompt_usd=0.0001,
        cost_completion_usd=0.0002,
        estimated_cost_usd=0.0003,
    )
    assert resp.cost_prompt_usd == 0.0001
    assert resp.cost_completion_usd == 0.0002

    chunk = LLMStreamChunk(
        done=True,
        cost_prompt_usd=0.0005,
        cost_completion_usd=0.0010,
        estimated_cost_usd=0.0015,
    )
    assert chunk.cost_prompt_usd == 0.0005
    assert chunk.cost_completion_usd == 0.0010

def test_chat_done_event_data_has_segregated_costs():
    event_data = ChatDoneEventData(
        domain="vendas",
        backend_used="externo",
        escalation_reason="nenhum",
        prompt_tokens=100,
        completion_tokens=50,
        cost_prompt_usd=0.0001,
        cost_completion_usd=0.0002,
        estimated_cost_usd=0.0003,
    )
    assert event_data.cost_prompt_usd == 0.0001
    assert event_data.cost_completion_usd == 0.0002
