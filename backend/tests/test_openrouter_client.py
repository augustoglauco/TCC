import json

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


async def test_timeout_s_property_e_setter():
    client = OpenRouterClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="test-key",
        model="anthropic/claude-3.5-haiku",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_transport({})),
    )

    assert client.timeout_s == 30.0

    client.timeout_s = 60.0

    assert client.timeout_s == 60.0


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
        # Formato real da API: o chunk de `usage` costuma vir com `choices`
        # PRESENTE mas VAZIO, não com um item de `delta` vazio.
        'data: {"choices":[],"usage":{"prompt_tokens":12,"completion_tokens":34}}',
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


def _png_bytes() -> bytes:
    import io

    pytest.importorskip("PIL", reason="Pillow não instalado")
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (4, 4), color="white").save(buf, format="PNG")
    return buf.getvalue()


async def test_describe_image_sem_vision_model_levanta_indisponivel():
    from app.router.openrouter_client import VisionModelIndisponivelError

    client = OpenRouterClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="chave-fake",
        model="anthropic/claude-3.5-haiku",
        timeout_s=30.0,
        # vision_model vazio (default)
    )
    with pytest.raises(VisionModelIndisponivelError):
        await client.describe_image(_png_bytes(), "identifique")


async def test_describe_image_ok_retorna_conteudo():
    mock_response = {"choices": [{"message": {"content": '{"produto":"X"}'}}]}
    client = OpenRouterClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="chave-fake",
        model="anthropic/claude-3.5-haiku",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_transport(mock_response)),
        vision_model="openai/gpt-4o-mini",
    )
    texto = await client.describe_image(_png_bytes(), "identifique")
    assert texto == '{"produto":"X"}'


async def test_describe_image_erro_http_vira_indisponivel():
    from app.router.openrouter_client import VisionModelIndisponivelError

    client = OpenRouterClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="chave-fake",
        model="anthropic/claude-3.5-haiku",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_transport({"error": "x"}, status_code=500)),
        vision_model="openai/gpt-4o-mini",
    )
    with pytest.raises(VisionModelIndisponivelError):
        await client.describe_image(_png_bytes(), "identifique")


async def test_vision_model_property_e_setter():
    client = OpenRouterClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="chave-fake",
        model="anthropic/claude-3.5-haiku",
        timeout_s=30.0,
    )
    assert client.vision_model == ""
    client.vision_model = "openai/gpt-4o-mini"
    assert client.vision_model == "openai/gpt-4o-mini"


@pytest.mark.asyncio
async def test_classify_intent_jev_sucesso():
    captured_request: dict = {}

    def mock_handler(request: httpx.Request) -> httpx.Response:
        captured_request["url"] = str(request.url)
        captured_request["body"] = json.loads(request.content)
        data = {
            "answers": {
                "dominio": {
                    "type": "choice",
                    "choice": "vendas",
                    "confidence": 0.95,
                }
            },
            "usage": {"input_tokens": 42, "output_tokens": 5, "cost": 0.000002},
        }
        return httpx.Response(200, json=data)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as mock_client:
        client = OpenRouterClient(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
            model="meta-llama/llama-3",
            timeout_s=5.0,
            client=mock_client,
            jev_model="typesafe/jev-latest",
        )
        domain, confidence = await client.classify_intent_jev(
            message="quanto custa o produto?", recent_messages=[]
        )
        assert domain == "vendas"
        assert confidence == 0.95
        # Endpoint dedicado, distinto de /chat/completions
        assert captured_request["url"].endswith("/systemone")
        # Corpo da requisição segue o schema estruturado do System One
        # (model/state/questions.dominio), não o formato de chat.
        body = captured_request["body"]
        assert body["model"] == "typesafe/jev-latest"
        assert body["questions"]["dominio"]["type"] == "choice"
        assert set(body["questions"]["dominio"]["criteria"]) == {
            "vendas",
            "suporte",
            "atendimento",
            "agendamento",
            "fora_escopo",
        }


@pytest.mark.asyncio
async def test_classify_intent_jev_choice_fora_do_enum_vira_fora_escopo():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        data = {"answers": {"dominio": {"type": "choice", "choice": "lixo", "confidence": 0.4}}}
        return httpx.Response(200, json=data)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as mock_client:
        client = OpenRouterClient(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
            model="meta-llama/llama-3",
            timeout_s=5.0,
            client=mock_client,
            jev_model="typesafe/jev-latest",
        )
        domain, _ = await client.classify_intent_jev(message="teste", recent_messages=[])
        assert domain == "fora_escopo"


@pytest.mark.asyncio
async def test_classify_tone_jev_noul_alto_escala():
    captured_request: dict = {}

    def mock_handler(request: httpx.Request) -> httpx.Response:
        captured_request["url"] = str(request.url)
        captured_request["body"] = json.loads(request.content)
        data = {"answers": {"escalar": {"type": "noul", "noul": 0.92}}}
        return httpx.Response(200, json=data)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as mock_client:
        client = OpenRouterClient(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
            model="meta-llama/llama-3",
            timeout_s=5.0,
            client=mock_client,
            jev_model="typesafe/jev-latest",
        )
        escalate, confidence = await client.classify_tone_jev(
            message="Ninguém me ajuda, preciso falar com um atendente agora!",
            recent_messages=[],
        )
        assert escalate is True
        assert confidence == 0.92
        assert captured_request["url"].endswith("/systemone")
        body = captured_request["body"]
        assert body["model"] == "typesafe/jev-latest"
        assert body["questions"]["escalar"]["type"] == "noul"


@pytest.mark.asyncio
async def test_classify_tone_jev_noul_baixo_nao_escala():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        data = {"answers": {"escalar": {"type": "noul", "noul": 0.1}}}
        return httpx.Response(200, json=data)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as mock_client:
        client = OpenRouterClient(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
            model="meta-llama/llama-3",
            timeout_s=5.0,
            client=mock_client,
            jev_model="typesafe/jev-latest",
        )
        escalate, confidence = await client.classify_tone_jev(
            message="Só queria saber o horário de funcionamento.", recent_messages=[]
        )
        assert escalate is False
        assert confidence == 0.1


@pytest.mark.asyncio
async def test_classify_tone_jev_falha_http_propaga_excecao():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as mock_client:
        client = OpenRouterClient(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
            model="meta-llama/llama-3",
            timeout_s=5.0,
            client=mock_client,
            jev_model="typesafe/jev-latest",
        )
        with pytest.raises(httpx.HTTPStatusError):
            await client.classify_tone_jev(message="teste", recent_messages=[])
