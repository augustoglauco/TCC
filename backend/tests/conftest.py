import shutil
import socket
import subprocess
import uuid

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.db.engine import create_db_engine, create_session_factory
from app.db.models import Base, RagCollection
from app.rag.embeddings import TextEmbedder


class _FakeQdrantRAGClient:
    """Dublê de `QdrantRAGClient` — só registra o que seria gravado/excluído
    no Qdrant (ou levanta `error`, se informado), sem depender de uma
    instância real.

    Compartilhado entre `test_rag_ingest.py` e `test_rag_api.py` (mesmo
    contrato, exercitado em duas camadas diferentes: pipeline de ingestão e
    endpoint HTTP).
    """

    def __init__(
        self,
        error: Exception | None = None,
        collections_existentes: set[str] | None = None,
    ) -> None:
        self._error = error
        # None = comportamento default (toda collection "já existe", como nos
        # testes anteriores à checagem self-healing de `ingest_bytes`); um
        # `set` explícito simula quais collections já existem no Qdrant,
        # usado pelo teste da recriação idempotente (ver `test_rag_ingest.py`).
        self._collections_existentes = collections_existentes
        self.upserts: list[tuple[str, list[str], str, str, str]] = []
        self.deleted: list[tuple[str, str]] = []
        self.dropped_collections: list[str] = []
        self.created_collections: list[str] = []

    async def collection_exists(self, collection_name: str) -> bool:
        if self._collections_existentes is None:
            return True
        return collection_name in self._collections_existentes

    async def create_collection(self, *, name: str, **kwargs) -> None:
        if self._error is not None:
            raise self._error
        self.created_collections.append(name)
        if self._collections_existentes is not None:
            self._collections_existentes.add(name)

    async def upsert_chunks(
        self,
        collection_name: str,
        embedder,
        chunks: list[str],
        source: str,
        domain: str,
        document_id: str,
    ) -> int:
        if self._error is not None:
            raise self._error
        self.upserts.append((collection_name, chunks, source, domain, document_id))
        return len(chunks)

    async def delete_by_document_id(self, collection_name: str, document_id: str) -> None:
        if self._error is not None:
            raise self._error
        self.deleted.append((collection_name, document_id))

    async def drop_collection(self, collection_name: str) -> None:
        if self._error is not None:
            raise self._error
        self.dropped_collections.append(collection_name)


@pytest.fixture(scope="session", autouse=True)
def _isola_banco_de_telemetria(tmp_path_factory):
    """Impede que a suíte escreva no Postgres real do desenvolvedor.

    O lifespan de `app.main` monta o engine a partir de `settings.postgres_dsn`
    e aponta os sessionmakers GLOBAIS de `app.services.ai_usage` e
    `app.services.ingestion_metrics` para ele (`main.py:253-257`). Todo teste
    que sobe a app de verdade (`with TestClient(app)`) executava esse lifespan
    com o `.env` real — e, como esses globais são variáveis de módulo que
    ninguém reseta, os registros fire-and-forget (`registrar_uso_ia(session=
    None, session_factory=None)`) dos testes SEGUINTES caíam no fallback
    global e gravavam no banco do dev, com os dados dos dublês.

    Sintoma que isso produziu (2026-10-12): o painel `/admin/metricas` exibia
    129 chamadas internas com modelo "desconhecido" e tokens vazios — a
    assinatura do dublê `_DomainAwareLLMClient`, que devolve `LLMResponse`
    sem `model_name` nem tokens. Nenhuma chamada real: o `OllamaClient`
    preenche `model_name` desde 2026-09-17.

    A fixture troca o DSN por um SQLite de arquivo próprio da sessão de
    testes, com o schema criado — assim o lifespan continua funcionando (e
    sendo exercitado de verdade), as gravações de telemetria continuam
    acontecendo e sendo observáveis, mas em um banco descartável.
    """
    import asyncio

    caminho = tmp_path_factory.mktemp("telemetria") / "telemetria_testes.sqlite"
    dsn = f"sqlite+aiosqlite:///{caminho}"

    async def _criar_schema() -> None:
        engine = create_db_engine(dsn)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(_criar_schema())

    mp = pytest.MonkeyPatch()
    mp.setattr(get_settings(), "postgres_dsn", dsn)
    yield dsn
    mp.undo()


@pytest.fixture(autouse=True)
def _reset_sessionmakers_globais():
    """Zera, entre testes, os sessionmakers globais de telemetria que o
    lifespan de `app.main` configura — segunda camada da proteção descrita em
    `_isola_banco_de_telemetria`. Sem isso, um teste que sobe a app deixa o
    global apontando para o banco dela e contamina os testes posteriores:
    `pytest tests/test_main_app.py tests/test_integration_domains.py` gravava
    12 eventos fora do banco do próprio teste; cada arquivo sozinho, nenhum."""
    yield
    from app.services.ai_usage import set_global_sessionmaker as _reset_ai
    from app.services.ingestion_metrics import set_global_sessionmaker as _reset_ing

    _reset_ai(None)
    _reset_ing(None)


@pytest.fixture(autouse=True)
def _reset_openrouter_cache():
    """Isola o cache em memória do processo da lista do OpenRouter
    (`app.model_catalog.characteristics._openrouter_cache`, TTL de 1h) entre
    testes — sem isso, o cache populado por um teste vazaria para o
    próximo e mascararia, por exemplo, uma falha de rede simulada.
    Compartilhada por `test_model_catalog_characteristics.py` e
    `test_model_catalog_api.py` (achado "Minor B" da revisão final — antes
    só o primeiro tinha essa fixture; o segundo fazia o reset manualmente
    em cada teste)."""
    import app.model_catalog.characteristics as mod

    mod._openrouter_cache["models"] = None
    mod._openrouter_cache["fetched_at"] = None
    yield


