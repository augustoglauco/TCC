# Registro e Exclusão de Documentos Ingeridos no RAG — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Toda ingestão de documento no RAG (upload HTTP ou script em lote) cria um registro em Postgres; a partir dele, um documento pode ser listado e excluído (linha do Postgres + pontos correspondentes no Qdrant).

**Architecture:** Primeiro uso real do Postgres do projeto (SQLAlchemy async + Alembic, infra já prevista mas nunca exercitada). Um `document_id` (UUID) gerado na ingestão amarra a linha do registro aos pontos do Qdrant (novo campo de payload). O pipeline de ingestão (`app/rag/ingest.py`) passa a receber uma sessão de DB e criar o registro como parte da própria ingestão, para os dois caminhos existentes (endpoint HTTP e script em lote). Frontend: página `/admin/ingestao` reorganizada em abas (Radix UI para modal/tabs), com tabela de documentos e exclusão via modal de confirmação.

**Tech Stack:** Backend: FastAPI, SQLAlchemy 2.0 (async, `asyncpg`), Alembic, Qdrant (`qdrant-client`), pytest + `aiosqlite` (testes). Frontend: Next.js 16 (App Router, `"use client"`), React 19, Tailwind CSS v4, `@radix-ui/react-dialog`, `@radix-ui/react-tabs`, Vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md`

## Global Constraints

- Exclusão de documento é **definitiva** (sem soft delete) — remove a linha do Postgres e os pontos do Qdrant.
- `document_id` (UUID) é gerado a cada ingestão, mesmo reenviando o mesmo arquivo — sem deduplicação (decisão já existente, mantida).
- Ordem de escrita: upsert no Qdrant primeiro, registro no Postgres depois. Falha do Postgres após upsert bem-sucedido → log de aviso (`rag_registro_orfao`), sem rollback cross-store.
- Testes de unidade da camada de DB usam SQLite assíncrono em memória (`aiosqlite`), não Postgres real.
- Frontend: só duas dependências novas — `@radix-ui/react-dialog` e `@radix-ui/react-tabs`. Sem kit de componentes visual completo (nada de shadcn CLI/MUI/Chakra).
- Todo texto de UI em português, consistente com o resto do frontend.
- Toda simplificação de MVP nova recebe comentário `# MVP: ...` no código, conforme `CLAUDE.md`.

---

## Backend

### Task 1: Alembic — scaffolding e primeira migração

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/migrations/env.py`
- Create: `backend/migrations/script.py.mako`
- Create: `backend/migrations/versions/0001_create_rag_documents.py`
- Modify: `backend/pyproject.toml` (dev dependency `aiosqlite`)

**Interfaces:**
- Produces: tabela Postgres `rag_documents` (colunas: `id` UUID PK, `filename` str, `domain` str, `chunk_count` int, `embedding_model` str, `chunk_size` int, `chunk_overlap` int, `origin` str, `created_at` datetime com timezone, default `now()`).

Este task não segue TDD (é scaffolding de infraestrutura, não código testável isoladamente) — a verificação é rodar a migração real contra o Postgres do `docker-compose.yml` no Task 12, depois que a tabela existir no ORM (Task 2).

- [ ] **Step 1: Adicionar `aiosqlite` às dependências de desenvolvimento**

Em `backend/pyproject.toml`, dentro de `[project.optional-dependencies]`:

```toml
dev = [
    "ruff>=0.5",
    "pytest>=8.2",
    "pytest-asyncio>=0.23",
    "aiosqlite>=0.20",
]
```

- [ ] **Step 2: Instalar as dependências novas**

Run: `cd backend && .venv/bin/pip install -e ".[dev]"`
Expected: instala `aiosqlite` (e `alembic`/`asyncpg`/`sqlalchemy` já presentes) sem erro.

- [ ] **Step 3: Criar `backend/alembic.ini`**

```ini
[alembic]
script_location = migrations

[loggers]
keys = root,sqlalchemy,alembic

[logger_root]
level = WARNING
handlers = console
qualname =

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handlers]
keys = console

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatters]
keys = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 4: Criar `backend/migrations/script.py.mako`**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 5: Criar `backend/migrations/env.py`**

Depende de `app.db.models.Base`, que só existe a partir do Task 2 — este arquivo pode ser criado agora (o import só é resolvido em runtime, quando a migração for de fato executada no Task 12).

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import get_settings
from app.db.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# MVP: DSN sempre lido de app.config.Settings (mesma fonte usada em produção),
# nunca de `alembic.ini` — evita ter a string de conexão duplicada em dois
# lugares que podem divergir.
config.set_main_option("sqlalchemy.url", get_settings().postgres_dsn)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 6: Criar a migração inicial `backend/migrations/versions/0001_create_rag_documents.py`**

```python
"""create rag_documents

Revision ID: 0001
Revises:
Create Date: 2026-09-14

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rag_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("domain", sa.String(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("embedding_model", sa.String(), nullable=False),
        sa.Column("chunk_size", sa.Integer(), nullable=False),
        sa.Column("chunk_overlap", sa.Integer(), nullable=False),
        sa.Column("origin", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("rag_documents")
```

- [ ] **Step 7: Commit**

```bash
git add backend/alembic.ini backend/migrations backend/pyproject.toml
git commit -m "chore(db): adiciona scaffolding do Alembic e migração inicial de rag_documents"
```

---

### Task 2: Engine/sessão SQLAlchemy e modelo `RagDocument`

**Files:**
- Create: `backend/src/app/db/models.py`
- Create: `backend/src/app/db/engine.py`
- Modify: `backend/tests/conftest.py` (fixture `db_session`)
- Test: `backend/tests/test_db_engine.py`

**Interfaces:**
- Produces: `app.db.models.Base` (`DeclarativeBase`), `app.db.models.RagDocument` (campos do Task 1); `app.db.engine.create_db_engine(dsn: str) -> AsyncEngine`, `app.db.engine.create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]`; fixture `db_session` (pytest, `AsyncSession` contra SQLite em memória com schema já criado).

- [ ] **Step 1: Escrever o teste (vai falhar — módulos ainda não existem)**

Criar `backend/tests/test_db_engine.py`:

```python
from sqlalchemy import select

from app.db.models import RagDocument


async def test_db_session_permite_inserir_e_consultar_rag_document(db_session):
    db_session.add(
        RagDocument(
            filename="a.txt",
            domain="vendas",
            chunk_count=1,
            embedding_model="modelo-teste",
            chunk_size=800,
            chunk_overlap=100,
            origin="upload",
        )
    )
    await db_session.commit()

    result = await db_session.execute(select(RagDocument))
    rows = result.scalars().all()

    assert len(rows) == 1
    assert rows[0].filename == "a.txt"
    assert rows[0].id is not None
    assert rows[0].created_at is not None
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd backend && .venv/bin/pytest tests/test_db_engine.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.db.models'` (ou fixture `db_session` não encontrada).

- [ ] **Step 3: Criar `backend/src/app/db/models.py`**

