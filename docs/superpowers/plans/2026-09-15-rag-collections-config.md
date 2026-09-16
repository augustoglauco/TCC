# Perfis de Collection Configuráveis + Playground de Busca — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir criar múltiplas collections do Qdrant com perfis de configuração completos (chunking, modelo de embedding, HNSW, quantização, payload indexing), ativar uma delas para o chat real, reingerir um documento em outra collection, e comparar buscas lado a lado num playground — tudo em `/admin/ingestao`.

**Architecture:** Postgres (`rag_collections`) vira a fonte de verdade dos perfis; `QdrantRAGClient` deixa de ter estado fixo de collection e passa a receber `collection_name`/`embedder` por chamada; um novo adapter (`ActiveCollectionRagClient`) resolve a collection ativa a cada busca do chat, satisfazendo o Protocol `RAGClient` sem mudar a assinatura que o orchestrator já usa. Arquivos originais de upload passam a ser salvos em disco para permitir reingestão.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (async) + Alembic + Postgres, Qdrant (`qdrant-client`), sentence-transformers, Next.js (App Router) + Radix UI (`Dialog`, `Tabs`) + Vitest/Testing Library.

**Spec:** `docs/superpowers/specs/2026-09-15-rag-collections-config-design.md`

## Global Constraints

- Perfis de collection são imutáveis após criados — mudar um parâmetro é criar uma nova collection (spec §2).
- `chunk_size` default 800, `chunk_overlap` default 100 (mesmos valores já usados hoje).
- `DEFAULT_TOP_K = 3`, `DEFAULT_SCORE_THRESHOLD = 0.35` continuam globais, não configuráveis por perfil, inclusive no playground (spec §6.3, §10).
- Modelos de embedding curados no frontend: `paraphrase-multilingual-MiniLM-L12-v2` (384), `paraphrase-multilingual-mpnet-base-v2` (768), `intfloat/multilingual-e5-base` (768), `intfloat/multilingual-e5-large` (1024) — mais opção "Outro" com campo livre (spec §7).
- Arquivos originais de upload salvos em `backend/data/rag_uploads/<document_id>_<filename>` (disco local, spec §3).
- `DELETE /api/rag/collections/{id}` é cascata (Qdrant → arquivos → Postgres) e só é bloqueado se a collection for a ativa (spec §6.1).
- Sem verificação automatizada de que HNSW/quantização/payload-index tiveram efeito real no Qdrant — o backend em memória usado nos testes os ignora silenciosamente (confirmado lendo `qdrant_client.local.qdrant_local.QdrantLocal`); só o teste `@pytest.mark.qdrant` contra o Qdrant real do `docker-compose.yml` exercita isso de verdade (spec §4, §8).
- Sem migração automática de documentos entre collections, sem benchmark formal (Fase 10 do roadmap), sem edição de collection existente, sem quota de collections (spec §10).

---

### Task 1: Modelo de dados — `RagCollection`, mudanças em `RagDocument`, migração 0002

**Files:**
- Modify: `backend/src/app/db/models.py`
- Create: `backend/migrations/versions/0002_rag_collections.py`
- Modify: `backend/tests/conftest.py`

**Interfaces:**
- Produces: `app.db.models.RagCollection` (colunas: `id`, `name`, `embedding_model`, `vector_dimension`, `distance_metric`, `chunk_size`, `chunk_overlap`, `hnsw_m`, `hnsw_ef_construct`, `hnsw_full_scan_threshold`, `hnsw_max_indexing_threads`, `hnsw_on_disk`, `hnsw_payload_m`, `quantization_type`, `quantization_config: dict`, `payload_indexes: list`, `is_active`, `created_at`); `app.db.models.RagDocument` ganha `collection_id`, `storage_path`, perde `embedding_model`/`chunk_size`/`chunk_overlap`; fixture `tests.conftest.active_collection` (uma `RagCollection` com `is_active=True` já commitada).

- [ ] **Step 1: Atualizar `app/db/models.py`**

```python
"""Modelos SQLAlchemy do backend (primeiro uso real do Postgres — ver
docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md).
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

_JsonVariant = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class RagCollection(Base):
    """Perfil completo e imutável de uma collection do Qdrant (Entregas
    B+C+D, além do MVP) — ver
    docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §3.

    Não há edição depois de criada: mudar qualquer parâmetro significa criar
    uma nova collection. Só uma linha pode ter `is_active=True` por vez,
    garantido na aplicação (`app.rag.collections_registry.activate_collection`),
    não por constraint de banco.
    """

    __tablename__ = "rag_collections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(unique=True)
    embedding_model: Mapped[str]
    vector_dimension: Mapped[int]
    distance_metric: Mapped[str]
    chunk_size: Mapped[int]
    chunk_overlap: Mapped[int]
    hnsw_m: Mapped[int]
    hnsw_ef_construct: Mapped[int]
    hnsw_full_scan_threshold: Mapped[int]
    hnsw_max_indexing_threads: Mapped[int]
    hnsw_on_disk: Mapped[bool]
    hnsw_payload_m: Mapped[int | None]
    quantization_type: Mapped[str]
    quantization_config: Mapped[dict] = mapped_column(_JsonVariant, default=dict)
    payload_indexes: Mapped[list] = mapped_column(_JsonVariant, default=list)
    is_active: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RagDocument(Base):
    """Registro de um documento ingerido no RAG (R4, além do MVP).

    `id` também é gravado como campo de payload em cada ponto do Qdrant
    daquele documento (ver `app.rag.qdrant_client.upsert_chunks`) — é o que
    permite excluir um documento e seus vetores juntos. `storage_path` é
    `None` para documentos ingeridos antes da entrega de perfis de
    collection existir (sem backfill, mesmo espírito de
    docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md §9).
    """

    __tablename__ = "rag_documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    collection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rag_collections.id"))
    filename: Mapped[str]
    domain: Mapped[str]
    chunk_count: Mapped[int]
    storage_path: Mapped[str | None]
    origin: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: Criar a migração Alembic `0002`**

```python
"""create rag_collections, add collection_id/storage_path to rag_documents

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-15

"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SEED_COLLECTION_ID = uuid.uuid4()


def upgrade() -> None:
    op.create_table(
        "rag_collections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("embedding_model", sa.String(), nullable=False),
        sa.Column("vector_dimension", sa.Integer(), nullable=False),
        sa.Column("distance_metric", sa.String(), nullable=False),
        sa.Column("chunk_size", sa.Integer(), nullable=False),
        sa.Column("chunk_overlap", sa.Integer(), nullable=False),
        sa.Column("hnsw_m", sa.Integer(), nullable=False),
        sa.Column("hnsw_ef_construct", sa.Integer(), nullable=False),
        sa.Column("hnsw_full_scan_threshold", sa.Integer(), nullable=False),
        sa.Column("hnsw_max_indexing_threads", sa.Integer(), nullable=False),
        sa.Column("hnsw_on_disk", sa.Boolean(), nullable=False),
        sa.Column("hnsw_payload_m", sa.Integer(), nullable=True),
        sa.Column("quantization_type", sa.String(), nullable=False),
        sa.Column("quantization_config", JSONB(), nullable=False),
        sa.Column("payload_indexes", JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    rag_collections = sa.table(
        "rag_collections",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("embedding_model", sa.String()),
        sa.column("vector_dimension", sa.Integer()),
        sa.column("distance_metric", sa.String()),
        sa.column("chunk_size", sa.Integer()),
        sa.column("chunk_overlap", sa.Integer()),
        sa.column("hnsw_m", sa.Integer()),
        sa.column("hnsw_ef_construct", sa.Integer()),
        sa.column("hnsw_full_scan_threshold", sa.Integer()),
        sa.column("hnsw_max_indexing_threads", sa.Integer()),
        sa.column("hnsw_on_disk", sa.Boolean()),
        sa.column("hnsw_payload_m", sa.Integer()),
        sa.column("quantization_type", sa.String()),
        sa.column("quantization_config", JSONB()),
        sa.column("payload_indexes", JSONB()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        rag_collections,
        [
            {
                "id": _SEED_COLLECTION_ID,
                "name": "docs_texto",
                "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
                "vector_dimension": 384,
                "distance_metric": "cosine",
                "chunk_size": 800,
                "chunk_overlap": 100,
                "hnsw_m": 16,
                "hnsw_ef_construct": 100,
                "hnsw_full_scan_threshold": 10000,
                "hnsw_max_indexing_threads": 0,
                "hnsw_on_disk": False,
                "hnsw_payload_m": None,
                "quantization_type": "none",
                "quantization_config": {},
                "payload_indexes": [],
                "is_active": True,
            }
        ],
    )

    op.add_column("rag_documents", sa.Column("collection_id", sa.Uuid(), nullable=True))
    op.add_column("rag_documents", sa.Column("storage_path", sa.String(), nullable=True))
    op.execute(
        sa.text("UPDATE rag_documents SET collection_id = :collection_id").bindparams(
            collection_id=_SEED_COLLECTION_ID
        )
    )
    op.alter_column("rag_documents", "collection_id", nullable=False)
    op.create_foreign_key(
        "fk_rag_documents_collection_id",
        "rag_documents",
        "rag_collections",
        ["collection_id"],
        ["id"],
    )
    op.drop_column("rag_documents", "embedding_model")
    op.drop_column("rag_documents", "chunk_size")
    op.drop_column("rag_documents", "chunk_overlap")


def downgrade() -> None:
    op.add_column("rag_documents", sa.Column("embedding_model", sa.String(), nullable=True))
    op.add_column("rag_documents", sa.Column("chunk_size", sa.Integer(), nullable=True))
    op.add_column("rag_documents", sa.Column("chunk_overlap", sa.Integer(), nullable=True))
    op.drop_constraint("fk_rag_documents_collection_id", "rag_documents", type_="foreignkey")
    op.drop_column("rag_documents", "collection_id")
    op.drop_column("rag_documents", "storage_path")
    op.drop_table("rag_collections")
```

- [ ] **Step 3: Adicionar fixture `active_collection` e atualizar `_FakeQdrantRAGClient` em `tests/conftest.py`**

Adicionar os imports `uuid` e `from app.db.models import RagCollection` no topo do arquivo (mantendo os já existentes), e adicionar, junto das fixtures existentes:

```python
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
```

Substituir a classe `_FakeQdrantRAGClient` inteira por:

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
        self.upserts: list[tuple[str, list[str], str, str, str]] = []
        self.deleted: list[tuple[str, str]] = []
        self.dropped_collections: list[str] = []

    async def upsert_chunks(
        self, collection_name: str, embedder, chunks: list[str], source: str, domain: str, document_id: str
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
```

- [ ] **Step 4: Rodar os testes existentes para ver a quebra esperada**

Run: `cd backend && .venv/bin/pytest tests/ -x -q`
Expected: FAIL — vários erros de import/assinatura (`test_rag_ingest.py`, `test_rag_api.py`, `test_rag_registry.py`, `test_rag_qdrant_client.py` ainda usam a API antiga). Isso é esperado: as próximas tasks corrigem cada arquivo. Confirme especificamente que **não há erro de sintaxe/import** em `app/db/models.py` (esse arquivo precisa importar limpo):

Run: `cd backend && .venv/bin/python -c "from app.db.models import Base, RagCollection, RagDocument; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/db/models.py backend/migrations/versions/0002_rag_collections.py backend/tests/conftest.py
git commit -m "feat(rag): adiciona modelo RagCollection e migração 0002 (perfis de collection)"
```

---

### Task 2: `app/rag/collections_registry.py` — CRUD de collections

**Files:**
- Create: `backend/src/app/rag/collections_registry.py`
- Create: `backend/tests/test_rag_collections_registry.py`

**Interfaces:**
- Consumes: `app.db.models.RagCollection`, `app.db.models.RagDocument` (Task 1).
- Produces: `create_collection(session, **campos) -> RagCollection`; `list_collections(session) -> list[RagCollection]`; `get_collection(session, collection_id: uuid.UUID) -> RagCollection | None`; `get_active_collection(session) -> RagCollection | None`; `activate_collection(session, collection_id: uuid.UUID) -> bool`; `delete_collection(session, collection_id: uuid.UUID) -> bool` (levanta `CollectionActiveError` se a collection for a ativa); exceção `CollectionActiveError`.

- [ ] **Step 1: Escrever os testes**

```python
import uuid

import pytest

from app.rag.collections_registry import (
    CollectionActiveError,
    activate_collection,
    create_collection,
    delete_collection,
    get_active_collection,
    get_collection,
    list_collections,
)
from app.rag.registry import create_document


async def _cria_collection(session, **overrides):
    defaults = dict(
        name=f"col_{uuid.uuid4().hex}",
        embedding_model="modelo-teste",
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
    )
    defaults.update(overrides)
    return await create_collection(session, **defaults)


async def test_create_collection_grava_e_devolve_a_collection_criada(db_session):
    collection = await _cria_collection(db_session, name="minha_collection")

    assert collection.name == "minha_collection"
    assert collection.is_active is False
    assert collection.id is not None


async def test_list_collections_retorna_mais_recente_primeiro(db_session):
    import asyncio

    primeira = await _cria_collection(db_session, name="primeira")
    await asyncio.sleep(1.1)  # garante segundo diferente no SQLite
    segunda = await _cria_collection(db_session, name="segunda")

    collections = await list_collections(db_session)

    assert [c.id for c in collections] == [segunda.id, primeira.id]


async def test_get_collection_inexistente_retorna_none(db_session):
    assert await get_collection(db_session, uuid.uuid4()) is None


async def test_get_active_collection_sem_nenhuma_ativa_retorna_none(db_session):
    await _cria_collection(db_session, is_active=False)

    assert await get_active_collection(db_session) is None


async def test_activate_collection_ativa_a_escolhida_e_desativa_as_demais(db_session):
    primeira = await _cria_collection(db_session, name="primeira", is_active=True)
    segunda = await _cria_collection(db_session, name="segunda", is_active=False)

    ativado = await activate_collection(db_session, segunda.id)

    assert ativado is True
    assert (await get_active_collection(db_session)).id == segunda.id
    await db_session.refresh(primeira)
    assert primeira.is_active is False


async def test_activate_collection_inexistente_retorna_false(db_session):
    assert await activate_collection(db_session, uuid.uuid4()) is False


async def test_delete_collection_inexistente_retorna_false(db_session):
    assert await delete_collection(db_session, uuid.uuid4()) is False


async def test_delete_collection_ativa_levanta_collection_active_error(db_session):
    collection = await _cria_collection(db_session, is_active=True)

    with pytest.raises(CollectionActiveError):
        await delete_collection(db_session, collection.id)


async def test_delete_collection_inativa_remove_e_retorna_true(db_session):
    collection = await _cria_collection(db_session, is_active=False)

    removida = await delete_collection(db_session, collection.id)

    assert removida is True
    assert await get_collection(db_session, collection.id) is None


async def test_delete_collection_remove_documentos_em_cascata(db_session):
    collection = await _cria_collection(db_session, is_active=False)
    await create_document(
        db_session,
        document_id=str(uuid.uuid4()),
        collection_id=collection.id,
        filename="a.txt",
        domain="vendas",
        chunk_count=1,
        storage_path=None,
        origin="upload",
    )

    await delete_collection(db_session, collection.id)

    from app.rag.registry import list_documents

    assert await list_documents(db_session) == []
```

- [ ] **Step 2: Rodar os testes para ver a falha**

Run: `cd backend && .venv/bin/pytest tests/test_rag_collections_registry.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.rag.collections_registry'` (e `create_document` ainda não aceita `collection_id`/`storage_path` — Task 6 corrige `registry.py`; por ora este teste falha em dois pontos diferentes, o que é esperado nesta etapa).

- [ ] **Step 3: Implementar `app/rag/collections_registry.py`**

```python
"""Registro de perfis de collection do RAG (Entregas B+C+D, além do MVP) —
CRUD sobre `app.db.models.RagCollection`.

Ver docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §3.
Perfis são imutáveis depois de criados — não há função de "update" aqui de
propósito (mudar um parâmetro é criar uma nova collection).
"""

import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RagCollection, RagDocument


class CollectionActiveError(Exception):
    """Levantada ao tentar excluir a collection atualmente ativa."""


async def create_collection(
    session: AsyncSession,
    *,
    name: str,
    embedding_model: str,
    vector_dimension: int,
    distance_metric: str,
    chunk_size: int,
    chunk_overlap: int,
    hnsw_m: int,
    hnsw_ef_construct: int,
    hnsw_full_scan_threshold: int,
    hnsw_max_indexing_threads: int,
    hnsw_on_disk: bool,
    hnsw_payload_m: int | None,
    quantization_type: str,
    quantization_config: dict,
    payload_indexes: list,
    is_active: bool = False,
) -> RagCollection:
    collection = RagCollection(
        id=uuid.uuid4(),
        name=name,
        embedding_model=embedding_model,
        vector_dimension=vector_dimension,
        distance_metric=distance_metric,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        hnsw_m=hnsw_m,
        hnsw_ef_construct=hnsw_ef_construct,
        hnsw_full_scan_threshold=hnsw_full_scan_threshold,
        hnsw_max_indexing_threads=hnsw_max_indexing_threads,
        hnsw_on_disk=hnsw_on_disk,
        hnsw_payload_m=hnsw_payload_m,
        quantization_type=quantization_type,
        quantization_config=quantization_config,
        payload_indexes=payload_indexes,
        is_active=is_active,
    )
    session.add(collection)
    await session.commit()
    await session.refresh(collection)
    return collection


async def list_collections(session: AsyncSession) -> list[RagCollection]:
    result = await session.execute(select(RagCollection).order_by(RagCollection.created_at.desc()))
    return list(result.scalars().all())


async def get_collection(session: AsyncSession, collection_id: uuid.UUID) -> RagCollection | None:
    return await session.get(RagCollection, collection_id)


async def get_active_collection(session: AsyncSession) -> RagCollection | None:
    result = await session.execute(select(RagCollection).where(RagCollection.is_active.is_(True)))
    return result.scalars().first()


async def activate_collection(session: AsyncSession, collection_id: uuid.UUID) -> bool:
    collection = await session.get(RagCollection, collection_id)
    if collection is None:
        return False
    await session.execute(update(RagCollection).values(is_active=False))
    collection.is_active = True
    await session.commit()
    return True


async def delete_collection(session: AsyncSession, collection_id: uuid.UUID) -> bool:
    """Remove a collection e, em cascata, os documentos registrados nela
    (ver docs/superpowers/specs/2026-09-15-rag-collections-config-design.md
    §6.1). A remoção da collection real no Qdrant e dos arquivos em disco é
    responsabilidade de quem chama esta função (`app.api.rag_collections`),
    feita ANTES desta chamada — ver ordem "Qdrant → arquivos → Postgres" na
    spec.
    """
    collection = await session.get(RagCollection, collection_id)
    if collection is None:
        return False
    if collection.is_active:
        raise CollectionActiveError(str(collection_id))
    await session.execute(delete(RagDocument).where(RagDocument.collection_id == collection_id))
    await session.delete(collection)
    await session.commit()
    return True
```

- [ ] **Step 4: Rodar os testes deste arquivo (ainda falham por causa de `create_document`)**

Run: `cd backend && .venv/bin/pytest tests/test_rag_collections_registry.py -v`
Expected: `test_delete_collection_remove_documentos_em_cascata` FALHA (`create_document` ainda não aceita `collection_id`/`storage_path`); as demais 8 PASSAM. Isso é esperado — Task 6 corrige `registry.py`, e este teste deve passar depois dela sem precisar editar este arquivo de novo.

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/rag/collections_registry.py backend/tests/test_rag_collections_registry.py
git commit -m "feat(rag): adiciona CRUD de perfis de collection (collections_registry)"
```

---

### Task 3: `app/rag/embedders_registry.py` — cache de embedders por modelo

**Files:**
- Create: `backend/src/app/rag/embedders_registry.py`
- Create: `backend/tests/test_rag_embedders_registry.py`

**Interfaces:**
- Consumes: `app.rag.embeddings.TextEmbedder` (existente, sem mudanças).
- Produces: `EmbedderRegistry` com método `get(model_name: str) -> TextEmbedder` (mesma instância para o mesmo nome).

- [ ] **Step 1: Escrever o teste**

```python
from app.rag.embedders_registry import EmbedderRegistry


def test_get_mesmo_modelo_duas_vezes_retorna_a_mesma_instancia():
    registry = EmbedderRegistry()

    a = registry.get("modelo-a")
    b = registry.get("modelo-a")

    assert a is b


def test_get_modelos_diferentes_retorna_instancias_diferentes():
    registry = EmbedderRegistry()

    a = registry.get("modelo-a")
    b = registry.get("modelo-b")

    assert a is not b
    assert a.model_name == "modelo-a"
    assert b.model_name == "modelo-b"
```

- [ ] **Step 2: Rodar para ver a falha**

Run: `cd backend && .venv/bin/pytest tests/test_rag_embedders_registry.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.rag.embedders_registry'`

- [ ] **Step 3: Implementar**

```python
"""Cache de instâncias de `TextEmbedder` por nome de modelo (Entregas B+C+D,
além do MVP) — evita recarregar/duplicar o mesmo modelo em VRAM quando
várias collections compartilham o mesmo `embedding_model` (ver
docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §5).
"""

import threading

from app.rag.embeddings import TextEmbedder


class EmbedderRegistry:
    def __init__(self) -> None:
        self._embedders: dict[str, TextEmbedder] = {}
        self._lock = threading.Lock()

    def get(self, model_name: str) -> TextEmbedder:
        with self._lock:
            embedder = self._embedders.get(model_name)
            if embedder is None:
                embedder = TextEmbedder(model_name)
                self._embedders[model_name] = embedder
            return embedder
```

- [ ] **Step 4: Rodar de novo**

Run: `cd backend && .venv/bin/pytest tests/test_rag_embedders_registry.py -v`
Expected: PASS (2 testes)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/rag/embedders_registry.py backend/tests/test_rag_embedders_registry.py
git commit -m "feat(rag): adiciona cache de embedders por modelo (EmbedderRegistry)"
```

---

### Task 4: Refatorar `app/rag/qdrant_client.py` — operações parametrizadas por collection

**Files:**
- Modify: `backend/src/app/rag/qdrant_client.py`
- Modify: `backend/tests/test_rag_qdrant_client.py`

**Interfaces:**
- Produces: `QdrantRAGClient(host, port, timeout_s=DEFAULT_TIMEOUT_S, client=None)` sem mais estado de collection fixa; `collection_exists(name) -> bool`; `create_collection(*, name, vector_dimension, distance_metric, hnsw_m, hnsw_ef_construct, hnsw_full_scan_threshold, hnsw_max_indexing_threads, hnsw_on_disk, hnsw_payload_m, quantization_type, quantization_config: dict, payload_indexes: list[dict]) -> None` (levanta `CollectionAlreadyExistsError` se já existir); `drop_collection(collection_name) -> None`; `upsert_chunks(collection_name, embedder, chunks, source, domain, document_id) -> int`; `search(collection_name, embedder, query, domain, top_k=DEFAULT_TOP_K, score_threshold=DEFAULT_SCORE_THRESHOLD) -> list[Document]`; `delete_by_document_id(collection_name, document_id) -> None`; exceção `CollectionAlreadyExistsError`.
- Consumes: `app.rag.embeddings.TextEmbedder` (parâmetro `embedder`, não mais fixo no construtor), `app.router.rag_client.Document`/`RAGConnectionError`.

**Nota importante:** este refactor remove `ensure_collection`/`_collection_ready`/`_collection_lock` — collections agora precisam existir antes de qualquer ingestão/busca (criadas explicitamente via `create_collection`, chamado pelo endpoint `POST /api/rag/collections` na Task 11). Por isso os testes de concorrência na criação implícita e de "cache de collection pronta invalidado por drop" da versão antiga deixam de fazer sentido e são removidos (não há mais criação implícita nem cache a invalidar) — ver comentário no arquivo de teste abaixo.

- [ ] **Step 1: Substituir todo o conteúdo de `backend/tests/test_rag_qdrant_client.py`**

```python
import uuid

import pytest
from qdrant_client import AsyncQdrantClient

from app.config import get_settings
from app.rag.embeddings import TextEmbedder
from app.rag.qdrant_client import CollectionAlreadyExistsError, QdrantRAGClient
from app.router.rag_client import Document, RAGConnectionError

_DEFAULT_HNSW = dict(
    hnsw_m=16,
    hnsw_ef_construct=100,
    hnsw_full_scan_threshold=10000,
    hnsw_max_indexing_threads=0,
    hnsw_on_disk=False,
    hnsw_payload_m=None,
)


@pytest.fixture
def qdrant() -> QdrantRAGClient:
    """Cliente RAG contra um Qdrant em memória (`location=":memory:"`) —
    evita depender de um Qdrant externo no ar e evita colisão entre testes."""
    return QdrantRAGClient(host="unused", port=0, client=AsyncQdrantClient(location=":memory:"))


async def _cria_collection(qdrant: QdrantRAGClient, dimension: int, name: str | None = None) -> str:
    name = name or f"test_{uuid.uuid4().hex}"
    await qdrant.create_collection(
        name=name,
        vector_dimension=dimension,
        distance_metric="cosine",
        quantization_type="none",
        quantization_config={},
        payload_indexes=[],
        **_DEFAULT_HNSW,
    )
    return name


async def test_create_collection_cria_e_collection_exists_confirma(
    qdrant: QdrantRAGClient, text_embedder: TextEmbedder
):
    name = await _cria_collection(qdrant, await text_embedder.get_dimension())

    assert await qdrant.collection_exists(name) is True


async def test_create_collection_duplicada_levanta_collection_already_exists(
    qdrant: QdrantRAGClient, text_embedder: TextEmbedder
):
    name = await _cria_collection(qdrant, await text_embedder.get_dimension())

    with pytest.raises(CollectionAlreadyExistsError):
        await _cria_collection(qdrant, await text_embedder.get_dimension(), name=name)


async def test_create_collection_com_payload_indexes_nao_levanta_erro(
    qdrant: QdrantRAGClient, text_embedder: TextEmbedder
):
    name = f"test_{uuid.uuid4().hex}"

    await qdrant.create_collection(
        name=name,
        vector_dimension=await text_embedder.get_dimension(),
        distance_metric="cosine",
        quantization_type="scalar",
        quantization_config={"quantile": 0.9, "always_ram": True},
        payload_indexes=[
            {"field": "domain", "schema_type": "keyword"},
            {"field": "content", "schema_type": "text", "text_params": {"tokenizer": "word"}},
        ],
        **_DEFAULT_HNSW,
    )

    assert await qdrant.collection_exists(name) is True


async def test_search_sem_collection_criada_retorna_lista_vazia(
    qdrant: QdrantRAGClient, text_embedder: TextEmbedder
):
    resultado = await qdrant.search("nome_inexistente", text_embedder, "qualquer pergunta", domain="vendas")

    assert resultado == []


async def test_upsert_chunks_vazio_nao_grava_e_retorna_zero(
    qdrant: QdrantRAGClient, text_embedder: TextEmbedder
):
    name = await _cria_collection(qdrant, await text_embedder.get_dimension())

    total = await qdrant.upsert_chunks(
        name, text_embedder, [], source="arquivo.txt", domain="vendas", document_id="doc-1"
    )

    assert total == 0
    assert await qdrant.search(name, text_embedder, "qualquer coisa", domain="vendas") == []


async def test_upsert_e_search_retorna_documento_com_conteudo_e_fonte(
    qdrant: QdrantRAGClient, text_embedder: TextEmbedder
):
    name = await _cria_collection(qdrant, await text_embedder.get_dimension())
    await qdrant.upsert_chunks(
        name,
        text_embedder,
        ["O gerador diesel GD-30 tem potência de 30 kVA e autonomia de 10 horas."],
        source="catalogo_geradores.txt",
        domain="vendas",
        document_id="doc-1",
    )

    resultado = await qdrant.search(name, text_embedder, "Qual a potência do gerador GD-30?", domain="vendas")

    assert len(resultado) == 1
    documento = resultado[0]
    assert isinstance(documento, Document)
    assert "GD-30" in documento.content
    assert documento.source == "catalogo_geradores.txt"
    assert documento.score > 0


async def test_search_filtra_por_domain_nao_traz_documento_de_outro_dominio(
    qdrant: QdrantRAGClient, text_embedder: TextEmbedder
):
    name = await _cria_collection(qdrant, await text_embedder.get_dimension())
    await qdrant.upsert_chunks(
        name,
        text_embedder,
        ["O gerador não liga: verificar bateria de partida e nível de combustível."],
        source="manual_gd30.txt",
        domain="suporte",
        document_id="doc-1",
    )

    resultado = await qdrant.search(name, text_embedder, "gerador não liga", domain="vendas")

    assert resultado == []


async def test_search_erro_de_conexao_vira_rag_connection_error(text_embedder: TextEmbedder):
    # Porta sem nenhum serviço no ar — falha de conexão, não busca vazia.
    client = QdrantRAGClient(host="localhost", port=1)

    with pytest.raises(RAGConnectionError):
        await client.search("qualquer_nome", text_embedder, "qualquer coisa", domain="vendas")


class _FailingEmbedder:
    """`get_dimension` funciona normalmente mas `embed` falha — simula um
    erro do modelo (ex.: texto degenerado extraído de um PDF) durante o
    próprio `upsert_chunks`."""

    async def get_dimension(self) -> int:
        return 384

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("falha simulada do modelo de embeddings")


async def test_upsert_chunks_com_falha_no_embedder_vira_rag_connection_error(
    qdrant: QdrantRAGClient, text_embedder: TextEmbedder
):
    name = await _cria_collection(qdrant, await text_embedder.get_dimension())

    with pytest.raises(RAGConnectionError):
        await qdrant.upsert_chunks(
            name, _FailingEmbedder(), ["texto qualquer"], source="arquivo.txt", domain="vendas", document_id="doc-1"
        )


@pytest.mark.qdrant
async def test_upsert_e_search_contra_qdrant_real_do_docker_compose(text_embedder: TextEmbedder):
    """Mesmo comportamento de `test_upsert_e_search_retorna_documento_...`,
    mas contra o Qdrant real do `docker-compose.yml` (não em memória) — só
    roda com o serviço no ar (ver `QDRANT_HOST`/`QDRANT_PORT` em `.env`).
    Também é o único teste que exercita HNSW/quantização/payload indexing de
    verdade — o backend em memória usado nos demais testes aceita esses
    parâmetros mas os ignora silenciosamente (confirmado lendo
    `qdrant_client.local.qdrant_local.QdrantLocal.create_collection` e
    `.create_payload_index` — ver
    docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §4).
    """
    settings = get_settings()
    client = QdrantRAGClient(host=settings.qdrant_host, port=settings.qdrant_port)
    name = f"test_{uuid.uuid4().hex}"

    try:
        await client.create_collection(
            name=name,
            vector_dimension=await text_embedder.get_dimension(),
            distance_metric="cosine",
            quantization_type="scalar",
            quantization_config={"quantile": 0.99, "always_ram": False},
            payload_indexes=[{"field": "domain", "schema_type": "keyword"}],
            **_DEFAULT_HNSW,
        )
        await client.upsert_chunks(
            name,
            text_embedder,
            ["A garantia padrão dos geradores é de 12 meses contra defeitos de fabricação."],
            source="politicas_troca_garantia.txt",
            domain="atendimento",
            document_id="doc-1",
        )

        resultado = await client.search(name, text_embedder, "qual o prazo de garantia?", domain="atendimento")

        assert len(resultado) == 1
        assert "garantia" in resultado[0].content.lower()
    finally:
        await client.drop_collection(name)


async def test_upsert_chunks_grava_document_id_no_payload_do_ponto(
    qdrant: QdrantRAGClient, text_embedder: TextEmbedder
):
    name = await _cria_collection(qdrant, await text_embedder.get_dimension())
    await qdrant.upsert_chunks(
        name, text_embedder, ["conteúdo de teste"], source="arquivo.txt", domain="vendas", document_id="doc-xyz"
    )

    pontos, _ = await qdrant._client.scroll(name, limit=10)

    assert len(pontos) == 1
    assert pontos[0].payload["document_id"] == "doc-xyz"


async def test_delete_by_document_id_remove_so_os_pontos_daquele_documento(
    qdrant: QdrantRAGClient, text_embedder: TextEmbedder
):
    name = await _cria_collection(qdrant, await text_embedder.get_dimension())
    await qdrant.upsert_chunks(
        name, text_embedder, ["conteúdo do documento A"], source="a.txt", domain="vendas", document_id="doc-a"
    )
    await qdrant.upsert_chunks(
        name, text_embedder, ["conteúdo do documento B"], source="b.txt", domain="vendas", document_id="doc-b"
    )

    await qdrant.delete_by_document_id(name, "doc-a")

    resultado = await qdrant.search(name, text_embedder, "conteúdo", domain="vendas")
    assert len(resultado) == 1
    assert resultado[0].source == "b.txt"


async def test_delete_by_document_id_sem_collection_nao_levanta_erro(qdrant: QdrantRAGClient):
    # Collection inexistente — deve ser um no-op silencioso, mesmo espírito
    # de `search` sem nada indexado.
    await qdrant.delete_by_document_id("nome_inexistente", "doc-inexistente")


async def test_delete_by_document_id_erro_de_conexao_vira_rag_connection_error():
    client = QdrantRAGClient(host="localhost", port=1)

    with pytest.raises(RAGConnectionError):
        await client.delete_by_document_id("qualquer_nome", "doc-1")
```

- [ ] **Step 2: Rodar os testes para confirmar que falham contra a implementação antiga**

Run: `cd backend && .venv/bin/pytest tests/test_rag_qdrant_client.py -v`
Expected: FAIL — `QdrantRAGClient.__init__()` não aceita mais chamadas sem `embedder`, `create_collection`/`collection_exists` não existem ainda, etc.

- [ ] **Step 3: Substituir todo o conteúdo de `backend/src/app/rag/qdrant_client.py`**

```python
"""Cliente RAG real via Qdrant (R4) — ingestão e busca vetorial de texto/PDF.

