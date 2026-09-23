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
    # "chat" (default): collection elegível a ser ativada e buscada pelo chat
    # público. "mcp_b2b": collection de conteúdo restrito ao canal MCP B2B —
    # nunca pode ser ativada nem buscada pelo chat (ver
    # docs/superpowers/specs/2026-09-21-ingestao-mcp-b2b-design.md §2/§4).
    purpose: Mapped[str] = mapped_column(default="chat")
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


class CrawlerPendingPage(Base):
    """Página crawleada com confiança de classificação abaixo do limiar,
    aguardando aprovação manual (R4, crawler de páginas) — ver
    docs/superpowers/specs/2026-09-19-crawler-paginas-design.md §"Dados".

    Deletada ao aprovar ou rejeitar — a tabela só reflete o que está
    pendente agora, sem histórico de decisões passadas. `url` é `unique`:
    recrawlear a mesma URL ainda pendente atualiza esta linha em vez de
    duplicar (upsert, ver `app.rag.crawler_pending.upsert_pending_page`).
    """

    __tablename__ = "crawler_pending_pages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    url: Mapped[str] = mapped_column(unique=True)
    extracted_text: Mapped[str]
    domain_proposed: Mapped[str]
    confidence: Mapped[float]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TomEscalonamento(Base):
    """Caso de escalonamento do Monitor de Tom (R8, Fase 4B) — ver
    docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md §5.

    Append-only: cada linha é o momento em que uma conversa escalou pela
    primeira vez (o estado "já escalada", que evita repetir o alerta, vive
    em memória em `app.router.tone_monitor._conversas_escaladas`, não
    nesta tabela). Sem mecanismo de "des-escalar" — decisão aceita da spec.
    """

    __tablename__ = "tom_escalonamentos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[str]
    mensagem: Mapped[str]
    motivo: Mapped[str | None]
    confianca: Mapped[float]
    provider_efetivo: Mapped[str]
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