```python
"""Modelos SQLAlchemy do backend (primeiro uso real do Postgres — ver
docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md).
"""

import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RagDocument(Base):
    """Registro de um documento ingerido no RAG (R4, além do MVP).

    `id` também é gravado como campo de payload em cada ponto do Qdrant
    daquele documento (ver `app.rag.qdrant_client.upsert_chunks`) — é o que
    permite excluir um documento e seus vetores juntos.
    """

    __tablename__ = "rag_documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    filename: Mapped[str]
    domain: Mapped[str]
    chunk_count: Mapped[int]
    embedding_model: Mapped[str]
    chunk_size: Mapped[int]
    chunk_overlap: Mapped[int]
    origin: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

- [ ] **Step 4: Criar `backend/src/app/db/engine.py`**

```python
"""Engine/sessão assíncrona do Postgres (SQLAlchemy 2.0).

# MVP: sem singleton/lru_cache global (ao contrário de `app.config.get_settings`)
# — o engine é criado explicitamente por quem precisa dele (`app.main` em
# produção, fixtures nos testes), para não prender uma conexão "morta" entre
# testes que sobem/derrubam o banco. Mesmo espírito do `QdrantRAGClient`, que
# também é instanciado explicitamente em vez de um singleton por config.
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_db_engine(dsn: str) -> AsyncEngine:
    return create_async_engine(dsn)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
```

- [ ] **Step 5: Adicionar a fixture `db_session` em `backend/tests/conftest.py`**

Adicionar ao final do arquivo (após os imports existentes, adicionar `import pytest_asyncio` não é necessário — `asyncio_mode = "auto"` já cobre fixtures async comuns do `pytest`; usar `@pytest.fixture` normal funciona com corrotinas sob esse modo):

```python
from app.db.engine import create_db_engine, create_session_factory
from app.db.models import Base


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
```

- [ ] **Step 6: Rodar e confirmar que passa**

Run: `cd backend && .venv/bin/pytest tests/test_db_engine.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/src/app/db/models.py backend/src/app/db/engine.py backend/tests/conftest.py backend/tests/test_db_engine.py
git commit -m "feat(db): adiciona engine/sessao SQLAlchemy async e modelo RagDocument"
```

---

### Task 3: `TextEmbedder.model_name` e `QdrantRAGClient.embedding_model_name`

**Files:**
- Modify: `backend/src/app/rag/embeddings.py`
- Modify: `backend/src/app/rag/qdrant_client.py`
- Test: `backend/tests/test_rag_embeddings.py`
- Test: `backend/tests/test_rag_qdrant_client.py`

**Interfaces:**
- Produces: `TextEmbedder.model_name -> str` (property); `QdrantRAGClient.embedding_model_name -> str` (property).
- Consumes (Task 7): usado por `app.rag.ingest` para preencher `RagDocument.embedding_model` sem precisar receber esse dado como parâmetro extra.

- [ ] **Step 1: Escrever o teste do embedder**

Adicionar ao final de `backend/tests/test_rag_embeddings.py`:

```python
def test_model_name_expoe_o_nome_do_modelo_configurado():
    embedder = TextEmbedder("modelo-de-teste")

    assert embedder.model_name == "modelo-de-teste"
```

(Confirme que `TextEmbedder` já está importado no topo do arquivo — se o arquivo existente importar só o necessário para os testes atuais, ajuste o import para incluir `TextEmbedder` caso ainda não esteja.)

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd backend && .venv/bin/pytest tests/test_rag_embeddings.py::test_model_name_expoe_o_nome_do_modelo_configurado -v`
Expected: FAIL — `AttributeError: 'TextEmbedder' object has no attribute 'model_name'`

- [ ] **Step 3: Implementar a property em `embeddings.py`**

Adicionar, logo após o método `__init__` da classe `TextEmbedder`:

```python
    @property
    def model_name(self) -> str:
        return self._model_name
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd backend && .venv/bin/pytest tests/test_rag_embeddings.py::test_model_name_expoe_o_nome_do_modelo_configurado -v`
Expected: PASS

- [ ] **Step 5: Escrever o teste do `QdrantRAGClient`**

Adicionar a `backend/tests/test_rag_qdrant_client.py` (perto das outras funções que usam a fixture `rag_client`):

```python
async def test_embedding_model_name_expoe_o_nome_do_modelo_do_embedder(
    rag_client: QdrantRAGClient, text_embedder: TextEmbedder
):
    assert rag_client.embedding_model_name == text_embedder.model_name
```

- [ ] **Step 6: Rodar e confirmar que falha**

Run: `cd backend && .venv/bin/pytest tests/test_rag_qdrant_client.py::test_embedding_model_name_expoe_o_nome_do_modelo_do_embedder -v`
Expected: FAIL — `AttributeError: 'QdrantRAGClient' object has no attribute 'embedding_model_name'`

- [ ] **Step 7: Implementar a property em `qdrant_client.py`**

Adicionar ao `QdrantRAGClient`, logo após `__init__`:

```python
    @property
    def embedding_model_name(self) -> str:
        return self._embedder.model_name
```

- [ ] **Step 8: Rodar e confirmar que passa**

Run: `cd backend && .venv/bin/pytest tests/test_rag_qdrant_client.py::test_embedding_model_name_expoe_o_nome_do_modelo_do_embedder -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add backend/src/app/rag/embeddings.py backend/src/app/rag/qdrant_client.py backend/tests/test_rag_embeddings.py backend/tests/test_rag_qdrant_client.py
git commit -m "feat(rag): expoe o nome do modelo de embedding via TextEmbedder/QdrantRAGClient"
```

---

### Task 4: `QdrantRAGClient.upsert_chunks` grava `document_id` no payload

**Files:**
- Modify: `backend/src/app/rag/qdrant_client.py`
- Modify: `backend/src/app/rag/ingest.py` (fix mínimo, ver Step 6 abaixo — reescrito por completo no Task 7)
- Modify: `backend/tests/conftest.py` (`_FakeQdrantRAGClient`)
- Modify: `backend/tests/test_rag_qdrant_client.py`

**Interfaces:**
- Consumes: nenhuma nova (mudança de assinatura de método já existente).
- Produces: `QdrantRAGClient.upsert_chunks(chunks: list[str], source: str, domain: str, document_id: str) -> int` (parâmetro `document_id` agora obrigatório); payload de cada ponto passa a ter `document_id` além de `content`/`source`/`domain`.

**Ruling registrada no pre-flight scan (ver ledger):** tornar `document_id` obrigatório quebra o único call site de produção de `upsert_chunks` (`app/rag/ingest.py::ingest_bytes`, chamado por `test_rag_ingest.py` e, via `api/rag.py::upload_document`, por `test_rag_api.py`) — nenhum dos dois arquivos de teste precisa mudar, mas `ingest.py` precisa de um fix mínimo (Step 6) para continuar passando `document_id` para `upsert_chunks`, mesmo sem ainda usar esse id para nada (isso só acontece no Task 7). Sem esse fix mínimo, a suíte fica quebrada entre o commit deste task e o commit do Task 7.

- [ ] **Step 1: Atualizar `_FakeQdrantRAGClient` em `backend/tests/conftest.py`**

Substituir a classe inteira por:

```python
class _FakeQdrantRAGClient:
    """Dublê de `QdrantRAGClient` — só registra o que seria gravado/excluído
    no Qdrant (ou levanta `error`, se informado), sem depender de uma
    instância real.

    Compartilhado entre `test_rag_ingest.py` e `test_rag_api.py` (mesmo
    contrato, exercitado em duas camadas diferentes: pipeline de ingestão e
    endpoint HTTP).
    """

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.embedding_model_name = "fake-embedding-model"
        self.upserts: list[tuple[list[str], str, str, str]] = []
        self.deleted_document_ids: list[str] = []

    async def upsert_chunks(
        self, chunks: list[str], source: str, domain: str, document_id: str
    ) -> int:
        if self._error is not None:
            raise self._error
        self.upserts.append((chunks, source, domain, document_id))
        return len(chunks)

    async def delete_by_document_id(self, document_id: str) -> None:
        if self._error is not None:
            raise self._error
        self.deleted_document_ids.append(document_id)
```

- [ ] **Step 2: Atualizar as chamadas de `upsert_chunks` já existentes em `test_rag_qdrant_client.py`**

Substituir cada chamada `rag_client.upsert_chunks([...], source=..., domain=...)` (ou `client.upsert_chunks(...)`) adicionando `document_id=...`. Lista exata das ocorrências a alterar (mesmo arquivo lido no início desta sessão):

```python
async def test_upsert_chunks_vazio_nao_grava_e_retorna_zero(rag_client: QdrantRAGClient):
    total = await rag_client.upsert_chunks(
        [], source="arquivo.txt", domain="vendas", document_id="doc-1"
    )

    assert total == 0
    assert await rag_client.search("qualquer coisa", domain="vendas") == []


async def test_upsert_e_search_retorna_documento_com_conteudo_e_fonte(rag_client: QdrantRAGClient):
    await rag_client.upsert_chunks(
        ["O gerador diesel GD-30 tem potência de 30 kVA e autonomia de 10 horas."],
        source="catalogo_geradores.txt",
        domain="vendas",
        document_id="doc-1",
    )

    resultado = await rag_client.search("Qual a potência do gerador GD-30?", domain="vendas")

    assert len(resultado) == 1
    documento = resultado[0]
    assert isinstance(documento, Document)
    assert "GD-30" in documento.content
    assert documento.source == "catalogo_geradores.txt"
    assert documento.score > 0


async def test_search_filtra_por_domain_nao_traz_documento_de_outro_dominio(
    rag_client: QdrantRAGClient,
):
    await rag_client.upsert_chunks(
        ["O gerador não liga: verificar bateria de partida e nível de combustível."],
        source="manual_gd30.txt",
        domain="suporte",
        document_id="doc-1",
    )

    resultado = await rag_client.search("gerador não liga", domain="vendas")

    assert resultado == []
```

```python
async def test_search_apos_drop_collection_volta_a_checar_existencia(
    rag_client: QdrantRAGClient,
):
    """Regressão: a guarda em memória (`_collection_ready`) que evita
    round trips repetidos ao Qdrant precisa ser invalidada por
    `drop_collection`, senão uma busca depois do drop tentaria consultar
    uma collection que não existe mais em vez de devolver lista vazia."""
    await rag_client.upsert_chunks(
        ["conteúdo de teste sobre o produto"],
        source="arquivo.txt",
        domain="vendas",
        document_id="doc-1",
    )
    assert len(await rag_client.search("produto", domain="vendas")) == 1

    await rag_client.drop_collection()

    assert await rag_client.search("produto", domain="vendas") == []
```

```python
async def test_upsert_chunks_com_falha_no_embedder_vira_rag_connection_error():
    client = QdrantRAGClient(
        host="unused",
        port=0,
        embedder=_FailingEmbedder(),
        collection_name=f"test_{uuid.uuid4().hex}",
        client=AsyncQdrantClient(location=":memory:"),
    )

    with pytest.raises(RAGConnectionError):
        await client.upsert_chunks(
            ["texto qualquer"], source="arquivo.txt", domain="vendas", document_id="doc-1"
        )


async def test_upsert_chunks_concorrentes_nao_colidem_na_criacao_da_collection(
    text_embedder: TextEmbedder,
):
    """Regressão: duas ingestões quase simultâneas contra uma collection que
    ainda não existe não devem tentar criá-la em paralelo (race
    check-then-act entre `collection_exists`/`create_collection`,
    serializada por `_collection_lock`)."""
    client = QdrantRAGClient(
        host="unused",
        port=0,
        embedder=text_embedder,
        collection_name=f"test_{uuid.uuid4().hex}",
        client=AsyncQdrantClient(location=":memory:"),
    )

    resultados = await asyncio.gather(
        client.upsert_chunks(
            ["texto A sobre o produto"], source="a.txt", domain="vendas", document_id="doc-a"
        ),
        client.upsert_chunks(
            ["texto B sobre o produto"], source="b.txt", domain="vendas", document_id="doc-b"
        ),
    )

    assert resultados == [1, 1]
    assert len(await client.search("produto", domain="vendas")) == 2
```

```python
@pytest.mark.qdrant
async def test_upsert_e_search_contra_qdrant_real_do_docker_compose(text_embedder: TextEmbedder):
    """Mesmo comportamento de `test_upsert_e_search_retorna_documento_...`,
    mas contra o Qdrant real do `docker-compose.yml` (não em memória) — só
    roda com o serviço no ar (ver `QDRANT_HOST`/`QDRANT_PORT` em `.env`)."""
    settings = get_settings()
    collection_name = f"test_{uuid.uuid4().hex}"
    client = QdrantRAGClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        embedder=text_embedder,
        collection_name=collection_name,
    )

    try:
        await client.upsert_chunks(
            ["A garantia padrão dos geradores é de 12 meses contra defeitos de fabricação."],
            source="politicas_troca_garantia.txt",
            domain="atendimento",
            document_id="doc-1",
        )

        resultado = await client.search("qual o prazo de garantia?", domain="atendimento")

        assert len(resultado) == 1
        assert "garantia" in resultado[0].content.lower()
    finally:
        await client.drop_collection()
```

(`test_search_sem_nada_indexado_retorna_lista_vazia` e `test_search_erro_de_conexao_vira_rag_connection_error` não chamam `upsert_chunks` — não precisam de mudança.)

- [ ] **Step 3: Rodar e confirmar que falham (assinatura ainda não mudou)**

Run: `cd backend && .venv/bin/pytest tests/test_rag_qdrant_client.py -v`
Expected: FAIL — `TypeError: QdrantRAGClient.upsert_chunks() got an unexpected keyword argument 'document_id'`

- [ ] **Step 4: Adicionar um teste novo para o payload gravar `document_id`**

Adicionar a `test_rag_qdrant_client.py`:

```python
async def test_upsert_chunks_grava_document_id_no_payload_do_ponto(rag_client: QdrantRAGClient):
    await rag_client.upsert_chunks(
        ["conteúdo de teste"], source="arquivo.txt", domain="vendas", document_id="doc-xyz"
    )

    pontos, _ = await rag_client._client.scroll(rag_client._collection_name, limit=10)

    assert len(pontos) == 1
    assert pontos[0].payload["document_id"] == "doc-xyz"
```

- [ ] **Step 5: Implementar em `qdrant_client.py` — `upsert_chunks` recebe `document_id`**

Substituir a assinatura e o corpo do método `upsert_chunks`:

```python
    async def upsert_chunks(
        self, chunks: list[str], source: str, domain: str, document_id: str
    ) -> int:
        """Embeda e grava `chunks` na collection, com payload
        `source`/`domain`/`document_id`.

        `document_id` amarra os pontos gravados ao registro em
        `app.rag.registry` — é o que permite excluir só os pontos de um
        documento específico (ver `delete_by_document_id`), mesmo quando o
        mesmo `source`/`domain` foi ingerido mais de uma vez (sem
        deduplicação — ver docstring do módulo).

        # MVP: sem deduplicação nem re-ingestão incremental — reingerir a
        # mesma fonte duas vezes cria pontos duplicados na collection (ver
        # docs/ARCHITECTURE.md §5, linha "RAG — textos, PDFs, BD e sites").
        Retorna o número de pontos gravados.
        """
        if not chunks:
            return 0

        await self.ensure_collection()
        try:
            vectors = await self._embedder.embed(chunks)
            points = [
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={
                        "content": chunk,
                        "source": source,
                        "domain": domain,
                        "document_id": document_id,
                    },
                )
                for chunk, vector in zip(chunks, vectors, strict=True)
            ]
            await self._client.upsert(collection_name=self._collection_name, points=points)
        except Exception as exc:
            raise RAGConnectionError(str(exc)) from exc
        return len(points)
```

- [ ] **Step 6: Fix mínimo em `ingest.py` para manter o único call site de produção válido**

`app/rag/ingest.py::ingest_bytes` é a única chamada de produção a `upsert_chunks` — sem este fix, `test_rag_ingest.py` e `test_rag_api.py` quebram com `TypeError: missing required keyword-only argument: 'document_id'` até o Task 7 reescrever este arquivo por completo. Este fix é só para manter a suíte verde nesse intervalo — não usa o id para nada ainda (o Task 7 substitui isso pela versão real, que reaproveita o mesmo id gerado para o payload do Qdrant e para o registro em Postgres).

Adicionar `import uuid` ao topo de `backend/src/app/rag/ingest.py` (junto dos outros imports) e alterar a chamada dentro de `ingest_bytes`:

```python
    count = await client.upsert_chunks(
        chunks, source=filename, domain=domain, document_id=str(uuid.uuid4())
    )
```

- [ ] **Step 7: Rodar a suíte completa do backend e confirmar que passa**

Run: `cd backend && .venv/bin/pytest -q`
Expected: PASS em todos os testes (inclusive `test_rag_ingest.py` e `test_rag_api.py`, que não foram tocados por este task mas dependiam do fix do Step 6 para continuar passando).

- [ ] **Step 8: Commit**

```bash
git add backend/src/app/rag/qdrant_client.py backend/src/app/rag/ingest.py backend/tests/conftest.py backend/tests/test_rag_qdrant_client.py
git commit -m "feat(rag): upsert_chunks grava document_id no payload de cada ponto do Qdrant"
```

---

### Task 5: `QdrantRAGClient.delete_by_document_id`

**Files:**
- Modify: `backend/src/app/rag/qdrant_client.py`
- Modify: `backend/tests/test_rag_qdrant_client.py`

**Interfaces:**
- Consumes: payload `document_id` gravado pelo Task 4.
- Produces: `QdrantRAGClient.delete_by_document_id(document_id: str) -> None`.

- [ ] **Step 1: Escrever os testes**

Adicionar a `backend/tests/test_rag_qdrant_client.py`:

```python
async def test_delete_by_document_id_remove_so_os_pontos_daquele_documento(
    rag_client: QdrantRAGClient,
):
    await rag_client.upsert_chunks(
        ["conteúdo do documento A"], source="a.txt", domain="vendas", document_id="doc-a"
    )
    await rag_client.upsert_chunks(
        ["conteúdo do documento B"], source="b.txt", domain="vendas", document_id="doc-b"
    )

    await rag_client.delete_by_document_id("doc-a")

    resultado = await rag_client.search("conteúdo", domain="vendas")
    assert len(resultado) == 1
    assert resultado[0].source == "b.txt"


async def test_delete_by_document_id_sem_collection_nao_levanta_erro(
    rag_client: QdrantRAGClient,
):
    # Nada foi ingerido ainda — a collection não existe. Excluir um
    # document_id nesse estado deve ser um no-op silencioso, mesmo
    # espírito de `search` sem nada indexado (ver docstring da classe).
    await rag_client.delete_by_document_id("doc-inexistente")


async def test_delete_by_document_id_erro_de_conexao_vira_rag_connection_error(
    text_embedder: TextEmbedder,
):
    client = QdrantRAGClient(host="localhost", port=1, embedder=text_embedder)

    with pytest.raises(RAGConnectionError):
        await client.delete_by_document_id("doc-1")
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd backend && .venv/bin/pytest tests/test_rag_qdrant_client.py -k delete_by_document_id -v`
Expected: FAIL — `AttributeError: 'QdrantRAGClient' object has no attribute 'delete_by_document_id'`

- [ ] **Step 3: Implementar o método**

Adicionar ao `QdrantRAGClient`, após `search`:

```python
    async def delete_by_document_id(self, document_id: str) -> None:
        """Remove todos os pontos com aquele `document_id` no payload.

        A exclusão da linha correspondente no registro (Postgres) é feita
        separadamente por quem chama este método (ver `app.api.rag`) — as
        duas exclusões não são transacionais entre si (mesma decisão de
        `upsert_chunks`, ver docs/superpowers/specs/2026-09-14-registro-
        documentos-rag-design.md §3).
        """
        try:
            if not self._collection_ready:
                exists = await self._client.collection_exists(self._collection_name)
                if not exists:
                    return
                self._collection_ready = True

            await self._client.delete(
                collection_name=self._collection_name,
                points_selector=Filter(
                    must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
                ),
            )
        except Exception as exc:
            raise RAGConnectionError(str(exc)) from exc
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd backend && .venv/bin/pytest tests/test_rag_qdrant_client.py -k delete_by_document_id -v`
Expected: PASS

- [ ] **Step 5: Rodar a suíte completa do arquivo (regressão)**

Run: `cd backend && .venv/bin/pytest tests/test_rag_qdrant_client.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/app/rag/qdrant_client.py backend/tests/test_rag_qdrant_client.py
git commit -m "feat(rag): adiciona QdrantRAGClient.delete_by_document_id"
```

---

### Task 6: `app.rag.registry` — CRUD do registro de documentos

**Files:**
- Create: `backend/src/app/rag/registry.py`
- Test: `backend/tests/test_rag_registry.py`

**Interfaces:**
- Consumes: `app.db.models.RagDocument` (Task 2), fixture `db_session` (Task 2).
- Produces: `create_document(session, *, document_id, filename, domain, chunk_count, embedding_model, chunk_size, chunk_overlap, origin) -> RagDocument`; `list_documents(session) -> list[RagDocument]` (mais recente primeiro); `delete_document(session, document_id: str) -> bool`.

- [ ] **Step 1: Escrever os testes**

Criar `backend/tests/test_rag_registry.py`:

```python
import uuid

from app.rag.registry import create_document, delete_document, list_documents


async def _cria(session, **overrides):
    defaults = dict(
        document_id=str(uuid.uuid4()),
        filename="catalogo.txt",
        domain="vendas",
        chunk_count=2,
        embedding_model="modelo-teste",
        chunk_size=800,
        chunk_overlap=100,
        origin="upload",
    )
    defaults.update(overrides)
    return await create_document(session, **defaults)


async def test_create_document_grava_e_devolve_o_documento_criado(db_session):
    documento = await _cria(db_session, filename="a.txt")

    assert documento.filename == "a.txt"
    assert documento.id is not None
    assert documento.created_at is not None


async def test_list_documents_retorna_mais_recente_primeiro(db_session):
    primeiro = await _cria(db_session, filename="primeiro.txt")
    segundo = await _cria(db_session, filename="segundo.txt")

    documentos = await list_documents(db_session)

    assert [d.id for d in documentos] == [segundo.id, primeiro.id]


async def test_list_documents_sem_nenhum_documento_retorna_lista_vazia(db_session):
    assert await list_documents(db_session) == []


async def test_delete_document_existente_remove_e_retorna_true(db_session):
    documento = await _cria(db_session)

    removido = await delete_document(db_session, str(documento.id))

    assert removido is True
    assert await list_documents(db_session) == []


async def test_delete_document_inexistente_retorna_false(db_session):
    removido = await delete_document(db_session, str(uuid.uuid4()))

    assert removido is False
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd backend && .venv/bin/pytest tests/test_rag_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.rag.registry'`

- [ ] **Step 3: Implementar `backend/src/app/rag/registry.py`**

```python
"""Registro de documentos ingeridos no RAG (R4, além do MVP) — CRUD sobre
`app.db.models.RagDocument`.