Desde a entrega de perfis de collection configuráveis (ver
docs/superpowers/specs/2026-09-15-rag-collections-config-design.md), esta
classe não guarda mais "a" collection fixa: cada operação recebe
explicitamente o nome da collection (e, quando aplicável, o embedder usado
por ela), porque o sistema agora suporta múltiplas collections com perfis
diferentes (ver `app.rag.collections_registry.RagCollection`). Coleções
precisam existir antes de qualquer ingestão/busca — são sempre criadas
explicitamente via `create_collection` (endpoint `POST /api/rag/collections`),
nunca implicitamente na primeira ingestão como antes desta entrega.

O contrato `RAGClient` Protocol (busca usada pelo orchestrator) é
implementado por `app.rag.active_collection_client.ActiveCollectionRagClient`,
não por esta classe diretamente — ver
docs/superpowers/specs/2026-09-05-roteador-basico-design.md §2.3 para a
origem do Protocol.
"""

import logging
import uuid

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    BinaryQuantization,
    BinaryQuantizationConfig,
    Distance,
    FieldCondition,
    Filter,
    HnswConfigDiff,
    MatchValue,
    PointStruct,
    ProductQuantization,
    ProductQuantizationConfig,
    ScalarQuantization,
    ScalarQuantizationConfig,
    ScalarType,
    TextIndexParams,
    TextIndexType,
    VectorParams,
)

from app.rag.embeddings import TextEmbedder
from app.router.rag_client import Document, RAGConnectionError

logger = logging.getLogger(__name__)

# MVP: top-k e limiar de score fixos por config, sem reranking (BM25 +
# similaridade combinada é evolução futura, ver docs/TECHNOLOGY_STACK.md,
# linha "Reranking") nem configuráveis por perfil de collection (ver
# docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §10).
DEFAULT_TOP_K = 3
DEFAULT_SCORE_THRESHOLD = 0.35
# O default da própria lib qdrant-client é 5s; nesta máquina de dev (WSL2),
# resolver "localhost" ocasionalmente demora mais que isso (tentativa de
# IPv6 antes de cair para IPv4), estourando o timeout default por uma
# lentidão de rede local, não uma falha real de infraestrutura — daí um
# default um pouco mais folgado aqui.
DEFAULT_TIMEOUT_S = 10.0

_DISTANCE_BY_METRIC = {
    "cosine": Distance.COSINE,
    "euclid": Distance.EUCLID,
    "dot": Distance.DOT,
    "manhattan": Distance.MANHATTAN,
}


class CollectionAlreadyExistsError(Exception):
    """Levantada por `create_collection` quando já existe uma collection com esse nome."""


def _quantization_from_config(quantization_type: str, quantization_config: dict):
    if quantization_type == "scalar":
        return ScalarQuantization(
            scalar=ScalarQuantizationConfig(
                type=ScalarType.INT8,
                quantile=quantization_config.get("quantile", 0.99),
                always_ram=quantization_config.get("always_ram", False),
            )
        )
    if quantization_type == "product":
        return ProductQuantization(
            product=ProductQuantizationConfig(
                compression=quantization_config.get("compression", "x16"),
                always_ram=quantization_config.get("always_ram", False),
            )
        )
    if quantization_type == "binary":
        return BinaryQuantization(
            binary=BinaryQuantizationConfig(always_ram=quantization_config.get("always_ram", False))
        )
    return None


def _payload_schema_from_index(payload_index: dict):
    schema_type = payload_index["schema_type"]
    if schema_type != "text":
        return schema_type
    text_params = payload_index.get("text_params") or {}
    return TextIndexParams(
        type=TextIndexType.TEXT,
        tokenizer=text_params.get("tokenizer", "word"),
        min_token_len=text_params.get("min_token_len"),
        max_token_len=text_params.get("max_token_len"),
        lowercase=text_params.get("lowercase", True),
    )


class QdrantRAGClient:
    """Operações de baixo nível sobre o Qdrant, parametrizadas por collection.

    Não guarda estado de qual collection é "a" collection — cada método
    recebe `collection_name` (e `embedder`, quando a operação envolve gerar
    vetores) explicitamente. Ver docstring do módulo.
    """

    def __init__(
        self,
        host: str,
        port: int,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        client: AsyncQdrantClient | None = None,
    ) -> None:
        self._client = (
            client
            if client is not None
            else AsyncQdrantClient(host=host, port=port, timeout=int(timeout_s))
        )

    async def collection_exists(self, collection_name: str) -> bool:
        try:
            return await self._client.collection_exists(collection_name)
        except Exception as exc:
            raise RAGConnectionError(str(exc)) from exc

    async def create_collection(
        self,
        *,
        name: str,
        vector_dimension: int,
        distance_metric: str,
        hnsw_m: int,
        hnsw_ef_construct: int,
        hnsw_full_scan_threshold: int,
        hnsw_max_indexing_threads: int,
        hnsw_on_disk: bool,
        hnsw_payload_m: int | None,
        quantization_type: str,
        quantization_config: dict,
        payload_indexes: list[dict],
    ) -> None:
        """Cria a collection com os parâmetros completos do perfil.

        Levanta `CollectionAlreadyExistsError` se já existir uma collection
        com esse nome (checagem explícita antes de criar, em vez de deixar o
        Qdrant levantar seu próprio erro genérico de conflito).

        # MVP: sem cache de "collection existe" por nome — ao contrário da
        # versão anterior desta classe (`ensure_collection`/`_collection_ready`),
        # múltiplas collections agora podem ser criadas/excluídas em runtime
        # via API, e um cache sem invalidação abriria uma janela de
        # inconsistência (achar que uma collection excluída ainda existe).
        """
        try:
            if await self._client.collection_exists(name):
                raise CollectionAlreadyExistsError(name)
            await self._client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=vector_dimension, distance=_DISTANCE_BY_METRIC[distance_metric]
                ),
                hnsw_config=HnswConfigDiff(
                    m=hnsw_m,
                    ef_construct=hnsw_ef_construct,
                    full_scan_threshold=hnsw_full_scan_threshold,
                    max_indexing_threads=hnsw_max_indexing_threads,
                    on_disk=hnsw_on_disk,
                    payload_m=hnsw_payload_m,
                ),
                quantization_config=_quantization_from_config(quantization_type, quantization_config),
            )
            for payload_index in payload_indexes:
                await self._client.create_payload_index(
                    collection_name=name,
                    field_name=payload_index["field"],
                    field_schema=_payload_schema_from_index(payload_index),
                )
        except CollectionAlreadyExistsError:
            raise
        except Exception as exc:
            raise RAGConnectionError(str(exc)) from exc

    async def drop_collection(self, collection_name: str) -> None:
        try:
            await self._client.delete_collection(collection_name)
        except Exception as exc:
            raise RAGConnectionError(str(exc)) from exc

    async def upsert_chunks(
        self,
        collection_name: str,
        embedder: TextEmbedder,
        chunks: list[str],
        source: str,
        domain: str,
        document_id: str,
    ) -> int:
        """Embeda e grava `chunks` em `collection_name`, com payload
        `source`/`domain`/`document_id`.

        # MVP: sem deduplicação nem re-ingestão incremental — reingerir a
        # mesma fonte duas vezes cria pontos duplicados na collection.
        Pressupõe que `collection_name` já existe (criada via
        `create_collection`) — sem criação implícita.
        """
        if not chunks:
            return 0
        try:
            vectors = await embedder.embed(chunks)
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
            await self._client.upsert(collection_name=collection_name, points=points)
        except Exception as exc:
            raise RAGConnectionError(str(exc)) from exc
        return len(points)

    async def search(
        self,
        collection_name: str,
        embedder: TextEmbedder,
        query: str,
        domain: str,
        top_k: int = DEFAULT_TOP_K,
        score_threshold: float = DEFAULT_SCORE_THRESHOLD,
    ) -> list[Document]:
        """Busca por similaridade em `collection_name`, filtrada por `domain`.

        Lista vazia é devolvida tanto quando a collection ainda não existe
        quanto quando a busca roda normalmente e não acha nada acima do
        limiar — os dois são sinal de negócio válido. Falha de
        infraestrutura vira `RAGConnectionError`.
        """
        try:
            if not await self._client.collection_exists(collection_name):
                return []
            [query_vector] = await embedder.embed([query])
            response = await self._client.query_points(
                collection_name=collection_name,
                query=query_vector,
                query_filter=Filter(
                    must=[FieldCondition(key="domain", match=MatchValue(value=domain))]
                ),
                limit=top_k,
                score_threshold=score_threshold,
            )
            return [
                Document(
                    content=point.payload["content"],
                    source=point.payload["source"],
                    score=point.score,
                )
                for point in response.points
            ]
        except Exception as exc:
            raise RAGConnectionError(str(exc)) from exc

    async def delete_by_document_id(self, collection_name: str, document_id: str) -> None:
        """Remove todos os pontos com aquele `document_id` no payload de
        `collection_name`."""
        try:
            if not await self._client.collection_exists(collection_name):
                return
            await self._client.delete(
                collection_name=collection_name,
                points_selector=Filter(
                    must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
                ),
            )
        except Exception as exc:
            raise RAGConnectionError(str(exc)) from exc
```

- [ ] **Step 4: Rodar os testes de novo**

Run: `cd backend && .venv/bin/pytest tests/test_rag_qdrant_client.py -v -m "not qdrant"`
Expected: PASS (todos, exceto o marcado `@pytest.mark.qdrant`, que só roda com o Qdrant real do `docker-compose.yml` no ar — sem ele, é pulado automaticamente por `conftest.py`)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/rag/qdrant_client.py backend/tests/test_rag_qdrant_client.py
git commit -m "refactor(rag): QdrantRAGClient passa a operar por collection explícita, não fixa"
```

---

### Task 5: `app/rag/active_collection_client.py` — adapter do `RAGClient` Protocol

**Files:**
- Create: `backend/src/app/rag/active_collection_client.py`
- Create: `backend/tests/test_rag_active_collection_client.py`

**Interfaces:**
- Consumes: `app.rag.qdrant_client.QdrantRAGClient` (Task 4), `app.rag.collections_registry.get_active_collection` (Task 2), `app.rag.embedders_registry.EmbedderRegistry` (Task 3), `sqlalchemy.ext.asyncio.async_sessionmaker`.
- Produces: `ActiveCollectionRagClient(qdrant, session_factory, embedders)` implementando o Protocol `app.router.rag_client.RAGClient` — `async def search(query: str, domain: str) -> list[Document]`.

- [ ] **Step 1: Escrever os testes**

```python
import uuid

import pytest
from qdrant_client import AsyncQdrantClient

from app.db.engine import create_db_engine, create_session_factory
from app.db.models import Base, RagCollection
from app.rag.active_collection_client import ActiveCollectionRagClient
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.embeddings import TextEmbedder
from app.rag.qdrant_client import QdrantRAGClient

_DEFAULT_HNSW = dict(
    hnsw_m=16,
    hnsw_ef_construct=100,
    hnsw_full_scan_threshold=10000,
    hnsw_max_indexing_threads=0,
    hnsw_on_disk=False,
    hnsw_payload_m=None,
)


async def _engine_e_sessionmaker_vazios():
    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, create_session_factory(engine)


async def test_search_usa_a_collection_marcada_como_ativa(text_embedder: TextEmbedder):
    engine, factory = await _engine_e_sessionmaker_vazios()
    collection_name = f"test_{uuid.uuid4().hex}"
    dimension = await text_embedder.get_dimension()

    async with factory() as session:
        session.add(
            RagCollection(
                id=uuid.uuid4(),
                name=collection_name,
                embedding_model=text_embedder.model_name,
                vector_dimension=dimension,
                distance_metric="cosine",
                chunk_size=800,
                chunk_overlap=100,
                quantization_type="none",
                quantization_config={},
                payload_indexes=[],
                is_active=True,
                **_DEFAULT_HNSW,
            )
        )
        await session.commit()

    qdrant = QdrantRAGClient(host="unused", port=0, client=AsyncQdrantClient(location=":memory:"))
    await qdrant.create_collection(
        name=collection_name,
        vector_dimension=dimension,
        distance_metric="cosine",
        quantization_type="none",
        quantization_config={},
        payload_indexes=[],
        **_DEFAULT_HNSW,
    )
    await qdrant.upsert_chunks(
        collection_name,
        text_embedder,
        ["conteúdo sobre o produto X"],
        source="a.txt",
        domain="vendas",
        document_id="doc-1",
    )

    client = ActiveCollectionRagClient(qdrant, factory, EmbedderRegistry())
    resultado = await client.search("produto X", domain="vendas")

    assert len(resultado) == 1
    assert resultado[0].source == "a.txt"
    await engine.dispose()


async def test_search_sem_collection_ativa_retorna_lista_vazia():
    engine, factory = await _engine_e_sessionmaker_vazios()
    qdrant = QdrantRAGClient(host="unused", port=0, client=AsyncQdrantClient(location=":memory:"))

    client = ActiveCollectionRagClient(qdrant, factory, EmbedderRegistry())
    resultado = await client.search("qualquer coisa", domain="vendas")

    assert resultado == []
    await engine.dispose()
```

- [ ] **Step 2: Rodar para ver a falha**

Run: `cd backend && .venv/bin/pytest tests/test_rag_active_collection_client.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.rag.active_collection_client'`

- [ ] **Step 3: Implementar**

```python
"""Adapter que implementa o Protocol `RAGClient` (usado pelo orchestrator)
resolvendo, a cada busca, qual collection está marcada como ativa — ver
docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §4.1.

Isso é uma coupling nova: a busca do RAG passa a depender do Postgres (antes
só a ingestão dependia, desde a Entrega A). `# MVP: sem cache do id da
collection ativa em memória — um round trip extra ao Postgres por mensagem
de chat é aceitável neste protótipo`.
"""

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.rag.collections_registry import get_active_collection
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import QdrantRAGClient
from app.router.rag_client import Document


class ActiveCollectionRagClient:
    def __init__(
        self,
        qdrant: QdrantRAGClient,
        session_factory: async_sessionmaker,
        embedders: EmbedderRegistry,
    ) -> None:
        self._qdrant = qdrant
        self._session_factory = session_factory
        self._embedders = embedders

    async def search(self, query: str, domain: str) -> list[Document]:
        async with self._session_factory() as session:
            collection = await get_active_collection(session)
        if collection is None:
            return []
        embedder = self._embedders.get(collection.embedding_model)
        return await self._qdrant.search(collection.name, embedder, query, domain)
```

- [ ] **Step 4: Rodar de novo**

Run: `cd backend && .venv/bin/pytest tests/test_rag_active_collection_client.py -v`
Expected: PASS (2 testes)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/rag/active_collection_client.py backend/tests/test_rag_active_collection_client.py
git commit -m "feat(rag): adiciona ActiveCollectionRagClient (adapter RAGClient por collection ativa)"
```

---

### Task 6: Atualizar `app/rag/registry.py` — documentos ligados a uma collection

**Files:**
- Modify: `backend/src/app/rag/registry.py`
- Modify: `backend/tests/test_rag_registry.py`

**Interfaces:**
- Produces: `create_document(session, *, document_id, collection_id, filename, domain, chunk_count, storage_path, origin) -> RagDocument` (assinatura muda: perde `embedding_model`/`chunk_size`/`chunk_overlap`, ganha `collection_id`/`storage_path`); `list_documents(session) -> list[RagDocument]` (sem mudança de assinatura); `delete_document(session, document_id) -> bool` (sem mudança); novas: `list_documents_by_collection(session, collection_id) -> list[RagDocument]`; `count_documents_by_collection(session) -> dict[uuid.UUID, int]`.

- [ ] **Step 1: Atualizar `backend/tests/test_rag_registry.py`**

Substituir a função `_cria` e adicionar os dois novos testes, mantendo os demais testes do arquivo (`test_create_document_...`, `test_list_documents_...`, `test_delete_document_...`) só trocando as chamadas de `_cria` para a nova assinatura:

```python
import asyncio
import uuid

from app.rag.registry import (
    count_documents_by_collection,
    create_document,
    delete_document,
    list_documents,
    list_documents_by_collection,
)


async def _cria(session, *, collection_id, **overrides):
    defaults = dict(
        document_id=str(uuid.uuid4()),
        collection_id=collection_id,
        filename="catalogo.txt",
        domain="vendas",
        chunk_count=2,
        storage_path=None,
        origin="upload",
    )
    defaults.update(overrides)
    return await create_document(session, **defaults)


async def test_create_document_grava_e_devolve_o_documento_criado(db_session, active_collection):
    documento = await _cria(db_session, collection_id=active_collection.id, filename="a.txt")

    assert documento.filename == "a.txt"
    assert documento.collection_id == active_collection.id
    assert documento.id is not None
    assert documento.created_at is not None


async def test_list_documents_retorna_mais_recente_primeiro(db_session, active_collection):
    primeiro = await _cria(db_session, collection_id=active_collection.id, filename="primeiro.txt")
    await asyncio.sleep(1.1)  # Ensure different SQLite second precision
    segundo = await _cria(db_session, collection_id=active_collection.id, filename="segundo.txt")

    documentos = await list_documents(db_session)

    assert [d.id for d in documentos] == [segundo.id, primeiro.id]


async def test_list_documents_sem_nenhum_documento_retorna_lista_vazia(db_session):
    assert await list_documents(db_session) == []


async def test_delete_document_existente_remove_e_retorna_true(db_session, active_collection):
    documento = await _cria(db_session, collection_id=active_collection.id)

    removido = await delete_document(db_session, str(documento.id))

    assert removido is True
    assert await list_documents(db_session) == []


async def test_delete_document_inexistente_retorna_false(db_session):
    removido = await delete_document(db_session, str(uuid.uuid4()))

    assert removido is False


async def test_list_documents_by_collection_filtra_pela_collection(db_session, active_collection):
    from app.rag.collections_registry import create_collection

    outra_collection = await create_collection(
        db_session,
        name="outra",
        embedding_model="modelo-teste",
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
    )
    await _cria(db_session, collection_id=active_collection.id, filename="da_ativa.txt")
    await _cria(db_session, collection_id=outra_collection.id, filename="da_outra.txt")

    documentos = await list_documents_by_collection(db_session, active_collection.id)

    assert [d.filename for d in documentos] == ["da_ativa.txt"]


async def test_count_documents_by_collection_agrupa_por_collection(db_session, active_collection):
    await _cria(db_session, collection_id=active_collection.id, filename="a.txt")
    await _cria(db_session, collection_id=active_collection.id, filename="b.txt")

    contagens = await count_documents_by_collection(db_session)

    assert contagens[active_collection.id] == 2
```

- [ ] **Step 2: Rodar para ver a falha**

Run: `cd backend && .venv/bin/pytest tests/test_rag_registry.py -v`
Expected: FAIL — `create_document` ainda não aceita `collection_id`/`storage_path`, e `list_documents_by_collection`/`count_documents_by_collection` não existem.

- [ ] **Step 3: Atualizar `backend/src/app/rag/registry.py`**

```python
"""Registro de documentos ingeridos no RAG (R4, além do MVP) — CRUD sobre
`app.db.models.RagDocument`.

