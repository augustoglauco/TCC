"""Modelos SQLAlchemy do backend (primeiro uso real do Postgres — ver
docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md).
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

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
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class Produto(Base):
    """Backend único de catálogo/estoque/preços (R12, Fase 5) — reaproveitado
    tanto pelo RAG (R4, leitura genérica via `app.rag.db_connector`) quanto
    pelo futuro servidor MCP B2B (recursos de leitura + ferramentas
    transacionais, ver `docs/ARCHITECTURE.md` §6).

    Estende a tabela fixture `produtos` já criada pela migração `0003`
    (antes só um exemplo para o conector de BD do RAG, sem model SQLAlchemy
    dedicado) em vez de duplicar um schema paralelo — decisão registrada em
    `docs/ARCHITECTURE.md` §5. Os campos técnicos (`especificacoes_tecnicas`,
    `dimensoes_cm`, `peso_kg`) cobrem o recurso "catálogo de produtos" do R12;
    `preco` (já existente) + `preco_promocional`/`promocao_valida_ate` cobrem
    o recurso "tabela de preços"; estoque e desconto por volume ficam em
    tabelas relacionadas próprias (`ProdutoEstoque`, `ProdutoDescontoVolume`),
    porque são "um produto para N linhas" (N centros de distribuição, N
    faixas de desconto), não caberiam bem como colunas únicas.

    # MVP: "manuais e documentação" (o quarto recurso do R12) **não** vira
    # linha nesta tabela nem tabela nova — continuam sendo documentos RAG
    # normais (PDF/texto ingeridos via `app.rag.ingest`, collection
    # `purpose="mcp_b2b"` para o conteúdo exclusivo do canal B2B, ver decisão
    # de 2026-09-21 em `docs/ARCHITECTURE.md` §5). Manuais são texto longo
    # não-estruturado — forçá-los em colunas de banco duplicaria o pipeline
    # de busca semântica que o RAG já resolve bem; o "backend único" do R12
    # cobre os três recursos estruturados (catálogo, estoque, preços), o
    # quarto recurso (manuais) é servido pela infraestrutura RAG já existente.
    """

    __tablename__ = "produtos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nome: Mapped[str]
    descricao: Mapped[str]
    preco: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    categoria: Mapped[str]
    especificacoes_tecnicas: Mapped[str | None]
    dimensoes_cm: Mapped[str | None]
    peso_kg: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    preco_promocional: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    promocao_valida_ate: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    estoques: Mapped[list["ProdutoEstoque"]] = relationship(
        back_populates="produto", cascade="all, delete-orphan"
    )
    descontos_volume: Mapped[list["ProdutoDescontoVolume"]] = relationship(
        back_populates="produto", cascade="all, delete-orphan"
    )


class ProdutoEstoque(Base):
    """Quantidade disponível de um produto por centro de distribuição (R12).

    # MVP: "em tempo real" significa "lido a cada consulta" — não há stream/
    # webhook de atualização de estoque de um sistema externo (não existe tal
    # sistema neste protótipo); atualizações são feitas diretamente nesta
    # tabela via `app.db.catalog.atualizar_estoque`. Sem tratamento de
    # concorrência em reservas/pedidos (lock otimista/pessimista) — fora do
    # MVP por decisão explícita (`docs/ARCHITECTURE.md` §6, "Governança e
    # segurança"), fica para quando a ferramenta de reserva/pedido existir.
    """

    __tablename__ = "produto_estoque"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), index=True)
    centro_distribuicao: Mapped[str]
    quantidade: Mapped[int]
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    produto: Mapped["Produto"] = relationship(back_populates="estoques")


class ProdutoDescontoVolume(Base):
    """Faixa de desconto por quantidade mínima comprada (R12) — parte do
    recurso "tabela de preços" (`docs/ARCHITECTURE.md` §6: "descontos por
    volume e campanhas"). `percentual_desconto` é aplicado sobre `preco` (ou
    `preco_promocional`, quando vigente) quando a quantidade cotada atinge
    `quantidade_minima` — a lógica de aplicação em si (cotação automática) é
    a ferramenta MCP de um item futuro desta mesma fase, não implementada
    aqui.
    """

    __tablename__ = "produto_descontos_volume"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), index=True)
    quantidade_minima: Mapped[int]
    percentual_desconto: Mapped[Decimal] = mapped_column(Numeric(5, 2))

    produto: Mapped["Produto"] = relationship(back_populates="descontos_volume")