Ver docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RagDocument


async def create_document(
    session: AsyncSession,
    *,
    document_id: str,
    filename: str,
    domain: str,
    chunk_count: int,
    embedding_model: str,
    chunk_size: int,
    chunk_overlap: int,
    origin: str,
) -> RagDocument:
    document = RagDocument(
        id=uuid.UUID(document_id),
        filename=filename,
        domain=domain,
        chunk_count=chunk_count,
        embedding_model=embedding_model,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        origin=origin,
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document


async def list_documents(session: AsyncSession) -> list[RagDocument]:
    result = await session.execute(select(RagDocument).order_by(RagDocument.created_at.desc()))
    return list(result.scalars().all())


async def delete_document(session: AsyncSession, document_id: str) -> bool:
    document = await session.get(RagDocument, uuid.UUID(document_id))
    if document is None:
        return False
    await session.delete(document)
    await session.commit()
    return True
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd backend && .venv/bin/pytest tests/test_rag_registry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/rag/registry.py backend/tests/test_rag_registry.py
git commit -m "feat(rag): adiciona registry.py com CRUD do registro de documentos"
```

---

### Task 7: `app.rag.ingest` cria o registro como parte da ingestão

**Files:**
- Modify: `backend/src/app/rag/ingest.py`
- Modify: `backend/tests/test_rag_ingest.py`

**Interfaces:**
- Consumes: `QdrantRAGClient.upsert_chunks(..., document_id)` (Task 4), `QdrantRAGClient.embedding_model_name` (Task 3), `app.rag.registry.create_document` (Task 6), `app.rag.chunking.chunk_text` (constantes `DEFAULT_CHUNK_SIZE`/`DEFAULT_CHUNK_OVERLAP` já existentes).
- Produces: `ingest_bytes(client, filename, content, domain, session, origin) -> RagDocument`; `ingest_file(client, path, domain, session, origin) -> RagDocument`; `ingest_directory(client, directory, session, origin="batch_script") -> list[RagDocument]`. **Mudança de assinatura e de tipo de retorno** em relação à versão atual (antes retornava `int`, agora retorna `RagDocument`/`list[RagDocument]`) — usado pelo Task 11 (`api/rag.py`) e pelo Task 12 (`ingest_sample_docs.py`).

- [ ] **Step 1: Reescrever os testes existentes**

Substituir o conteúdo de `backend/tests/test_rag_ingest.py` por:

```python
from pathlib import Path

from app.rag.chunking import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
from app.rag.ingest import ingest_bytes, ingest_directory, ingest_file
from tests.conftest import _FakeQdrantRAGClient
from tests.test_rag_pdf_extract import _build_minimal_pdf


async def test_ingest_file_le_txt_faz_chunking_e_grava_com_domain_informado(tmp_path: Path, db_session):
    arquivo = tmp_path / "catalogo.txt"
    arquivo.write_text("Conteúdo de exemplo sobre o catálogo de produtos.", encoding="utf-8")
    client = _FakeQdrantRAGClient()

    documento = await ingest_file(client, arquivo, domain="vendas", session=db_session, origin="upload")

    assert documento.filename == "catalogo.txt"
    assert documento.domain == "vendas"
    assert documento.chunk_count == 1
    assert documento.embedding_model == client.embedding_model_name
    assert documento.chunk_size == DEFAULT_CHUNK_SIZE
    assert documento.chunk_overlap == DEFAULT_CHUNK_OVERLAP
    assert documento.origin == "upload"
    chunks, source, domain, document_id = client.upserts[0]
    assert source == "catalogo.txt"
    assert domain == "vendas"
    assert document_id == str(documento.id)
    assert "catálogo de produtos" in chunks[0]


async def test_ingest_file_extrai_texto_de_pdf(tmp_path: Path, db_session):
    arquivo = tmp_path / "manual.pdf"
    arquivo.write_bytes(_build_minimal_pdf("Texto do manual em PDF"))
    client = _FakeQdrantRAGClient()

    documento = await ingest_file(client, arquivo, domain="suporte", session=db_session, origin="upload")

    assert documento.chunk_count == 1
    chunks, _source, _domain, _document_id = client.upserts[0]
    assert "Texto do manual em PDF" in chunks[0]


async def test_ingest_directory_infere_domain_do_subdiretorio_e_ignora_extensao_nao_suportada(
    tmp_path: Path, db_session
):
    (tmp_path / "vendas").mkdir()
    (tmp_path / "vendas" / "catalogo.txt").write_text("catálogo de vendas", encoding="utf-8")
    (tmp_path / "suporte").mkdir()
    (tmp_path / "suporte" / "manual.txt").write_text("manual de suporte técnico", encoding="utf-8")
    (tmp_path / "suporte" / "planilha.csv").write_text("nao,deveria,entrar", encoding="utf-8")
    client = _FakeQdrantRAGClient()

    documentos = await ingest_directory(client, tmp_path, session=db_session)

    assert len(documentos) == 2
    domains_ingeridos = {documento.domain for documento in documentos}
    assert domains_ingeridos == {"vendas", "suporte"}
    assert all(documento.origin == "batch_script" for documento in documentos)


async def test_ingest_directory_sem_arquivos_suportados_retorna_lista_vazia(tmp_path: Path, db_session):
    (tmp_path / "vendas").mkdir()
    (tmp_path / "vendas" / "planilha.csv").write_text("nao,suportado", encoding="utf-8")
    client = _FakeQdrantRAGClient()

    documentos = await ingest_directory(client, tmp_path, session=db_session)

    assert documentos == []
    assert client.upserts == []


async def test_ingest_bytes_le_txt_faz_chunking_e_grava_com_domain_informado(db_session):
    client = _FakeQdrantRAGClient()

    documento = await ingest_bytes(
        client,
        "catalogo.txt",
        "Conteúdo de exemplo sobre o catálogo.".encode(),
        domain="vendas",
        session=db_session,
        origin="upload",
    )

    assert documento.chunk_count == 1
    chunks, source, domain, document_id = client.upserts[0]
    assert source == "catalogo.txt"
    assert domain == "vendas"
    assert document_id == str(documento.id)
    assert "catálogo" in chunks[0]


async def test_ingest_bytes_extrai_texto_de_pdf(db_session):
    client = _FakeQdrantRAGClient()

    documento = await ingest_bytes(
        client,
        "manual.pdf",
        _build_minimal_pdf("Texto do manual em PDF"),
        domain="suporte",
        session=db_session,
        origin="upload",
    )

    assert documento.chunk_count == 1
    chunks, _source, _domain, _document_id = client.upserts[0]
    assert "Texto do manual em PDF" in chunks[0]
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd backend && .venv/bin/pytest tests/test_rag_ingest.py -v`
Expected: FAIL — `TypeError: ingest_file() got an unexpected keyword argument 'session'` (assinatura ainda não mudou).

- [ ] **Step 3: Reescrever `backend/src/app/rag/ingest.py`**

Substituir o conteúdo do arquivo por:

```python
"""Pipeline mínimo de ingestão de PDFs/textos no RAG (R4).

Toda ingestão (via `ingest_bytes`, usado tanto pelo endpoint de upload
quanto — indiretamente, via `ingest_file`/`ingest_directory` — pelo script
em lote) cria um registro em `app.rag.registry`, amarrado aos pontos do
Qdrant pelo `document_id` gerado aqui (ver
docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md §3).

# MVP: pipeline pensado para rodar sob demanda via script ou endpoint HTTP,
# não como serviço/observador de diretório — sem deduplicação nem
# re-ingestão incremental (reingerir a mesma fonte cria um registro novo e
# pontos duplicados no Qdrant, ver `app.rag.qdrant_client.upsert_chunks`).
Ordem de escrita: upsert no Qdrant primeiro, registro no Postgres depois —
se a escrita no Postgres falhar depois do upsert ter tido sucesso, sobra um
ponto órfão no Qdrant sem registro; isso é logado como aviso, sem tentativa
de rollback cross-store (ver spec §3, "sem transação distribuída
Qdrant+Postgres").
"""

import logging
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RagDocument
from app.rag.chunking import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, chunk_text
from app.rag.pdf_extract import extract_text_from_pdf
from app.rag.qdrant_client import QdrantRAGClient
from app.rag.registry import create_document

logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}