Ver docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md e
docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §3.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RagDocument


async def create_document(
    session: AsyncSession,
    *,
    document_id: str,
    collection_id: uuid.UUID,
    filename: str,
    domain: str,
    chunk_count: int,
    storage_path: str | None,
    origin: str,
) -> RagDocument:
    document = RagDocument(
        id=uuid.UUID(document_id),
        collection_id=collection_id,
        filename=filename,
        domain=domain,
        chunk_count=chunk_count,
        storage_path=storage_path,
        origin=origin,
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document


async def list_documents(session: AsyncSession) -> list[RagDocument]:
    result = await session.execute(select(RagDocument).order_by(RagDocument.created_at.desc()))
    return list(result.scalars().all())


async def list_documents_by_collection(session: AsyncSession, collection_id: uuid.UUID) -> list[RagDocument]:
    result = await session.execute(
        select(RagDocument).where(RagDocument.collection_id == collection_id)
    )
    return list(result.scalars().all())


async def count_documents_by_collection(session: AsyncSession) -> dict[uuid.UUID, int]:
    result = await session.execute(
        select(RagDocument.collection_id, func.count()).group_by(RagDocument.collection_id)
    )
    return dict(result.all())


async def delete_document(session: AsyncSession, document_id: str) -> bool:
    document = await session.get(RagDocument, uuid.UUID(document_id))
    if document is None:
        return False
    await session.delete(document)
    await session.commit()
    return True
```

- [ ] **Step 4: Rodar todos os testes de registry e collections_registry (a Task 2 tinha um teste pendente disso)**

Run: `cd backend && .venv/bin/pytest tests/test_rag_registry.py tests/test_rag_collections_registry.py -v`
Expected: PASS (todos, incluindo `test_delete_collection_remove_documentos_em_cascata` da Task 2, que dependia desta mudança)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/rag/registry.py backend/tests/test_rag_registry.py
git commit -m "feat(rag): liga documentos a uma collection (collection_id, storage_path)"
```

---

### Task 7: Atualizar `app/rag/ingest.py` — ingestão por collection + reingestão

**Files:**
- Modify: `backend/src/app/rag/ingest.py`
- Modify: `backend/tests/test_rag_ingest.py`

**Interfaces:**
- Consumes: `app.rag.qdrant_client.QdrantRAGClient` (Task 4), `app.rag.embeddings.TextEmbedder`, `app.db.models.RagCollection`/`RagDocument`, `app.rag.registry.create_document` (Task 6).
- Produces: `ingest_bytes(qdrant, embedder, collection, uploads_dir, filename, content, domain, session, origin) -> RagDocument`; `ingest_file(qdrant, embedder, collection, uploads_dir, path, domain, session, origin) -> RagDocument`; `ingest_directory(qdrant, embedder, collection, uploads_dir, directory, session, origin="batch_script") -> list[RagDocument]`; `reingest_document(qdrant, embedder, source_document, target_collection, session) -> RagDocument` (levanta `ValueError` se `source_document.storage_path is None`).

- [ ] **Step 1: Substituir todo o conteúdo de `backend/tests/test_rag_ingest.py`**

```python
from pathlib import Path

from app.rag.ingest import ingest_bytes, ingest_directory, ingest_file, reingest_document
from tests.conftest import _FakeQdrantRAGClient
from tests.test_rag_pdf_extract import _build_minimal_pdf


async def test_ingest_file_le_txt_faz_chunking_e_grava_com_domain_informado(
    tmp_path: Path, db_session, active_collection
):
    arquivo = tmp_path / "catalogo.txt"
    arquivo.write_text("Conteúdo de exemplo sobre o catálogo de produtos.", encoding="utf-8")
    client = _FakeQdrantRAGClient()
    uploads_dir = tmp_path / "uploads"

    documento = await ingest_file(
        client, active_collection.embedding_model, active_collection, uploads_dir, arquivo,
        domain="vendas", session=db_session, origin="upload",
    )

    assert documento.filename == "catalogo.txt"
    assert documento.domain == "vendas"
    assert documento.chunk_count == 1
    assert documento.collection_id == active_collection.id
    assert documento.storage_path is not None
    assert Path(documento.storage_path).read_bytes() == arquivo.read_bytes()
    assert documento.origin == "upload"
    collection_name, chunks, source, domain, document_id = client.upserts[0]
    assert collection_name == active_collection.name
    assert source == "catalogo.txt"
    assert domain == "vendas"
    assert document_id == str(documento.id)
    assert "catálogo de produtos" in chunks[0]


async def test_ingest_file_extrai_texto_de_pdf(tmp_path: Path, db_session, active_collection):
    arquivo = tmp_path / "manual.pdf"
    arquivo.write_bytes(_build_minimal_pdf("Texto do manual em PDF"))
    client = _FakeQdrantRAGClient()

    documento = await ingest_file(
        client, active_collection.embedding_model, active_collection, tmp_path / "uploads", arquivo,
        domain="suporte", session=db_session, origin="upload",
    )

    assert documento.chunk_count == 1
    _collection_name, chunks, _source, _domain, _document_id = client.upserts[0]
    assert "Texto do manual em PDF" in chunks[0]


async def test_ingest_directory_infere_domain_do_subdiretorio_e_ignora_extensao_nao_suportada(
    tmp_path: Path, db_session, active_collection
):
    origem = tmp_path / "origem"
    (origem / "vendas").mkdir(parents=True)
    (origem / "vendas" / "catalogo.txt").write_text("catálogo de vendas", encoding="utf-8")
    (origem / "suporte").mkdir()
    (origem / "suporte" / "manual.txt").write_text("manual de suporte técnico", encoding="utf-8")
    (origem / "suporte" / "planilha.csv").write_text("nao,deveria,entrar", encoding="utf-8")
    client = _FakeQdrantRAGClient()

    documentos = await ingest_directory(
        client, active_collection.embedding_model, active_collection, tmp_path / "uploads", origem,
        session=db_session,
    )

    assert len(documentos) == 2
    domains_ingeridos = {documento.domain for documento in documentos}
    assert domains_ingeridos == {"vendas", "suporte"}
    assert all(documento.origin == "batch_script" for documento in documentos)


async def test_ingest_directory_sem_arquivos_suportados_retorna_lista_vazia(
    tmp_path: Path, db_session, active_collection
):
    origem = tmp_path / "origem"
    (origem / "vendas").mkdir(parents=True)
    (origem / "vendas" / "planilha.csv").write_text("nao,suportado", encoding="utf-8")
    client = _FakeQdrantRAGClient()

    documentos = await ingest_directory(
        client, active_collection.embedding_model, active_collection, tmp_path / "uploads", origem,
        session=db_session,
    )

    assert documentos == []
    assert client.upserts == []


async def test_ingest_bytes_le_txt_faz_chunking_e_grava_com_domain_informado(
    tmp_path: Path, db_session, active_collection
):
    client = _FakeQdrantRAGClient()

    documento = await ingest_bytes(
        client, active_collection.embedding_model, active_collection, tmp_path / "uploads",
        "catalogo.txt", "Conteúdo de exemplo sobre o catálogo.".encode(),
        domain="vendas", session=db_session, origin="upload",
    )

    assert documento.chunk_count == 1
    _collection_name, chunks, source, domain, document_id = client.upserts[0]
    assert source == "catalogo.txt"
    assert domain == "vendas"
    assert document_id == str(documento.id)
    assert "catálogo" in chunks[0]


async def test_ingest_bytes_extrai_texto_de_pdf(tmp_path: Path, db_session, active_collection):
    client = _FakeQdrantRAGClient()

    documento = await ingest_bytes(
        client, active_collection.embedding_model, active_collection, tmp_path / "uploads",
        "manual.pdf", _build_minimal_pdf("Texto do manual em PDF"),
        domain="suporte", session=db_session, origin="upload",
    )

    assert documento.chunk_count == 1
    _collection_name, chunks, _source, _domain, _document_id = client.upserts[0]
    assert "Texto do manual em PDF" in chunks[0]


async def test_reingest_document_le_arquivo_salvo_e_grava_na_collection_destino(
    tmp_path: Path, db_session, active_collection
):
    from app.rag.collections_registry import create_collection

    client = _FakeQdrantRAGClient()
    original = await ingest_bytes(
        client, active_collection.embedding_model, active_collection, tmp_path / "uploads",
        "catalogo.txt", "Conteúdo original.".encode(),
        domain="vendas", session=db_session, origin="upload",
    )
    destino = await create_collection(
        db_session,
        name="destino",
        embedding_model="outro-modelo",
        vector_dimension=768,
        distance_metric="cosine",
        chunk_size=400,
        chunk_overlap=50,
        hnsw_m=16,
        hnsw_ef_construct=100,
        hnsw_full_scan_threshold=10000,
        hnsw_max_indexing_threads=0,
        hnsw_on_disk=False,
        hnsw_payload_m=None,
        quantization_type="none",
        quantization_config={},
        payload_indexes=[],
    )

    reingerido = await reingest_document(client, "outro-modelo", original, destino, session=db_session)

    assert reingerido.id != original.id
    assert reingerido.collection_id == destino.id
    assert reingerido.filename == "catalogo.txt"
    assert reingerido.origin == "reingest"
    assert reingerido.storage_path == original.storage_path
    collection_name, _chunks, _source, _domain, _document_id = client.upserts[-1]
    assert collection_name == "destino"


async def test_reingest_document_sem_storage_path_levanta_value_error(db_session, active_collection):
    import uuid

    from app.rag.registry import create_document

    documento_antigo = await create_document(
        db_session,
        document_id=str(uuid.uuid4()),
        collection_id=active_collection.id,
        filename="antigo.txt",
        domain="vendas",
        chunk_count=1,
        storage_path=None,
        origin="upload",
    )
    client = _FakeQdrantRAGClient()

    try:
        await reingest_document(client, "modelo", documento_antigo, active_collection, session=db_session)
        assert False, "deveria ter levantado ValueError"
    except ValueError:
        pass
```

- [ ] **Step 2: Rodar para ver a falha**

Run: `cd backend && .venv/bin/pytest tests/test_rag_ingest.py -v`
Expected: FAIL — assinaturas antigas de `ingest_bytes`/`ingest_file`/`ingest_directory`, `reingest_document` não existe.

- [ ] **Step 3: Substituir todo o conteúdo de `backend/src/app/rag/ingest.py`**

```python
"""Pipeline de ingestão de PDFs/textos no RAG (R4) — por collection, com
reingestão em outra collection (Entregas B+C+D, além do MVP).

Toda ingestão cria um registro em `app.rag.registry`, amarrado aos pontos do
Qdrant pelo `document_id` gerado aqui, e salva o arquivo original em disco
(`uploads_dir`) para permitir reingestão futura em outra collection (ver
docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §3, §5).

# MVP: pipeline pensado para rodar sob demanda via script ou endpoint HTTP,
# não como serviço/observador de diretório — sem deduplicação nem
# re-ingestão incremental automática (reingerir a mesma fonte cria um
# registro novo e pontos duplicados no Qdrant).
Ordem de escrita: upsert no Qdrant primeiro, registro no Postgres depois —
se a escrita no Postgres falhar depois do upsert ter tido sucesso, sobra um
ponto órfão no Qdrant sem registro; isso é logado como aviso, sem tentativa
de rollback cross-store.
"""

import logging
import uuid
from pathlib import Path
from typing import get_args

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RagCollection, RagDocument
from app.models.rag import RagDomain
from app.rag.chunking import chunk_text
from app.rag.embeddings import TextEmbedder
from app.rag.pdf_extract import extract_text_from_pdf
from app.rag.qdrant_client import QdrantRAGClient
from app.rag.registry import create_document

logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}
_VALID_DOMAINS = set(get_args(RagDomain))


def _extract_text(filename: str, content: bytes) -> str:
    if Path(filename).suffix.lower() == ".pdf":
        return extract_text_from_pdf(content)
    return content.decode("utf-8")


async def ingest_bytes(
    qdrant: QdrantRAGClient,
    embedder: TextEmbedder,
    collection: RagCollection,
    uploads_dir: Path,
    filename: str,
    content: bytes,
    domain: str,
    session: AsyncSession,
    origin: str,
) -> RagDocument:
    """Extrai texto, faz chunking com os parâmetros de `collection`, grava
    no Qdrant, salva o arquivo original em `uploads_dir` e cria o registro
    do documento."""
    text = _extract_text(filename, content)
    chunks = chunk_text(text, chunk_size=collection.chunk_size, overlap=collection.chunk_overlap)
    document_id = str(uuid.uuid4())
    chunk_count = await qdrant.upsert_chunks(
        collection.name, embedder, chunks, source=filename, domain=domain, document_id=document_id
    )

    uploads_dir.mkdir(parents=True, exist_ok=True)
    storage_path = uploads_dir / f"{document_id}_{filename}"
    storage_path.write_bytes(content)

    logger.info(
        "rag_ingest arquivo=%s domain=%s chunks=%d document_id=%s collection=%s",
        filename,
        domain,
        chunk_count,
        document_id,
        collection.name,
    )
    try:
        return await create_document(
            session,
            document_id=document_id,
            collection_id=collection.id,
            filename=filename,
            domain=domain,
            chunk_count=chunk_count,
            storage_path=str(storage_path),
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
    qdrant: QdrantRAGClient,
    embedder: TextEmbedder,
    collection: RagCollection,
    uploads_dir: Path,
    path: Path,
    domain: str,
    session: AsyncSession,
    origin: str,
) -> RagDocument:
    """Mesma lógica de `ingest_bytes`, a partir de um arquivo em disco."""
    return await ingest_bytes(
        qdrant, embedder, collection, uploads_dir, path.name, path.read_bytes(), domain, session, origin
    )


async def ingest_directory(
    qdrant: QdrantRAGClient,
    embedder: TextEmbedder,
    collection: RagCollection,
    uploads_dir: Path,
    directory: Path,
    session: AsyncSession,
    origin: str = "batch_script",
) -> list[RagDocument]:
    """Ingere todos os arquivos suportados (.txt/.md/.pdf) de `directory` na
    `collection` informada.

    # MVP: domínio inferido do nome do subdiretório imediato de cada arquivo
    # (ex.: `sample_docs/vendas/catalogo.txt` -> domain="vendas"). Arquivos
    # em subdiretórios cujo nome não é um domínio válido são ignorados (com
    # aviso no log).
    """
    documentos = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        domain = path.parent.name
        if domain not in _VALID_DOMAINS:
            logger.warning(
                "rag_ingest_domain_invalido arquivo=%s domain=%s — ignorado, domínios válidos: %s",
                path,
                domain,
                sorted(_VALID_DOMAINS),
            )
            continue
        documentos.append(
            await ingest_file(qdrant, embedder, collection, uploads_dir, path, domain, session, origin)
        )
    return documentos


async def reingest_document(
    qdrant: QdrantRAGClient,
    embedder: TextEmbedder,
    source_document: RagDocument,
    target_collection: RagCollection,
    session: AsyncSession,
) -> RagDocument:
    """Reingere o arquivo original de `source_document` (lido de
    `storage_path`) na `target_collection`, com os parâmetros de chunking e
    o embedder dessa collection destino. Cria um documento **novo** — não
    move nem apaga o original.
    """
    if source_document.storage_path is None:
        raise ValueError(
            f"documento {source_document.id} não tem arquivo salvo, não é possível reingerir "
            "(ingerido antes desta funcionalidade existir)"
        )
    content = Path(source_document.storage_path).read_bytes()
    text = _extract_text(source_document.filename, content)
    chunks = chunk_text(
        text, chunk_size=target_collection.chunk_size, overlap=target_collection.chunk_overlap
    )
    document_id = str(uuid.uuid4())
    chunk_count = await qdrant.upsert_chunks(
        target_collection.name,
        embedder,
        chunks,
        source=source_document.filename,
        domain=source_document.domain,
        document_id=document_id,
    )
    return await create_document(
        session,
        document_id=document_id,
        collection_id=target_collection.id,
        filename=source_document.filename,
        domain=source_document.domain,
        chunk_count=chunk_count,
        storage_path=source_document.storage_path,
        origin="reingest",
    )
```

- [ ] **Step 4: Rodar de novo**

Run: `cd backend && .venv/bin/pytest tests/test_rag_ingest.py -v`
Expected: PASS (todos)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/rag/ingest.py backend/tests/test_rag_ingest.py
git commit -m "feat(rag): ingestão por collection, salva arquivo original e permite reingestão"
```

---

### Task 8: Reescrever `app/models/rag.py` — schemas de documentos, collections e playground

**Files:**
- Modify: `backend/src/app/models/rag.py`

**Interfaces:**
- Produces: `RagDomain`, `DocumentIngestResponse`, `DocumentRegistryResponse` (sem `embedding_model`/`chunk_size`/`chunk_overlap`; ganha `collection_id`/`collection_name`; `origin` aceita `"reingest"`), `ReingestRequest`, `HnswConfigRequest`, `ScalarQuantizationRequest`, `ProductQuantizationRequest`, `BinaryQuantizationRequest`, `QuantizationRequest`, `TextIndexParamsRequest`, `PayloadIndexRequest`, `CollectionCreateRequest`, `CollectionResponse`, `PlaygroundSearchRequest`, `PlaygroundDocumentResult`, `PlaygroundResultItem`, `PlaygroundSearchResponse`.

Este módulo é só definição de schemas Pydantic (sem lógica própria testável isoladamente além da validação de `chunk_size > chunk_overlap`, coberta no Step 3 abaixo) — não há passo de "escrever teste primeiro" aqui; a cobertura vem dos testes de API das Tasks 10-12, que exercitam esses schemas através dos endpoints reais.

- [ ] **Step 1: Substituir todo o conteúdo de `backend/src/app/models/rag.py`**

```python
"""Schemas Pydantic dos endpoints do RAG (R4, além do MVP): documentos,
collections e playground de busca comparativo.

Contrato de documentos espelhado em `docs/FRONTEND.md` §4
(`POST /api/rag/documents`). Contrato de collections/playground em
docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §6.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

# MVP: só os três domínios com RAG de texto (o mesmo conjunto usado por
# `app.rag.qdrant_client` para filtrar busca) — "agendamento" e "fora_escopo"
# não têm collection própria (ver `app.router.classifier.Domain`).
RagDomain = Literal["vendas", "suporte", "atendimento"]

DistanceMetric = Literal["cosine", "euclid", "dot", "manhattan"]
QuantizationType = Literal["none", "scalar", "product", "binary"]
PayloadSchemaTypeLiteral = Literal[
    "keyword", "integer", "float", "bool", "geo", "datetime", "uuid", "text"
]


class DocumentIngestResponse(BaseModel):
    """Resposta de `POST /api/rag/documents`."""

    filename: str = Field(..., description="Nome do arquivo enviado.")
    domain: RagDomain = Field(..., description="Domínio informado no upload.")
    chunks: int = Field(..., description="Número de chunks gravados no Qdrant.")


class DocumentRegistryResponse(BaseModel):
    """Um item de `GET /api/rag/documents`."""

    id: UUID
    filename: str
    domain: RagDomain
    chunk_count: int
    collection_id: UUID
    collection_name: str
    origin: Literal["upload", "batch_script", "reingest"]
    created_at: datetime


class ReingestRequest(BaseModel):
    """Corpo de `POST /api/rag/documents/{document_id}/reingest`."""

    target_collection_id: UUID


class HnswConfigRequest(BaseModel):
    m: int = 16
    ef_construct: int = 100
    full_scan_threshold: int = 10000
    max_indexing_threads: int = 0
    on_disk: bool = False
    payload_m: int | None = None


class ScalarQuantizationRequest(BaseModel):
    quantile: float = 0.99
    always_ram: bool = False


class ProductQuantizationRequest(BaseModel):
    compression: Literal["x4", "x8", "x16", "x32", "x64"] = "x16"
    always_ram: bool = False


class BinaryQuantizationRequest(BaseModel):
    always_ram: bool = False


class QuantizationRequest(BaseModel):
    type: QuantizationType = "none"
    scalar: ScalarQuantizationRequest | None = None
    product: ProductQuantizationRequest | None = None
    binary: BinaryQuantizationRequest | None = None


class TextIndexParamsRequest(BaseModel):
    tokenizer: Literal["prefix", "whitespace", "word", "multilingual"] = "word"
    min_token_len: int | None = None
    max_token_len: int | None = None
    lowercase: bool = True


class PayloadIndexRequest(BaseModel):
    field: str = Field(..., min_length=1)
    schema_type: PayloadSchemaTypeLiteral
    text_params: TextIndexParamsRequest | None = None


class CollectionCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    embedding_model: str = Field(..., min_length=1)
    distance_metric: DistanceMetric = "cosine"
    chunk_size: int = 800
    chunk_overlap: int = 100
    hnsw: HnswConfigRequest = Field(default_factory=HnswConfigRequest)
    quantization: QuantizationRequest = Field(default_factory=QuantizationRequest)
    payload_indexes: list[PayloadIndexRequest] = Field(default_factory=list)

    @model_validator(mode="after")
    def _valida_chunking(self) -> "CollectionCreateRequest":
        if self.chunk_size <= self.chunk_overlap:
            raise ValueError("chunk_size deve ser maior que chunk_overlap")
        return self


class CollectionResponse(BaseModel):
    id: UUID
    name: str
    embedding_model: str
    vector_dimension: int
    distance_metric: DistanceMetric
    chunk_size: int
    chunk_overlap: int
    hnsw_m: int
    hnsw_ef_construct: int
    hnsw_full_scan_threshold: int
    hnsw_max_indexing_threads: int
    hnsw_on_disk: bool
    hnsw_payload_m: int | None
    quantization_type: QuantizationType
    quantization_config: dict
    payload_indexes: list[PayloadIndexRequest]
    is_active: bool
    document_count: int
    created_at: datetime


class PlaygroundSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    domain: RagDomain
    collection_ids: list[UUID] = Field(..., min_length=1)


class PlaygroundDocumentResult(BaseModel):
    content: str
    source: str
    score: float


class PlaygroundResultItem(BaseModel):
    collection_id: UUID
    collection_name: str
    latency_ms: float | None = None
    results: list[PlaygroundDocumentResult] = Field(default_factory=list)
    error: str | None = None


class PlaygroundSearchResponse(BaseModel):
    items: list[PlaygroundResultItem]
```

- [ ] **Step 2: Verificar que o módulo importa limpo**

Run: `cd backend && .venv/bin/python -c "from app.models.rag import CollectionCreateRequest, CollectionResponse, PlaygroundSearchRequest, DocumentRegistryResponse; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/src/app/models/rag.py
git commit -m "feat(rag): schemas Pydantic de collections, reingestão e playground"
```

---

### Task 9: `app/api/rag_dependencies.py` — dependências FastAPI compartilhadas

**Files:**
- Create: `backend/src/app/api/rag_dependencies.py`

**Interfaces:**
- Produces: `get_qdrant_client(request) -> QdrantRAGClient`, `get_embedder_registry(request) -> EmbedderRegistry`, `get_uploads_dir(request) -> Path`, `get_db_session(request) -> AsyncIterator[AsyncSession]` — lidos de `request.app.state.qdrant_client` / `.embedder_registry` / `.rag_uploads_dir` / `.db_sessionmaker` (montados na Task 13).

Este arquivo só extrai leituras de `request.app.state` já usadas hoje em `app/api/rag.py` (`get_db_session`) para um lugar compartilhado entre `app/api/rag.py`, `app/api/rag_collections.py` (Task 11) e `app/api/rag_playground.py` (Task 12) — sem lógica própria para testar isoladamente; a cobertura vem dos testes de endpoint das tasks seguintes, que sobrescrevem essas dependências via `app.dependency_overrides`.

- [ ] **Step 1: Criar `backend/src/app/api/rag_dependencies.py`**

```python
"""Dependências FastAPI compartilhadas entre os módulos de API do RAG
(documentos, collections, playground) — extraídas para não duplicar a mesma
leitura de `app.state` em três arquivos.
"""

from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import QdrantRAGClient


def get_qdrant_client(request: Request) -> QdrantRAGClient:
    return request.app.state.qdrant_client


def get_embedder_registry(request: Request) -> EmbedderRegistry:
    return request.app.state.embedder_registry


def get_uploads_dir(request: Request) -> Path:
    return request.app.state.rag_uploads_dir


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.db_sessionmaker() as session:
        yield session
```

- [ ] **Step 2: Verificar que importa limpo**

Run: `cd backend && .venv/bin/python -c "from app.api.rag_dependencies import get_qdrant_client, get_embedder_registry, get_uploads_dir, get_db_session; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/src/app/api/rag_dependencies.py
git commit -m "refactor(rag): extrai dependências FastAPI compartilhadas do RAG"
```

---

### Task 10: Atualizar `app/api/rag.py` — upload/list/delete por collection + reingestão

**Files:**
- Modify: `backend/src/app/api/rag.py`
- Modify: `backend/tests/test_rag_api.py`

**Interfaces:**
- Consumes: `app.api.rag_dependencies` (Task 9), `app.rag.ingest.ingest_bytes`/`reingest_document` (Task 7), `app.rag.collections_registry.get_collection`/`get_active_collection`/`list_collections` (Task 2), `app.rag.registry.list_documents`/`delete_document` (Task 6), `app.models.rag.*` (Task 8).
- Produces: `POST /api/rag/documents` (ganha campo de formulário opcional `collection_id`), `GET /api/rag/documents` (resposta com `collection_id`/`collection_name`), `DELETE /api/rag/documents/{id}` (remove também o arquivo em disco), `POST /api/rag/documents/{id}/reingest` (novo).

**Nota de comportamento intencional:** `DELETE /api/rag/documents/{id}` passa a checar o registro no Postgres **antes** de chamar o Qdrant (precisa saber a qual collection o documento pertence para excluir os pontos certos) — diferente da versão anterior, que chamava o Qdrant primeiro mesmo para um `document_id` inexistente. O teste `test_excluir_documento_inexistente_retorna_404` é reescrito para refletir isso.

- [ ] **Step 1: Substituir todo o conteúdo de `backend/tests/test_rag_api.py`**

```python
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.rag import router as rag_router
from app.api.rag_dependencies import get_db_session, get_embedder_registry, get_qdrant_client, get_uploads_dir
from app.rag.embedders_registry import EmbedderRegistry
from app.router.rag_client import RAGConnectionError
from tests.conftest import _FakeQdrantRAGClient
from tests.test_rag_pdf_extract import _build_minimal_pdf


def _build_app(rag_client, db_session, uploads_dir) -> FastAPI:
    app = FastAPI()
    app.include_router(rag_router)
    app.dependency_overrides[get_qdrant_client] = lambda: rag_client
    app.dependency_overrides[get_embedder_registry] = lambda: EmbedderRegistry()
    app.dependency_overrides[get_uploads_dir] = lambda: uploads_dir
    app.dependency_overrides[get_db_session] = lambda: db_session
    return app


def test_upload_documento_txt_ingere_e_retorna_numero_de_chunks(db_session, active_collection, tmp_path):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", b"Conteudo de exemplo sobre o catalogo.", "text/plain")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {"filename": "catalogo.txt", "domain": "vendas", "chunks": 1}
    collection_name, _chunks, source, domain, _document_id = fake.upserts[0]
    assert collection_name == active_collection.name
    assert (source, domain) == ("catalogo.txt", "vendas")


def test_upload_com_collection_id_explicito_usa_essa_collection(db_session, active_collection, tmp_path):
    import asyncio

    from app.rag.collections_registry import create_collection

    outra = asyncio.run(
        create_collection(
            db_session,
            name="outra",
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
        )
    )
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "vendas", "collection_id": str(outra.id)},
        files={"file": ("catalogo.txt", b"conteudo", "text/plain")},
    )

    assert response.status_code == 200
    collection_name, *_ = fake.upserts[0]
    assert collection_name == "outra"


def test_upload_com_collection_id_inexistente_retorna_404(db_session, active_collection, tmp_path):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "vendas", "collection_id": "00000000-0000-0000-0000-000000000000"},
        files={"file": ("catalogo.txt", b"conteudo", "text/plain")},
    )

    assert response.status_code == 404


def test_upload_documento_pdf_ingere(db_session, active_collection, tmp_path):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "suporte"},
        files={"file": ("manual.pdf", _build_minimal_pdf("Texto do manual em PDF"), "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["chunks"] == 1


def test_upload_formato_nao_suportado_retorna_400(db_session, active_collection, tmp_path):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("planilha.csv", b"nao,suportado", "text/csv")},
    )

    assert response.status_code == 400
    assert fake.upserts == []


def test_upload_domain_invalido_retorna_422(db_session, active_collection, tmp_path):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "agendamento"},
        files={"file": ("catalogo.txt", b"conteudo", "text/plain")},
    )

    assert response.status_code == 422


def test_upload_com_qdrant_indisponivel_retorna_503(db_session, active_collection, tmp_path):
    fake = _FakeQdrantRAGClient(error=RAGConnectionError("qdrant fora do ar"))
    client = TestClient(_build_app(fake, db_session, tmp_path))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", b"conteudo", "text/plain")},
    )

    assert response.status_code == 503


def test_upload_txt_com_encoding_invalido_retorna_400_em_vez_de_500(db_session, active_collection, tmp_path):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))

    conteudo_invalido = "áéíóú".encode("latin-1")

    response = client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", conteudo_invalido, "text/plain")},
    )

    assert response.status_code == 400
    assert fake.upserts == []


def test_upload_pdf_corrompido_retorna_400_em_vez_de_500(db_session, active_collection, tmp_path):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "suporte"},
        files={"file": ("manual.pdf", b"isto nao e um pdf valido", "application/pdf")},
    )

    assert response.status_code == 400
    assert fake.upserts == []


def test_listar_documentos_vazio_retorna_lista_vazia(db_session, tmp_path):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))

    response = client.get("/api/rag/documents")

    assert response.status_code == 200
    assert response.json() == []


def test_listar_documentos_apos_upload_retorna_o_documento_com_a_collection(
    db_session, active_collection, tmp_path
):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))
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
    assert body[0]["collection_id"] == str(active_collection.id)
    assert body[0]["collection_name"] == active_collection.name


def test_excluir_documento_existente_remove_do_registro_do_qdrant_e_do_disco(
    db_session, active_collection, tmp_path
):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))
    client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", b"conteudo de exemplo", "text/plain")},
    )
    documento = client.get("/api/rag/documents").json()[0]
    document_id = documento["id"]

    response = client.delete(f"/api/rag/documents/{document_id}")

    assert response.status_code == 204
    assert client.get("/api/rag/documents").json() == []
    assert fake.deleted == [(active_collection.name, document_id)]
    arquivos_restantes = list((tmp_path).rglob("*catalogo.txt"))
    assert arquivos_restantes == []


def test_excluir_documento_inexistente_retorna_404_sem_chamar_qdrant(db_session, tmp_path):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))
    document_id = "00000000-0000-0000-0000-000000000000"

    response = client.delete(f"/api/rag/documents/{document_id}")

    assert response.status_code == 404
    assert fake.deleted == []


def test_reingest_documento_cria_novo_registro_na_collection_destino(db_session, active_collection, tmp_path):
    import asyncio

    from app.rag.collections_registry import create_collection

    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))
    client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", b"conteudo de exemplo", "text/plain")},
    )
    document_id = client.get("/api/rag/documents").json()[0]["id"]
    destino = asyncio.run(
        create_collection(
            db_session,
            name="destino",
            embedding_model="fake-embedding-model",
            vector_dimension=384,
            distance_metric="cosine",
            chunk_size=400,
            chunk_overlap=50,
            hnsw_m=16,
            hnsw_ef_construct=100,
            hnsw_full_scan_threshold=10000,
            hnsw_max_indexing_threads=0,
            hnsw_on_disk=False,
            hnsw_payload_m=None,
            quantization_type="none",
            quantization_config={},
            payload_indexes=[],
        )
    )

    response = client.post(
        f"/api/rag/documents/{document_id}/reingest", json={"target_collection_id": str(destino.id)}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["collection_id"] == str(destino.id)
    assert body["origin"] == "reingest"
    assert UUID(body["id"]) != UUID(document_id)


def test_reingest_documento_inexistente_retorna_404(db_session, active_collection, tmp_path):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))

    response = client.post(
        "/api/rag/documents/00000000-0000-0000-0000-000000000000/reingest",
        json={"target_collection_id": str(active_collection.id)},
    )

    assert response.status_code == 404


def test_reingest_para_collection_destino_inexistente_retorna_404(db_session, active_collection, tmp_path):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))
    client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", b"conteudo de exemplo", "text/plain")},
    )
    document_id = client.get("/api/rag/documents").json()[0]["id"]

    response = client.post(
        f"/api/rag/documents/{document_id}/reingest",
        json={"target_collection_id": "00000000-0000-0000-0000-000000000000"},
    )

    assert response.status_code == 404
```

- [ ] **Step 2: Rodar para ver a falha**

Run: `cd backend && .venv/bin/pytest tests/test_rag_api.py -v`
Expected: FAIL — endpoint ainda não aceita `collection_id`, não expõe `/reingest`, `get_qdrant_client`/`get_embedder_registry`/`get_uploads_dir` ainda não existem em `app.api.rag`.

- [ ] **Step 3: Substituir todo o conteúdo de `backend/src/app/api/rag.py`**

```python
"""Endpoints HTTP de documentos do RAG (R4, além do MVP): upload, listagem,
exclusão e reingestão em outra collection.

# MVP: sem autenticação (rotas não listadas na navegação pública do
# frontend, mas não protegidas por login). `upload_document` complementa,
# sem substituir, o script de ingestão em lote
# (`backend/scripts/ingest_sample_docs.py`). Mesma limitação de
# `app.rag.qdrant_client.upsert_chunks`: sem deduplicação/reingestão
# incremental automática. Decisão registrada em `docs/ARCHITECTURE.md` §5.
"""

import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pypdf.errors import PyPdfError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rag_dependencies import get_db_session, get_embedder_registry, get_qdrant_client, get_uploads_dir
from app.db.models import RagDocument
from app.models.rag import DocumentIngestResponse, DocumentRegistryResponse, RagDomain, ReingestRequest
from app.rag.collections_registry import get_active_collection, get_collection, list_collections
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.ingest import SUPPORTED_SUFFIXES, ingest_bytes, reingest_document
from app.rag.qdrant_client import QdrantRAGClient
from app.rag.registry import delete_document, list_documents
from app.router.rag_client import RAGConnectionError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag", tags=["rag"])


def _document_to_response(document: RagDocument, collection_name: str) -> DocumentRegistryResponse:
    return DocumentRegistryResponse(
        id=document.id,
        filename=document.filename,
        domain=document.domain,
        chunk_count=document.chunk_count,
        collection_id=document.collection_id,
        collection_name=collection_name,
        origin=document.origin,
        created_at=document.created_at,
    )


@router.post("/documents", response_model=DocumentIngestResponse)
async def upload_document(
    domain: RagDomain = Form(...),
    file: UploadFile = File(...),
    collection_id: UUID | None = Form(None),
    qdrant: QdrantRAGClient = Depends(get_qdrant_client),
    embedders: EmbedderRegistry = Depends(get_embedder_registry),
    uploads_dir: Path = Depends(get_uploads_dir),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentIngestResponse:
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Formato não suportado: '{suffix or filename}'. Use um destes: {sorted(SUPPORTED_SUFFIXES)}.",
        )

    if collection_id is not None:
        collection = await get_collection(session, collection_id)
        if collection is None:
            raise HTTPException(status_code=404, detail="Collection não encontrada.")
    else:
        collection = await get_active_collection(session)
        if collection is None:
            raise HTTPException(status_code=503, detail="Nenhuma collection ativa configurada.")

    embedder = embedders.get(collection.embedding_model)
    content = await file.read()
    try:
        documento = await ingest_bytes(
            qdrant, embedder, collection, uploads_dir, filename, content, domain,
            session=session, origin="upload",
        )
    except RAGConnectionError as exc:
        logger.error("rag_upload_indisponivel", extra={"rag": {"event": "rag_upload_indisponivel", "erro": str(exc)}})
        raise HTTPException(
            status_code=503, detail="Serviço de RAG temporariamente indisponível, tente novamente."
        ) from exc
    except (UnicodeDecodeError, PyPdfError) as exc:
        raise HTTPException(
            status_code=400, detail=f"Não foi possível extrair texto de '{filename}': {exc}"
        ) from exc
    except SQLAlchemyError as exc:
        logger.error(
            "rag_registro_indisponivel", extra={"rag": {"event": "rag_registro_indisponivel", "erro": str(exc)}}
        )
        raise HTTPException(
            status_code=503,
            detail="Serviço de registro de documentos temporariamente indisponível, tente novamente.",
        ) from exc

    return DocumentIngestResponse(filename=filename, domain=domain, chunks=documento.chunk_count)


@router.get("/documents", response_model=list[DocumentRegistryResponse])
async def get_documents(session: AsyncSession = Depends(get_db_session)) -> list[DocumentRegistryResponse]:
    try:
        documentos = await list_documents(session)
        collections = await list_collections(session)
    except SQLAlchemyError as exc:
        logger.error(
            "rag_registro_indisponivel", extra={"rag": {"event": "rag_registro_indisponivel", "erro": str(exc)}}
        )
        raise HTTPException(
            status_code=503,
            detail="Serviço de registro de documentos temporariamente indisponível, tente novamente.",
        ) from exc
    nomes = {collection.id: collection.name for collection in collections}
    return [_document_to_response(documento, nomes.get(documento.collection_id, "?")) for documento in documentos]


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document_endpoint(
    document_id: UUID,
    qdrant: QdrantRAGClient = Depends(get_qdrant_client),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    document = await session.get(RagDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")

    collection = await get_collection(session, document.collection_id)
    if collection is not None:
        try:
            await qdrant.delete_by_document_id(collection.name, str(document_id))
        except RAGConnectionError as exc:
            logger.error("rag_delete_indisponivel", extra={"rag": {"event": "rag_delete_indisponivel", "erro": str(exc)}})
            raise HTTPException(
                status_code=503, detail="Serviço de RAG temporariamente indisponível, tente novamente."
            ) from exc

    if document.storage_path is not None:
        Path(document.storage_path).unlink(missing_ok=True)

    try:
        await delete_document(session, str(document_id))
    except SQLAlchemyError as exc:
        logger.error(
            "rag_registro_indisponivel", extra={"rag": {"event": "rag_registro_indisponivel", "erro": str(exc)}}
        )
        raise HTTPException(
            status_code=503,
            detail="Serviço de registro de documentos temporariamente indisponível, tente novamente.",
        ) from exc


@router.post("/documents/{document_id}/reingest", response_model=DocumentRegistryResponse)
async def reingest_document_endpoint(
    document_id: UUID,
    body: ReingestRequest,
    qdrant: QdrantRAGClient = Depends(get_qdrant_client),
    embedders: EmbedderRegistry = Depends(get_embedder_registry),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentRegistryResponse:
    source_document = await session.get(RagDocument, document_id)
    if source_document is None:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")

    target_collection = await get_collection(session, body.target_collection_id)
    if target_collection is None:
        raise HTTPException(status_code=404, detail="Collection destino não encontrada.")

    if source_document.storage_path is None:
        raise HTTPException(
            status_code=409,
            detail="Documento sem arquivo salvo (ingerido antes desta funcionalidade existir) — não é possível reingerir.",
        )

    embedder = embedders.get(target_collection.embedding_model)
    try:
        novo_documento = await reingest_document(qdrant, embedder, source_document, target_collection, session)
    except RAGConnectionError as exc:
        raise HTTPException(
            status_code=503, detail="Serviço de RAG temporariamente indisponível, tente novamente."
        ) from exc

    return _document_to_response(novo_documento, target_collection.name)
```

- [ ] **Step 4: Rodar de novo**

Run: `cd backend && .venv/bin/pytest tests/test_rag_api.py -v`
Expected: PASS (todos)

- [ ] **Step 5: Rodar a suíte inteira do RAG para ver o estado geral até aqui**

Run: `cd backend && .venv/bin/pytest tests/ -v -m "not qdrant and not gpu"`
Expected: PASS em tudo (as próximas tasks ainda não têm testes escritos, então nada além do já coberto deve aparecer)

- [ ] **Step 6: Commit**

```bash
git add backend/src/app/api/rag.py backend/tests/test_rag_api.py
git commit -m "feat(rag): upload/listagem/exclusão por collection + endpoint de reingestão"
```

---

### Task 11: `app/api/rag_collections.py` — endpoints de collections

**Files:**
- Create: `backend/src/app/api/rag_collections.py`
- Create: `backend/tests/test_rag_collections_api.py`

**Interfaces:**
- Consumes: `app.api.rag_dependencies` (Task 9), `app.models.rag.CollectionCreateRequest`/`CollectionResponse` (Task 8), `app.rag.collections_registry.*` (Task 2), `app.rag.registry.count_documents_by_collection`/`list_documents_by_collection` (Task 6), `app.rag.qdrant_client.QdrantRAGClient`/`CollectionAlreadyExistsError` (Task 4).
- Produces: `POST /api/rag/collections`, `GET /api/rag/collections`, `POST /api/rag/collections/{id}/activate`, `DELETE /api/rag/collections/{id}` (cascata).

- [ ] **Step 1: Escrever `backend/tests/test_rag_collections_api.py`**

Usa o `QdrantRAGClient` real em memória (mesmo padrão da Task 4), não o `_FakeQdrantRAGClient` — este endpoint chama `qdrant.create_collection(...)`, que o fake (pensado só para `upsert_chunks`/`delete_by_document_id`/`drop_collection` nos testes de documentos) não implementa. Todas as funções de teste que populam estado via funções assíncronas (`create_document`, `create_collection` do registry) são `async def`, seguindo o mesmo padrão já usado em `test_rag_api.py`/`test_rag_collections_registry.py`.

```python
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from qdrant_client import AsyncQdrantClient

from app.api.rag_collections import router as rag_collections_router
from app.api.rag_dependencies import get_db_session, get_embedder_registry, get_qdrant_client
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import QdrantRAGClient

_DEFAULT_HNSW = dict(
    hnsw_m=16,
    hnsw_ef_construct=100,
    hnsw_full_scan_threshold=10000,
    hnsw_max_indexing_threads=0,
    hnsw_on_disk=False,
    hnsw_payload_m=None,
)


class _FakeEmbedderRegistry(EmbedderRegistry):
    """Sobrepõe `get` para devolver um embedder falso com dimensão fixa,
    sem baixar/carregar `sentence-transformers` de verdade nos testes de
    endpoint (isso já é coberto pelos testes reais de `embeddings.py`)."""

    def get(self, model_name: str):
        class _FakeEmbedder:
            async def get_dimension(self) -> int:
                return 384

        return _FakeEmbedder()


def _qdrant() -> QdrantRAGClient:
    return QdrantRAGClient(host="unused", port=0, client=AsyncQdrantClient(location=":memory:"))


def _build_app(qdrant: QdrantRAGClient, db_session) -> FastAPI:
    app = FastAPI()
    app.include_router(rag_collections_router)
    app.dependency_overrides[get_qdrant_client] = lambda: qdrant
    app.dependency_overrides[get_embedder_registry] = lambda: _FakeEmbedderRegistry()
    app.dependency_overrides[get_db_session] = lambda: db_session
    return app


_PAYLOAD_MINIMO = {
    "name": "nova_collection",
    "embedding_model": "fake-embedding-model",
    "distance_metric": "cosine",
    "chunk_size": 800,
    "chunk_overlap": 100,
    "hnsw": {"m": 16, "ef_construct": 100, "full_scan_threshold": 10000, "max_indexing_threads": 0, "on_disk": False, "payload_m": None},
    "quantization": {"type": "none"},
    "payload_indexes": [{"field": "domain", "schema_type": "keyword"}],
}


def test_criar_collection_grava_no_qdrant_e_no_registro(db_session):
    client = TestClient(_build_app(_qdrant(), db_session))

    response = client.post("/api/rag/collections", json=_PAYLOAD_MINIMO)

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "nova_collection"
    assert body["vector_dimension"] == 384
    assert body["is_active"] is False
    assert body["document_count"] == 0


async def test_criar_collection_com_nome_duplicado_retorna_409(db_session, active_collection):
    qdrant = _qdrant()
    await qdrant.create_collection(
        name=active_collection.name,
        vector_dimension=384,
        distance_metric="cosine",
        quantization_type="none",
        quantization_config={},
        payload_indexes=[],
        **_DEFAULT_HNSW,
    )
    client = TestClient(_build_app(qdrant, db_session))
    payload = {**_PAYLOAD_MINIMO, "name": active_collection.name}

    response = client.post("/api/rag/collections", json=payload)

    assert response.status_code == 409


def test_criar_collection_com_chunk_size_menor_que_overlap_retorna_422(db_session):
    client = TestClient(_build_app(_qdrant(), db_session))
    payload = {**_PAYLOAD_MINIMO, "chunk_size": 100, "chunk_overlap": 200}

    response = client.post("/api/rag/collections", json=payload)

    assert response.status_code == 422


async def test_listar_collections_inclui_contagem_de_documentos(db_session, active_collection):
    from app.rag.registry import create_document

    await create_document(
        db_session,
        document_id=str(uuid.uuid4()),
        collection_id=active_collection.id,
        filename="a.txt",
        domain="vendas",
        chunk_count=1,
        storage_path=None,
        origin="upload",
    )
    client = TestClient(_build_app(_qdrant(), db_session))

    response = client.get("/api/rag/collections")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["document_count"] == 1
    assert body[0]["is_active"] is True


async def test_ativar_collection_troca_qual_esta_ativa(db_session, active_collection):
    from app.rag.collections_registry import create_collection

    outra = await create_collection(
        db_session,
        name="outra",
        embedding_model="fake-embedding-model",
        vector_dimension=384,
        distance_metric="cosine",
        chunk_size=800,
        chunk_overlap=100,
        quantization_type="none",
        quantization_config={},
        payload_indexes=[],
        **_DEFAULT_HNSW,
    )
    client = TestClient(_build_app(_qdrant(), db_session))

    response = client.post(f"/api/rag/collections/{outra.id}/activate")

    assert response.status_code == 204
    body = client.get("/api/rag/collections").json()
    ativa = next(c for c in body if c["id"] == str(outra.id))
    assert ativa["is_active"] is True


def test_ativar_collection_inexistente_retorna_404(db_session):
    client = TestClient(_build_app(_qdrant(), db_session))

    response = client.post("/api/rag/collections/00000000-0000-0000-0000-000000000000/activate")

    assert response.status_code == 404


async def test_excluir_collection_ativa_retorna_409_sem_tocar_qdrant(db_session, active_collection):
    qdrant = _qdrant()
    await qdrant.create_collection(
        name=active_collection.name,
        vector_dimension=384,
        distance_metric="cosine",
        quantization_type="none",
        quantization_config={},
        payload_indexes=[],
        **_DEFAULT_HNSW,
    )
    client = TestClient(_build_app(qdrant, db_session))

    response = client.delete(f"/api/rag/collections/{active_collection.id}")

    assert response.status_code == 409
    assert await qdrant.collection_exists(active_collection.name) is True


async def test_excluir_collection_inativa_remove_em_cascata(db_session, active_collection):
    from app.rag.collections_registry import create_collection
    from app.rag.registry import create_document

    inativa = await create_collection(
        db_session,
        name="para_excluir",
        embedding_model="fake-embedding-model",
        vector_dimension=384,
        distance_metric="cosine",
        chunk_size=800,
        chunk_overlap=100,
        quantization_type="none",
        quantization_config={},
        payload_indexes=[],
        **_DEFAULT_HNSW,
    )
    await create_document(
        db_session,
        document_id=str(uuid.uuid4()),
        collection_id=inativa.id,
        filename="a.txt",
        domain="vendas",
        chunk_count=1,
        storage_path=None,
        origin="upload",
    )
    qdrant = _qdrant()
    await qdrant.create_collection(
        name="para_excluir",
        vector_dimension=384,
        distance_metric="cosine",
        quantization_type="none",
        quantization_config={},
        payload_indexes=[],
        **_DEFAULT_HNSW,
    )
    client = TestClient(_build_app(qdrant, db_session))

    response = client.delete(f"/api/rag/collections/{inativa.id}")

    assert response.status_code == 204
    assert await qdrant.collection_exists("para_excluir") is False
    body = client.get("/api/rag/collections").json()
    assert [c["id"] for c in body] == [str(active_collection.id)]


def test_excluir_collection_inexistente_retorna_404(db_session):
    client = TestClient(_build_app(_qdrant(), db_session))

    response = client.delete("/api/rag/collections/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
```

- [ ] **Step 2: Rodar para ver a falha**

Run: `cd backend && .venv/bin/pytest tests/test_rag_collections_api.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.api.rag_collections'`

- [ ] **Step 3: Implementar `backend/src/app/api/rag_collections.py`**

```python
"""Endpoints HTTP de perfis de collection do RAG (Entregas B+C+D, além do
MVP): criação, listagem, ativação e exclusão em cascata.

Ver docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §6.1.
"""

import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rag_dependencies import get_db_session, get_embedder_registry, get_qdrant_client
from app.models.rag import CollectionCreateRequest, CollectionResponse
from app.rag.collections_registry import (
    CollectionActiveError,
    activate_collection,
    create_collection,
    delete_collection,
    list_collections,
)
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import CollectionAlreadyExistsError, QdrantRAGClient
from app.rag.registry import count_documents_by_collection, list_documents_by_collection
from app.router.rag_client import RAGConnectionError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag/collections", tags=["rag-collections"])


def _quantization_config_dict(quantization) -> dict:
    if quantization.type == "scalar" and quantization.scalar is not None:
        return quantization.scalar.model_dump()
    if quantization.type == "product" and quantization.product is not None:
        return quantization.product.model_dump()
    if quantization.type == "binary" and quantization.binary is not None:
        return quantization.binary.model_dump()
    return {}


def _to_response(collection, document_count: int) -> CollectionResponse:
    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        embedding_model=collection.embedding_model,
        vector_dimension=collection.vector_dimension,
        distance_metric=collection.distance_metric,
        chunk_size=collection.chunk_size,
        chunk_overlap=collection.chunk_overlap,
        hnsw_m=collection.hnsw_m,
        hnsw_ef_construct=collection.hnsw_ef_construct,
        hnsw_full_scan_threshold=collection.hnsw_full_scan_threshold,
        hnsw_max_indexing_threads=collection.hnsw_max_indexing_threads,
        hnsw_on_disk=collection.hnsw_on_disk,
        hnsw_payload_m=collection.hnsw_payload_m,
        quantization_type=collection.quantization_type,
        quantization_config=collection.quantization_config,
        payload_indexes=collection.payload_indexes,
        is_active=collection.is_active,
        document_count=document_count,
        created_at=collection.created_at,
    )


@router.post("", response_model=CollectionResponse)
async def create_collection_endpoint(
    body: CollectionCreateRequest,
    qdrant: QdrantRAGClient = Depends(get_qdrant_client),
    embedders: EmbedderRegistry = Depends(get_embedder_registry),
    session: AsyncSession = Depends(get_db_session),
) -> CollectionResponse:
    embedder = embedders.get(body.embedding_model)
    try:
        dimension = await embedder.get_dimension()
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"Não foi possível carregar o modelo de embedding: {exc}"
        ) from exc

    payload_indexes = [item.model_dump() for item in body.payload_indexes]
    quantization_config = _quantization_config_dict(body.quantization)

    try:
        await qdrant.create_collection(
            name=body.name,
            vector_dimension=dimension,
            distance_metric=body.distance_metric,
            hnsw_m=body.hnsw.m,
            hnsw_ef_construct=body.hnsw.ef_construct,
            hnsw_full_scan_threshold=body.hnsw.full_scan_threshold,
            hnsw_max_indexing_threads=body.hnsw.max_indexing_threads,
            hnsw_on_disk=body.hnsw.on_disk,
            hnsw_payload_m=body.hnsw.payload_m,
            quantization_type=body.quantization.type,
            quantization_config=quantization_config,
            payload_indexes=payload_indexes,
        )
    except CollectionAlreadyExistsError as exc:
        raise HTTPException(
            status_code=409, detail=f"Já existe uma collection chamada '{body.name}'."
        ) from exc
    except RAGConnectionError as exc:
        raise HTTPException(
            status_code=503, detail="Serviço de RAG temporariamente indisponível, tente novamente."
        ) from exc

    try:
        collection = await create_collection(
            session,
            name=body.name,
            embedding_model=body.embedding_model,
            vector_dimension=dimension,
            distance_metric=body.distance_metric,
            chunk_size=body.chunk_size,
            chunk_overlap=body.chunk_overlap,
            hnsw_m=body.hnsw.m,
            hnsw_ef_construct=body.hnsw.ef_construct,
            hnsw_full_scan_threshold=body.hnsw.full_scan_threshold,
            hnsw_max_indexing_threads=body.hnsw.max_indexing_threads,
            hnsw_on_disk=body.hnsw.on_disk,
            hnsw_payload_m=body.hnsw.payload_m,
            quantization_type=body.quantization.type,
            quantization_config=quantization_config,
            payload_indexes=payload_indexes,
        )
    except SQLAlchemyError as exc:
        logger.warning(
            "rag_collection_orfa nome=%s — collection criada no Qdrant sem registro correspondente no Postgres",
            body.name,
        )
        raise HTTPException(
            status_code=503,
            detail="Serviço de registro de collections temporariamente indisponível, tente novamente.",
        ) from exc

    return _to_response(collection, document_count=0)


@router.get("", response_model=list[CollectionResponse])
async def list_collections_endpoint(session: AsyncSession = Depends(get_db_session)) -> list[CollectionResponse]:
    collections = await list_collections(session)
    counts = await count_documents_by_collection(session)
    return [_to_response(collection, counts.get(collection.id, 0)) for collection in collections]


@router.post("/{collection_id}/activate", status_code=204)
async def activate_collection_endpoint(
    collection_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> None:
    ativado = await activate_collection(session, collection_id)
    if not ativado:
        raise HTTPException(status_code=404, detail="Collection não encontrada.")


@router.delete("/{collection_id}", status_code=204)
async def delete_collection_endpoint(
    collection_id: UUID,
    qdrant: QdrantRAGClient = Depends(get_qdrant_client),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    collections = await list_collections(session)
    collection = next((c for c in collections if c.id == collection_id), None)
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection não encontrada.")
    if collection.is_active:
        raise HTTPException(
            status_code=409, detail="Não é possível excluir a collection ativa. Ative outra collection antes."
        )

    documentos = await list_documents_by_collection(session, collection_id)

    try:
        await qdrant.drop_collection(collection.name)
    except RAGConnectionError as exc:
        raise HTTPException(
            status_code=503, detail="Serviço de RAG temporariamente indisponível, tente novamente."
        ) from exc

    for documento in documentos:
        if documento.storage_path is not None:
            Path(documento.storage_path).unlink(missing_ok=True)

    try:
        await delete_collection(session, collection_id)
    except CollectionActiveError as exc:
        raise HTTPException(status_code=409, detail="Não é possível excluir a collection ativa.") from exc
```

- [ ] **Step 4: Registrar o router em `app/main.py` para os testes de endpoint rodarem via `TestClient` isolado (já feito na Task 13; por ora rode os testes deste arquivo isoladamente, que montam sua própria `FastAPI()` sem depender de `app.main`)**

Run: `cd backend && .venv/bin/pytest tests/test_rag_collections_api.py -v`
Expected: PASS (todos — ajuste as três funções apontadas no Step 1 para `async def` se o modo do `pytest-asyncio` exigir, conforme a nota ali)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/api/rag_collections.py backend/tests/test_rag_collections_api.py
git commit -m "feat(rag): endpoints de criação/listagem/ativação/exclusão de collections"
```

---

### Task 12: `app/api/rag_playground.py` — busca comparativa entre collections

**Files:**
- Create: `backend/src/app/api/rag_playground.py`
- Create: `backend/tests/test_rag_playground_api.py`

**Interfaces:**
- Consumes: `app.api.rag_dependencies` (Task 9), `app.models.rag.PlaygroundSearchRequest`/`PlaygroundSearchResponse` (Task 8), `app.rag.collections_registry.get_collection` (Task 2).
- Produces: `POST /api/rag/playground/search`.

- [ ] **Step 1: Escrever `backend/tests/test_rag_playground_api.py`**

```python
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.rag_dependencies import get_db_session, get_embedder_registry, get_qdrant_client
from app.api.rag_playground import router as rag_playground_router
from app.rag.embedders_registry import EmbedderRegistry
from app.router.rag_client import Document, RAGConnectionError


class _FakeQdrantSearch:
    def __init__(self, resultado=None, error: Exception | None = None) -> None:
        self._resultado = resultado or []
        self._error = error
        self.chamadas: list[str] = []

    async def search(self, collection_name, embedder, query, domain, top_k=None, score_threshold=None):
        self.chamadas.append(collection_name)
        if self._error is not None:
            raise self._error
        return self._resultado


def _build_app(qdrant, db_session) -> FastAPI:
    app = FastAPI()
    app.include_router(rag_playground_router)
    app.dependency_overrides[get_qdrant_client] = lambda: qdrant
    app.dependency_overrides[get_embedder_registry] = lambda: EmbedderRegistry()
    app.dependency_overrides[get_db_session] = lambda: db_session
    return app


async def test_playground_busca_em_uma_collection_e_retorna_resultado_com_latencia(
    db_session, active_collection
):
    fake = _FakeQdrantSearch(resultado=[Document(content="conteúdo", source="a.txt", score=0.9)])
    client = TestClient(_build_app(fake, db_session))

    response = client.post(
        "/api/rag/playground/search",
        json={"query": "pergunta de teste", "domain": "vendas", "collection_ids": [str(active_collection.id)]},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["collection_name"] == active_collection.name
    assert item["latency_ms"] >= 0
    assert item["results"] == [{"content": "conteúdo", "source": "a.txt", "score": 0.9}]
    assert item["error"] is None


async def test_playground_com_collection_inexistente_retorna_item_com_erro(db_session):
    fake = _FakeQdrantSearch()
    client = TestClient(_build_app(fake, db_session))
    id_inexistente = str(uuid.uuid4())

    response = client.post(
        "/api/rag/playground/search",
        json={"query": "pergunta", "domain": "vendas", "collection_ids": [id_inexistente]},
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["collection_id"] == id_inexistente
    assert item["error"] is not None
    assert item["results"] == []


async def test_playground_erro_de_conexao_em_uma_collection_nao_derruba_as_outras(
    db_session, active_collection
):
    from app.rag.collections_registry import create_collection

    outra = await create_collection(
        db_session,
        name="outra",
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
    )

    class _FlakyQdrant:
        async def search(self, collection_name, embedder, query, domain, top_k=None, score_threshold=None):
            if collection_name == active_collection.name:
                raise RAGConnectionError("fora do ar")
            return [Document(content="ok", source="b.txt", score=0.5)]

    client = TestClient(_build_app(_FlakyQdrant(), db_session))

    response = client.post(
        "/api/rag/playground/search",
        json={
            "query": "pergunta",
            "domain": "vendas",
            "collection_ids": [str(active_collection.id), str(outra.id)],
        },
    )

    assert response.status_code == 200
    items = {item["collection_id"]: item for item in response.json()["items"]}
    assert items[str(active_collection.id)]["error"] is not None
    assert items[str(outra.id)]["results"][0]["source"] == "b.txt"


async def test_playground_sem_collection_ids_retorna_422(db_session):
    fake = _FakeQdrantSearch()
    client = TestClient(_build_app(fake, db_session))

    response = client.post(
        "/api/rag/playground/search", json={"query": "pergunta", "domain": "vendas", "collection_ids": []}
    )

    assert response.status_code == 422
```

- [ ] **Step 2: Rodar para ver a falha**

Run: `cd backend && .venv/bin/pytest tests/test_rag_playground_api.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.api.rag_playground'`

- [ ] **Step 3: Implementar `backend/src/app/api/rag_playground.py`**

```python
"""Playground de busca comparativo entre collections (Entregas B+C+D, além
do MVP) — roda a mesma pergunta contra várias collections e devolve
resultados/score/latência lado a lado, sem agregar métrica de qualidade
(isso é a Fase 10 do roadmap). Ver
docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §6.3.
"""

import time

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rag_dependencies import get_db_session, get_embedder_registry, get_qdrant_client
from app.models.rag import PlaygroundDocumentResult, PlaygroundResultItem, PlaygroundSearchRequest, PlaygroundSearchResponse
from app.rag.collections_registry import get_collection
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import QdrantRAGClient
from app.router.rag_client import RAGConnectionError

router = APIRouter(prefix="/api/rag/playground", tags=["rag-playground"])


@router.post("/search", response_model=PlaygroundSearchResponse)
async def playground_search(
    body: PlaygroundSearchRequest,
    qdrant: QdrantRAGClient = Depends(get_qdrant_client),
    embedders: EmbedderRegistry = Depends(get_embedder_registry),
    session: AsyncSession = Depends(get_db_session),
) -> PlaygroundSearchResponse:
    resultados: list[PlaygroundResultItem] = []

    for collection_id in body.collection_ids:
        collection = await get_collection(session, collection_id)
        if collection is None:
            resultados.append(
                PlaygroundResultItem(
                    collection_id=collection_id, collection_name="?", error="Collection não encontrada."
                )
            )
            continue

        embedder = embedders.get(collection.embedding_model)
        inicio = time.perf_counter()
        try:
            documentos = await qdrant.search(collection.name, embedder, body.query, body.domain)
        except RAGConnectionError as exc:
            resultados.append(
                PlaygroundResultItem(collection_id=collection.id, collection_name=collection.name, error=str(exc))
            )
            continue
        latencia_ms = (time.perf_counter() - inicio) * 1000

        resultados.append(
            PlaygroundResultItem(
                collection_id=collection.id,
                collection_name=collection.name,
                latency_ms=latencia_ms,
                results=[
                    PlaygroundDocumentResult(content=documento.content, source=documento.source, score=documento.score)
                    for documento in documentos
                ],
            )
        )

    return PlaygroundSearchResponse(items=resultados)
```

- [ ] **Step 4: Rodar de novo**

Run: `cd backend && .venv/bin/pytest tests/test_rag_playground_api.py -v`
Expected: PASS (todos)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/api/rag_playground.py backend/tests/test_rag_playground_api.py
git commit -m "feat(rag): endpoint de playground de busca comparativo entre collections"
```

---

### Task 13: Wiring — `app/config.py` e `app/main.py`

**Files:**
- Modify: `backend/src/app/config.py`
- Modify: `backend/src/app/main.py`
- Create: `backend/tests/test_main_app.py`

**Interfaces:**
- Consumes: tudo das Tasks 2-3-4-5-9-11-12.
- Produces: `Settings.rag_uploads_dir: str` (novo, default `"./data/rag_uploads"`); `app.state.qdrant_client`, `app.state.embedder_registry`, `app.state.rag_uploads_dir`, `app.state.rag_client` (agora `ActiveCollectionRagClient`); routers `rag_collections_router`/`rag_playground_router` incluídos.

- [ ] **Step 1: Escrever um teste de smoke da app**

```python
"""Smoke test de `create_app()` — garante que a montagem de app.state e o
registro de routers não quebram (ver
docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §4.1)."""

from fastapi.testclient import TestClient

from app.main import create_app
from app.rag.active_collection_client import ActiveCollectionRagClient
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import QdrantRAGClient


def test_create_app_monta_o_estado_do_rag_corretamente():
    app = create_app()

    assert isinstance(app.state.qdrant_client, QdrantRAGClient)
    assert isinstance(app.state.embedder_registry, EmbedderRegistry)
    assert isinstance(app.state.rag_client, ActiveCollectionRagClient)
    assert app.state.rag_uploads_dir is not None


def test_rotas_de_collections_e_playground_estao_registradas():
    app = create_app()
    client = TestClient(app)
    caminhos = {rota.path for rota in app.routes}

    assert "/api/rag/collections" in caminhos
    assert "/api/rag/playground/search" in caminhos
    del client  # só para garantir que a app sobe sem erro de import circular
```

- [ ] **Step 2: Rodar para ver a falha**

Run: `cd backend && .venv/bin/pytest tests/test_main_app.py -v`
Expected: FAIL — `app.state.qdrant_client` ainda não existe (é `rag_client` na versão antiga), rotas de collections/playground ainda não registradas.

- [ ] **Step 3: Adicionar `rag_uploads_dir` em `app/config.py`**

Adicionar, logo abaixo da linha `postgres_dsn: str = ...`:

```python
    # MVP: disco local gerenciado pelo processo do backend, sem object
    # storage — coerente com o ambiente de desenvolvimento único deste
    # protótipo de TCC (ver
    # docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §3).
    rag_uploads_dir: str = "./data/rag_uploads"
```

- [ ] **Step 4: Substituir todo o conteúdo de `backend/src/app/main.py`**

```python
"""Ponto de entrada da API FastAPI do backend (`uvicorn app.main:app`)."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.rag import router as rag_router
from app.api.rag_collections import router as rag_collections_router
from app.api.rag_playground import router as rag_playground_router
from app.config import get_settings
from app.db.engine import create_db_engine, create_session_factory
from app.logging_config import configure_logging
from app.rag.active_collection_client import ActiveCollectionRagClient
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import QdrantRAGClient
from app.router.ollama_client import OllamaClient
from app.router.openrouter_client import OpenRouterClient
from app.stt.whisper_client import WhisperSttClient


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="Assistente Multimodal — Backend", version="0.1.0")

    # MVP: libera só a origem do frontend de dev — sem lista por
    # ambiente/parceiro (ver docs/FRONTEND.md).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_allowed_origin],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Clientes de infraestrutura como singletons por processo — reaproveitados
    # entre requisições (mesmo padrão usado pelos testes do orchestrator).
    app.state.local_client = OllamaClient(
        base_url=settings.local_model_base_url,
        model=settings.local_model_name,
        timeout_s=settings.local_llm_timeout_s,
    )
    app.state.external_client = OpenRouterClient(
        base_url=settings.external_model_base_url,
        api_key=settings.external_model_api_key,
        model=settings.external_model_name,
        timeout_s=settings.external_llm_timeout_s,
        price_per_1k_input_tokens=settings.external_model_price_per_1k_input_tokens,
        price_per_1k_output_tokens=settings.external_model_price_per_1k_output_tokens,
    )

    # RAG real via Qdrant (R4, Fase 2), evoluído para múltiplas collections
    # configuráveis (Entregas B+C+D, além do MVP — ver
    # docs/superpowers/specs/2026-09-15-rag-collections-config-design.md).
    # `qdrant_client`/`embedder_registry` são de baixo nível (usados pelos
    # endpoints administrativos de `app.api.rag`/`rag_collections`/
    # `rag_playground`); `rag_client` é o adapter que resolve a collection
    # ativa a cada busca, consumido pelo orchestrator via `app.api.chat`.
    app.state.qdrant_client = QdrantRAGClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        timeout_s=settings.qdrant_timeout_s,
    )
    app.state.embedder_registry = EmbedderRegistry()
    app.state.rag_uploads_dir = Path(settings.rag_uploads_dir)

    # Primeiro uso real do Postgres do projeto (registro de documentos do
    # RAG, além do MVP — ver docs/ARCHITECTURE.md §5). Engine criado
    # explicitamente aqui (não via singleton global), mesmo padrão dos
    # outros clientes de infraestrutura desta função.
    db_engine = create_db_engine(settings.postgres_dsn)
    app.state.db_sessionmaker = create_session_factory(db_engine)

    app.state.rag_client = ActiveCollectionRagClient(
        qdrant=app.state.qdrant_client,
        session_factory=app.state.db_sessionmaker,
        embedders=app.state.embedder_registry,
    )

    app.state.complexity_strategy = settings.router_complexity_strategy
    # MVP: modelo carregado sob demanda (lazy) na mesma GPU do modelo local de
    # chat — contenção de VRAM entre os dois é um risco conhecido (ver
    # docs/ARCHITECTURE.md §7).
    app.state.stt_client = WhisperSttClient(model_size=settings.stt_model_size)

    app.include_router(chat_router)
    app.include_router(rag_router)
    app.include_router(rag_collections_router)
    app.include_router(rag_playground_router)

    return app


