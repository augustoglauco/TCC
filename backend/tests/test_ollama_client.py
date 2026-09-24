import json

import httpx
import pytest

from app.router.llm_client import LLMStreamChunk
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


async def test_timeout_s_property_e_setter():
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_transport({})),
    )

    assert client.timeout_s == 30.0

    client.timeout_s = 60.0

    assert client.timeout_s == 60.0


def _capturing_transport(json_response: dict) -> tuple[httpx.MockTransport, list[dict]]:
    payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json=json_response)

    return httpx.MockTransport(handler), payloads


async def test_temperature_none_por_padrao_nao_manda_options():
    transport, payloads = _capturing_transport({"response": "oi"})
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=transport),
    )

    assert client.temperature is None

    await client.generate("oi")

    assert "options" not in payloads[0]


async def test_temperature_setada_manda_options_no_payload():
    transport, payloads = _capturing_transport({"response": "oi"})
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=transport),
    )

    client.temperature = 0.0

    assert client.temperature == 0.0

    await client.generate("oi")

    assert payloads[0]["options"] == {"temperature": 0.0}


async def test_generate_manda_think_false():
    # Achado real (2026-09-23): modelos com capability "thinking" (ex.:
    # gemma4:12b-it-q4_K_M) geram milhares de tokens de raciocínio interno
    # antes de responder um JSON curto — ~50s e às vezes resposta vazia/
    # incorreta para os três chamadores de generate() (classificador,
    # extração de agendamento, classificador do crawler), que só querem
    # JSON estruturado curto. think=False evita isso; confirmado que Ollama
    # ignora o campo com segurança em modelos sem a capability.
    transport, payloads = _capturing_transport({"response": "oi"})
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=transport),
    )

    await client.generate("oi")

    assert payloads[0]["think"] is False


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


async def test_generate_stream_emite_um_chunk_de_texto_por_linha_e_chunk_final_com_telemetria():
    lines = [
        json.dumps({"response": "Olá"}),
        json.dumps({"response": ", tudo bem?"}),
        json.dumps(
            {
                "response": "",
                "done": True,
                "prompt_eval_count": 12,
                "eval_count": 34,
                "total_duration": 2_500_000_000,
                "load_duration": 500_000_000,
                "prompt_eval_duration": 200_000_000,
                "eval_duration": 1_800_000_000,
            }
        ),
    ]
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_streaming_transport(lines)),
    )

    chunks = [chunk async for chunk in client.generate_stream("oi")]

    assert len(chunks) == 3
    assert chunks[0] == LLMStreamChunk(text="Olá")
    assert chunks[1] == LLMStreamChunk(text=", tudo bem?")
    assert chunks[2].done is True
    assert chunks[2].text is None
    assert chunks[2].prompt_tokens == 12
    assert chunks[2].completion_tokens == 34
    assert chunks[2].total_duration_ms == 2500.0
    assert chunks[2].load_duration_ms == 500.0
    assert chunks[2].prompt_eval_duration_ms == 200.0
    assert chunks[2].eval_duration_ms == 1800.0
    assert chunks[2].model_name == "llama3.1:8b"


async def test_generate_stream_manda_think_false():
    # Correção de 2026-09-24 (docs/ARCHITECTURE.md §5): a decisão original
    # de think=False só em generate() (2026-09-23) não previa que um modelo
    # com capability thinking pudesse gastar todo o orçamento de geração
    # raciocinando no chat via streaming também — reproduzido direto contra
    # o Ollama com qwen3.5:9b (ver teste seguinte).
    payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        body = json.dumps({"response": "oi", "done": True}).encode()
        return httpx.Response(200, content=body)

    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    _ = [chunk async for chunk in client.generate_stream("oi")]

    assert payloads[0]["think"] is False


async def test_generate_stream_thinking_esgota_orcamento_sem_gerar_resposta():
    # Reproduz o achado real: um modelo com capability thinking pode
    # devolver só linhas com `thinking` preenchido e `response` vazio, até
    # `done: true` com `eval_count` não-zero — o orçamento inteiro foi
    # consumido "pensando", sem nunca chegar no texto de resposta. Este
    # teste documenta que o parsing atual (ignora `thinking`, só lê
    # `response`) não quebra nesse caso — não emite chunk de texto algum,
    # só o chunk final com a telemetria — mas é justamente esse caminho que
    # think=False (testado acima) evita entrar.
    lines = [
        json.dumps({"response": "", "thinking": "Deixa eu pensar", "done": False}),
        json.dumps({"response": "", "thinking": " nisso...", "done": False}),
        json.dumps(
            {
                "response": "",
                "done": True,
                "done_reason": "length",
                "prompt_eval_count": 36,
                "eval_count": 20,
                "total_duration": 991_332_838,
            }
        ),
    ]
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="qwen3.5:9b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_streaming_transport(lines)),
    )

    chunks = [chunk async for chunk in client.generate_stream("oi")]

    assert len(chunks) == 1
    assert chunks[0].done is True
    assert chunks[0].completion_tokens == 20


async def test_generate_stream_levanta_excecao_quando_linha_traz_error():
    # O Ollama pode emitir uma linha `{"error": "..."}` no meio do stream
    # (ex.: falta de VRAM durante o cold-start do modelo) em vez de
    # `response`/`done` — o cliente deve propagar isso como exceção, não
    # ignorar silenciosamente a linha.
    lines = [
        json.dumps({"response": "Olá"}),
        json.dumps({"error": "model requires more system memory than is available"}),
    ]
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_streaming_transport(lines)),
    )

    with pytest.raises(RuntimeError, match="system memory"):
        _ = [chunk async for chunk in client.generate_stream("oi")]


async def test_generate_stream_com_resposta_de_uma_linha_so():
    lines = [
        json.dumps(
            {
                "response": "ok",
                "done": True,
                "prompt_eval_count": 1,
                "eval_count": 1,
                "total_duration": 100_000_000,
            }
        ),
    ]
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_streaming_transport(lines)),
    )

    chunks = [chunk async for chunk in client.generate_stream("oi")]

    # Uma linha só, mas com `response` não vazio E `done=True` — emite os
    # dois: o fragmento de texto primeiro, depois o chunk final.
    assert len(chunks) == 2
    assert chunks[0] == LLMStreamChunk(text="ok")
    assert chunks[1].done is True