def _extract_text(filename: str, content: bytes) -> str:
    if Path(filename).suffix.lower() == ".pdf":
        return extract_text_from_pdf(content)
    return content.decode("utf-8")


async def ingest_bytes(
    client: QdrantRAGClient,
    filename: str,
    content: bytes,
    domain: str,
    session: AsyncSession,
    origin: str,
) -> RagDocument:
    """Extrai texto, faz chunking, grava no Qdrant e cria o registro do
    documento (`app.rag.registry.create_document`).

    `origin` distingue quem disparou a ingestão ("upload" — endpoint HTTP,
    "batch_script" — `scripts/ingest_sample_docs.py`), só para fins de
    auditoria no registro.
    """
    text = _extract_text(filename, content)
    chunks = chunk_text(text)
    document_id = str(uuid.uuid4())
    chunk_count = await client.upsert_chunks(
        chunks, source=filename, domain=domain, document_id=document_id
    )
    logger.info(
        "rag_ingest arquivo=%s domain=%s chunks=%d document_id=%s",
        filename,
        domain,
        chunk_count,
        document_id,
    )
    try:
        return await create_document(
            session,
            document_id=document_id,
            filename=filename,
            domain=domain,
            chunk_count=chunk_count,
            embedding_model=client.embedding_model_name,
            chunk_size=DEFAULT_CHUNK_SIZE,
            chunk_overlap=DEFAULT_CHUNK_OVERLAP,
            origin=origin,
        )
    except Exception:
        logger.warning(
            "rag_registro_orfao document_id=%s arquivo=%s — pontos gravados no Qdrant sem "
            "registro correspondente no Postgres",
            document_id,
            filename,
        )
        raise


async def ingest_file(
    client: QdrantRAGClient, path: Path, domain: str, session: AsyncSession, origin: str
) -> RagDocument:
    """Mesma lógica de `ingest_bytes`, a partir de um arquivo em disco."""
    return await ingest_bytes(client, path.name, path.read_bytes(), domain, session, origin)


async def ingest_directory(
    client: QdrantRAGClient,
    directory: Path,
    session: AsyncSession,
    origin: str = "batch_script",
) -> list[RagDocument]:
    """Ingere todos os arquivos suportados (.txt/.md/.pdf) de `directory`.

    # MVP: domínio inferido do nome do subdiretório imediato de cada arquivo
    # (ex.: `sample_docs/vendas/catalogo.txt` -> domain="vendas") — convenção
    # simples por convenção de pasta, sem metadados explícitos por arquivo.
    Retorna um documento de registro por arquivo ingerido.
    """
    documentos = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        domain = path.parent.name
        documentos.append(await ingest_file(client, path, domain, session, origin))
    return documentos
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd backend && .venv/bin/pytest tests/test_rag_ingest.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/rag/ingest.py backend/tests/test_rag_ingest.py
git commit -m "feat(rag): ingest_bytes/ingest_file/ingest_directory criam o registro do documento"
```

---

### Task 8: `DocumentRegistryResponse` (schema Pydantic)

**Files:**
- Modify: `backend/src/app/models/rag.py`

**Interfaces:**
- Consumes: `app.db.models.RagDocument` (campos espelhados).
- Produces: `app.models.rag.DocumentRegistryResponse` — usado pelo Task 11 (endpoints `GET`/`DELETE`).

Este task não tem teste próprio (schema Pydantic sem lógica) — é exercitado pelos testes de endpoint do Task 11.

- [ ] **Step 1: Adicionar o schema em `backend/src/app/models/rag.py`**

Adicionar ao final do arquivo (após `DocumentIngestResponse`), incluindo o import de `datetime` e `UUID` no topo:

```python
from datetime import datetime
from uuid import UUID
```

```python
class DocumentRegistryResponse(BaseModel):
    """Um item de `GET /api/rag/documents` — espelha `app.db.models.RagDocument`."""

    id: UUID
    filename: str = Field(..., description="Nome do arquivo ingerido.")
    domain: RagDomain
    chunk_count: int = Field(..., description="Número de chunks gravados no Qdrant.")
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    origin: Literal["upload", "batch_script"]
    created_at: datetime

    model_config = {"from_attributes": True}
```

`model_config = {"from_attributes": True}` permite `DocumentRegistryResponse.model_validate(rag_document_instance)` diretamente a partir do objeto ORM, sem montar um dict manualmente (usado no Task 11).

- [ ] **Step 2: Verificar que o módulo ainda importa sem erro**

Run: `cd backend && .venv/bin/python -c "from app.models.rag import DocumentRegistryResponse"`
Expected: sem erro.

- [ ] **Step 3: Commit**

```bash
git add backend/src/app/models/rag.py
git commit -m "feat(rag): adiciona schema DocumentRegistryResponse"
```

---

### Task 9: Wiring do DB em `app.main` e dependência `get_db_session`

**Files:**
- Modify: `backend/src/app/main.py`
- Modify: `backend/src/app/api/rag.py`

**Interfaces:**
- Consumes: `app.db.engine.create_db_engine`/`create_session_factory` (Task 2), `settings.postgres_dsn` (já existe em `app.config`).
- Produces: `app.state.db_sessionmaker` (novo, em `app.main.create_app`); `app.api.rag.get_db_session(request: Request) -> AsyncIterator[AsyncSession]` (dependência FastAPI, usada pelo Task 11).

- [ ] **Step 1: Adicionar o engine/sessionmaker em `create_app` (`backend/src/app/main.py`)**

No topo do arquivo, adicionar aos imports:

```python
from app.db.engine import create_db_engine, create_session_factory
```

Dentro de `create_app()`, logo após a linha que cria `app.state.rag_client` (antes de `app.state.complexity_strategy`):

```python
    # Primeiro uso real do Postgres do projeto (registro de documentos do
    # RAG, além do MVP — ver docs/ARCHITECTURE.md §5). Engine criado
    # explicitamente aqui (não via singleton global), mesmo padrão dos
    # outros clientes de infraestrutura desta função.
    db_engine = create_db_engine(settings.postgres_dsn)
    app.state.db_sessionmaker = create_session_factory(db_engine)
```

- [ ] **Step 2: Adicionar a dependência `get_db_session` em `backend/src/app/api/rag.py`**

Adicionar aos imports do arquivo:

```python
from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
```

Adicionar, antes da definição de `upload_document`:

```python
async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.db_sessionmaker() as session:
        yield session
```

- [ ] **Step 3: Verificar que a aplicação ainda sobe sem erro**

Run: `cd backend && .venv/bin/python -c "from app.main import create_app; create_app()"`
Expected: sem erro (a criação do engine não abre conexão de fato — `create_async_engine` é lazy — então isso funciona mesmo sem Postgres no ar).

- [ ] **Step 4: Commit**

```bash
git add backend/src/app/main.py backend/src/app/api/rag.py
git commit -m "feat(api): conecta o engine do Postgres ao app e adiciona get_db_session"
```

---

### Task 10: Endpoints `GET`/`DELETE /api/rag/documents` e `upload_document` cria registro

**Files:**
- Modify: `backend/src/app/api/rag.py`
- Modify: `backend/tests/test_rag_api.py`

**Interfaces:**
- Consumes: `ingest_bytes(..., session, origin="upload")` (Task 7), `app.rag.registry.list_documents`/`delete_document` (Task 6), `QdrantRAGClient.delete_by_document_id` (Task 5), `DocumentRegistryResponse` (Task 8), `get_db_session` (Task 9).
- Produces: `GET /api/rag/documents -> list[DocumentRegistryResponse]`; `DELETE /api/rag/documents/{document_id}` -> 204 (sucesso) ou 404 (não encontrado).

- [ ] **Step 1: Reescrever os testes existentes que dependiam do `upsert_chunks` de 3 posições**

Substituir o conteúdo de `backend/tests/test_rag_api.py` por:

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.rag import get_db_session, get_rag_client
from app.api.rag import router as rag_router
from app.router.rag_client import RAGConnectionError
from tests.conftest import _FakeQdrantRAGClient
from tests.test_rag_pdf_extract import _build_minimal_pdf


def _build_app(rag_client, db_session) -> FastAPI:
    app = FastAPI()
    app.include_router(rag_router)
    app.dependency_overrides[get_rag_client] = lambda: rag_client
    app.dependency_overrides[get_db_session] = lambda: db_session
    return app


def test_upload_documento_txt_ingere_e_retorna_numero_de_chunks(db_session):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", b"Conteudo de exemplo sobre o catalogo.", "text/plain")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {"filename": "catalogo.txt", "domain": "vendas", "chunks": 1}
    assert fake.upserts[0][1:3] == ("catalogo.txt", "vendas")


def test_upload_documento_pdf_ingere(db_session):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "suporte"},
        files={
            "file": (
                "manual.pdf",
                _build_minimal_pdf("Texto do manual em PDF"),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["chunks"] == 1


def test_upload_formato_nao_suportado_retorna_400(db_session):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("planilha.csv", b"nao,suportado", "text/csv")},
    )

    assert response.status_code == 400
    assert fake.upserts == []


def test_upload_domain_invalido_retorna_422(db_session):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "agendamento"},
        files={"file": ("catalogo.txt", b"conteudo", "text/plain")},
    )

    assert response.status_code == 422


def test_upload_com_qdrant_indisponivel_retorna_503(db_session):
    fake = _FakeQdrantRAGClient(error=RAGConnectionError("qdrant fora do ar"))
    client = TestClient(_build_app(fake, db_session))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", b"conteudo", "text/plain")},
    )

    assert response.status_code == 503


def test_upload_txt_com_encoding_invalido_retorna_400_em_vez_de_500(db_session):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session))

    conteudo_invalido = "áéíóú".encode("latin-1")

    response = client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", conteudo_invalido, "text/plain")},
    )

    assert response.status_code == 400
    assert fake.upserts == []


def test_upload_pdf_corrompido_retorna_400_em_vez_de_500(db_session):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "suporte"},
        files={"file": ("manual.pdf", b"isto nao e um pdf valido", "application/pdf")},
    )

    assert response.status_code == 400
    assert fake.upserts == []


def test_listar_documentos_vazio_retorna_lista_vazia(db_session):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session))

    response = client.get("/api/rag/documents")

    assert response.status_code == 200
    assert response.json() == []


def test_listar_documentos_apos_upload_retorna_o_documento(db_session):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session))
    client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", b"conteudo de exemplo", "text/plain")},
    )

    response = client.get("/api/rag/documents")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["filename"] == "catalogo.txt"
    assert body[0]["domain"] == "vendas"
    assert body[0]["origin"] == "upload"
    assert body[0]["chunk_count"] == 1


def test_excluir_documento_existente_remove_do_registro_e_do_qdrant(db_session):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session))
    upload = client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", b"conteudo de exemplo", "text/plain")},
    )
    document_id = client.get("/api/rag/documents").json()[0]["id"]

    response = client.delete(f"/api/rag/documents/{document_id}")

    assert response.status_code == 204
    assert client.get("/api/rag/documents").json() == []
    assert fake.deleted_document_ids == [document_id]


def test_excluir_documento_inexistente_retorna_404(db_session):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session))

    response = client.delete("/api/rag/documents/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert fake.deleted_document_ids == []
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd backend && .venv/bin/pytest tests/test_rag_api.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_db_session' from 'app.api.rag'` (a versão do Task 9 já criou `get_db_session`, mas `upload_document` ainda não a usa e as rotas novas não existem).