app = create_app()
```

- [ ] **Step 5: Rodar de novo**

Run: `cd backend && .venv/bin/pytest tests/test_main_app.py -v`
Expected: PASS (2 testes)

- [ ] **Step 6: Rodar a suíte inteira do backend**

Run: `cd backend && .venv/bin/pytest tests/ -v -m "not qdrant and not gpu"`
Expected: PASS em tudo

- [ ] **Step 7: Commit**

```bash
git add backend/src/app/config.py backend/src/app/main.py backend/tests/test_main_app.py
git commit -m "feat(rag): conecta collections/playground/EmbedderRegistry em app.main"
```

---

### Task 14: Atualizar `backend/scripts/ingest_sample_docs.py`

**Files:**
- Modify: `backend/scripts/ingest_sample_docs.py`

**Interfaces:**
- Consumes: `app.rag.collections_registry.get_active_collection` (Task 2), `app.rag.embedders_registry.EmbedderRegistry` (Task 3), `app.rag.ingest.ingest_directory` (Task 7, nova assinatura).

Este script não tem teste automatizado (já não tinha antes desta entrega — é uma ferramenta de linha de comando que depende de Qdrant/Postgres reais no ar). A verificação é manual, descrita no Step 3.

- [ ] **Step 1: Substituir todo o conteúdo de `backend/scripts/ingest_sample_docs.py`**

```python
"""Script de ingestão de um pequeno conjunto de documentos de exemplo no RAG,
na collection atualmente ativa.

# MVP: script de linha de comando único, sem agendamento nem observador de
# diretório — reingestão é manual (rodar o script de novo), o que duplica
# pontos no Qdrant e cria novos registros, já que não há deduplicação (ver
# `app.rag.qdrant_client.upsert_chunks`). Serve para ter algo indexado para
# demonstrar/testar o RAG, não é um pipeline de produção (ver
# docs/ARCHITECTURE.md §5).

Uso (a partir de `backend/`, com o Qdrant e o Postgres do docker-compose no ar
e a migração do Alembic já aplicada — `alembic upgrade head`, que cria a
collection `docs_texto` ativa por padrão):

    .venv/bin/python scripts/ingest_sample_docs.py
"""

