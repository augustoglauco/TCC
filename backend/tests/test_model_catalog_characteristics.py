from unittest.mock import AsyncMock

import httpx
import pytest

import app.model_catalog.characteristics as model_catalog_characteristics
from app.model_catalog.characteristics import _fetch_huggingface, _fetch_ollama, _fetch_openrouter


@pytest.fixture(autouse=True)
def _reset_openrouter_cache():
    """Isola o cache em memória do módulo entre testes — sem isso, o
    cache (TTL de 1h) populado por um teste vazaria para o próximo e
    mascararia, por exemplo, uma falha de rede simulada."""
    model_catalog_characteristics._openrouter_cache["models"] = None
    model_catalog_characteristics._openrouter_cache["fetched_at"] = None
    yield


def _mock_openrouter_transport(models: list[dict]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": models})

    return httpx.MockTransport(handler)


async def test_fetch_openrouter_mapeia_modelo_multimodal():
    models = [
        {
            "id": "openai/gpt-4o-mini",
            "context_length": 128000,
            "architecture": {
                "input_modalities": ["text", "image", "file"],
                "output_modalities": ["text"],
            },
            "pricing": {"prompt": "0.00000015", "completion": "0.0000006"},
            "knowledge_cutoff": "2023-10-31",
        }
    ]
    http_client = httpx.AsyncClient(transport=_mock_openrouter_transport(models))

    resultado = await _fetch_openrouter("openai/gpt-4o-mini", http_client)

    assert resultado is not None
    assert resultado["input_modalities"] == ["text", "image", "file"]
    assert resultado["output_modalities"] == ["text"]
    assert resultado["context_length"] == 128000
    assert resultado["pricing_prompt_per_1k"] == pytest.approx(0.00000015 * 1000)
    assert resultado["pricing_completion_per_1k"] == pytest.approx(0.0000006 * 1000)
    assert resultado["knowledge_cutoff"] == "2023-10-31"
    assert resultado["raw_payload"] == models[0]


async def test_fetch_openrouter_tag_inexistente_retorna_none():
    http_client = httpx.AsyncClient(transport=_mock_openrouter_transport([{"id": "outro/modelo"}]))

    assert await _fetch_openrouter("nao/existe", http_client) is None


async def test_fetch_openrouter_erro_de_rede_retorna_none():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede", request=request)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    assert await _fetch_openrouter("openai/gpt-4o-mini", http_client) is None


async def test_fetch_openrouter_cacheia_lista_entre_chamadas():
    """Duas tags pedidas em sequência não devem disparar duas requisições —
    a lista completa (466 modelos reais) é cacheada em memória do processo
    por 1h (ver spec §2)."""
    import app.model_catalog.characteristics as mod

    mod._openrouter_cache["models"] = None
    mod._openrouter_cache["fetched_at"] = None

    chamadas = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas["n"] += 1
        return httpx.Response(
            200, json={"data": [{"id": "a/a"}, {"id": "b/b", "context_length": 1000}]}
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    await _fetch_openrouter("a/a", http_client)
    await _fetch_openrouter("b/b", http_client)

    assert chamadas["n"] == 1


async def test_fetch_ollama_modelo_com_visao():
    ollama_client = AsyncMock()
    ollama_client.get_model_details = AsyncMock(
        return_value={
            "capabilities": ["completion", "vision"],
            "details": {"parameter_size": "7.6B", "quantization_level": "Q4_K_M"},
            "model_info": {"qwen2vl.context_length": 32768},
        }
    )

    resultado = await _fetch_ollama("qwen2-vl:7b", ollama_client)

    assert resultado is not None
    assert resultado["input_modalities"] == ["text", "image"]
    assert resultado["output_modalities"] == ["text"]
    assert resultado["context_length"] == 32768
    assert resultado["parameter_size"] == "7.6B"
    assert resultado["quantization"] == "Q4_K_M"


async def test_fetch_ollama_modelo_so_texto():
    ollama_client = AsyncMock()
    ollama_client.get_model_details = AsyncMock(
        return_value={
            "capabilities": ["completion", "tools"],
            "details": {"parameter_size": "14.8B", "quantization_level": "Q4_K_M"},
            "model_info": {"qwen2.context_length": 131072},
        }
    )

    resultado = await _fetch_ollama("qwen2.5-coder:14b", ollama_client)

    assert resultado["input_modalities"] == ["text"]


async def test_fetch_ollama_modelo_nao_baixado_retorna_none():
    ollama_client = AsyncMock()
    ollama_client.get_model_details = AsyncMock(return_value=None)

    assert await _fetch_ollama("modelo-inexistente", ollama_client) is None


def _mock_hf_transport(payload: dict, status_code: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)

    return httpx.MockTransport(handler)


async def test_fetch_huggingface_modelo_multimodal():
    payload = {"pipeline_tag": "image-text-to-text", "tags": ["multimodal"]}
    http_client = httpx.AsyncClient(transport=_mock_hf_transport(payload))

    resultado = await _fetch_huggingface("hf.co/Qwen/Qwen2.5-VL-7B-Instruct", http_client)

    assert resultado is not None
    assert resultado["input_modalities"] == ["text", "image"]
    assert resultado["output_modalities"] == ["text"]


async def test_fetch_huggingface_remove_sufixo_de_quantizacao():
    capturado = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["path"] = request.url.path
        return httpx.Response(200, json={"pipeline_tag": "text-generation"})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    await _fetch_huggingface("hf.co/usuario/repo:Q4_K_M", http_client)

    assert capturado["path"] == "/api/models/usuario/repo"


async def test_fetch_huggingface_pipeline_tag_desconhecido():
    http_client = httpx.AsyncClient(transport=_mock_hf_transport({"pipeline_tag": "algo-novo"}))

    resultado = await _fetch_huggingface("hf.co/usuario/repo", http_client)

    assert resultado["input_modalities"] == ["desconhecido"]
    assert resultado["output_modalities"] == ["desconhecido"]


async def test_fetch_huggingface_tag_sem_prefixo_hf_co_retorna_none_sem_chamar_rede():
    chamou = {"sim": False}

    def handler(request: httpx.Request) -> httpx.Response:
        chamou["sim"] = True
        return httpx.Response(200, json={})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    assert await _fetch_huggingface("llama3.1:8b", http_client) is None
    assert chamou["sim"] is False


async def test_fetch_huggingface_repo_inexistente_retorna_none():
    http_client = httpx.AsyncClient(transport=_mock_hf_transport({}, status_code=404))

    assert await _fetch_huggingface("hf.co/usuario/nao-existe", http_client) is None