- [ ] **Step 3: Reescrever `backend/src/app/api/rag.py`**

Substituir o conteúdo do arquivo por:

```python
"""Endpoints HTTP do registro de documentos do RAG (R4, além do MVP).

# MVP: sem autenticação (rotas não listadas na navegação pública do
# frontend, mas não protegidas por login). `upload_document` complementa,
# sem substituir, o script de ingestão em lote
# (`backend/scripts/ingest_sample_docs.py`). Mesma limitação de
# `app.rag.qdrant_client.upsert_chunks`: sem deduplicação/reingestão
# incremental. Decisão registrada em `docs/ARCHITECTURE.md` §5.
"""

import logging
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pypdf.errors import PyPdfError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rag import DocumentIngestResponse, DocumentRegistryResponse, RagDomain
from app.rag.ingest import SUPPORTED_SUFFIXES, ingest_bytes
from app.rag.qdrant_client import QdrantRAGClient
from app.rag.registry import delete_document, list_documents
from app.router.rag_client import RAGConnectionError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag", tags=["rag"])


def get_rag_client(request: Request) -> QdrantRAGClient:
    return request.app.state.rag_client


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.db_sessionmaker() as session:
        yield session


@router.post("/documents", response_model=DocumentIngestResponse)
async def upload_document(
    domain: RagDomain = Form(...),
    file: UploadFile = File(...),
    rag_client: QdrantRAGClient = Depends(get_rag_client),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentIngestResponse:
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Formato não suportado: '{suffix or filename}'. "
            f"Use um destes: {sorted(SUPPORTED_SUFFIXES)}.",
        )

    content = await file.read()
    try:
        documento = await ingest_bytes(
            rag_client, filename, content, domain, session=session, origin="upload"
        )
    except RAGConnectionError as exc:
        logger.error(
            "rag_upload_indisponivel",
            extra={"rag": {"event": "rag_upload_indisponivel", "erro": str(exc)}},
        )
        raise HTTPException(
            status_code=503, detail="Serviço de RAG temporariamente indisponível, tente novamente."
        ) from exc
    except (UnicodeDecodeError, PyPdfError) as exc:
        raise HTTPException(
            status_code=400, detail=f"Não foi possível extrair texto de '{filename}': {exc}"
        ) from exc

    return DocumentIngestResponse(filename=filename, domain=domain, chunks=documento.chunk_count)


@router.get("/documents", response_model=list[DocumentRegistryResponse])
async def get_documents(
    session: AsyncSession = Depends(get_db_session),
) -> list[DocumentRegistryResponse]:
    documentos = await list_documents(session)
    return [DocumentRegistryResponse.model_validate(documento) for documento in documentos]


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document_endpoint(
    document_id: str,
    rag_client: QdrantRAGClient = Depends(get_rag_client),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    removido = await delete_document(session, document_id)
    if not removido:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")

    try:
        await rag_client.delete_by_document_id(document_id)
    except RAGConnectionError as exc:
        logger.error(
            "rag_delete_indisponivel",
            extra={"rag": {"event": "rag_delete_indisponivel", "erro": str(exc)}},
        )
        raise HTTPException(
            status_code=503, detail="Serviço de RAG temporariamente indisponível, tente novamente."
        ) from exc
```

Nota: `get_rag_client` deixa de ser importado de `app.api.chat` (import cruzado que só existia porque `app.api.rag` reaproveitava a dependência de `chat.py`) e passa a ser definido localmente aqui — evita acoplar os dois routers por um detalhe de wiring. `app.api.chat.get_rag_client` continua existindo sem mudança (usado pelo `/api/chat/messages`).

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd backend && .venv/bin/pytest tests/test_rag_api.py -v`
Expected: PASS

- [ ] **Step 5: Rodar a suíte inteira do backend (regressão ampla)**

Run: `cd backend && .venv/bin/pytest -v`
Expected: PASS em todos os testes que não exigem infraestrutura externa (`gpu`/`qdrant` marcados são pulados se a infra não estiver no ar).

- [ ] **Step 6: Commit**

```bash
git add backend/src/app/api/rag.py backend/tests/test_rag_api.py
git commit -m "feat(api): adiciona GET/DELETE /api/rag/documents e upload_document cria registro"
```

---

### Task 11: `ingest_sample_docs.py` cria registros

**Files:**
- Modify: `backend/scripts/ingest_sample_docs.py`

**Interfaces:**
- Consumes: `ingest_directory(client, directory, session, origin="batch_script")` (Task 7), `app.db.engine.create_db_engine`/`create_session_factory` (Task 2).

Script de linha de comando — sem teste automatizado (mesma situação do arquivo antes desta mudança); verificado manualmente no Task 12.

- [ ] **Step 1: Reescrever `backend/scripts/ingest_sample_docs.py`**

```python
"""Script de ingestão de um pequeno conjunto de documentos de exemplo no RAG.

# MVP: script de linha de comando único, sem agendamento nem observador de
# diretório — reingestão é manual (rodar o script de novo), o que duplica
# pontos no Qdrant e cria novos registros, já que não há deduplicação (ver
# `app.rag.qdrant_client.upsert_chunks`). Serve para ter algo indexado para
# demonstrar/testar o RAG, não é um pipeline de produção (ver
# docs/ARCHITECTURE.md §5).

Uso (a partir de `backend/`, com o Qdrant e o Postgres do docker-compose no ar):

    .venv/bin/python scripts/ingest_sample_docs.py
"""

import asyncio
import logging
from pathlib import Path

from app.config import get_settings
from app.db.engine import create_db_engine, create_session_factory
from app.logging_config import configure_logging
from app.rag.embeddings import TextEmbedder
from app.rag.ingest import ingest_directory
from app.rag.qdrant_client import QdrantRAGClient

SAMPLE_DOCS_DIR = Path(__file__).parent / "sample_docs"


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    embedder = TextEmbedder(settings.rag_embedding_model)
    client = QdrantRAGClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        embedder=embedder,
        timeout_s=settings.qdrant_timeout_s,
    )
    db_engine = create_db_engine(settings.postgres_dsn)
    session_factory = create_session_factory(db_engine)

    async with session_factory() as session:
        documentos = await ingest_directory(client, SAMPLE_DOCS_DIR, session=session)

    total_chunks = sum(documento.chunk_count for documento in documentos)
    print(
        f"Ingeridos {len(documentos)} documento(s), {total_chunks} chunk(s) "
        f"a partir de {SAMPLE_DOCS_DIR}"
    )
    await db_engine.dispose()


if __name__ == "__main__":
    logging.getLogger(__name__).info("iniciando ingestão de documentos de exemplo")
    asyncio.run(main())
```

- [ ] **Step 2: Commit**

```bash
git add backend/scripts/ingest_sample_docs.py
git commit -m "feat(scripts): ingest_sample_docs cria registro de cada documento ingerido"
```

---

### Task 12: Aplicar a migração e validar manualmente contra Postgres+Qdrant reais

**Files:** nenhum (verificação manual de infraestrutura).

Este task não é TDD — é a validação de que a Task 1 (migração) e o restante do backend funcionam de ponta a ponta contra os serviços reais, já que os Tasks 1–11 só foram verificados contra SQLite em memória e um Qdrant em memória.

- [ ] **Step 1: Confirmar que Postgres e Qdrant do `docker-compose.yml` estão no ar**

Docker já está integrado nesta distro WSL e os dois serviços já estavam rodando quando este plano foi escrito (`docker compose ps` mostrou `backend-postgres-1` healthy na porta 5433 e `backend-qdrant-1` na 6335) — só confirmar que continuam assim antes de seguir; se não estiverem, subir com o comando abaixo.

Run: `cd backend && docker compose up -d postgres qdrant`
Expected: os dois containers ficam `healthy`/`running`.

- [ ] **Step 2: Aplicar a migração**

Run: `cd backend && .venv/bin/alembic upgrade head`
Expected: sem erro; log do Alembic mostra a revisão `0001` aplicada.

- [ ] **Step 3: Confirmar a tabela existe**

Run: `docker compose exec postgres psql -U postgres -d assistente -c '\d rag_documents'`
Expected: mostra as colunas definidas no Task 1.

- [ ] **Step 4: Rodar o script de ingestão de exemplo**

Run: `cd backend && .venv/bin/python scripts/ingest_sample_docs.py`
Expected: imprime `Ingeridos N documento(s), M chunk(s)...` sem erro.

- [ ] **Step 5: Confirmar os registros foram criados**

Run: `docker compose exec postgres psql -U postgres -d assistente -c 'select filename, domain, origin, chunk_count from rag_documents;'`
Expected: uma linha por arquivo de `backend/scripts/sample_docs/`, todas com `origin = batch_script`.

- [ ] **Step 6: Subir o backend e testar os endpoints manualmente**

Run: `cd backend && source .venv/bin/activate && uvicorn app.main:app --app-dir src --host 0.0.0.0 --port 8000`

Em outro terminal:

Run: `curl -s http://localhost:8000/api/rag/documents | python3 -m json.tool`
Expected: lista JSON com os documentos do Task 5, mais recente primeiro.

Run: `curl -s -X DELETE http://localhost:8000/api/rag/documents/<um-id-da-lista-anterior> -w '\n%{http_code}\n'`
Expected: `204`, e uma nova chamada a `GET /api/rag/documents` não traz mais aquele documento.

- [ ] **Step 7: Nenhum commit neste task** (nenhum arquivo foi alterado — é validação).

---

## Frontend

### Task 13: Dependências Radix UI

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Instalar as duas dependências**

Run: `cd frontend && npm install @radix-ui/react-dialog@^1.1.0 @radix-ui/react-tabs@^1.1.0`
Expected: adiciona as duas entradas em `dependencies` de `package.json` (e `package-lock.json` é atualizado).

- [ ] **Step 2: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore(frontend): adiciona @radix-ui/react-dialog e @radix-ui/react-tabs"
```

---

### Task 14: Tipos e cliente HTTP do registro de documentos

**Files:**
- Modify: `frontend/lib/types/rag.ts`
- Modify: `frontend/lib/api/rag.ts`

**Interfaces:**
- Produces: `DocumentRegistryEntry` (tipo, campos espelhando `DocumentRegistryResponse` do backend, snake_case — mesma convenção de `ChatMessageResponse`); `listDocuments(): Promise<DocumentRegistryEntry[]>`; `deleteDocument(id: string): Promise<void>`.

Sem teste próprio (tipos + funções de API simples, sem lógica de decisão) — exercitadas pelos testes de componente dos Tasks 17/18.

- [ ] **Step 1: Adicionar o tipo em `frontend/lib/types/rag.ts`**

Adicionar ao final do arquivo:

```typescript
export type RagDocumentOrigin = "upload" | "batch_script";