import asyncio
import logging
from pathlib import Path

from app.config import get_settings
from app.db.engine import create_db_engine, create_session_factory
from app.logging_config import configure_logging
from app.rag.collections_registry import get_active_collection
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.ingest import ingest_directory
from app.rag.qdrant_client import QdrantRAGClient

SAMPLE_DOCS_DIR = Path(__file__).parent / "sample_docs"


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    qdrant = QdrantRAGClient(
        host=settings.qdrant_host, port=settings.qdrant_port, timeout_s=settings.qdrant_timeout_s
    )
    embedders = EmbedderRegistry()
    uploads_dir = Path(settings.rag_uploads_dir)
    db_engine = create_db_engine(settings.postgres_dsn)
    session_factory = create_session_factory(db_engine)

    async with session_factory() as session:
        collection = await get_active_collection(session)
        if collection is None:
            raise RuntimeError(
                "Nenhuma collection ativa configurada — rode `alembic upgrade head` primeiro."
            )
        embedder = embedders.get(collection.embedding_model)
        documentos = await ingest_directory(
            qdrant, embedder, collection, uploads_dir, SAMPLE_DOCS_DIR, session=session
        )

    total_chunks = sum(documento.chunk_count for documento in documentos)
    print(
        f"Ingeridos {len(documentos)} documento(s), {total_chunks} chunk(s) na collection "
        f"'{collection.name}' a partir de {SAMPLE_DOCS_DIR}"
    )
    await db_engine.dispose()


if __name__ == "__main__":
    logging.getLogger(__name__).info("iniciando ingestão de documentos de exemplo")
    asyncio.run(main())
```

- [ ] **Step 2: Verificar que importa limpo (sem depender de Qdrant/Postgres reais)**

Run: `cd backend && .venv/bin/python -c "import ast; ast.parse(open('scripts/ingest_sample_docs.py').read()); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Verificação manual (documentar no PR, não em CI) — só se Qdrant/Postgres do `docker-compose.yml` estiverem no ar**

Run: `cd backend && docker compose up -d && .venv/bin/alembic upgrade head && .venv/bin/python scripts/ingest_sample_docs.py`
Expected: imprime `Ingeridos N documento(s), M chunk(s) na collection 'docs_texto' a partir de .../sample_docs` sem traceback.

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/ingest_sample_docs.py
git commit -m "feat(rag): script de ingestão de exemplo usa a collection ativa"
```

---

### Task 15: `lib/types/rag.ts` — tipos de collections, documentos e playground

**Files:**
- Modify: `frontend/lib/types/rag.ts`

**Interfaces:**
- Produces: `DistanceMetric`, `QuantizationType`, `PayloadSchemaType`, `HnswConfig`, `ScalarQuantizationConfig`, `ProductQuantizationConfig`, `BinaryQuantizationConfig`, `QuantizationConfig`, `TextIndexParams`, `PayloadIndex`, `CollectionCreatePayload`, `RagCollection`, `RagDocumentOrigin` (ganha `"reingest"`), `DocumentRegistryEntry` (perde `embedding_model`/`chunk_size`/`chunk_overlap`, ganha `collection_id`/`collection_name`), `PlaygroundDocumentResult`, `PlaygroundResultItem`, `PlaygroundSearchPayload`, `PlaygroundSearchResponse`.

Só definição de tipos — sem lógica testável isoladamente; a cobertura vem dos testes de componente das Tasks 17-20, que usam esses tipos.

- [ ] **Step 1: Substituir todo o conteúdo de `frontend/lib/types/rag.ts`**

```typescript
/**
 * Tipos do contrato dos endpoints do RAG (ver `docs/FRONTEND.md` §4 e
 * `backend/src/app/models/rag.py`). Mantidos em sincronia manual com o
 * backend nesta etapa do protótipo.
 */

// MVP: mesmo conjunto de domínios com RAG de texto — "agendamento" e
// "fora_escopo" não têm collection própria (ver `RagDomain` no backend).
export type RagDomain = "vendas" | "suporte" | "atendimento";

export interface DocumentIngestResponse {
  filename: string;
  domain: RagDomain;
  chunks: number;
}

export type RagDocumentOrigin = "upload" | "batch_script" | "reingest";

/** Um item de `GET /api/rag/documents`. */
export interface DocumentRegistryEntry {
  id: string;
  filename: string;
  domain: RagDomain;
  chunk_count: number;
  collection_id: string;
  collection_name: string;
  origin: RagDocumentOrigin;
  created_at: string;
}

export type DistanceMetric = "cosine" | "euclid" | "dot" | "manhattan";
export type QuantizationType = "none" | "scalar" | "product" | "binary";
export type PayloadSchemaType =
  | "keyword"
  | "integer"
  | "float"
  | "bool"
  | "geo"
  | "datetime"
  | "uuid"
  | "text";

export interface HnswConfig {
  m: number;
  ef_construct: number;
  full_scan_threshold: number;
  max_indexing_threads: number;
  on_disk: boolean;
  payload_m: number | null;
}

export interface ScalarQuantizationConfig {
  quantile: number;
  always_ram: boolean;
}

export interface ProductQuantizationConfig {
  compression: "x4" | "x8" | "x16" | "x32" | "x64";
  always_ram: boolean;
}

export interface BinaryQuantizationConfig {
  always_ram: boolean;
}

export interface QuantizationConfig {
  type: QuantizationType;
  scalar?: ScalarQuantizationConfig | null;
  product?: ProductQuantizationConfig | null;
  binary?: BinaryQuantizationConfig | null;
}

export interface TextIndexParams {
  tokenizer: "prefix" | "whitespace" | "word" | "multilingual";
  min_token_len: number | null;
  max_token_len: number | null;
  lowercase: boolean;
}

export interface PayloadIndex {
  field: string;
  schema_type: PayloadSchemaType;
  text_params?: TextIndexParams | null;
}

