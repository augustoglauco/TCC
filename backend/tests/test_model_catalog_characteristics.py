from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import select

import app.model_catalog.characteristics as model_catalog_characteristics
from app.db.models import ModelCharacteristics
from app.model_catalog.characteristics import (
    _fetch_huggingface,
    _fetch_ollama,
    _fetch_openrouter,
    get_or_fetch,
)


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


@pytest.fixture
def http_client_openrouter_ok():
    payload = [{"id": "openai/gpt-4o-mini", "context_length": 128000, "architecture": {}}]

    def handler(request):
        return httpx.Response(200, json={"data": payload})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_get_or_fetch_busca_e_salva_quando_nao_existe(db_session, http_client_openrouter_ok):
    import app.model_catalog.characteristics as mod

    mod._openrouter_cache["models"] = None
    mod._openrouter_cache["fetched_at"] = None

    resultado = await get_or_fetch(
        db_session, "openrouter", "openai/gpt-4o-mini", http_client=http_client_openrouter_ok
    )

    assert resultado is not None
    assert resultado.source == "openrouter"
    assert resultado.tag == "openai/gpt-4o-mini"
    assert resultado.context_length == 128000

    linhas = (await db_session.execute(select(ModelCharacteristics))).scalars().all()
    assert len(linhas) == 1


async def test_get_or_fetch_cache_fresco_nao_rechama_a_fonte(db_session):
    existente = ModelCharacteristics(
        source="openrouter",
        tag="openai/gpt-4o-mini",
        is_multimodal=True,
        input_modalities=["text", "image"],
        output_modalities=["text"],
        context_length=128000,
        raw_payload={},
        fetched_at=datetime.now(UTC),
    )
    db_session.add(existente)
    await db_session.commit()

    http_client_nao_deve_ser_chamado = AsyncMock()

    resultado = await get_or_fetch(
        db_session,
        "openrouter",
        "openai/gpt-4o-mini",
        http_client=http_client_nao_deve_ser_chamado,
    )

    assert resultado.id == existente.id
    http_client_nao_deve_ser_chamado.get.assert_not_called()


async def test_get_or_fetch_cache_stale_rechama_e_atualiza(db_session, http_client_openrouter_ok):
    import app.model_catalog.characteristics as mod

    mod._openrouter_cache["models"] = None
    mod._openrouter_cache["fetched_at"] = None

    antigo = ModelCharacteristics(
        source="openrouter",
        tag="openai/gpt-4o-mini",
        is_multimodal=False,
        input_modalities=["text"],
        output_modalities=["text"],
        context_length=1,
        raw_payload={},
        fetched_at=datetime.now(UTC) - timedelta(days=8),
    )
    db_session.add(antigo)
    await db_session.commit()
    id_antigo = antigo.id

    resultado = await get_or_fetch(
        db_session, "openrouter", "openai/gpt-4o-mini", http_client=http_client_openrouter_ok
    )

    assert resultado.id == id_antigo  # upsert na mesma linha, não duplica
    assert resultado.context_length == 128000


async def test_get_or_fetch_force_refresh_ignora_cache_fresco(
    db_session, http_client_openrouter_ok
):
    import app.model_catalog.characteristics as mod

    mod._openrouter_cache["models"] = None
    mod._openrouter_cache["fetched_at"] = None

    fresco = ModelCharacteristics(
        source="openrouter",
        tag="openai/gpt-4o-mini",
        is_multimodal=False,
        input_modalities=["text"],
        output_modalities=["text"],
        context_length=1,
        raw_payload={},
        fetched_at=datetime.now(UTC),
    )
    db_session.add(fresco)
    await db_session.commit()

    resultado = await get_or_fetch(
        db_session,
        "openrouter",
        "openai/gpt-4o-mini",
        force_refresh=True,
        http_client=http_client_openrouter_ok,
    )

    assert resultado.context_length == 128000


async def test_get_or_fetch_falha_com_cache_stale_serve_o_stale(db_session):
    def handler(request):
        raise httpx.ConnectError("sem rede", request=request)

    http_client_falho = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    import app.model_catalog.characteristics as mod

    mod._openrouter_cache["models"] = None
    mod._openrouter_cache["fetched_at"] = None

    antigo = ModelCharacteristics(
        source="openrouter",
        tag="openai/gpt-4o-mini",
        is_multimodal=False,
        input_modalities=["text"],
        output_modalities=["text"],
        context_length=42,
        raw_payload={},
        fetched_at=datetime.now(UTC) - timedelta(days=8),
    )
    db_session.add(antigo)
    await db_session.commit()

    resultado = await get_or_fetch(
        db_session, "openrouter", "openai/gpt-4o-mini", http_client=http_client_falho
    )

    assert resultado is not None
    assert resultado.context_length == 42  # continua servindo o stale


async def test_get_or_fetch_falha_sem_cache_nenhum_retorna_none(db_session):
    def handler(request):
        raise httpx.ConnectError("sem rede", request=request)

    http_client_falho = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    import app.model_catalog.characteristics as mod

    mod._openrouter_cache["models"] = None
    mod._openrouter_cache["fetched_at"] = None

    resultado = await get_or_fetch(
        db_session, "openrouter", "tag/nunca-visto", http_client=http_client_falho
    )

    assert resultado is None
