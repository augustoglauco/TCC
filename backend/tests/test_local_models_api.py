import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.local_models import _background_tasks, get_ollama_client, get_pull_progress_store
from app.api.local_models import router as local_models_router
from app.router.ollama_client import LocalModel, PullProgressLine


class _FakeOllamaClient:
    """Dublê de `OllamaClient` — sem depender de um servidor Ollama real."""

    def __init__(self, models: list[LocalModel], model_ativo: str) -> None:
        self._models = models
        self.model = model_ativo
        self.pull_calls: list[str] = []
        self._pull_lines: dict[str, list[PullProgressLine]] = {}

    async def list_local_models(self) -> list[LocalModel]:
        return self._models

    def programar_pull(self, name: str, linhas: list[PullProgressLine]) -> None:
        self._pull_lines[name] = linhas

    async def pull_model_streaming(self, name: str):
        self.pull_calls.append(name)
        for linha in self._pull_lines.get(name, []):
            yield linha


def _build_app(ollama: _FakeOllamaClient, progress_store: dict | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(local_models_router)
    app.dependency_overrides[get_ollama_client] = lambda: ollama
    app.dependency_overrides[get_pull_progress_store] = lambda: (
        progress_store if progress_store is not None else {}
    )
    return app


def test_listar_modelos_marca_o_ativo(monkeypatch):
    ollama = _FakeOllamaClient(
        models=[
            LocalModel(name="llama3.1:8b", size_bytes=100, modified_at="2026-01-01"),
            LocalModel(name="qwen2.5:7b", size_bytes=200, modified_at="2026-01-02"),
        ],
        model_ativo="qwen2.5:7b",
    )
    client = TestClient(_build_app(ollama))

    response = client.get("/api/admin/local-models")

    assert response.status_code == 200
    body = response.json()
    assert body["active_model"] == "qwen2.5:7b"
    ativos = {m["name"]: m["is_active"] for m in body["models"]}
    assert ativos == {"llama3.1:8b": False, "qwen2.5:7b": True}


def test_ativar_modelo_existente_troca_o_ativo():
    ollama = _FakeOllamaClient(
        models=[
            LocalModel(name="llama3.1:8b", size_bytes=100, modified_at="2026-01-01"),
            LocalModel(name="qwen2.5:7b", size_bytes=200, modified_at="2026-01-02"),
        ],
        model_ativo="qwen2.5:7b",
    )
    client = TestClient(_build_app(ollama))

    response = client.post("/api/admin/local-models/activate", json={"name": "llama3.1:8b"})

    assert response.status_code == 204
    assert ollama.model == "llama3.1:8b"


def test_ativar_modelo_nao_baixado_retorna_404():
    ollama = _FakeOllamaClient(models=[], model_ativo="llama3.1:8b")
    client = TestClient(_build_app(ollama))

    response = client.post("/api/admin/local-models/activate", json={"name": "inexistente"})

    assert response.status_code == 404
    assert ollama.model == "llama3.1:8b"


def test_pull_dispara_download_e_devolve_202_na_hora():
    ollama = _FakeOllamaClient(models=[], model_ativo="llama3.1:8b")
    ollama.programar_pull(
        "novo-modelo",
        [
            PullProgressLine(
                status="pulling manifest", digest=None, total=None, completed=None, error=None
            ),
            PullProgressLine(
                status="pulling sha256:abc",
                digest="sha256:abc",
                total=1000,
                completed=1000,
                error=None,
            ),
            PullProgressLine(
                status="success", digest=None, total=None, completed=None, error=None
            ),
        ],
    )
    progress_store: dict = {}
    client = TestClient(_build_app(ollama, progress_store))

    response = client.post("/api/admin/local-models/pull", json={"name": "novo-modelo"})

    assert response.status_code == 202
    assert response.json() == {"name": "novo-modelo"}


async def test_pull_atualiza_o_progresso_ate_done():
    ollama = _FakeOllamaClient(models=[], model_ativo="llama3.1:8b")
    ollama.programar_pull(
        "novo-modelo",
        [
            PullProgressLine(
                status="pulling manifest", digest=None, total=None, completed=None, error=None
            ),
            PullProgressLine(
                status="pulling sha256:abc",
                digest="sha256:abc",
                total=1000,
                completed=500,
                error=None,
            ),
            PullProgressLine(
                status="success", digest=None, total=None, completed=None, error=None
            ),
        ],
    )
    progress_store: dict = {}
    client = TestClient(_build_app(ollama, progress_store))

    client.post("/api/admin/local-models/pull", json={"name": "novo-modelo"})
    # A tarefa em background roda no mesmo loop de eventos do TestClient
    # (TransportClient síncrono por baixo do capô roda o loop até
    # completar cada requisição) — como o dublê itera uma lista já pronta
    # em memória (sem I/O de verdade), a tarefa termina antes da próxima
    # requisição HTTP. Se este teste ficar flaky, trocar por um
    # `await asyncio.sleep(0)` explícito não resolveria (TestClient não
    # compartilha o loop do teste `async def`) — nesse caso, poll o
    # endpoint de status algumas vezes com um pequeno `time.sleep` entre
    # tentativas em vez de assumir conclusão imediata.
    await asyncio.sleep(0)

    response = client.get("/api/admin/local-models/pull-status", params={"name": "novo-modelo"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert body["percent"] == 100.0


async def test_pull_sem_linha_de_sucesso_marca_erro():
    """Item 1 (nice-to-have parked): se o stream termina sem uma linha
    `{"status": "success"}` (ex.: conexão encerrada de forma limpa antes da
    confirmação do Ollama), o pull não deve ser marcado como `done`."""
    ollama = _FakeOllamaClient(models=[], model_ativo="llama3.1:8b")
    ollama.programar_pull(
        "modelo-sem-confirmacao",
        [
            PullProgressLine(
                status="pulling manifest", digest=None, total=None, completed=None, error=None
            ),
            PullProgressLine(
                status="pulling sha256:abc",
                digest="sha256:abc",
                total=1000,
                completed=1000,
                error=None,
            ),
            # Sem linha "success" — stream terminou limpo, mas sem confirmação.
        ],
    )
    progress_store: dict = {}
    client = TestClient(_build_app(ollama, progress_store))

    client.post("/api/admin/local-models/pull", json={"name": "modelo-sem-confirmacao"})
    await asyncio.sleep(0)

    response = client.get(
        "/api/admin/local-models/pull-status", params={"name": "modelo-sem-confirmacao"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert "confirmação" in body["detail"].lower()


async def test_pull_concluido_remove_a_tarefa_do_set_de_referencias_fortes():
    """Item 2 (nice-to-have parked): a Task de background deve ser
    descartada do set `_background_tasks` assim que termina, para não
    vazar memória nem deixar o set crescendo indefinidamente."""
    _background_tasks.clear()
    ollama = _FakeOllamaClient(models=[], model_ativo="llama3.1:8b")
    ollama.programar_pull(
        "modelo-referencia-forte",
        [
            PullProgressLine(
                status="success", digest=None, total=None, completed=None, error=None
            ),
        ],
    )
    progress_store: dict = {}
    client = TestClient(_build_app(ollama, progress_store))

    client.post("/api/admin/local-models/pull", json={"name": "modelo-referencia-forte"})
    await asyncio.sleep(0)

    response = client.get(
        "/api/admin/local-models/pull-status", params={"name": "modelo-referencia-forte"}
    )
    assert response.json()["status"] == "done"
    assert len(_background_tasks) == 0


def test_pull_duplicado_nao_dispara_segunda_tarefa():
    ollama = _FakeOllamaClient(models=[], model_ativo="llama3.1:8b")
    progress_store = {"ja-baixando": {"status": "pulling", "percent": 10.0, "detail": "..."}}
    client = TestClient(_build_app(ollama, progress_store))

    response = client.post("/api/admin/local-models/pull", json={"name": "ja-baixando"})

    assert response.status_code == 202
    assert ollama.pull_calls == []


def test_status_sem_pull_iniciado_retorna_404():
    ollama = _FakeOllamaClient(models=[], model_ativo="llama3.1:8b")
    client = TestClient(_build_app(ollama))

    response = client.get("/api/admin/local-models/pull-status", params={"name": "nunca-baixado"})

    assert response.status_code == 404


def test_status_com_nome_contendo_barra_e_dois_pontos_funciona():
    """Regressão: nomes de modelo podem conter `/` (Hugging Face) e `:`
    (tag) — o endpoint usa `name` como query param, não path param, para
    não quebrar nesses casos."""
    ollama = _FakeOllamaClient(models=[], model_ativo="llama3.1:8b")
    progress_store = {
        "hf.co/usuario/repo:Q4_K_M": {"status": "done", "percent": 100.0, "detail": "concluído"}
    }
    client = TestClient(_build_app(ollama, progress_store))

    response = client.get(
        "/api/admin/local-models/pull-status", params={"name": "hf.co/usuario/repo:Q4_K_M"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "done"