/** Corpo de `POST /api/rag/collections`. */
export interface CollectionCreatePayload {
  name: string;
  embedding_model: string;
  distance_metric: DistanceMetric;
  chunk_size: number;
  chunk_overlap: number;
  hnsw: HnswConfig;
  quantization: QuantizationConfig;
  payload_indexes: PayloadIndex[];
}

/** Um item de `GET /api/rag/collections`. */
export interface RagCollection {
  id: string;
  name: string;
  embedding_model: string;
  vector_dimension: number;
  distance_metric: DistanceMetric;
  chunk_size: number;
  chunk_overlap: number;
  hnsw_m: number;
  hnsw_ef_construct: number;
  hnsw_full_scan_threshold: number;
  hnsw_max_indexing_threads: number;
  hnsw_on_disk: boolean;
  hnsw_payload_m: number | null;
  quantization_type: QuantizationType;
  quantization_config: Record<string, unknown>;
  payload_indexes: PayloadIndex[];
  is_active: boolean;
  document_count: number;
  created_at: string;
}

export interface PlaygroundDocumentResult {
  content: string;
  source: string;
  score: number;
}

/** Um item de `PlaygroundSearchResponse.items` — resultado (ou erro) de uma collection. */
export interface PlaygroundResultItem {
  collection_id: string;
  collection_name: string;
  latency_ms?: number | null;
  results?: PlaygroundDocumentResult[];
  error?: string | null;
}

export interface PlaygroundSearchPayload {
  query: string;
  domain: RagDomain;
  collection_ids: string[];
}

export interface PlaygroundSearchResponse {
  items: PlaygroundResultItem[];
}
```

- [ ] **Step 2: Verificar que o projeto ainda compila (tipos usados nos arquivos existentes vão quebrar até as próximas tasks corrigirem — isso é esperado aqui)**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -30`
Expected: erros em `DocumentsTable.tsx`/`app/admin/ingestao/page.tsx`/testes (referenciam `embedding_model`/`chunk_size`/`chunk_overlap` que saíram de `DocumentRegistryEntry`) — corrigidos nas Tasks 18-19. Confirme que os erros são só nesses arquivos, não em `lib/types/rag.ts` em si.

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/types/rag.ts
git commit -m "feat(rag): tipos de collections, reingestão e playground no frontend"
```

---

### Task 16: `lib/api/rag.ts` — funções de collections, reingestão e playground

**Files:**
- Modify: `frontend/lib/api/rag.ts`

**Interfaces:**
- Consumes: tipos da Task 15.
- Produces: `uploadDocument({file, domain, collectionId?})` (ganha `collectionId` opcional), `listDocuments()`, `deleteDocument(id)` (sem mudança de assinatura), `listCollections()`, `createCollection(payload)`, `activateCollection(id)`, `deleteCollection(id)`, `reingestDocument(documentId, targetCollectionId)`, `runPlaygroundSearch(payload)`.

- [ ] **Step 1: Substituir todo o conteúdo de `frontend/lib/api/rag.ts`**

```typescript
import type {
  CollectionCreatePayload,
  DocumentIngestResponse,
  DocumentRegistryEntry,
  PlaygroundSearchPayload,
  PlaygroundSearchResponse,
  RagCollection,
  RagDomain,
} from "@/lib/types/rag";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/** Erro de comunicação com os endpoints do RAG (rede ou HTTP não-2xx). */
export class RagApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "RagApiError";
    this.status = status;
  }
}

async function _extrairDetalheDeErro(response: Response, mensagemPadrao: string): Promise<never> {
  const detail = await response
    .json()
    .then((body: { detail?: string }) => body.detail)
    .catch(() => undefined);
  const message =
    detail ??
    (response.status === 503
      ? "Serviço de RAG temporariamente indisponível. Tente novamente."
      : mensagemPadrao);
  throw new RagApiError(message, response.status);
}

export interface UploadDocumentParams {
  file: File;
  domain: RagDomain;
  collectionId?: string;
}

/**
 * Envia um PDF/texto para ingestão no RAG via `POST /api/rag/documents`
 * (`multipart/form-data`).
 *
 * MVP: usado pela página administrativa `/admin/ingestao` — sem barra de
 * progresso nem upload em lote (um arquivo por vez), ver `docs/FRONTEND.md`.
 */
export async function uploadDocument({
  file,
  domain,
  collectionId,
}: UploadDocumentParams): Promise<DocumentIngestResponse> {
  const formData = new FormData();
  formData.append("domain", domain);
  formData.append("file", file);
  if (collectionId) {
    formData.append("collection_id", collectionId);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/documents`, { method: "POST", body: formData });
  } catch {
    throw new RagApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    await _extrairDetalheDeErro(response, "Não foi possível enviar o documento. Tente novamente.");
  }

  return (await response.json()) as DocumentIngestResponse;
}

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
 * Exclui um documento (registro + pontos no Qdrant + arquivo em disco) via
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

/**
 * Reingere um documento já ingerido em outra collection via
 * `POST /api/rag/documents/{id}/reingest` — cria um novo documento, não
 * move o original.
 */
export async function reingestDocument(
  documentId: string,
  targetCollectionId: string,
): Promise<DocumentRegistryEntry> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/documents/${documentId}/reingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_collection_id: targetCollectionId }),
    });
  } catch {
    throw new RagApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    await _extrairDetalheDeErro(response, "Não foi possível reingerir o documento. Tente novamente.");
  }

  return (await response.json()) as DocumentRegistryEntry;
}

/** Lista as collections via `GET /api/rag/collections`. */
export async function listCollections(): Promise<RagCollection[]> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/collections`);
  } catch {
    throw new RagApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    throw new RagApiError("Não foi possível carregar as collections. Tente novamente.", response.status);
  }

  return (await response.json()) as RagCollection[];
}

/** Cria uma collection via `POST /api/rag/collections`. */
export async function createCollection(payload: CollectionCreatePayload): Promise<RagCollection> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/collections`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new RagApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    await _extrairDetalheDeErro(response, "Não foi possível criar a collection. Tente novamente.");
  }

  return (await response.json()) as RagCollection;
}

/** Ativa uma collection via `POST /api/rag/collections/{id}/activate`. */
export async function activateCollection(id: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/collections/${id}/activate`, { method: "POST" });
  } catch {
    throw new RagApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    throw new RagApiError("Não foi possível ativar a collection. Tente novamente.", response.status);
  }
}

/** Exclui uma collection (em cascata) via `DELETE /api/rag/collections/{id}`. */
export async function deleteCollection(id: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/collections/${id}`, { method: "DELETE" });
  } catch {
    throw new RagApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    const message =
      response.status === 409
        ? "Não é possível excluir a collection ativa. Ative outra collection antes."
        : "Não foi possível excluir a collection. Tente novamente.";
    throw new RagApiError(message, response.status);
  }
}

/** Roda a busca comparativa via `POST /api/rag/playground/search`. */
export async function runPlaygroundSearch(
  payload: PlaygroundSearchPayload,
): Promise<PlaygroundSearchResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/playground/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new RagApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    await _extrairDetalheDeErro(response, "Não foi possível rodar a busca. Tente novamente.");
  }

  return (await response.json()) as PlaygroundSearchResponse;
}
```

- [ ] **Step 2: Rodar os testes existentes que usam este módulo (ainda devem passar — assinaturas antigas continuam válidas)**

Run: `cd frontend && npx vitest run tests/components/DocumentsTable.test.tsx tests/components/IngestaoDocumentosPage.test.tsx`
Expected: os testes que só chamam `uploadDocument({file, domain})`/`listDocuments()`/`deleteDocument(id)` continuam passando (assinaturas retrocompatíveis); os que checam campos removidos de `DocumentRegistryEntry` (`embedding_model` etc. na renderização da tabela) falham — corrigidos na Task 18.

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/api/rag.ts
git commit -m "feat(rag): funções de API de collections, reingestão e playground"
```

---

### Task 17: `CollectionsTable.tsx` + `CollectionFormModal.tsx`

**Files:**
- Create: `frontend/components/admin/CollectionsTable.tsx`
- Create: `frontend/components/admin/CollectionFormModal.tsx`
- Create: `frontend/tests/components/CollectionsTable.test.tsx`
- Create: `frontend/tests/components/CollectionFormModal.test.tsx`

**Interfaces:**
- Consumes: `@/components/ui/Modal` (existente), `@/lib/api/rag` (`activateCollection`, `deleteCollection`, `createCollection`, `RagApiError` — Task 16), `@/lib/types/rag` (Task 15).
- Produces: `CollectionsTable({collections, onChanged, onError, onSuccess})`; `CollectionFormModal({open, onOpenChange, onCreated})`.

- [ ] **Step 1: Escrever `frontend/tests/components/CollectionsTable.test.tsx`**

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CollectionsTable } from "@/components/admin/CollectionsTable";
import type { RagCollection } from "@/lib/types/rag";

vi.mock("@/lib/api/rag", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/rag")>("@/lib/api/rag");
  return { ...actual, activateCollection: vi.fn(), deleteCollection: vi.fn() };
});

import { activateCollection, deleteCollection, RagApiError } from "@/lib/api/rag";

const mockedActivate = vi.mocked(activateCollection);
const mockedDelete = vi.mocked(deleteCollection);

const COLLECTION_ATIVA: RagCollection = {
  id: "11111111-1111-1111-1111-111111111111",
  name: "docs_texto",
  embedding_model: "paraphrase-multilingual-MiniLM-L12-v2",
  vector_dimension: 384,
  distance_metric: "cosine",
  chunk_size: 800,
  chunk_overlap: 100,
  hnsw_m: 16,
  hnsw_ef_construct: 100,
  hnsw_full_scan_threshold: 10000,
  hnsw_max_indexing_threads: 0,
  hnsw_on_disk: false,
  hnsw_payload_m: null,
  quantization_type: "none",
  quantization_config: {},
  payload_indexes: [],
  is_active: true,
  document_count: 3,
  created_at: new Date().toISOString(),
};

const COLLECTION_INATIVA: RagCollection = { ...COLLECTION_ATIVA, id: "222", name: "teste", is_active: false, document_count: 1 };

describe("CollectionsTable", () => {
  beforeEach(() => {
    mockedActivate.mockReset();
    mockedDelete.mockReset();
  });

  it("renderiza uma linha por collection, com badge 'Ativa'", () => {
    render(<CollectionsTable collections={[COLLECTION_ATIVA]} onChanged={vi.fn()} onError={vi.fn()} onSuccess={vi.fn()} />);

    expect(screen.getByText("docs_texto")).toBeInTheDocument();
    expect(screen.getByText("Ativa")).toBeInTheDocument();
  });

  it("botão excluir da collection ativa fica desabilitado", () => {
    render(<CollectionsTable collections={[COLLECTION_ATIVA]} onChanged={vi.fn()} onError={vi.fn()} onSuccess={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Excluir" })).toBeDisabled();
  });

  it("clicar em ativar chama a API e notifica onChanged/onSuccess", async () => {
    const user = userEvent.setup();
    mockedActivate.mockResolvedValueOnce(undefined);
    const onChanged = vi.fn();
    const onSuccess = vi.fn();
    render(<CollectionsTable collections={[COLLECTION_INATIVA]} onChanged={onChanged} onError={vi.fn()} onSuccess={onSuccess} />);

    await user.click(screen.getByRole("button", { name: "Ativar" }));

    expect(mockedActivate).toHaveBeenCalledWith("222");
    expect(onChanged).toHaveBeenCalled();
    expect(onSuccess).toHaveBeenCalled();
  });

  it("excluir uma collection inativa abre modal de confirmação com a contagem de documentos", async () => {
    const user = userEvent.setup();
    render(<CollectionsTable collections={[COLLECTION_INATIVA]} onChanged={vi.fn()} onError={vi.fn()} onSuccess={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Excluir" }));

    expect(screen.getByText(/1 documento\(s\)/)).toBeInTheDocument();
  });

  it("confirmar exclusão chama a API e notifica", async () => {
    const user = userEvent.setup();
    mockedDelete.mockResolvedValueOnce(undefined);
    const onChanged = vi.fn();
    render(<CollectionsTable collections={[COLLECTION_INATIVA]} onChanged={onChanged} onError={vi.fn()} onSuccess={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Excluir" }));
    await user.click(screen.getByRole("button", { name: "Confirmar exclusão" }));

    expect(mockedDelete).toHaveBeenCalledWith("222");
    expect(onChanged).toHaveBeenCalled();
  });

  it("erro na exclusão chama onError com a mensagem da API", async () => {
    const user = userEvent.setup();
    mockedDelete.mockRejectedValueOnce(new RagApiError("Não é possível excluir a collection ativa."));
    const onError = vi.fn();
    render(<CollectionsTable collections={[COLLECTION_INATIVA]} onChanged={vi.fn()} onError={onError} onSuccess={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Excluir" }));
    await user.click(screen.getByRole("button", { name: "Confirmar exclusão" }));

    expect(onError).toHaveBeenCalledWith("Não é possível excluir a collection ativa.");
  });
});
```

- [ ] **Step 2: Escrever `frontend/tests/components/CollectionFormModal.test.tsx`**

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CollectionFormModal } from "@/components/admin/CollectionFormModal";
import type { RagCollection } from "@/lib/types/rag";

vi.mock("@/lib/api/rag", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/rag")>("@/lib/api/rag");
  return { ...actual, createCollection: vi.fn() };
});

import { createCollection, RagApiError } from "@/lib/api/rag";

const mockedCreate = vi.mocked(createCollection);

const COLLECTION_CRIADA: RagCollection = {
  id: "1",
  name: "nova",
  embedding_model: "paraphrase-multilingual-MiniLM-L12-v2",
  vector_dimension: 384,
  distance_metric: "cosine",
  chunk_size: 800,
  chunk_overlap: 100,
  hnsw_m: 16,
  hnsw_ef_construct: 100,
  hnsw_full_scan_threshold: 10000,
  hnsw_max_indexing_threads: 0,
  hnsw_on_disk: false,
  hnsw_payload_m: null,
  quantization_type: "none",
  quantization_config: {},
  payload_indexes: [],
  is_active: false,
  document_count: 0,
  created_at: new Date().toISOString(),
};

