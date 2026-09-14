import shutil
import socket
import subprocess

import pytest

from app.config import get_settings
from app.rag.embeddings import TextEmbedder


@pytest.fixture(scope="session")
def text_embedder() -> TextEmbedder:
    """Instância compartilhada do embedder real (sentence-transformers).

    Escopo de sessão para carregar o modelo uma única vez (o download/carga
    do modelo é o custo caro, não a inferência em si) — reaproveitada entre
    todos os testes que precisam de embeddings reais.
    """
    return TextEmbedder()


def _gpu_disponivel() -> bool:
    """Detecta GPU NVIDIA via `nvidia-smi` — sem depender de `torch` (não é
    dependência do projeto; faster-whisper roda sobre ctranslate2, não
    expõe uma checagem de disponibilidade de GPU própria)."""
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return False
    try:
        return subprocess.run([nvidia_smi, "-L"], capture_output=True, timeout=5).returncode == 0
    except OSError:
        return False


def _qdrant_disponivel() -> bool:
    """Testa conectividade TCP rápida com o Qdrant configurado em `.env`
    (`QDRANT_HOST`/`QDRANT_PORT`) — checagem síncrona simples via socket, sem
    precisar do client async (não há event loop rodando neste ponto da
    coleta de testes)."""
    settings = get_settings()
    try:
        with socket.create_connection(
            (settings.qdrant_host, settings.qdrant_port), timeout=1.0
        ):
            return True
    except OSError:
        return False


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    # MVP: checagem simples de disponibilidade de infra opcional (GPU,
    # Qdrant) — os markers `gpu`/`qdrant` (registrados em pyproject.toml)
    # antes só documentavam a dependência sem nada pular de fato o teste
    # quando a infra não está no ar; isso fazia `pytest` falhar (em vez de
    # pular) em uma máquina sem GPU/sem `docker compose up`.
    marker_names = {mark.name for item in items for mark in item.iter_markers()}
    gpu_ok = _gpu_disponivel() if "gpu" in marker_names else True
    qdrant_ok = _qdrant_disponivel() if "qdrant" in marker_names else True

    skip_gpu = pytest.mark.skip(reason="GPU NVIDIA não detectada (nvidia-smi ausente/sem GPU)")
    skip_qdrant = pytest.mark.skip(
        reason="Qdrant não respondeu em QDRANT_HOST:QDRANT_PORT (ver backend/docker-compose.yml)"
    )

    for item in items:
        if "gpu" in item.keywords and not gpu_ok:
            item.add_marker(skip_gpu)
        if "qdrant" in item.keywords and not qdrant_ok:
            item.add_marker(skip_qdrant)