/** Um item de `GET /api/rag/documents` (ver `backend/src/app/models/rag.py`). */
export interface DocumentRegistryEntry {
  id: string;
  filename: string;
  domain: RagDomain;
  chunk_count: number;
  embedding_model: string;
  chunk_size: number;
  chunk_overlap: number;
  origin: RagDocumentOrigin;
  created_at: string;
}
```

- [ ] **Step 2: Adicionar as funções em `frontend/lib/api/rag.ts`**

Adicionar ao final do arquivo (reaproveitando `API_BASE_URL` e `RagApiError` já definidos no topo):

```typescript
import type { DocumentIngestResponse, DocumentRegistryEntry, RagDomain } from "@/lib/types/rag";

/**
 * Lista os documentos registrados via `GET /api/rag/documents`.
 *
 * MVP: usado pela aba "Documentos ingeridos" de `/admin/ingestao` — sem
 * paginação nem filtro no backend (lista completa, ordenada do mais recente
 * para o mais antigo).
 */
export async function listDocuments(): Promise<DocumentRegistryEntry[]> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/documents`);
  } catch {
    throw new RagApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    throw new RagApiError("Não foi possível carregar os documentos. Tente novamente.", response.status);
  }

  return (await response.json()) as DocumentRegistryEntry[];
}

/**
 * Exclui um documento (registro + pontos no Qdrant) via
 * `DELETE /api/rag/documents/{id}`.
 */
export async function deleteDocument(id: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/documents/${id}`, { method: "DELETE" });
  } catch {
    throw new RagApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    const message =
      response.status === 404
        ? "Documento não encontrado (talvez já tenha sido excluído)."
        : "Não foi possível excluir o documento. Tente novamente.";
    throw new RagApiError(message, response.status);
  }
}
```

Ajustar o import já existente no topo do arquivo (`import type { DocumentIngestResponse, RagDomain } from "@/lib/types/rag";`) para incluir `DocumentRegistryEntry`, substituindo-o pelo import combinado acima (remover a linha antiga duplicada).

- [ ] **Step 3: Verificar que o projeto ainda compila**

Run: `cd frontend && npx tsc --noEmit`
Expected: sem erros de tipo.

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/types/rag.ts frontend/lib/api/rag.ts
git commit -m "feat(frontend): adiciona listDocuments/deleteDocument e DocumentRegistryEntry"
```

---

### Task 15: `components/ui/Modal.tsx`

**Files:**
- Create: `frontend/components/ui/Modal.tsx`
- Test: `frontend/tests/components/Modal.test.tsx`

**Interfaces:**
- Produces: `Modal({ open, onOpenChange, title, description, children, footer }): JSX.Element` — usado pelo Task 18 (`DocumentsTable`).

- [ ] **Step 1: Escrever o teste**

Criar `frontend/tests/components/Modal.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Modal } from "@/components/ui/Modal";

describe("Modal", () => {
  it("não renderiza o conteúdo quando `open` é false", () => {
    render(
      <Modal open={false} onOpenChange={vi.fn()} title="Título">
        Conteúdo
      </Modal>,
    );

    expect(screen.queryByText("Conteúdo")).not.toBeInTheDocument();
  });

  it("renderiza título e conteúdo quando `open` é true", () => {
    render(
      <Modal open={true} onOpenChange={vi.fn()} title="Confirmar exclusão">
        Tem certeza?
      </Modal>,
    );

    expect(screen.getByText("Confirmar exclusão")).toBeInTheDocument();
    expect(screen.getByText("Tem certeza?")).toBeInTheDocument();
  });

  it("chama onOpenChange(false) ao clicar no botão de fechar", async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    render(
      <Modal open={true} onOpenChange={onOpenChange} title="Título">
        Conteúdo
      </Modal>,
    );

    await user.click(screen.getByRole("button", { name: "Fechar" }));

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd frontend && npm test -- Modal.test.tsx`
Expected: FAIL — `Failed to resolve import "@/components/ui/Modal"`

- [ ] **Step 3: Implementar `frontend/components/ui/Modal.tsx`**

```tsx
"use client";

import * as Dialog from "@radix-ui/react-dialog";
import type { ReactNode } from "react";

export interface ModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
}

/**
 * Modal genérico (não específico de RAG) sobre `@radix-ui/react-dialog` —
 * a primitiva cobre foco/Esc/teclado, a aparência é Tailwind próprio (ver
 * docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md §6).
 */
export function Modal({ open, onOpenChange, title, description, children, footer }: ModalProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-lg bg-white p-6 shadow-xl">
          <Dialog.Title className="text-lg font-semibold text-gray-900">{title}</Dialog.Title>
          {description && (
            <Dialog.Description className="mt-1 text-sm text-gray-600">
              {description}
            </Dialog.Description>
          )}
          <div className="mt-4">{children}</div>
          {footer && <div className="mt-6 flex justify-end gap-3">{footer}</div>}
          <Dialog.Close asChild>
            <button
              type="button"
              aria-label="Fechar"
              className="absolute right-4 top-4 text-gray-400 hover:text-gray-600"
            >
              ✕
            </button>
          </Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd frontend && npm test -- Modal.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ui/Modal.tsx frontend/tests/components/Modal.test.tsx
git commit -m "feat(frontend): adiciona componente Modal generico sobre Radix Dialog"
```

---

### Task 16: `components/ui/Tabs.tsx`

**Files:**
- Create: `frontend/components/ui/Tabs.tsx`
- Test: `frontend/tests/components/Tabs.test.tsx`

**Interfaces:**
- Produces: `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent` (wrappers estilizados sobre `@radix-ui/react-tabs`) — usados pelo Task 19 (`app/admin/ingestao/page.tsx`).

- [ ] **Step 1: Escrever o teste**

Criar `frontend/tests/components/Tabs.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";

function ExemploTabs() {
  return (
    <Tabs defaultValue="a">
      <TabsList>
        <TabsTrigger value="a">Aba A</TabsTrigger>
        <TabsTrigger value="b">Aba B</TabsTrigger>
        <TabsTrigger value="c" disabled>
          Aba C
        </TabsTrigger>
      </TabsList>
      <TabsContent value="a">Conteúdo A</TabsContent>
      <TabsContent value="b">Conteúdo B</TabsContent>
      <TabsContent value="c">Conteúdo C</TabsContent>
    </Tabs>
  );
}

describe("Tabs", () => {
  it("mostra o conteúdo da aba padrão e troca ao clicar em outra aba", async () => {
    const user = userEvent.setup();
    render(<ExemploTabs />);

    expect(screen.getByText("Conteúdo A")).toBeInTheDocument();
    expect(screen.queryByText("Conteúdo B")).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Aba B" }));

    expect(screen.getByText("Conteúdo B")).toBeInTheDocument();
    expect(screen.queryByText("Conteúdo A")).not.toBeInTheDocument();
  });

  it("não deixa selecionar uma aba desabilitada", async () => {
    const user = userEvent.setup();
    render(<ExemploTabs />);

    await user.click(screen.getByRole("tab", { name: "Aba C" }));

    expect(screen.queryByText("Conteúdo C")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd frontend && npm test -- Tabs.test.tsx`
Expected: FAIL — `Failed to resolve import "@/components/ui/Tabs"`

- [ ] **Step 3: Implementar `frontend/components/ui/Tabs.tsx`**

```tsx
"use client";

import * as RadixTabs from "@radix-ui/react-tabs";
import type { ReactNode } from "react";

export const Tabs = RadixTabs.Root;

export function TabsList({ children }: { children: ReactNode }) {
  return (
    <RadixTabs.List className="flex gap-1 border-b border-gray-200">{children}</RadixTabs.List>
  );
}

export function TabsTrigger({
  value,
  disabled,
  children,
}: {
  value: string;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <RadixTabs.Trigger
      value={value}
      disabled={disabled}
      className="px-4 py-2 text-sm font-medium text-gray-600 data-[state=active]:border-b-2 data-[state=active]:border-gray-900 data-[state=active]:text-gray-900 disabled:cursor-not-allowed disabled:opacity-40"
    >
      {children}
    </RadixTabs.Trigger>
  );
}

export function TabsContent({ value, children }: { value: string; children: ReactNode }) {
  return <RadixTabs.Content value={value} className="pt-6">{children}</RadixTabs.Content>;
}
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd frontend && npm test -- Tabs.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ui/Tabs.tsx frontend/tests/components/Tabs.test.tsx
git commit -m "feat(frontend): adiciona componentes Tabs sobre Radix Tabs"
```

---

### Task 17: `components/ui/Toast.tsx` + `useToast`

**Files:**
- Create: `frontend/components/ui/Toast.tsx`
- Test: `frontend/tests/components/Toast.test.tsx`

**Interfaces:**
- Produces: `useToast(): { toasts: ToastMessage[]; showToast(message: string, variant?: "success" | "error"): void; dismissToast(id: string): void }`; `ToastStack({ toasts, onDismiss }): JSX.Element` — usados pelo Task 19.

- [ ] **Step 1: Escrever o teste**

Criar `frontend/tests/components/Toast.test.tsx`:

```typescript
import { act, render, renderHook, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ToastStack, useToast } from "@/components/ui/Toast";

describe("useToast/ToastStack", () => {
  it("adiciona um toast e renderiza a mensagem", () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.showToast("Documento excluído.", "success");
    });

    render(<ToastStack toasts={result.current.toasts} onDismiss={() => {}} />);

    expect(screen.getByText("Documento excluído.")).toBeInTheDocument();
  });

  it("remove o toast ao chamar dismissToast", () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.showToast("Erro ao excluir.", "error");
    });
    const [toast] = result.current.toasts;

    act(() => {
      result.current.dismissToast(toast.id);
    });

    expect(result.current.toasts).toHaveLength(0);
  });
});
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd frontend && npm test -- Toast.test.tsx`
Expected: FAIL — `Failed to resolve import "@/components/ui/Toast"`

- [ ] **Step 3: Implementar `frontend/components/ui/Toast.tsx`**

```tsx
"use client";

import { useCallback, useState } from "react";

export type ToastVariant = "success" | "error";

export interface ToastMessage {
  id: string;
  message: string;
  variant: ToastVariant;
}

/**
 * Toast genérico, sem fila global nem persistência entre páginas — estado
 * local a quem chama o hook (uma única tela administrativa, ver
 * docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md §6).
 */
export function useToast() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const dismissToast = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const showToast = useCallback(
    (message: string, variant: ToastVariant = "success") => {
      const id = crypto.randomUUID();
      setToasts((current) => [...current, { id, message, variant }]);
      setTimeout(() => dismissToast(id), 4000);
    },
    [dismissToast],
  );

  return { toasts, showToast, dismissToast };
}

export function ToastStack({
  toasts,
  onDismiss,
}: {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
}) {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          role="status"
          className={`rounded-md px-4 py-3 text-sm shadow-lg ${
            toast.variant === "success" ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"
          }`}
        >
          <div className="flex items-center gap-3">
            <span>{toast.message}</span>
            <button
              type="button"
              aria-label="Fechar aviso"
              onClick={() => onDismiss(toast.id)}
              className="text-current opacity-60 hover:opacity-100"
            >
              ✕
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd frontend && npm test -- Toast.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ui/Toast.tsx frontend/tests/components/Toast.test.tsx
git commit -m "feat(frontend): adiciona hook useToast e componente ToastStack"
```

---

### Task 18: `components/admin/DomainBadge.tsx` e `components/admin/DocumentsTable.tsx`

**Files:**
- Create: `frontend/components/admin/DomainBadge.tsx`
- Create: `frontend/components/admin/DocumentsTable.tsx`
- Test: `frontend/tests/components/DocumentsTable.test.tsx`

**Interfaces:**
- Consumes: `DocumentRegistryEntry` (Task 14), `deleteDocument` (Task 14), `Modal` (Task 15).
- Produces: `DomainBadge({ domain }): JSX.Element`; `DocumentsTable({ documents, onDeleted }): JSX.Element` — usado pelo Task 19.

- [ ] **Step 1: Implementar `frontend/components/admin/DomainBadge.tsx`** (sem teste dedicado — trivial, exercitado pelo teste da tabela)