class _CommitFailingSession:
    """Encapsula uma `AsyncSession` real, repassando toda leitura/escrita
    normalmente, exceto `commit()`, que levanta `SQLAlchemyError` — simula
    uma falha de Postgres na escrita final de um endpoint (ex.:
    `reingest_document`/`delete_collection` gravando o resultado), depois
    que leituras/lookups anteriores no mesmo request já tiveram sucesso.
    Usado nos testes de achado #2 da revisão final (endpoints das
    collections/reingest que não tratavam `SQLAlchemyError` como os
    handlers de documentos já tratavam).
    """

    def __init__(self, session) -> None:
        self._session = session

    def __getattr__(self, name):
        return getattr(self._session, name)

    async def commit(self) -> None:
        raise SQLAlchemyError("conexão com o banco indisponível")


@pytest.fixture(scope="session")
def text_embedder() -> TextEmbedder:
    """Instância compartilhada do embedder real (sentence-transformers).

    Escopo de sessão para carregar o modelo uma única vez (o download/carga
    do modelo é o custo caro, não a inferência em si) — reaproveitada entre
    todos os testes que precisam de embeddings reais.
    """
    return TextEmbedder()


@pytest.fixture
async def active_collection(db_session) -> RagCollection:
    """Uma `RagCollection` ativa já commitada — usada por todo teste que
    precisa de uma collection para ingerir/buscar (ver
    docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §3)."""
    collection = RagCollection(
        id=uuid.uuid4(),
        name="docs_texto",
        embedding_model="fake-embedding-model",
        vector_dimension=384,
        distance_metric="cosine",
        chunk_size=800,
        chunk_overlap=100,
        hnsw_m=16,
        hnsw_ef_construct=100,
        hnsw_full_scan_threshold=10000,
        hnsw_max_indexing_threads=0,
        hnsw_on_disk=False,
        hnsw_payload_m=None,
        quantization_type="none",
        quantization_config={},
        payload_indexes=[],
        is_active=True,
    )
    db_session.add(collection)
    await db_session.commit()
    await db_session.refresh(collection)
    return collection


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
        with socket.create_connection((settings.qdrant_host, settings.qdrant_port), timeout=1.0):
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


@pytest.fixture
async def db_session():
    """Sessão contra um SQLite assíncrono em memória, schema já criado —
    usado por todo teste que precisa do registro de documentos
    (`app.rag.registry`), sem depender de um Postgres real no ar.

    # MVP: teste de unidade da camada de acesso a dados usa SQLite em
    # memória em vez do Postgres real — cobre a lógica de CRUD, não
    # peculiaridades específicas do dialeto Postgres (ver
    # docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md §7).
    """
    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def admin_headers(db_session) -> dict[str, str]:
    """Cria um `Cliente` admin real em `db_session` e devolve o header
    `Authorization` correspondente — todo router sob `_require_admin`/
    `require_admin` (ver `app.api.admin_auth`) exige essa checagem desde a
    revisão de 2026-10-04 (achado: vários endpoints administrativos sem
    nenhuma autenticação no servidor)."""
    from app.db.models import Cliente

    admin = Cliente(nome="Admin Teste", email="admin@empresa.com")
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return {"Authorization": f"Bearer mock-token-{admin.id}"}


class _FakeClipImageStore:
    """Dublê do `ClipImageStore` para os testes das APIs de produtos: não
    embeda nem grava vetor nenhum no Qdrant."""

    async def upsert_image(self, **kwargs) -> str:
        return f"clip-fake-{uuid.uuid4().hex[:8]}"

    async def delete_image(self, image_id: str) -> None:
        return None

    async def delete_images_by_product_id(self, produto_id: int) -> None:
        return None

    async def delete_images_by_url(self, imagem_url: str) -> None:
        return None


@pytest.fixture
def app_sqlite(db_session, tmp_path, monkeypatch):
    """App real (`create_app`) com o banco trocado pelo SQLite em memória da
    fixture `db_session`, o CLIP/Qdrant por um dublê e as fotos de produto
    gravadas em `tmp_path`.

    Antes, os testes das APIs de produtos e do extrator de catálogo usavam o
    Postgres, o Qdrant e a pasta de fotos reais do desenvolvedor: criavam e
    apagavam produtos de verdade e, quando falhavam no meio, deixavam lixo no
    catálogo (o "Produto Teste Lote" apareceu como candidato no teste local
    de 2026-09-27, cenário V12).
    """
    from app.api.admin_products import _get_clip_embedder, _get_clip_store
    from app.api.rag_dependencies import get_db_session
    from app.main import create_app

    monkeypatch.setattr(get_settings(), "product_images_dir", str(tmp_path))
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: db_session
    app.dependency_overrides[_get_clip_store] = lambda: _FakeClipImageStore()
    app.dependency_overrides[_get_clip_embedder] = lambda: object()
    return app


@pytest.fixture(autouse=True)
def _reset_agent_runtime():
    """O runtime dos agentes (R13) é estado de processo: restaura entre testes."""
    from app.agents.runtime import AgentRuntime, runtime

    runtime.__dict__.update(AgentRuntime().__dict__)
    yield
    runtime.__dict__.update(AgentRuntime().__dict__)


@pytest.fixture(autouse=True)
def _sem_smtp_real(monkeypatch):
    """Testes nunca enviam e-mail de verdade, mesmo com SMTP no `.env` local.

    Testes de envio que precisam de SMTP configurado definem os campos por
    conta própria (e trocam o transporte por um falso).
    """
    from app.config import get_settings

    settings = get_settings()
    for campo in ("smtp_host", "smtp_user", "smtp_password", "smtp_from", "admin_alert_email"):
        monkeypatch.setattr(settings, campo, "", raising=False)
