import httpx
import pytest

import app.model_catalog.characteristics as model_catalog_characteristics
from app.model_catalog.characteristics import _fetch_openrouter


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