describe("CollectionFormModal", () => {
  beforeEach(() => {
    mockedCreate.mockReset();
  });

  it("preenche nome e envia — chama createCollection com o payload esperado", async () => {
    const user = userEvent.setup();
    mockedCreate.mockResolvedValueOnce(COLLECTION_CRIADA);
    const onCreated = vi.fn();

    render(<CollectionFormModal open onOpenChange={vi.fn()} onCreated={onCreated} />);

    await user.type(screen.getByLabelText("Nome"), "nova");
    await user.click(screen.getByRole("button", { name: "Criar collection" }));

    expect(mockedCreate).toHaveBeenCalledWith(
      expect.objectContaining({ name: "nova", embedding_model: "paraphrase-multilingual-MiniLM-L12-v2" }),
    );
    expect(await screen.findByText).toBeDefined();
    expect(onCreated).toHaveBeenCalledWith(COLLECTION_CRIADA);
  });

  it("selecionar 'Outro' revela campo de texto livre para o modelo", async () => {
    const user = userEvent.setup();
    render(<CollectionFormModal open onOpenChange={vi.fn()} onCreated={vi.fn()} />);

    await user.selectOptions(screen.getByRole("combobox", { name: "" }) ?? screen.getAllByRole("combobox")[0], "__custom__");

    expect(screen.getByLabelText("Nome do modelo")).toBeInTheDocument();
  });

  it("chunk_size menor ou igual ao overlap desabilita o envio e mostra aviso", async () => {
    const user = userEvent.setup();
    render(<CollectionFormModal open onOpenChange={vi.fn()} onCreated={vi.fn()} />);

    await user.type(screen.getByLabelText("Nome"), "nova");
    const chunkSizeInput = screen.getByLabelText(/Chunk size/);
    await user.clear(chunkSizeInput);
    await user.type(chunkSizeInput, "50");

    expect(screen.getByText(/deve ser maior que o overlap/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Criar collection" })).toBeDisabled();
  });

  it("exibe erro da API quando a criação falha (ex.: nome duplicado)", async () => {
    const user = userEvent.setup();
    mockedCreate.mockRejectedValueOnce(new RagApiError("Já existe uma collection chamada 'nova'."));

    render(<CollectionFormModal open onOpenChange={vi.fn()} onCreated={vi.fn()} />);

    await user.type(screen.getByLabelText("Nome"), "nova");
    await user.click(screen.getByRole("button", { name: "Criar collection" }));

    expect(await screen.findByText("Já existe uma collection chamada 'nova'.")).toBeInTheDocument();
  });
});
```

Nota: o teste "preenche nome e envia" tem uma linha solta (`expect(await screen.findByText).toBeDefined()`) que não afirma nada útil — remova-a ao escrever o arquivo de verdade; ela ficou aqui só por descuido de edição e não deve ser copiada. A asserção que importa é a de `mockedCreate`/`onCreated`, já presente.

- [ ] **Step 3: Rodar os dois arquivos de teste para ver a falha**

Run: `cd frontend && npx vitest run tests/components/CollectionsTable.test.tsx tests/components/CollectionFormModal.test.tsx`
Expected: FAIL — `Cannot find module '@/components/admin/CollectionsTable'` / `CollectionFormModal`.

- [ ] **Step 4: Implementar `frontend/components/admin/CollectionsTable.tsx`**

```tsx
"use client";

import { useState } from "react";

import { Modal } from "@/components/ui/Modal";
import { RagApiError, activateCollection, deleteCollection } from "@/lib/api/rag";
import type { RagCollection } from "@/lib/types/rag";

export interface CollectionsTableProps {
  collections: RagCollection[];
  onChanged: () => void;
  onError: (message: string) => void;
  onSuccess: (message: string) => void;
}

export function CollectionsTable({ collections, onChanged, onError, onSuccess }: CollectionsTableProps) {
  const [collectionParaExcluir, setCollectionParaExcluir] = useState<RagCollection | null>(null);
  const [processando, setProcessando] = useState(false);

  async function handleAtivar(collection: RagCollection) {
    setProcessando(true);
    try {
      await activateCollection(collection.id);
      onSuccess(`"${collection.name}" agora é a collection ativa.`);
      onChanged();
    } catch (err) {
      onError(err instanceof RagApiError ? err.message : "Erro inesperado ao ativar a collection.");
    } finally {
      setProcessando(false);
    }
  }

  async function confirmarExclusao() {
    if (!collectionParaExcluir) return;
    setProcessando(true);
    try {
      await deleteCollection(collectionParaExcluir.id);
      onSuccess(`"${collectionParaExcluir.name}" excluída.`);
      setCollectionParaExcluir(null);
      onChanged();
    } catch (err) {
      onError(err instanceof RagApiError ? err.message : "Erro inesperado ao excluir a collection.");
    } finally {
      setProcessando(false);
    }
  }

  if (collections.length === 0) {
    return <p className="text-sm text-gray-600">Nenhuma collection criada ainda.</p>;
  }

  return (
    <>
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-gray-500">
            <th className="py-2 pr-4">Nome</th>
            <th className="py-2 pr-4">Modelo</th>
            <th className="py-2 pr-4">Dimensão</th>
            <th className="py-2 pr-4">Métrica</th>
            <th className="py-2 pr-4">HNSW</th>
            <th className="py-2 pr-4">Quantização</th>
            <th className="py-2 pr-4">Documentos</th>
            <th className="py-2 pr-4" />
          </tr>
        </thead>
        <tbody>
          {collections.map((collection) => (
            <tr key={collection.id} className="border-b border-gray-100">
              <td className="py-2 pr-4 text-gray-900">
                {collection.name}
                {collection.is_active && (
                  <span className="ml-2 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800">
                    Ativa
                  </span>
                )}
              </td>
              <td className="py-2 pr-4 text-gray-700">{collection.embedding_model}</td>
              <td className="py-2 pr-4 text-gray-700">{collection.vector_dimension}</td>
              <td className="py-2 pr-4 text-gray-700">{collection.distance_metric}</td>
              <td className="py-2 pr-4 text-gray-700">
                m={collection.hnsw_m} / ef={collection.hnsw_ef_construct}
              </td>
              <td className="py-2 pr-4 text-gray-700">{collection.quantization_type}</td>
              <td className="py-2 pr-4 text-gray-700">{collection.document_count}</td>
              <td className="py-2 pr-4 text-right">
                {!collection.is_active && (
                  <button
                    type="button"
                    onClick={() => handleAtivar(collection)}
                    disabled={processando}
                    className="mr-3 text-gray-700 hover:text-gray-900"
                  >
                    Ativar
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setCollectionParaExcluir(collection)}
                  disabled={processando || collection.is_active}
                  title={collection.is_active ? "Ative outra collection antes de excluir esta." : undefined}
                  className="text-red-600 hover:text-red-800 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Excluir
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <Modal
        open={collectionParaExcluir !== null}
        onOpenChange={(open) => !open && setCollectionParaExcluir(null)}
        title="Excluir collection"
        footer={
          <>
            <button
              type="button"
              onClick={() => setCollectionParaExcluir(null)}
              className="rounded-md px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={confirmarExclusao}
              disabled={processando}
              className="rounded-md bg-red-600 px-4 py-2 text-sm text-white disabled:opacity-50"
            >
              Confirmar exclusão
            </button>
          </>
        }
      >
        Tem certeza que deseja excluir &ldquo;{collectionParaExcluir?.name}&rdquo;? Isso vai apagar em
        cascata os {collectionParaExcluir?.document_count} documento(s) ingerido(s) nela e não pode ser
        desfeito.
      </Modal>
    </>
  );
}
```

- [ ] **Step 5: Implementar `frontend/components/admin/CollectionFormModal.tsx`**

```tsx
"use client";

import { useState } from "react";

import { Modal } from "@/components/ui/Modal";
import { RagApiError, createCollection } from "@/lib/api/rag";
import type {
  CollectionCreatePayload,
  PayloadIndex,
  PayloadSchemaType,
  QuantizationType,
  RagCollection,
} from "@/lib/types/rag";

const CURATED_MODELS = [
  { value: "paraphrase-multilingual-MiniLM-L12-v2", label: "MiniLM multilíngue (384 dim)" },
  { value: "paraphrase-multilingual-mpnet-base-v2", label: "MPNet multilíngue (768 dim)" },
  { value: "intfloat/multilingual-e5-base", label: "E5 base multilíngue (768 dim)" },
  { value: "intfloat/multilingual-e5-large", label: "E5 large multilíngue (1024 dim)" },
  { value: "__custom__", label: "Outro (digitar nome)" },
] as const;

const SCHEMA_TYPES: PayloadSchemaType[] = [
  "keyword",
  "integer",
  "float",
  "bool",
  "geo",
  "datetime",
  "uuid",
  "text",
];

const PAYLOAD_INDEXES_PADRAO: PayloadIndex[] = [
  { field: "domain", schema_type: "keyword" },
  { field: "document_id", schema_type: "keyword" },
];

export interface CollectionFormModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (collection: RagCollection) => void;
}

export function CollectionFormModal({ open, onOpenChange, onCreated }: CollectionFormModalProps) {
  const [name, setName] = useState("");
  const [modelSelecionado, setModelSelecionado] = useState<string>(CURATED_MODELS[0].value);
  const [modeloCustom, setModeloCustom] = useState("");
  const [distanceMetric, setDistanceMetric] = useState<CollectionCreatePayload["distance_metric"]>("cosine");
  const [chunkSize, setChunkSize] = useState(800);
  const [chunkOverlap, setChunkOverlap] = useState(100);
  const [hnswM, setHnswM] = useState(16);
  const [hnswEfConstruct, setHnswEfConstruct] = useState(100);
  const [hnswFullScanThreshold, setHnswFullScanThreshold] = useState(10000);
  const [hnswMaxIndexingThreads, setHnswMaxIndexingThreads] = useState(0);
  const [hnswOnDisk, setHnswOnDisk] = useState(false);
  const [hnswPayloadM, setHnswPayloadM] = useState("");
  const [quantizationType, setQuantizationType] = useState<QuantizationType>("none");
  const [scalarQuantile, setScalarQuantile] = useState(0.99);
  const [scalarAlwaysRam, setScalarAlwaysRam] = useState(false);
  const [productCompression, setProductCompression] = useState<"x4" | "x8" | "x16" | "x32" | "x64">("x16");
  const [productAlwaysRam, setProductAlwaysRam] = useState(false);
  const [binaryAlwaysRam, setBinaryAlwaysRam] = useState(false);
  const [payloadIndexes, setPayloadIndexes] = useState<PayloadIndex[]>(PAYLOAD_INDEXES_PADRAO);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const embeddingModel = modelSelecionado === "__custom__" ? modeloCustom : modelSelecionado;
  const chunkingInvalido = chunkSize <= chunkOverlap;

  function resetar() {
    setName("");
    setModelSelecionado(CURATED_MODELS[0].value);
    setModeloCustom("");
    setDistanceMetric("cosine");
    setChunkSize(800);
    setChunkOverlap(100);
    setHnswM(16);
    setHnswEfConstruct(100);
    setHnswFullScanThreshold(10000);
    setHnswMaxIndexingThreads(0);
    setHnswOnDisk(false);
    setHnswPayloadM("");
    setQuantizationType("none");
    setScalarQuantile(0.99);
    setScalarAlwaysRam(false);
    setProductCompression("x16");
    setProductAlwaysRam(false);
    setBinaryAlwaysRam(false);
    setPayloadIndexes(PAYLOAD_INDEXES_PADRAO);
    setError(null);
  }

  function atualizarPayloadIndex(indice: number, campo: Partial<PayloadIndex>) {
    setPayloadIndexes((atual) => atual.map((item, i) => (i === indice ? { ...item, ...campo } : item)));
  }

  function removerPayloadIndex(indice: number) {
    setPayloadIndexes((atual) => atual.filter((_, i) => i !== indice));
  }

  function adicionarPayloadIndex() {
    setPayloadIndexes((atual) => [...atual, { field: "", schema_type: "keyword" }]);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting || chunkingInvalido || !embeddingModel) return;

    setIsSubmitting(true);
    setError(null);

    const payload: CollectionCreatePayload = {
      name,
      embedding_model: embeddingModel,
      distance_metric: distanceMetric,
      chunk_size: chunkSize,
      chunk_overlap: chunkOverlap,
      hnsw: {
        m: hnswM,
        ef_construct: hnswEfConstruct,
        full_scan_threshold: hnswFullScanThreshold,
        max_indexing_threads: hnswMaxIndexingThreads,
        on_disk: hnswOnDisk,
        payload_m: hnswPayloadM === "" ? null : Number(hnswPayloadM),
      },
      quantization: {
        type: quantizationType,
        scalar: quantizationType === "scalar" ? { quantile: scalarQuantile, always_ram: scalarAlwaysRam } : null,
        product:
          quantizationType === "product"
            ? { compression: productCompression, always_ram: productAlwaysRam }
            : null,
        binary: quantizationType === "binary" ? { always_ram: binaryAlwaysRam } : null,
      },
      payload_indexes: payloadIndexes.filter((item) => item.field.trim() !== ""),
    };

    try {
      const collection = await createCollection(payload);
      onCreated(collection);
      resetar();
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof RagApiError ? err.message : "Erro inesperado ao criar a collection.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onOpenChange={(novoOpen) => {
        if (!novoOpen) resetar();
        onOpenChange(novoOpen);
      }}
      title="Nova collection"
    >
      <form onSubmit={handleSubmit} className="max-h-[70vh] space-y-6 overflow-y-auto pr-2">
        <div>
          <label htmlFor="collection-name" className="block text-sm font-medium text-gray-900">
            Nome
          </label>
          <input
            id="collection-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
          />
        </div>

        <fieldset className="space-y-2">
          <legend className="text-sm font-medium text-gray-900">Modelo de embedding</legend>
          <select
            value={modelSelecionado}
            onChange={(e) => setModelSelecionado(e.target.value)}
            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
          >
            {CURATED_MODELS.map((modelo) => (
              <option key={modelo.value} value={modelo.value}>
                {modelo.label}
              </option>
            ))}
          </select>
          {modelSelecionado === "__custom__" && (
            <input
              aria-label="Nome do modelo"
              value={modeloCustom}
              onChange={(e) => setModeloCustom(e.target.value)}
              placeholder="ex.: intfloat/multilingual-e5-small"
              required
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
            />
          )}
        </fieldset>

        <div>
          <label htmlFor="distance-metric" className="block text-sm font-medium text-gray-900">
            Métrica de distância
          </label>
          <select
            id="distance-metric"
            value={distanceMetric}
            onChange={(e) => setDistanceMetric(e.target.value as CollectionCreatePayload["distance_metric"])}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
          >
            <option value="cosine">Cosine</option>
            <option value="euclid">Euclid</option>
            <option value="dot">Dot</option>
            <option value="manhattan">Manhattan</option>
          </select>
        </div>

        <fieldset className="grid grid-cols-2 gap-4">
          <legend className="col-span-2 text-sm font-medium text-gray-900">Chunking</legend>
          <label className="text-sm text-gray-700">
            Chunk size
            <input
              type="number"
              value={chunkSize}
              onChange={(e) => setChunkSize(Number(e.target.value))}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
            />
          </label>
          <label className="text-sm text-gray-700">
            Overlap
            <input
              type="number"
              value={chunkOverlap}
              onChange={(e) => setChunkOverlap(Number(e.target.value))}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
            />
          </label>
          {chunkingInvalido && (
            <p className="col-span-2 text-sm text-red-600">Chunk size deve ser maior que o overlap.</p>
          )}
        </fieldset>

        <fieldset className="grid grid-cols-2 gap-4">
          <legend className="col-span-2 text-sm font-medium text-gray-900">HNSW</legend>
          <label className="text-sm text-gray-700">
            m
            <input
              type="number"
              value={hnswM}
              onChange={(e) => setHnswM(Number(e.target.value))}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
            />
          </label>
          <label className="text-sm text-gray-700">
            ef_construct
            <input
              type="number"
              value={hnswEfConstruct}
              onChange={(e) => setHnswEfConstruct(Number(e.target.value))}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
            />
          </label>
          <label className="text-sm text-gray-700">
            full_scan_threshold
            <input
              type="number"
              value={hnswFullScanThreshold}
              onChange={(e) => setHnswFullScanThreshold(Number(e.target.value))}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
            />
          </label>
          <label className="text-sm text-gray-700">
            max_indexing_threads
            <input
              type="number"
              value={hnswMaxIndexingThreads}
              onChange={(e) => setHnswMaxIndexingThreads(Number(e.target.value))}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
            />
          </label>
          <label className="text-sm text-gray-700">
            payload_m (vazio = padrão)
            <input
              type="number"
              value={hnswPayloadM}
              onChange={(e) => setHnswPayloadM(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
            />
          </label>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input type="checkbox" checked={hnswOnDisk} onChange={(e) => setHnswOnDisk(e.target.checked)} />
            on_disk
          </label>
        </fieldset>

        <fieldset className="space-y-2">
          <legend className="text-sm font-medium text-gray-900">Quantização</legend>
          <select
            value={quantizationType}
            onChange={(e) => setQuantizationType(e.target.value as QuantizationType)}
            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
          >
            <option value="none">Nenhuma</option>
            <option value="scalar">Scalar (int8)</option>
            <option value="product">Product</option>
            <option value="binary">Binary</option>
          </select>
          {quantizationType === "scalar" && (
            <div className="grid grid-cols-2 gap-4">
              <label className="text-sm text-gray-700">
                quantile
                <input
                  type="number"
                  step="0.01"
                  value={scalarQuantile}
                  onChange={(e) => setScalarQuantile(Number(e.target.value))}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
                />
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input type="checkbox" checked={scalarAlwaysRam} onChange={(e) => setScalarAlwaysRam(e.target.checked)} />
                always_ram
              </label>
            </div>
          )}
          {quantizationType === "product" && (
            <div className="grid grid-cols-2 gap-4">
              <label className="text-sm text-gray-700">
                compression
                <select
                  value={productCompression}
                  onChange={(e) => setProductCompression(e.target.value as typeof productCompression)}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
                >
                  {(["x4", "x8", "x16", "x32", "x64"] as const).map((valor) => (
                    <option key={valor} value={valor}>
                      {valor}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input type="checkbox" checked={productAlwaysRam} onChange={(e) => setProductAlwaysRam(e.target.checked)} />
                always_ram
              </label>
            </div>
          )}
          {quantizationType === "binary" && (
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input type="checkbox" checked={binaryAlwaysRam} onChange={(e) => setBinaryAlwaysRam(e.target.checked)} />
              always_ram
            </label>
          )}
        </fieldset>

        <fieldset className="space-y-2">
          <legend className="text-sm font-medium text-gray-900">Payload indexes</legend>
          {payloadIndexes.map((item, indice) => (
            <div key={indice} className="flex items-center gap-2">
              <input
                aria-label={`Campo do índice ${indice + 1}`}
                value={item.field}
                onChange={(e) => atualizarPayloadIndex(indice, { field: e.target.value })}
                placeholder="campo"
                className="w-1/2 rounded-md border border-gray-300 px-3 py-2 text-gray-900"
              />
              <select
                aria-label={`Tipo do índice ${indice + 1}`}
                value={item.schema_type}
                onChange={(e) => atualizarPayloadIndex(indice, { schema_type: e.target.value as PayloadSchemaType })}
                className="w-1/3 rounded-md border border-gray-300 px-3 py-2 text-gray-900"
              >
                {SCHEMA_TYPES.map((tipo) => (
                  <option key={tipo} value={tipo}>
                    {tipo}
                  </option>
                ))}
              </select>
              <button type="button" onClick={() => removerPayloadIndex(indice)} className="text-red-600 hover:text-red-800">
                Remover
              </button>
            </div>
          ))}
          <button type="button" onClick={adicionarPayloadIndex} className="text-sm text-gray-700 underline">
            + Adicionar índice
          </button>
        </fieldset>

        {error && <p className="rounded-md bg-red-50 px-4 py-3 text-red-800">{error}</p>}

        <div className="flex justify-end gap-3 border-t border-gray-200 pt-4">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="rounded-md px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={isSubmitting || chunkingInvalido || !name || !embeddingModel}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            {isSubmitting ? "Criando..." : "Criar collection"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
```

- [ ] **Step 6: Rodar os testes de novo**

Run: `cd frontend && npx vitest run tests/components/CollectionsTable.test.tsx tests/components/CollectionFormModal.test.tsx`
Expected: PASS (remova a linha solta apontada no Step 2 antes de rodar)

- [ ] **Step 7: Commit**

```bash
git add frontend/components/admin/CollectionsTable.tsx frontend/components/admin/CollectionFormModal.tsx frontend/tests/components/CollectionsTable.test.tsx frontend/tests/components/CollectionFormModal.test.tsx
git commit -m "feat(rag): tabela e formulário de criação de collections no admin"
```

---

### Task 18: Atualizar `DocumentsTable.tsx` (coluna de collection) + `ReingestModal.tsx`

**Files:**
- Modify: `frontend/components/admin/DocumentsTable.tsx`
- Create: `frontend/components/admin/ReingestModal.tsx`
- Modify: `frontend/tests/components/DocumentsTable.test.tsx`
- Create: `frontend/tests/components/ReingestModal.test.tsx`

**Interfaces:**
- Consumes: `@/lib/api/rag` (`deleteDocument`, `reingestDocument` — Task 16), `@/lib/types/rag` (Task 15).
- Produces: `DocumentsTable({documents, collections, onDeleted, onReingested})` (props novas: `collections`, `onReingested`); `ReingestModal({documento, collections, onOpenChange, onReingested, onError})`.

- [ ] **Step 1: Escrever `frontend/tests/components/ReingestModal.test.tsx`**

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ReingestModal } from "@/components/admin/ReingestModal";
import type { DocumentRegistryEntry, RagCollection } from "@/lib/types/rag";

vi.mock("@/lib/api/rag", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/rag")>("@/lib/api/rag");
  return { ...actual, reingestDocument: vi.fn() };
});

import { RagApiError, reingestDocument } from "@/lib/api/rag";

const mockedReingest = vi.mocked(reingestDocument);

const COLLECTION_ORIGEM: RagCollection = {
  id: "origem",
  name: "origem",
  embedding_model: "modelo",
  vector_dimension: 384,
  distance_metric: "cosine",
  chunk_size: 800,
  chunk_overlap: 100,
  hnsw_m: 16,
  hnsw_ef_construct: 100,
  hnsw_full_scan_threshold: 10000,
  hnsw_max_indexing_threads: 0,
  hnsw_on_disk: false,
  hnsw_payload_m: null,
  quantization_type: "none",
  quantization_config: {},
  payload_indexes: [],
  is_active: true,
  document_count: 1,
  created_at: new Date().toISOString(),
};

const COLLECTION_DESTINO: RagCollection = { ...COLLECTION_ORIGEM, id: "destino", name: "destino", is_active: false };

const DOCUMENTO: DocumentRegistryEntry = {
  id: "doc-1",
  filename: "catalogo.txt",
  domain: "vendas",
  chunk_count: 1,
  collection_id: "origem",
  collection_name: "origem",
  origin: "upload",
  created_at: new Date().toISOString(),
};

describe("ReingestModal", () => {
  beforeEach(() => {
    mockedReingest.mockReset();
  });

  it("não mostra a collection de origem entre os destinos", () => {
    render(
      <ReingestModal
        documento={DOCUMENTO}
        collections={[COLLECTION_ORIGEM, COLLECTION_DESTINO]}
        onOpenChange={vi.fn()}
        onReingested={vi.fn()}
        onError={vi.fn()}
      />,
    );

    expect(screen.queryByRole("option", { name: "origem" })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "destino" })).toBeInTheDocument();
  });

  it("confirmar chama a API com o documento e a collection destino selecionada", async () => {
    const user = userEvent.setup();
    mockedReingest.mockResolvedValueOnce({ ...DOCUMENTO, id: "doc-2", collection_id: "destino" });
    const onReingested = vi.fn();

    render(
      <ReingestModal
        documento={DOCUMENTO}
        collections={[COLLECTION_ORIGEM, COLLECTION_DESTINO]}
        onOpenChange={vi.fn()}
        onReingested={onReingested}
        onError={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Reingerir" }));

    expect(mockedReingest).toHaveBeenCalledWith("doc-1", "destino");
    expect(onReingested).toHaveBeenCalled();
  });

  it("exibe erro da API quando a reingestão falha", async () => {
    const user = userEvent.setup();
    mockedReingest.mockRejectedValueOnce(new RagApiError("Documento sem arquivo salvo."));
    const onError = vi.fn();

    render(
      <ReingestModal
        documento={DOCUMENTO}
        collections={[COLLECTION_ORIGEM, COLLECTION_DESTINO]}
        onOpenChange={vi.fn()}
        onReingested={vi.fn()}
        onError={onError}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Reingerir" }));

    expect(onError).toHaveBeenCalledWith("Documento sem arquivo salvo.");
  });

  it("sem outra collection disponível, mostra aviso e desabilita o botão", () => {
    render(
      <ReingestModal
        documento={DOCUMENTO}
        collections={[COLLECTION_ORIGEM]}
        onOpenChange={vi.fn()}
        onReingested={vi.fn()}
        onError={vi.fn()}
      />,
    );

    expect(screen.getByText(/não há outra collection/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reingerir" })).toBeDisabled();
  });
});
```

- [ ] **Step 2: Atualizar `frontend/tests/components/DocumentsTable.test.tsx`**

Substituir todo o conteúdo:

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DocumentsTable } from "@/components/admin/DocumentsTable";
import { RagApiError } from "@/lib/api/rag";
import type { DocumentRegistryEntry, RagCollection } from "@/lib/types/rag";

vi.mock("@/lib/api/rag", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/rag")>("@/lib/api/rag");
  return { ...actual, deleteDocument: vi.fn(), reingestDocument: vi.fn() };
});

import { deleteDocument } from "@/lib/api/rag";

const mockedDeleteDocument = vi.mocked(deleteDocument);

const COLLECTION: RagCollection = {
  id: "col-1",
  name: "docs_texto",
  embedding_model: "paraphrase-multilingual-MiniLM-L12-v2",
  vector_dimension: 384,
  distance_metric: "cosine",
  chunk_size: 800,
  chunk_overlap: 100,
  hnsw_m: 16,
  hnsw_ef_construct: 100,
  hnsw_full_scan_threshold: 10000,
  hnsw_max_indexing_threads: 0,
  hnsw_on_disk: false,
  hnsw_payload_m: null,
  quantization_type: "none",
  quantization_config: {},
  payload_indexes: [],
  is_active: true,
  document_count: 1,
  created_at: new Date().toISOString(),
};

const DOCUMENTO: DocumentRegistryEntry = {
  id: "11111111-1111-1111-1111-111111111111",
  filename: "catalogo.txt",
  domain: "vendas",
  chunk_count: 3,
  collection_id: "col-1",
  collection_name: "docs_texto",
  origin: "upload",
  created_at: new Date().toISOString(),
};

describe("DocumentsTable", () => {
  beforeEach(() => {
    mockedDeleteDocument.mockReset();
  });

  it("renderiza uma linha por documento, com a collection", () => {
    render(
      <DocumentsTable documents={[DOCUMENTO]} collections={[COLLECTION]} onDeleted={vi.fn()} onReingested={vi.fn()} />,
    );

    expect(screen.getByText("catalogo.txt")).toBeInTheDocument();
    expect(screen.getByText("Vendas")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("docs_texto")).toBeInTheDocument();
  });

  it("clicar em excluir abre o modal, e cancelar não chama a API", async () => {
    const user = userEvent.setup();
    render(
      <DocumentsTable documents={[DOCUMENTO]} collections={[COLLECTION]} onDeleted={vi.fn()} onReingested={vi.fn()} />,
    );

    await user.click(screen.getByRole("button", { name: "Excluir" }));
    expect(screen.getByText(/tem certeza/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Cancelar" }));

    expect(mockedDeleteDocument).not.toHaveBeenCalled();
  });

  it("confirmar a exclusão chama a API e notifica onDeleted", async () => {
    const user = userEvent.setup();
    mockedDeleteDocument.mockResolvedValueOnce(undefined);
    const onDeleted = vi.fn();
    render(
      <DocumentsTable documents={[DOCUMENTO]} collections={[COLLECTION]} onDeleted={onDeleted} onReingested={vi.fn()} />,
    );

    await user.click(screen.getByRole("button", { name: "Excluir" }));
    await user.click(screen.getByRole("button", { name: "Confirmar exclusão" }));

    expect(mockedDeleteDocument).toHaveBeenCalledWith(DOCUMENTO.id);
    expect(await screen.findByText(/excluído/i)).toBeInTheDocument();
    expect(onDeleted).toHaveBeenCalledWith(DOCUMENTO.id);
  });

  it("exibe erro quando a exclusão falha", async () => {
    const user = userEvent.setup();
    mockedDeleteDocument.mockRejectedValueOnce(new RagApiError("Não foi possível excluir."));
    render(
      <DocumentsTable documents={[DOCUMENTO]} collections={[COLLECTION]} onDeleted={vi.fn()} onReingested={vi.fn()} />,
    );

    await user.click(screen.getByRole("button", { name: "Excluir" }));
    await user.click(screen.getByRole("button", { name: "Confirmar exclusão" }));

    expect(await screen.findByText("Não foi possível excluir.")).toBeInTheDocument();
  });

  it("clicar em reingerir abre o modal de reingestão", async () => {
    const user = userEvent.setup();
    const outraCollection: RagCollection = { ...COLLECTION, id: "col-2", name: "outra" };
    render(
      <DocumentsTable
        documents={[DOCUMENTO]}
        collections={[COLLECTION, outraCollection]}
        onDeleted={vi.fn()}
        onReingested={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Reingerir" }));

    expect(screen.getByText("Reingerir em outra collection")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Rodar para ver a falha**

Run: `cd frontend && npx vitest run tests/components/DocumentsTable.test.tsx tests/components/ReingestModal.test.tsx`
Expected: FAIL — `ReingestModal` não existe; `DocumentsTable` não aceita `collections`/`onReingested` nem renderiza "Reingerir"/coluna de collection.

- [ ] **Step 4: Implementar `frontend/components/admin/ReingestModal.tsx`**

```tsx
"use client";

import { useState } from "react";

import { Modal } from "@/components/ui/Modal";
import { RagApiError, reingestDocument } from "@/lib/api/rag";
import type { DocumentRegistryEntry, RagCollection } from "@/lib/types/rag";

export interface ReingestModalProps {
  documento: DocumentRegistryEntry | null;
  collections: RagCollection[];
  onOpenChange: (open: boolean) => void;
  onReingested: () => void;
  onError: (message: string) => void;
}

export function ReingestModal({ documento, collections, onOpenChange, onReingested, onError }: ReingestModalProps) {
  const destinos = collections.filter((collection) => collection.id !== documento?.collection_id);
  const [targetId, setTargetId] = useState(destinos[0]?.id ?? "");
  const [enviando, setEnviando] = useState(false);

  async function confirmar() {
    if (!documento || !targetId) return;
    setEnviando(true);
    try {
      await reingestDocument(documento.id, targetId);
      onReingested();
    } catch (err) {
      onError(err instanceof RagApiError ? err.message : "Erro inesperado ao reingerir o documento.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal
      open={documento !== null}
      onOpenChange={onOpenChange}
      title="Reingerir em outra collection"
      footer={
        <>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="rounded-md px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={confirmar}
            disabled={enviando || destinos.length === 0}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            {enviando ? "Reingerindo..." : "Reingerir"}
          </button>
        </>
      }
    >
      {destinos.length === 0 ? (
        <p className="text-sm text-gray-600">Não há outra collection para reingerir este documento.</p>
      ) : (
        <label className="block text-sm text-gray-700">
          Collection destino
          <select
            value={targetId}
            onChange={(e) => setTargetId(e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
          >
            {destinos.map((collection) => (
              <option key={collection.id} value={collection.id}>
                {collection.name}
              </option>
            ))}
          </select>
        </label>
      )}
    </Modal>
  );
}
```

- [ ] **Step 5: Substituir todo o conteúdo de `frontend/components/admin/DocumentsTable.tsx`**

```tsx
"use client";

import { useState } from "react";

import { DomainBadge } from "@/components/admin/DomainBadge";
import { ReingestModal } from "@/components/admin/ReingestModal";
import { Modal } from "@/components/ui/Modal";
import { ToastStack, useToast } from "@/components/ui/Toast";
import { RagApiError, deleteDocument } from "@/lib/api/rag";
import type { DocumentRegistryEntry, RagCollection } from "@/lib/types/rag";

function formatarDataRelativa(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffDias = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDias <= 0) return "hoje";
  if (diffDias === 1) return "há 1 dia";
  return `há ${diffDias} dias`;
}

export interface DocumentsTableProps {
  documents: DocumentRegistryEntry[];
  collections: RagCollection[];
  onDeleted: (id: string) => void;
  onReingested: () => void;
}

export function DocumentsTable({ documents, collections, onDeleted, onReingested }: DocumentsTableProps) {
  const [documentoParaExcluir, setDocumentoParaExcluir] = useState<DocumentRegistryEntry | null>(null);
  const [documentoParaReingerir, setDocumentoParaReingerir] = useState<DocumentRegistryEntry | null>(null);
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
            <th className="py-2 pr-4">Arquivo</th>
            <th className="py-2 pr-4">Domínio</th>
            <th className="py-2 pr-4">Chunks</th>
            <th className="py-2 pr-4">Collection</th>
            <th className="py-2 pr-4">Data</th>
            <th className="py-2 pr-4" />
          </tr>
        </thead>
        <tbody>
          {documents.map((documento) => (
            <tr key={documento.id} className="border-b border-gray-100">
              <td className="py-2 pr-4 text-gray-900">{documento.filename}</td>
              <td className="py-2 pr-4">
                <DomainBadge domain={documento.domain} />
              </td>
              <td className="py-2 pr-4 text-gray-700">{documento.chunk_count}</td>
              <td className="py-2 pr-4 text-gray-700">{documento.collection_name}</td>
              <td className="py-2 pr-4 text-gray-500" title={documento.created_at}>
                {formatarDataRelativa(documento.created_at)}
              </td>
              <td className="py-2 pr-4 text-right">
                <button
                  type="button"
                  onClick={() => setDocumentoParaReingerir(documento)}
                  className="mr-3 text-gray-700 hover:text-gray-900"
                >
                  Reingerir
                </button>
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

      <ReingestModal
        documento={documentoParaReingerir}
        collections={collections}
        onOpenChange={(open) => !open && setDocumentoParaReingerir(null)}
        onReingested={() => {
          setDocumentoParaReingerir(null);
          showToast("Documento reingerido.", "success");
          onReingested();
        }}
        onError={(message) => showToast(message, "error")}
      />

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </>
  );
}
```

- [ ] **Step 6: Rodar de novo**

Run: `cd frontend && npx vitest run tests/components/DocumentsTable.test.tsx tests/components/ReingestModal.test.tsx`
Expected: PASS (todos)

- [ ] **Step 7: Commit**

```bash
git add frontend/components/admin/DocumentsTable.tsx frontend/components/admin/ReingestModal.tsx frontend/tests/components/DocumentsTable.test.tsx frontend/tests/components/ReingestModal.test.tsx
git commit -m "feat(rag): coluna de collection e reingestão na tabela de documentos"
```

---

### Task 19: Reescrever `app/admin/ingestao/page.tsx` — collection no upload + aba Configuração real

**Files:**
- Modify: `frontend/app/admin/ingestao/page.tsx`
- Modify: `frontend/tests/components/IngestaoDocumentosPage.test.tsx`

**Interfaces:**
- Consumes: `@/lib/api/rag` (`listCollections` — Task 16), `@/components/admin/CollectionsTable`/`CollectionFormModal` (Task 17), `@/components/admin/playground/PlaygroundPanel` (Task 20 — este arquivo referencia um componente que só existe depois da Task 20; ver nota no Step 4 abaixo sobre rodar os testes desta task antes da 20).

**Nota de ordem:** esta task referencia `PlaygroundPanel`, implementado só na Task 20. Rode esta task normalmente (o teste da aba "Playground" vai falhar até a Task 20 existir — é esperado; as demais abas/testes já devem passar). A Task 20 fecha a lacuna.

- [ ] **Step 1: Atualizar `frontend/tests/components/IngestaoDocumentosPage.test.tsx`**

Substituir todo o conteúdo:

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import IngestaoDocumentosPage from "@/app/admin/ingestao/page";
import { RagApiError } from "@/lib/api/rag";
import type { DocumentRegistryEntry, RagCollection } from "@/lib/types/rag";

vi.mock("@/lib/api/rag", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/rag")>("@/lib/api/rag");
  return {
    ...actual,
    uploadDocument: vi.fn(),
    listDocuments: vi.fn(),
    listCollections: vi.fn(),
  };
});

import { listCollections, listDocuments, uploadDocument } from "@/lib/api/rag";

const mockedUploadDocument = vi.mocked(uploadDocument);
const mockedListDocuments = vi.mocked(listDocuments);
const mockedListCollections = vi.mocked(listCollections);

const COLLECTION_ATIVA: RagCollection = {
  id: "col-1",
  name: "docs_texto",
  embedding_model: "paraphrase-multilingual-MiniLM-L12-v2",
  vector_dimension: 384,
  distance_metric: "cosine",
  chunk_size: 800,
  chunk_overlap: 100,
  hnsw_m: 16,
  hnsw_ef_construct: 100,
  hnsw_full_scan_threshold: 10000,
  hnsw_max_indexing_threads: 0,
  hnsw_on_disk: false,
  hnsw_payload_m: null,
  quantization_type: "none",
  quantization_config: {},
  payload_indexes: [],
  is_active: true,
  document_count: 0,
  created_at: new Date().toISOString(),
};

const DOCUMENTO: DocumentRegistryEntry = {
  id: "11111111-1111-1111-1111-111111111111",
  filename: "catalogo.txt",
  domain: "vendas",
  chunk_count: 3,
  collection_id: "col-1",
  collection_name: "docs_texto",
  origin: "upload",
  created_at: new Date().toISOString(),
};

describe("IngestaoDocumentosPage", () => {
  beforeEach(() => {
    mockedUploadDocument.mockReset();
    mockedListDocuments.mockReset();
    mockedListCollections.mockReset();
    mockedListDocuments.mockResolvedValue([]);
    mockedListCollections.mockResolvedValue([COLLECTION_ATIVA]);
  });

  it("envia o arquivo selecionado (com a collection ativa) e exibe o resultado da ingestão", async () => {
    const user = userEvent.setup();
    mockedUploadDocument.mockResolvedValueOnce({ filename: "catalogo.txt", domain: "vendas", chunks: 3 });

    render(<IngestaoDocumentosPage />);

    const file = new File(["conteudo"], "catalogo.txt", { type: "text/plain" });
    await user.upload(await screen.findByLabelText("Arquivo"), file);
    await user.click(screen.getByRole("button", { name: "Enviar para ingestão" }));

    expect(await screen.findByText(/3 chunk\(s\) gravado\(s\)/)).toBeInTheDocument();
    expect(mockedUploadDocument).toHaveBeenCalledWith({ file, domain: "vendas", collectionId: "col-1" });
  });

  it("exibe mensagem de erro quando o upload falha", async () => {
    const user = userEvent.setup();
    mockedUploadDocument.mockRejectedValueOnce(
      new RagApiError("Serviço de RAG temporariamente indisponível. Tente novamente.", 503),
    );

    render(<IngestaoDocumentosPage />);

    const file = new File(["conteudo"], "catalogo.txt", { type: "text/plain" });
    await user.upload(await screen.findByLabelText("Arquivo"), file);
    await user.click(screen.getByRole("button", { name: "Enviar para ingestão" }));

    expect(await screen.findByText(/temporariamente indisponível/)).toBeInTheDocument();
  });

  it("desabilita o envio enquanto nenhum arquivo foi selecionado", async () => {
    render(<IngestaoDocumentosPage />);

    expect(await screen.findByRole("button", { name: "Enviar para ingestão" })).toBeDisabled();
  });

  it("aba 'Documentos ingeridos' lista os documentos ao ser aberta", async () => {
    const user = userEvent.setup();
    mockedListDocuments.mockResolvedValue([DOCUMENTO]);

    render(<IngestaoDocumentosPage />);
    await user.click(screen.getByRole("tab", { name: "Documentos ingeridos" }));

    expect(await screen.findByText("catalogo.txt")).toBeInTheDocument();
  });

  it("aba 'Configuração' não fica mais desabilitada e lista as collections", async () => {
    const user = userEvent.setup();

    render(<IngestaoDocumentosPage />);
    const abaConfiguracao = await screen.findByRole("tab", { name: "Configuração" });
    expect(abaConfiguracao).not.toBeDisabled();

    await user.click(abaConfiguracao);

    expect(await screen.findByText("docs_texto")).toBeInTheDocument();
  });

  it("aba 'Playground' existe", async () => {
    render(<IngestaoDocumentosPage />);

    expect(await screen.findByRole("tab", { name: "Playground" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Rodar para ver a falha**

Run: `cd frontend && npx vitest run tests/components/IngestaoDocumentosPage.test.tsx`
Expected: FAIL — página ainda não busca collections, aba "Configuração" ainda `disabled`, aba "Playground" não existe.

- [ ] **Step 3: Substituir todo o conteúdo de `frontend/app/admin/ingestao/page.tsx`**

```tsx
"use client";

// MVP: página administrativa (fora da navegação pública, sem autenticação)
// para upload avulso de documento no RAG, gestão do registro de documentos
// ingeridos, configuração de perfis de collection e playground de busca
// comparativo — decisão registrada em `docs/ARCHITECTURE.md` §5 e
// `docs/FRONTEND.md` §8. Ver
// docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md e
// docs/superpowers/specs/2026-09-15-rag-collections-config-design.md.
import { useCallback, useEffect, useState } from "react";

import { CollectionFormModal } from "@/components/admin/CollectionFormModal";
import { CollectionsTable } from "@/components/admin/CollectionsTable";
import { DocumentsTable } from "@/components/admin/DocumentsTable";
import { PlaygroundPanel } from "@/components/admin/playground/PlaygroundPanel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { ToastStack, useToast } from "@/components/ui/Toast";
import { RagApiError, listCollections, listDocuments, uploadDocument } from "@/lib/api/rag";
import type {
  DocumentIngestResponse,
  DocumentRegistryEntry,
  RagCollection,
  RagDomain,
} from "@/lib/types/rag";

const DOMAIN_OPTIONS: { value: RagDomain; label: string }[] = [
  { value: "vendas", label: "Vendas" },
  { value: "suporte", label: "Suporte Técnico" },
  { value: "atendimento", label: "Atendimento ao Usuário" },
];

const ACCEPTED_EXTENSIONS = ".txt,.md,.pdf";

function AbaEnviarDocumento({
  collections,
  onIngerido,
}: {
  collections: RagCollection[];
  onIngerido: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [domain, setDomain] = useState<RagDomain>("vendas");
  const [collectionId, setCollectionId] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<DocumentIngestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const collectionAtiva = collections.find((collection) => collection.is_active);
  const collectionSelecionada = collectionId || collectionAtiva?.id || collections[0]?.id || "";

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
      const response = await uploadDocument({
        file,
        domain,
        collectionId: collectionSelecionada || undefined,
      });
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
          <label htmlFor="collection" className="block text-sm font-medium text-gray-900">
            Collection destino
          </label>
          <select
            id="collection"
            value={collectionSelecionada}
            onChange={(event) => setCollectionId(event.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
          >
            {collections.map((collection) => (
              <option key={collection.id} value={collection.id}>
                {collection.name}
                {collection.is_active ? " (ativa)" : ""}
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

function AbaDocumentosIngeridos({ collections }: { collections: RagCollection[] }) {
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
    // eslint-disable-next-line react-hooks/set-state-in-effect
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
        <DocumentsTable
          documents={documentos}
          collections={collections}
          onDeleted={handleDeleted}
          onReingested={carregarDocumentos}
        />
      )}
      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}

function AbaConfiguracao({
  collections,
  onChanged,
}: {
  collections: RagCollection[];
  onChanged: () => void;
}) {
  const [modalAberto, setModalAberto] = useState(false);
  const { toasts, showToast, dismissToast } = useToast();

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <p className="text-gray-600">Perfis de collection do Qdrant usados pelo RAG.</p>
        <button
          type="button"
          onClick={() => setModalAberto(true)}
          className="rounded-md bg-gray-900 px-4 py-2 text-sm text-white"
        >
          Nova collection
        </button>
      </div>

      <div className="mt-6">
        <CollectionsTable
          collections={collections}
          onChanged={onChanged}
          onError={(message) => showToast(message, "error")}
          onSuccess={(message) => showToast(message, "success")}
        />
      </div>

      <CollectionFormModal
        open={modalAberto}
        onOpenChange={setModalAberto}
        onCreated={() => {
          setModalAberto(false);
          showToast("Collection criada.", "success");
          onChanged();
        }}
      />

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}

export default function IngestaoDocumentosPage() {
  const [reloadKey, setReloadKey] = useState(0);
  const [collections, setCollections] = useState<RagCollection[]>([]);
  const { toasts, showToast, dismissToast } = useToast();

  const carregarColecoes = useCallback(async () => {
    try {
      setCollections(await listCollections());
    } catch (err) {
      showToast(
        err instanceof RagApiError ? err.message : "Erro inesperado ao carregar as collections.",
        "error",
      );
    }
  }, [showToast]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    carregarColecoes();
  }, [carregarColecoes]);

  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <h1 className="text-2xl font-semibold text-gray-900">Ingestão de documentos (RAG)</h1>
      <p className="mt-2 text-gray-600">Página interna, sem impacto na navegação pública do site.</p>

      <Tabs defaultValue="enviar" className="mt-8">
        <TabsList>
          <TabsTrigger value="enviar">Enviar documento</TabsTrigger>
          <TabsTrigger value="documentos">Documentos ingeridos</TabsTrigger>
          <TabsTrigger value="configuracao">Configuração</TabsTrigger>
          <TabsTrigger value="playground">Playground</TabsTrigger>
        </TabsList>
        <TabsContent value="enviar">
          <AbaEnviarDocumento collections={collections} onIngerido={() => setReloadKey((key) => key + 1)} />
        </TabsContent>
        <TabsContent value="documentos">
          <AbaDocumentosIngeridos key={reloadKey} collections={collections} />
        </TabsContent>
        <TabsContent value="configuracao">
          <AbaConfiguracao collections={collections} onChanged={carregarColecoes} />
        </TabsContent>
        <TabsContent value="playground">
          <PlaygroundPanel collections={collections} />
        </TabsContent>
      </Tabs>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
```

- [ ] **Step 4: Rodar os testes desta task (aceitável falhar só no que depende da Task 20)**

Run: `cd frontend && npx vitest run tests/components/IngestaoDocumentosPage.test.tsx`
Expected: FAIL só em `Cannot find module '@/components/admin/playground/PlaygroundPanel'` (import quebra o arquivo inteiro — todos os testes deste arquivo falham até a Task 20 criar o módulo; isso é esperado nesta task isolada). Não faça commit ainda — o Step 4 da Task 20 fecha isso.

- [ ] **Step 5: Commit (feito junto com a Task 20, já que os dois arquivos dependem um do outro para os testes passarem)**

Sem commit isolado aqui — ver Step final da Task 20.

---

### Task 20: Playground de busca comparativo (`PlaygroundForm`, `ComparisonResultCard`, `PlaygroundPanel`)

**Files:**
- Create: `frontend/components/admin/playground/PlaygroundForm.tsx`
- Create: `frontend/components/admin/playground/ComparisonResultCard.tsx`
- Create: `frontend/components/admin/playground/PlaygroundPanel.tsx`
- Create: `frontend/tests/components/PlaygroundPanel.test.tsx`

**Interfaces:**
- Consumes: `@/lib/api/rag` (`runPlaygroundSearch` — Task 16), `@/lib/types/rag` (`RagCollection`, `RagDomain`, `PlaygroundResultItem` — Task 15).
- Produces: `PlaygroundForm({collections, onSubmit, isSubmitting})`; `ComparisonResultCard({item})`; `PlaygroundPanel({collections})` (usado por `app/admin/ingestao/page.tsx`, Task 19).

- [ ] **Step 1: Escrever `frontend/tests/components/PlaygroundPanel.test.tsx`**

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PlaygroundPanel } from "@/components/admin/playground/PlaygroundPanel";
import type { RagCollection } from "@/lib/types/rag";

vi.mock("@/lib/api/rag", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/rag")>("@/lib/api/rag");
  return { ...actual, runPlaygroundSearch: vi.fn() };
});

import { RagApiError, runPlaygroundSearch } from "@/lib/api/rag";

const mockedRunSearch = vi.mocked(runPlaygroundSearch);

function collection(overrides: Partial<RagCollection>): RagCollection {
  return {
    id: "1",
    name: "docs_texto",
    embedding_model: "modelo",
    vector_dimension: 384,
    distance_metric: "cosine",
    chunk_size: 800,
    chunk_overlap: 100,
    hnsw_m: 16,
    hnsw_ef_construct: 100,
    hnsw_full_scan_threshold: 10000,
    hnsw_max_indexing_threads: 0,
    hnsw_on_disk: false,
    hnsw_payload_m: null,
    quantization_type: "none",
    quantization_config: {},
    payload_indexes: [],
    is_active: true,
    document_count: 0,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

const COLLECTION_A = collection({ id: "a", name: "collection-a" });
const COLLECTION_B = collection({ id: "b", name: "collection-b", is_active: false });

describe("PlaygroundPanel", () => {
  beforeEach(() => {
    mockedRunSearch.mockReset();
  });

  it("botão comparar fica desabilitado sem pergunta ou sem collection marcada", () => {
    render(<PlaygroundPanel collections={[COLLECTION_A, COLLECTION_B]} />);

    expect(screen.getByRole("button", { name: "Comparar" })).toBeDisabled();
  });

  it("roda a busca e renderiza um card por collection, com resultado e erro isolados", async () => {
    const user = userEvent.setup();
    mockedRunSearch.mockResolvedValueOnce({
      items: [
        {
          collection_id: "a",
          collection_name: "collection-a",
          latency_ms: 12.3,
          results: [{ content: "conteúdo de teste", source: "a.txt", score: 0.8 }],
        },
        {
          collection_id: "b",
          collection_name: "collection-b",
          error: "Serviço de RAG temporariamente indisponível.",
        },
      ],
    });

    render(<PlaygroundPanel collections={[COLLECTION_A, COLLECTION_B]} />);

    await user.type(screen.getByLabelText("Pergunta de teste"), "qual a garantia?");
    await user.click(screen.getByLabelText("collection-a"));
    await user.click(screen.getByLabelText("collection-b"));
    await user.click(screen.getByRole("button", { name: "Comparar" }));

    expect(mockedRunSearch).toHaveBeenCalledWith({
      query: "qual a garantia?",
      domain: "vendas",
      collection_ids: ["a", "b"],
    });
    expect(await screen.findByText("conteúdo de teste")).toBeInTheDocument();
    expect(screen.getByText("Serviço de RAG temporariamente indisponível.")).toBeInTheDocument();
  });

  it("exibe erro geral quando a chamada falha por inteiro", async () => {
    const user = userEvent.setup();
    mockedRunSearch.mockRejectedValueOnce(new RagApiError("Não foi possível rodar a busca."));

    render(<PlaygroundPanel collections={[COLLECTION_A]} />);

    await user.type(screen.getByLabelText("Pergunta de teste"), "pergunta");
    await user.click(screen.getByLabelText("collection-a"));
    await user.click(screen.getByRole("button", { name: "Comparar" }));

    expect(await screen.findByText("Não foi possível rodar a busca.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Rodar para ver a falha**

Run: `cd frontend && npx vitest run tests/components/PlaygroundPanel.test.tsx`
Expected: FAIL — `Cannot find module '@/components/admin/playground/PlaygroundPanel'`

- [ ] **Step 3: Implementar `frontend/components/admin/playground/PlaygroundForm.tsx`**

```tsx
"use client";

import { useState } from "react";

import type { RagCollection, RagDomain } from "@/lib/types/rag";

const DOMAIN_OPTIONS: { value: RagDomain; label: string }[] = [
  { value: "vendas", label: "Vendas" },
  { value: "suporte", label: "Suporte Técnico" },
  { value: "atendimento", label: "Atendimento ao Usuário" },
];

export interface PlaygroundFormProps {
  collections: RagCollection[];
  onSubmit: (params: { query: string; domain: RagDomain; collectionIds: string[] }) => void;
  isSubmitting: boolean;
}

export function PlaygroundForm({ collections, onSubmit, isSubmitting }: PlaygroundFormProps) {
  const [query, setQuery] = useState("");
  const [domain, setDomain] = useState<RagDomain>("vendas");
  const [selecionadas, setSelecionadas] = useState<string[]>([]);

  function alternarCollection(id: string) {
    setSelecionadas((atual) => (atual.includes(id) ? atual.filter((item) => item !== id) : [...atual, id]));
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim() || selecionadas.length === 0 || isSubmitting) return;
    onSubmit({ query, domain, collectionIds: selecionadas });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="playground-query" className="block text-sm font-medium text-gray-900">
          Pergunta de teste
        </label>
        <textarea
          id="playground-query"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          rows={3}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
        />
      </div>

      <div>
        <label htmlFor="playground-domain" className="block text-sm font-medium text-gray-900">
          Domínio
        </label>
        <select
          id="playground-domain"
          value={domain}
          onChange={(e) => setDomain(e.target.value as RagDomain)}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
        >
          {DOMAIN_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium text-gray-900">Collections a comparar</legend>
        {collections.map((collection) => (
          <label key={collection.id} className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={selecionadas.includes(collection.id)}
              onChange={() => alternarCollection(collection.id)}
            />
            {collection.name}
          </label>
        ))}
      </fieldset>

      <button
        type="submit"
        disabled={!query.trim() || selecionadas.length === 0 || isSubmitting}
        className="rounded-md bg-gray-900 px-4 py-2 text-sm text-white disabled:opacity-50"
      >
        {isSubmitting ? "Comparando..." : "Comparar"}
      </button>
    </form>
  );
}
```

- [ ] **Step 4: Implementar `frontend/components/admin/playground/ComparisonResultCard.tsx`**

```tsx
import type { PlaygroundResultItem } from "@/lib/types/rag";

export function ComparisonResultCard({ item }: { item: PlaygroundResultItem }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <h3 className="font-medium text-gray-900">{item.collection_name}</h3>

      {item.error ? (
        <p className="mt-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-800">{item.error}</p>
      ) : (
        <>
          {item.latency_ms !== undefined && item.latency_ms !== null && (
            <p className="mt-1 text-xs text-gray-500">{item.latency_ms.toFixed(0)} ms</p>
          )}
          {item.results && item.results.length > 0 ? (
            <ul className="mt-2 space-y-2">
              {item.results.map((resultado, indice) => (
                <li key={indice} className="rounded-md bg-gray-50 p-2 text-sm text-gray-700">
                  <p className="text-xs text-gray-500">
                    {resultado.source} — score {resultado.score.toFixed(3)}
                  </p>
                  <p>{resultado.content}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-gray-600">Nenhum resultado encontrado.</p>
          )}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Implementar `frontend/components/admin/playground/PlaygroundPanel.tsx`**

```tsx
"use client";

import { useState } from "react";

import { ComparisonResultCard } from "@/components/admin/playground/ComparisonResultCard";
import { PlaygroundForm } from "@/components/admin/playground/PlaygroundForm";
import { RagApiError, runPlaygroundSearch } from "@/lib/api/rag";
import type { PlaygroundResultItem, RagCollection, RagDomain } from "@/lib/types/rag";

export function PlaygroundPanel({ collections }: { collections: RagCollection[] }) {
  const [resultados, setResultados] = useState<PlaygroundResultItem[] | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(params: { query: string; domain: RagDomain; collectionIds: string[] }) {
    setIsSubmitting(true);
    setError(null);
    try {
      const response = await runPlaygroundSearch({
        query: params.query,
        domain: params.domain,
        collection_ids: params.collectionIds,
      });
      setResultados(response.items);
    } catch (err) {
      setError(err instanceof RagApiError ? err.message : "Erro inesperado ao rodar a busca.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      <p className="text-gray-600">
        Compare os resultados de busca da mesma pergunta em collections diferentes.
      </p>

      <div className="mt-6">
        <PlaygroundForm collections={collections} onSubmit={handleSubmit} isSubmitting={isSubmitting} />
      </div>

      {error && <p className="mt-6 rounded-md bg-red-50 px-4 py-3 text-red-800">{error}</p>}

      {resultados && (
        <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
          {resultados.map((item) => (
            <ComparisonResultCard key={item.collection_id} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Rodar os testes desta task**

Run: `cd frontend && npx vitest run tests/components/PlaygroundPanel.test.tsx`
Expected: PASS (todos)

- [ ] **Step 7: Rodar a suíte inteira do frontend (fecha a Task 19 também)**

Run: `cd frontend && npx vitest run`
Expected: PASS em tudo

- [ ] **Step 8: Verificar tipos do projeto inteiro**

Run: `cd frontend && npx tsc --noEmit`
Expected: sem erros

- [ ] **Step 9: Commit (fecha Tasks 19 e 20 juntas, já que os testes de uma dependem do código da outra)**

```bash
git add frontend/app/admin/ingestao/page.tsx frontend/tests/components/IngestaoDocumentosPage.test.tsx frontend/components/admin/playground/ frontend/tests/components/PlaygroundPanel.test.tsx
git commit -m "feat(rag): playground de busca comparativo e aba Configuração real no admin"
```

---

### Task 21: Documentação — `docs/ARCHITECTURE.md` §5 e `docs/ROADMAP.md`

**Files:**
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/ROADMAP.md`

**Interfaces:** nenhuma (só documentação) — mas é obrigatória por `CLAUDE.md` regras 5, 6 e 9: toda tarefa concluída atualiza o roadmap, decisão de arquitetura nova é registrada em `docs/ARCHITECTURE.md`, e documentação reflete o estado atual.

- [ ] **Step 1: Adicionar a nota em `docs/ARCHITECTURE.md` §5**

Inserir, logo depois do parágrafo que termina em `docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md.` (linha ~154, antes de `### Tabela de escopo por requisito`):

```markdown
**Decisão registrada (além do MVP, a pedido explícito, 2026-09-15):** o
registro de documentos acima evolui para **múltiplos perfis de collection**
configuráveis (chunk size/overlap, modelo de embedding, dimensão, métrica de
distância, HNSW, quantização de vetores, payload indexing do Qdrant) —
Entregas B e C+D anunciadas como "spec futura" na decisão anterior, agora
combinadas numa só entrega por ficarem interdependentes. Cada collection é um
perfil imutável (mudar um parâmetro é criar uma nova collection); uma delas é
marcada como "ativa" e é a que o chat de fato usa, enquanto as demais servem
para comparação num playground de busca administrativo (pergunta única
rodada contra várias collections, resultados/score/latência lado a lado, sem
métrica agregada de qualidade — isso continua reservado para a Fase 10,
Avaliação Experimental). Documentos ganham um arquivo original salvo em
disco (`backend/data/rag_uploads/`), permitindo reingerir o mesmo documento
em outra collection para comparação. Como a entrega anterior, **não faz
parte do MVP original** — fica registrada aqui e no roadmap para não ser
confundida com item do escopo original nem esquecida na revisão final (Fase
11). Detalhes de implementação:
`docs/superpowers/specs/2026-09-15-rag-collections-config-design.md`.
```

- [ ] **Step 2: Marcar as Entregas B e C+D como feitas em `docs/ROADMAP.md`**

Na seção "Extra fora do MVP — Registro e Configuração de Ingestão do RAG", trocar:

```markdown
- [ ] **Entrega B** — chunk size/overlap configuráveis por ingestão
- [ ] **Entrega C+D** — configuração avançada da collection do Qdrant
      (modelo de embedding/dimensão/métrica de distância, HNSW, quantização
      de vetores, payload indexing)
```

por:

```markdown
- [x] **Entregas B+C+D** — perfis de collection configuráveis (chunk
      size/overlap, modelo de embedding/dimensão/métrica de distância,
      HNSW, quantização de vetores, payload indexing) combinadas numa só
      entrega (ficaram interdependentes na sessão de brainstorming de
      2026-09-15), com playground de busca comparativo entre collections e
      reingestão de um documento em outra collection. Ver
      `docs/superpowers/specs/2026-09-15-rag-collections-config-design.md`.
```

- [ ] **Step 3: Commit**

```bash
git add docs/ARCHITECTURE.md docs/ROADMAP.md
git commit -m "docs: registra as Entregas B+C+D (perfis de collection do RAG) fora do MVP"
```

---

## Self-review desta plan

**Cobertura da spec:** §2 (Postgres como fonte de verdade) → Tasks 1-2; §3 (modelo de dados) → Task 1; §4 (criação de collection no Qdrant + nota de teste sobre backend local ignorar HNSW/quantização) → Task 4; §4.1 (wiring da busca ativa) → Tasks 5, 13; §5 (ingestão/reingestão/cache de embedders) → Tasks 3, 7; §6.1 (API de collections) → Task 11; §6.2 (API de documentos) → Task 10; §6.3 (playground) → Task 12; §7 (frontend) → Tasks 15-20; §8 (testes) → embutido em cada task; §9 (registro em ARCHITECTURE.md) → Task 21; §10 (não-objetivos) → respeitado em todas as tasks (sem edição de collection existente, sem benchmark formal, sem quota, sem `top_k`/`score_threshold` configuráveis). CLAUDE.md regra 5 (roadmap) → Task 21.

**Inconsistência encontrada e corrigida:** a primeira versão da Task 11 usava `_FakeQdrantRAGClient` (que só implementa `upsert_chunks`/`delete_by_document_id`/`drop_collection`) para testar `POST /api/rag/collections`, que chama `qdrant.create_collection(...)` — método inexistente no fake. Corrigido trocando para o `QdrantRAGClient` real contra Qdrant em memória (mesmo padrão da Task 4), o que também eliminou a ambiguidade `asyncio.run` vs. `async def` que a primeira versão deixava para quem fosse executar decidir.

**Consistência de tipos/assinaturas verificada:** `ingest_bytes`/`ingest_file`/`ingest_directory`/`reingest_document` (Task 7) são chamados com a mesma assinatura nas Tasks 7 e 10; `QdrantRAGClient.create_collection`/`upsert_chunks`/`search`/`delete_by_document_id` (Task 4) usados consistentemente nas Tasks 5, 7, 10, 11, 12; `collections_registry.*` (Task 2) usado com os mesmos nomes de parâmetro em todas as tasks que o chamam nos testes (6, 7, 10, 11); os tipos TypeScript de `RagCollection`/`CollectionCreatePayload`/`DocumentRegistryEntry`/`PlaygroundResultItem` (Task 15) espelham exatamente os campos dos schemas Pydantic correspondentes (Task 8) — incluindo a assimetria deliberada entre `CollectionCreateRequest` (entrada, HNSW/quantização aninhados) e `CollectionResponse` (saída, campos `hnsw_*`/`quantization_*` no nível raiz, espelhando as colunas do banco).