```tsx
import type { RagDomain } from "@/lib/types/rag";

const DOMAIN_STYLES: Record<RagDomain, string> = {
  vendas: "bg-blue-100 text-blue-800",
  suporte: "bg-amber-100 text-amber-800",
  atendimento: "bg-purple-100 text-purple-800",
};

const DOMAIN_LABELS: Record<RagDomain, string> = {
  vendas: "Vendas",
  suporte: "Suporte Técnico",
  atendimento: "Atendimento ao Usuário",
};

export function DomainBadge({ domain }: { domain: RagDomain }) {
  return (
    <span className={`rounded-full px-2 py-1 text-xs font-medium ${DOMAIN_STYLES[domain]}`}>
      {DOMAIN_LABELS[domain]}
    </span>
  );
}
```

- [ ] **Step 2: Escrever o teste de `DocumentsTable`**

Criar `frontend/tests/components/DocumentsTable.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DocumentsTable } from "@/components/admin/DocumentsTable";
import { RagApiError } from "@/lib/api/rag";
import type { DocumentRegistryEntry } from "@/lib/types/rag";

vi.mock("@/lib/api/rag", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/rag")>("@/lib/api/rag");
  return { ...actual, deleteDocument: vi.fn() };
});

import { deleteDocument } from "@/lib/api/rag";

const mockedDeleteDocument = vi.mocked(deleteDocument);

const DOCUMENTO: DocumentRegistryEntry = {
  id: "11111111-1111-1111-1111-111111111111",
  filename: "catalogo.txt",
  domain: "vendas",
  chunk_count: 3,
  embedding_model: "paraphrase-multilingual-MiniLM-L12-v2",
  chunk_size: 800,
  chunk_overlap: 100,
  origin: "upload",
  created_at: new Date().toISOString(),
};

describe("DocumentsTable", () => {
  beforeEach(() => {
    mockedDeleteDocument.mockReset();
  });

  it("renderiza uma linha por documento", () => {
    render(<DocumentsTable documents={[DOCUMENTO]} onDeleted={vi.fn()} />);

    expect(screen.getByText("catalogo.txt")).toBeInTheDocument();
    expect(screen.getByText("Vendas")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("clicar em excluir abre o modal, e cancelar não chama a API", async () => {
    const user = userEvent.setup();
    render(<DocumentsTable documents={[DOCUMENTO]} onDeleted={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Excluir" }));
    expect(screen.getByText(/tem certeza/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Cancelar" }));

    expect(mockedDeleteDocument).not.toHaveBeenCalled();
  });

  it("confirmar a exclusão chama a API e notifica onDeleted", async () => {
    const user = userEvent.setup();
    mockedDeleteDocument.mockResolvedValueOnce(undefined);
    const onDeleted = vi.fn();
    render(<DocumentsTable documents={[DOCUMENTO]} onDeleted={onDeleted} />);

    await user.click(screen.getByRole("button", { name: "Excluir" }));
    await user.click(screen.getByRole("button", { name: "Confirmar exclusão" }));

    expect(mockedDeleteDocument).toHaveBeenCalledWith(DOCUMENTO.id);
    expect(await screen.findByText(/excluído/i)).toBeInTheDocument();
    expect(onDeleted).toHaveBeenCalledWith(DOCUMENTO.id);
  });

  it("exibe erro quando a exclusão falha", async () => {
    const user = userEvent.setup();
    mockedDeleteDocument.mockRejectedValueOnce(new RagApiError("Não foi possível excluir."));
    render(<DocumentsTable documents={[DOCUMENTO]} onDeleted={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Excluir" }));
    await user.click(screen.getByRole("button", { name: "Confirmar exclusão" }));

    expect(await screen.findByText("Não foi possível excluir.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Rodar e confirmar que falha**

Run: `cd frontend && npm test -- DocumentsTable.test.tsx`
Expected: FAIL — `Failed to resolve import "@/components/admin/DocumentsTable"`

- [ ] **Step 4: Implementar `frontend/components/admin/DocumentsTable.tsx`**

```tsx
"use client";

import { useState } from "react";

import { DomainBadge } from "@/components/admin/DomainBadge";
import { Modal } from "@/components/ui/Modal";
import { ToastStack, useToast } from "@/components/ui/Toast";
import { RagApiError, deleteDocument } from "@/lib/api/rag";
import type { DocumentRegistryEntry } from "@/lib/types/rag";

function formatarDataRelativa(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffDias = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDias <= 0) return "hoje";
  if (diffDias === 1) return "há 1 dia";
  return `há ${diffDias} dias`;
}

export interface DocumentsTableProps {
  documents: DocumentRegistryEntry[];
  onDeleted: (id: string) => void;
}

