"""Modelos SQLAlchemy do backend (primeiro uso real do Postgres — ver
docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md).
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
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
    uma nova collection. Cada purpose ("chat", "mcp_b2b", "admin") pode ter
    uma linha com `is_active=True` por vez, garantido na aplicação
    (`app.rag.collections_registry.activate_collection`), não por constraint de banco.
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
    # Finalidade da collection: "chat" (pública do visitante), "mcp_b2b" (parceiros B2B),
    # ou "admin" (uso interno da administração). Cada propósito possui sua collection ativa.
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
    preco_base_fornecedor: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    imagem_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    estoques: Mapped[list[ProdutoEstoque]] = relationship(
        back_populates="produto", cascade="all, delete-orphan"
    )
    descontos_volume: Mapped[list[ProdutoDescontoVolume]] = relationship(
        back_populates="produto", cascade="all, delete-orphan"
    )
    imagens: Mapped[list[ProdutoImagem]] = relationship(
        back_populates="produto",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )


class ProdutoImagem(Base):
    """Associação de imagens físicas e vetoriais ao catálogo de produtos."""

    __tablename__ = "produto_imagens"
    __mapper_args__ = {"confirm_deleted_rows": False}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    produto_id: Mapped[int] = mapped_column(
        ForeignKey("produtos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    imagem_url: Mapped[str] = mapped_column(String(500), nullable=False)
    clip_image_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_principal: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    produto: Mapped[Produto] = relationship(back_populates="imagens")


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

    produto: Mapped[Produto] = relationship(back_populates="estoques")


class ProdutoCompatibilidade(Base):
    """Par de produtos compatíveis entre si (R12, Fase 5, ferramenta
    "validação de compatibilidade") — ver decisão registrada em
    `docs/ARCHITECTURE.md` §5 (2026-09-24).

    A linha é direcional na escrita (`produto_id` -> `compativel_com_id`),
    mas a consulta (`app.db.catalog.sao_compativeis`) verifica os dois
    sentidos — "A compatível com B" implica "B compatível com A" do ponto de
    vista de quem consulta, sem duplicar a escrita com uma segunda linha
    invertida.

    # MVP: pares cadastrados manualmente via fixture de migração (mesmo
    # padrão dos 5 produtos/estoque/descontos já semeados na migração 0008)
    # — sem regra automática de dedução por categoria/especificação técnica;
    # evolução futura, não este item.
    """

    __tablename__ = "produto_compatibilidades"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), index=True)
    compativel_com_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), index=True)


class Pedido(Base):
    """Cabeçalho de uma reserva/pedido (R12, Fase 5, ferramenta "reserva ou
    pedido") — ver decisão registrada em `docs/ARCHITECTURE.md` §5
    (2026-09-24).

    # MVP: sem lock otimista/pessimista (corrida entre duas reservas
    # concorrentes pode sobre-reservar), sem trilha de auditoria, sem
    # pagamento/gateway real — simplificação já registrada na modelagem do
    # backend único desta fase (`docs/ARCHITECTURE.md` §6, "Governança e
    # segurança", evolução futura explícita). `status` fica sempre
    # `"reservado"` neste protótipo (sem fluxo de confirmação/cancelamento).
    """

    __tablename__ = "pedidos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(default="reservado")
    user_email: Mapped[str | None] = mapped_column(index=True, nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(index=True, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    itens: Mapped[list[PedidoItem]] = relationship(
        back_populates="pedido", cascade="all, delete-orphan"
    )


class PedidoItem(Base):
    """Item de um pedido/reserva — produto, quantidade e o preço unitário
    vigente no momento da reserva (não recalculado depois, mesmo que o
    preço do produto mude)."""

    __tablename__ = "pedido_itens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    pedido_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pedidos.id"), index=True)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), index=True)
    centro_distribuicao: Mapped[str]
    quantidade: Mapped[int]
    preco_unitario: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    pedido: Mapped[Pedido] = relationship(back_populates="itens")


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

    produto: Mapped[Produto] = relationship(back_populates="descontos_volume")


class Conversa(Base):
    """Uma conversa do chat (R9, Fase 6) — ver decisão de 2026-09-25 em
    `docs/ARCHITECTURE.md` §5. `id` é o mesmo `conversation_id` que o widget
    guarda no `localStorage`.

    # MVP: um visitante = um navegador, sem login. `email`/`perfil` (R10)
    # ficam aqui mesmo, sem tabela de visitante separada.
    """

    __tablename__ = "conversas"

    id: Mapped[str] = mapped_column(primary_key=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # Resumo automático periódico (R9) e quantas mensagens ele já cobre.
    resumo: Mapped[str | None]
    mensagens_resumidas: Mapped[int] = mapped_column(default=0)
    # Classificação do usuário (R10).
    email: Mapped[str | None]
    perfil: Mapped[str | None]
    perfil_motivo: Mapped[str | None]

    # Status e encerramento (Contabilizador de Tokens e Ciclo de Vida do Chat)
    status: Mapped[str] = mapped_column(String(20), default="aberta", server_default="aberta", index=True)
    encerrada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    motivo_encerramento: Mapped[str | None] = mapped_column(String(50), nullable=True)

    mensagens: Mapped[list[ConversaMensagem]] = relationship(
        back_populates="conversa", order_by="ConversaMensagem.id"
    )


class ConversaMensagem(Base):
    """Uma mensagem de uma conversa: do cliente ou a resposta do assistente
    (R9). `id` inteiro autoincremental dá a ordem de gravação — duas
    mensagens gravadas no mesmo instante teriam o mesmo `criada_em`."""

    __tablename__ = "conversa_mensagens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversa_id: Mapped[str] = mapped_column(ForeignKey("conversas.id"), index=True)
    papel: Mapped[str]  # "cliente" | "assistente"
    texto: Mapped[str]
    # Domínio da resposta (só nas mensagens do assistente) — usado pela
    # classificação do usuário (R10: intenção de compra).
    dominio: Mapped[str | None]
    # Métricas do evento `done` da resposta (modelo, tokens, latência, RAG,
    # perfil) — o painel ⚙️ reaparece nas mensagens recarregadas (R9).
    metricas: Mapped[dict | None] = mapped_column(_JsonVariant, nullable=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversa: Mapped[Conversa] = relationship(back_populates="mensagens")


class Cliente(Base):
    """Base de clientes fictícia (R10, Fase 6) — ver decisão de 2026-09-25 em
    `docs/ARCHITECTURE.md` §5. O e-mail captado na conversa é cruzado com
    esta tabela para classificar o visitante (Cliente/Esporádico).

    # MVP: base fictícia semeada na migração `0011`, sem cadastro pelo site.
    """

    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    nome: Mapped[str]
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    compras: Mapped[list[ClienteCompra]] = relationship(back_populates="cliente")


class ClienteCompra(Base):
    """Compra de um cliente (R10) — quantidade e recência definem se ele é
    Cliente ou Esporádico."""

    __tablename__ = "cliente_compras"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), index=True)
    produto_id: Mapped[int | None] = mapped_column(ForeignKey("produtos.id"))
    quantidade: Mapped[int]
    valor_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    comprado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cliente: Mapped[Cliente] = relationship(back_populates="compras")


class Agendamento(Base):
    """Registro de agendamento de visita técnica ou comercial (R11, Fase 7).
    Sincronizado com o Google Calendar via MCP."""

    __tablename__ = "agendamentos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_email: Mapped[str] = mapped_column(String, index=True)
    nome_cliente: Mapped[str] = mapped_column(String)
    telefone: Mapped[str | None] = mapped_column(String, nullable=True)
    data_hora_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    data_hora_fim: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="confirmado", index=True)
    origem: Mapped[str] = mapped_column(String, default="chat")
    google_event_id: Mapped[str | None] = mapped_column(String, nullable=True)
    google_event_link: Mapped[str | None] = mapped_column(String, nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ModelCharacteristics(Base):
    """Características de um modelo (multimodalidade, contexto, specs),
    buscadas em fontes externas (OpenRouter/Ollama/Hugging Face) e
    cacheadas — ver docs/superpowers/specs/2026-10-03-caracteristicas-
    modelo-hover-design.md. Staleness de 7 dias; refresh manual disponível
    via endpoint dedicado.

    # MVP: cache por tag exata, sem normalização entre fontes (a mesma
    # família de modelo pode aparecer como linhas separadas se buscada via
    # OpenRouter e via Ollama) — cada fonte+tag é uma unidade independente.
    """

    __tablename__ = "model_characteristics"
    __table_args__ = (
        UniqueConstraint("source", "tag", name="uq_model_characteristics_source_tag"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source: Mapped[str]
    tag: Mapped[str]
    is_multimodal: Mapped[bool] = mapped_column(Boolean, default=False)
    input_modalities: Mapped[list] = mapped_column(_JsonVariant, default=list)
    output_modalities: Mapped[list] = mapped_column(_JsonVariant, default=list)
    context_length: Mapped[int | None]
    parameter_size: Mapped[str | None]
    quantization: Mapped[str | None]
    pricing_prompt_per_1k: Mapped[float | None]
    pricing_completion_per_1k: Mapped[float | None]
    knowledge_cutoff: Mapped[str | None]
    raw_payload: Mapped[dict] = mapped_column(_JsonVariant, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AppSetting(Base):
    """Parâmetros de configuração e execução persistidos no banco."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[object] = mapped_column(_JsonVariant, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AdminChart(Base):
    """Gráficos dinâmicos gerados via chat pelo Administrador e persistidos
    para exibição no painel permanente /admin/dashboards.
    """

    __tablename__ = "admin_charts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    tipo_grafico: Mapped[str] = mapped_column(String(50), nullable=False)
    config_json: Mapped[dict] = mapped_column(_JsonVariant, nullable=False, default=dict)
    dados_json: Mapped[list] = mapped_column(_JsonVariant, nullable=False, default=list)
    sql_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    fixado: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    ordem: Mapped[int] = mapped_column(default=0, index=True)
    criado_por: Mapped[str] = mapped_column(String(255), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IngestionCostEvent(Base):
    """Eventos de telemetria e custo de processamento com modelos externos
    fora do fluxo de chat de clientes (ex: Crawler de páginas web, extração de
    catálogos de produtos via visão computacional, etc).
    """

    __tablename__ = "ingestion_cost_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_identifier: Mapped[str | None] = mapped_column(String(500), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(default=0)
    completion_tokens: Mapped[int] = mapped_column(default=0)
    cost_prompt_usd: Mapped[float] = mapped_column(default=0.0)
    cost_completion_usd: Mapped[float] = mapped_column(default=0.0)
    total_cost_usd: Mapped[float] = mapped_column(default=0.0)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