export function DocumentsTable({ documents, onDeleted }: DocumentsTableProps) {
  const [documentoParaExcluir, setDocumentoParaExcluir] = useState<DocumentRegistryEntry | null>(
    null,
  );
  const [excluindo, setExcluindo] = useState(false);
  const { toasts, showToast, dismissToast } = useToast();

  async function confirmarExclusao() {
    if (!documentoParaExcluir) return;
    setExcluindo(true);
    try {
      await deleteDocument(documentoParaExcluir.id);
      showToast(`"${documentoParaExcluir.filename}" excluído.`, "success");
      onDeleted(documentoParaExcluir.id);
      setDocumentoParaExcluir(null);
    } catch (err) {
      showToast(
        err instanceof RagApiError ? err.message : "Erro inesperado ao excluir o documento.",
        "error",
      );
    } finally {
      setExcluindo(false);
    }
  }

  if (documents.length === 0) {
    return <p className="text-sm text-gray-600">Nenhum documento ingerido ainda.</p>;
  }

  return (
    <>
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-gray-500">
            <th className="py-2">Arquivo</th>
            <th className="py-2">Domínio</th>
            <th className="py-2">Chunks</th>
            <th className="py-2">Modelo de embedding</th>
            <th className="py-2">Data</th>
            <th className="py-2" />
          </tr>
        </thead>
        <tbody>
          {documents.map((documento) => (
            <tr key={documento.id} className="border-b border-gray-100">
              <td className="py-2 text-gray-900">{documento.filename}</td>
              <td className="py-2">
                <DomainBadge domain={documento.domain} />
              </td>
              <td className="py-2 text-gray-700">{documento.chunk_count}</td>
              <td className="py-2 text-gray-700">{documento.embedding_model}</td>
              <td className="py-2 text-gray-500" title={documento.created_at}>
                {formatarDataRelativa(documento.created_at)}
              </td>
              <td className="py-2 text-right">
                <button
                  type="button"
                  onClick={() => setDocumentoParaExcluir(documento)}
                  className="text-red-600 hover:text-red-800"
                >
                  Excluir
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <Modal
        open={documentoParaExcluir !== null}
        onOpenChange={(open) => !open && setDocumentoParaExcluir(null)}
        title="Excluir documento"
        footer={
          <>
            <button
              type="button"
              onClick={() => setDocumentoParaExcluir(null)}
              className="rounded-md px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={confirmarExclusao}
              disabled={excluindo}
              className="rounded-md bg-red-600 px-4 py-2 text-sm text-white disabled:opacity-50"
            >
              Confirmar exclusão
            </button>
          </>
        }
      >
        Tem certeza que deseja excluir &ldquo;{documentoParaExcluir?.filename}&rdquo;? Os chunks
        já indexados serão removidos do RAG e essa ação não pode ser desfeita.
      </Modal>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </>
  );
}
```

- [ ] **Step 5: Rodar e confirmar que passa**

Run: `cd frontend && npm test -- DocumentsTable.test.tsx`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/components/admin/DomainBadge.tsx frontend/components/admin/DocumentsTable.tsx frontend/tests/components/DocumentsTable.test.tsx
git commit -m "feat(frontend): adiciona DocumentsTable com exclusao via modal de confirmacao"
```

---

### Task 19: Reescrever `/admin/ingestao` com abas

**Files:**
- Modify: `frontend/app/admin/ingestao/page.tsx`
- Modify: `frontend/tests/components/IngestaoDocumentosPage.test.tsx`

**Interfaces:**
- Consumes: `Tabs`/`TabsList`/`TabsTrigger`/`TabsContent` (Task 16), `DocumentsTable` (Task 18), `useToast`/`ToastStack` (Task 17), `listDocuments` (Task 14), `uploadDocument` (já existente).

Antes de codar: checar `node_modules/next/dist/docs/` por qualquer mudança relevante de App Router/Server Components que afete uma página `"use client"` com `useEffect`/fetch no client — ver nota de compatibilidade da spec §6.

- [ ] **Step 1: Atualizar `frontend/tests/components/IngestaoDocumentosPage.test.tsx`**

Substituir o conteúdo do arquivo por (mantém os três testes de upload já existentes, adaptados à navegação por aba, e adiciona dois testes novos para a aba "Documentos ingeridos"):

```typescript
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import IngestaoDocumentosPage from "@/app/admin/ingestao/page";
import { RagApiError } from "@/lib/api/rag";
import type { DocumentRegistryEntry } from "@/lib/types/rag";

vi.mock("@/lib/api/rag", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/rag")>("@/lib/api/rag");
  return {
    ...actual,
    uploadDocument: vi.fn(),
    listDocuments: vi.fn(),
  };
});

import { listDocuments, uploadDocument } from "@/lib/api/rag";

const mockedUploadDocument = vi.mocked(uploadDocument);
const mockedListDocuments = vi.mocked(listDocuments);

const DOCUMENTO: DocumentRegistryEntry = {
  id: "11111111-1111-1111-1111-111111111111",
  filename: "catalogo.txt",
  domain: "vendas",
  chunk_count: 3,
  embedding_model: "paraphrase-multilingual-MiniLM-L12-v2",
  chunk_size: 800,
  chunk_overlap: 100,
  origin: "upload",
  created_at: new Date().toISOString(),
};

describe("IngestaoDocumentosPage", () => {
  beforeEach(() => {
    mockedUploadDocument.mockReset();
    mockedListDocuments.mockReset();
    mockedListDocuments.mockResolvedValue([]);
  });

  it("envia o arquivo selecionado e exibe o resultado da ingestão", async () => {
    const user = userEvent.setup();
    mockedUploadDocument.mockResolvedValueOnce({
      filename: "catalogo.txt",
      domain: "vendas",
      chunks: 3,
    });

    render(<IngestaoDocumentosPage />);

    const file = new File(["conteudo"], "catalogo.txt", { type: "text/plain" });
    await user.upload(screen.getByLabelText("Arquivo"), file);
    await user.click(screen.getByRole("button", { name: "Enviar para ingestão" }));

    expect(await screen.findByText(/3 chunk\(s\) gravado\(s\)/)).toBeInTheDocument();
    expect(mockedUploadDocument).toHaveBeenCalledWith({ file, domain: "vendas" });
  });

  it("exibe mensagem de erro quando o upload falha", async () => {
    const user = userEvent.setup();
    mockedUploadDocument.mockRejectedValueOnce(
      new RagApiError("Serviço de RAG temporariamente indisponível. Tente novamente.", 503),
    );

    render(<IngestaoDocumentosPage />);

    const file = new File(["conteudo"], "catalogo.txt", { type: "text/plain" });
    await user.upload(screen.getByLabelText("Arquivo"), file);
    await user.click(screen.getByRole("button", { name: "Enviar para ingestão" }));

    expect(await screen.findByText(/temporariamente indisponível/)).toBeInTheDocument();
  });

  it("desabilita o envio enquanto nenhum arquivo foi selecionado", () => {
    render(<IngestaoDocumentosPage />);

    expect(screen.getByRole("button", { name: "Enviar para ingestão" })).toBeDisabled();
  });

  it("aba 'Documentos ingeridos' lista os documentos ao ser aberta", async () => {
    const user = userEvent.setup();
    mockedListDocuments.mockResolvedValue([DOCUMENTO]);

    render(<IngestaoDocumentosPage />);
    await user.click(screen.getByRole("tab", { name: "Documentos ingeridos" }));

    expect(await screen.findByText("catalogo.txt")).toBeInTheDocument();
  });

  it("aba 'Configuração' aparece desabilitada", () => {
    render(<IngestaoDocumentosPage />);

    expect(screen.getByRole("tab", { name: "Configuração" })).toBeDisabled();
  });
});
```

Nota sobre a mudança de teste em relação à versão anterior: o teste que checava "Erro inesperado" não aparecer junto do sucesso (regressão de `form.reset()`) é coberto implicitamente pelo primeiro teste (`findByText` falharia se o texto de erro também estivesse presente de forma ambígua) — mantém a mesma cobertura de comportamento sem duplicar a asserção.

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd frontend && npm test -- IngestaoDocumentosPage.test.tsx`
Expected: FAIL — os testes de aba não encontram `role="tab"` (página ainda não tem abas), `listDocuments` não é chamado.

- [ ] **Step 3: Reescrever `frontend/app/admin/ingestao/page.tsx`**

```tsx
"use client";

// MVP: página administrativa (fora da navegação pública, sem autenticação)
// para upload avulso de documento no RAG e gestão do registro de
// documentos ingeridos — decisão registrada em `docs/ARCHITECTURE.md` §5 e
// `docs/FRONTEND.md` §8. Ver
// docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md.
import { useCallback, useEffect, useState } from "react";

import { DocumentsTable } from "@/components/admin/DocumentsTable";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { ToastStack, useToast } from "@/components/ui/Toast";
import { RagApiError, listDocuments, uploadDocument } from "@/lib/api/rag";
import type { DocumentIngestResponse, DocumentRegistryEntry, RagDomain } from "@/lib/types/rag";

const DOMAIN_OPTIONS: { value: RagDomain; label: string }[] = [
  { value: "vendas", label: "Vendas" },
  { value: "suporte", label: "Suporte Técnico" },
  { value: "atendimento", label: "Atendimento ao Usuário" },
];

const ACCEPTED_EXTENSIONS = ".txt,.md,.pdf";

function AbaEnviarDocumento({ onIngerido }: { onIngerido: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [domain, setDomain] = useState<RagDomain>("vendas");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<DocumentIngestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || isSubmitting) {
      return;
    }
    const form = event.currentTarget;

    setIsSubmitting(true);
    setError(null);
    setResult(null);

    try {
      const response = await uploadDocument({ file, domain });
      setResult(response);
      setFile(null);
      form.reset();
      onIngerido();
    } catch (err) {
      setError(err instanceof RagApiError ? err.message : "Erro inesperado ao enviar o documento.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      <p className="text-gray-600">
        Envie um PDF ou texto (.txt/.md) para indexação no domínio escolhido.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 space-y-6">
        <div>
          <label htmlFor="domain" className="block text-sm font-medium text-gray-900">
            Domínio
          </label>
          <select
            id="domain"
            value={domain}
            onChange={(event) => setDomain(event.target.value as RagDomain)}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
          >
            {DOMAIN_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="file" className="block text-sm font-medium text-gray-900">
            Arquivo
          </label>
          <input
            id="file"
            type="file"
            accept={ACCEPTED_EXTENSIONS}
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="mt-1 block w-full text-gray-900"
          />
        </div>

        <button
          type="submit"
          disabled={!file || isSubmitting}
          className="rounded-md bg-gray-900 px-4 py-2 text-white disabled:opacity-50"
        >
          {isSubmitting ? "Enviando..." : "Enviar para ingestão"}
        </button>
      </form>

      {result && (
        <p className="mt-6 rounded-md bg-green-50 px-4 py-3 text-green-800">
          &ldquo;{result.filename}&rdquo; ingerido no domínio &ldquo;{result.domain}&rdquo; —{" "}
          {result.chunks} chunk(s) gravado(s).
        </p>
      )}
      {error && <p className="mt-6 rounded-md bg-red-50 px-4 py-3 text-red-800">{error}</p>}
    </div>
  );
}

function AbaDocumentosIngeridos() {
  const [documentos, setDocumentos] = useState<DocumentRegistryEntry[] | null>(null);
  const { toasts, showToast, dismissToast } = useToast();

  const carregarDocumentos = useCallback(async () => {
    try {
      setDocumentos(await listDocuments());
    } catch (err) {
      showToast(
        err instanceof RagApiError ? err.message : "Erro inesperado ao carregar os documentos.",
        "error",
      );
      setDocumentos([]);
    }
  }, [showToast]);

  useEffect(() => {
    carregarDocumentos();
  }, [carregarDocumentos]);

  function handleDeleted(id: string) {
    setDocumentos((atual) => atual?.filter((documento) => documento.id !== id) ?? null);
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      {documentos === null ? (
        <p className="text-sm text-gray-600">Carregando...</p>
      ) : (
        <DocumentsTable documents={documentos} onDeleted={handleDeleted} />
      )}
      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}

function AbaConfiguracao() {
  return (
    <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-6 text-sm text-gray-600">
      <p className="font-medium text-gray-900">Em breve.</p>
      <p className="mt-2">
        Configuração de tamanho/sobreposição de chunk, modelo de embedding, dimensão do vetor,
        métrica de distância, HNSW, quantização de vetores e payload indexing do Qdrant.
      </p>
    </div>
  );
}

export default function IngestaoDocumentosPage() {
  const [reloadKey, setReloadKey] = useState(0);

  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <h1 className="text-2xl font-semibold text-gray-900">Ingestão de documentos (RAG)</h1>
      <p className="mt-2 text-gray-600">
        Página interna, sem impacto na navegação pública do site.
      </p>

      <Tabs defaultValue="enviar" className="mt-8">
        <TabsList>
          <TabsTrigger value="enviar">Enviar documento</TabsTrigger>
          <TabsTrigger value="documentos">Documentos ingeridos</TabsTrigger>
          <TabsTrigger value="configuracao" disabled>
            Configuração
          </TabsTrigger>
        </TabsList>
        <TabsContent value="enviar">
          <AbaEnviarDocumento onIngerido={() => setReloadKey((key) => key + 1)} />
        </TabsContent>
        <TabsContent value="documentos">
          <AbaDocumentosIngeridos key={reloadKey} />
        </TabsContent>
        <TabsContent value="configuracao">
          <AbaConfiguracao />
        </TabsContent>
      </Tabs>
    </div>
  );
}
```

Nota: `key={reloadKey}` em `AbaDocumentosIngeridos` força uma remontagem (e portanto um novo `listDocuments()`) depois de um upload bem-sucedido na outra aba — mais simples que um estado compartilhado/contexto para uma única página administrativa.

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd frontend && npm test -- IngestaoDocumentosPage.test.tsx`
Expected: PASS

- [ ] **Step 5: Rodar a suíte completa do frontend (regressão)**

Run: `cd frontend && npm test`
Expected: PASS em todos os arquivos de teste.

- [ ] **Step 6: Verificar tipos e lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: sem erros.

- [ ] **Step 7: Testar manualmente no navegador**

Run: `cd frontend && npm run dev` (com o backend do Task 12 no ar)
Abrir `http://localhost:3000/admin/ingestao`, alternar entre as três abas, enviar um documento, confirmar que ele aparece na aba "Documentos ingeridos", excluir e confirmar que a linha some e o toast aparece.

- [ ] **Step 8: Commit**

```bash
git add frontend/app/admin/ingestao/page.tsx frontend/tests/components/IngestaoDocumentosPage.test.tsx
git commit -m "feat(frontend): reorganiza /admin/ingestao em abas com tabela de documentos"
```

---

## Documentação

### Task 20: Atualizar `docs/ARCHITECTURE.md`, `docs/ROADMAP.md` e `docs/FRONTEND.md`

**Files:**
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/FRONTEND.md`

Sem teste (documentação). Cumpre a Regra 6 (decisão de arquitetura nova) e a Regra 5 (roadmap sempre atualizado) do `CLAUDE.md`.

- [ ] **Step 1: Adicionar a decisão em `docs/ARCHITECTURE.md` §5**

Inserir, imediatamente após o parágrafo que termina em "...mesma limitação de `app.rag.qdrant_client.upsert_chunks`)." (o parágrafo "Decisão registrada (Fase 2)" sobre o endpoint HTTP/página administrativa):

```markdown
**Decisão registrada (além do MVP, a pedido explícito, 2026-09-14):** toda
ingestão de documento no RAG (endpoint HTTP ou script em lote) passa a criar
um registro persistente no Postgres (`rag_documents`) — o primeiro uso real
dessa infraestrutura, até então só prevista em config/`docker-compose.yml`.
A partir desse registro, um documento pode ser listado e excluído (linha do
Postgres + pontos correspondentes no Qdrant, amarrados por um `document_id`
gravado no payload de cada ponto). Esta funcionalidade **não faz parte do
MVP original** — foi implementada por pedido explícito do usuário antes de
retomar os itens pendentes da Fase 2 (conector de BD relacional, crawler).
Fica registrada aqui para não ser confundida com um item do escopo original
nem esquecida na revisão final (Fase 11). Detalhes de implementação:
`docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md`.
```

- [ ] **Step 2: Adicionar uma seção no `docs/ROADMAP.md`**

Inserir uma nova seção, depois de "## Fase 2 — Entrada Multimodal e RAG Textual (R2, R4, R5)" e antes de "## Fase 3 — RAG Multimodal, Tratamento de Imagem e Domínios (R4, R6, R7)":

```markdown
## Extra fora do MVP — Registro e Configuração de Ingestão do RAG

> Pedido explícito do usuário, fora do escopo original do MVP (ver
> `docs/ARCHITECTURE.md` §5 e
> `docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md`).
> Três entregas combinadas na mesma sessão de brainstorming (2026-09-14).

- [x] **Entrega A** — registro de documentos ingeridos (Postgres,
      `rag_documents`) + exclusão (registro + pontos no Qdrant), com página
      `/admin/ingestao` reorganizada em abas (Radix UI)
- [ ] **Entrega B** — chunk size/overlap configuráveis por ingestão
- [ ] **Entrega C+D** — configuração avançada da collection do Qdrant
      (modelo de embedding/dimensão/métrica de distância, HNSW, quantização
      de vetores, payload indexing)
```

(Marcar a Entrega A como `- [x]` só depois que todos os tasks anteriores deste plano estiverem de fato concluídos e verificados — não marcar antecipadamente.)

- [ ] **Step 3: Atualizar a tabela de contrato de API em `docs/FRONTEND.md` §4**

Substituir a linha existente:

```markdown
| `POST /api/rag/documents` | Upload de um PDF/texto (`multipart/form-data`: `file` + `domain`) para ingestão no RAG — usado pela página `/admin/ingestao` (ver `backend/src/app/api/rag.py`) |
```

por três linhas:

```markdown
| `POST /api/rag/documents` | Upload de um PDF/texto (`multipart/form-data`: `file` + `domain`) para ingestão no RAG — usado pela página `/admin/ingestao` (ver `backend/src/app/api/rag.py`) |
| `GET /api/rag/documents` | Lista o registro de documentos ingeridos (mais recente primeiro), fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `DELETE /api/rag/documents/{document_id}` | Exclui um documento (registro + pontos no Qdrant), fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
```

- [ ] **Step 4: Atualizar a nota de "Decisão revista (Fase 2)" em `docs/FRONTEND.md` §8**

No parágrafo que termina em "...Novas páginas administrativas continuam exigindo essa mesma análise caso a caso (registrada aqui ou em `docs/ARCHITECTURE.md`), não uma liberação geral.", adicionar ao final:

```markdown
`/admin/ingestao` foi ampliada (fora do MVP original, a pedido explícito,
2026-09-14) com um registro/exclusão de documentos e uma aba de
configuração reservada para entregas futuras — ver
`docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md`.
```

- [ ] **Step 5: Commit**

```bash
git add docs/ARCHITECTURE.md docs/ROADMAP.md docs/FRONTEND.md
git commit -m "docs: registra a entrega A (registro/exclusao de documentos do RAG) fora do MVP"
```

---

## Ordem de execução recomendada

Backend primeiro, de ponta a ponta (Tasks 1–12), depois frontend (Tasks 13–19), documentação por último (Task 20) — cada task depende só dos anteriores na mesma lista, sem dependências cruzadas "para frente".
