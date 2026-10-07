"""Schemas Pydantic do endpoint de chat (R2, R3, R5).

Contrato espelhado em `docs/FRONTEND.md` §4 (`POST /api/chat/messages`).
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


class RagChunkMetric(BaseModel):
    """Fonte (arquivo ingerido) e score de um chunk usado no contexto do RAG."""

    source: str = Field(..., description="Nome do arquivo de origem do chunk.")
    score: float = Field(..., description="Score de similaridade do chunk na busca vetorial.")


class CardProduto(BaseModel):
    """Card rico de produto (Fase 8) — um único produto resolvido em Vendas
    (`app.router.sales_catalog.SalesCatalogClient.consultar_detalhes`) sem
    cotação por quantidade. Ver docs/ARCHITECTURE.md §5 (2026-09-29)."""

    tipo: Literal["produto"] = "produto"
    produto_id: int
    nome: str
    preco: Decimal
    imagem_url: str | None = None
    estoque_total: int


class CardCotacao(BaseModel):
    """Card rico de cotação (Fase 8, R12) — mesmo produto único de
    `CardProduto`, mas com quantidade e desconto por volume já calculados
    (cliente informou uma quantidade na mensagem)."""

    tipo: Literal["cotacao"] = "cotacao"
    produto_id: int
    nome: str
    quantidade: int
    preco_unitario: Decimal
    percentual_desconto: Decimal
    subtotal: Decimal


class CardAgendamento(BaseModel):
    """Card rico de confirmação de agendamento (Fase 8, R11) — emitido só
    quando o evento é criado de verdade no Google Calendar."""

    tipo: Literal["agendamento"] = "agendamento"
    data_hora_inicio: datetime
    data_hora_fim: datetime
    google_event_link: str | None = None


class CardGrafico(BaseModel):
    """Card rico de gráfico analítico dinâmico gerado via chat (Dashboards)."""

    tipo: Literal["grafico"] = "grafico"
    chart_id: str
    titulo: str
    tipo_grafico: Literal["bar", "line", "pie", "area", "donut"]
    config: dict = Field(default_factory=dict)
    dados: list[dict] = Field(default_factory=list)
    fixado: bool = True


class CardDocumentoDownload(BaseModel):
    """Card rico de download de documento fonte do RAG (Fase 8, além do MVP)."""

    tipo: Literal["documento_download"] = "documento_download"
    documento_id: str = Field(..., description="UUID do documento na tabela rag_documents.")
    filename: str = Field(..., description="Nome do arquivo (ex.: Manual_GD30.pdf).")
    domain: str = Field(..., description="Domínio do documento (suporte, vendas, etc).")
    score: float = Field(..., description="Score de similaridade do melhor chunk.")
    download_url: str = Field(..., description="URL para download direto no backend.")
    file_size_bytes: int | None = Field(default=None, description="Tamanho do arquivo em bytes.")


# União discriminada por "tipo" — cobre produto, cotação, agendamento, gráficos
# dinâmicos e o card de download do documento-fonte do RAG
ChatCard = Annotated[
    CardProduto | CardCotacao | CardAgendamento | CardGrafico | CardDocumentoDownload,
    Field(discriminator="tipo"),
]


class ChatMessageRequest(BaseModel):
    """Corpo de `POST /api/chat/messages`."""

    # MVP: `message` é opcional para permitir o caso de áudio puro (widget de
    # chat gravando pelo microfone, sem digitar nada) — o validador abaixo
    # garante que pelo menos um dos dois (message ou audio) venha preenchido.
    message: str | None = Field(
        default=None, min_length=1, description="Texto da mensagem do usuário."
    )
    conversation_id: str | None = Field(
        default=None,
        description="ID da conversa a retomar; se omitido, uma nova conversa é criada.",
    )
    # MVP: quando preenchido, é decodificado e transcrito via STT local
    # (faster-whisper, ver `backend/src/app/stt/whisper_client.py`) antes de
    # chegar ao orchestrator — suporta wav e mp3 (formato detectado pelo
    # conteúdo, não pela extensão). Limitações que restam: sem robustez a
    # áudio ruidoso/silencioso, sem VAD, transcrição em português fixo (ver
    # docs/ARCHITECTURE.md §5/§7).
    audio: str | None = Field(
        default=None,
        description="Áudio da mensagem em base64 (ex.: wav, mp3) — processado via STT (R5).",
    )
    # MVP: fluxo de imagem (ver docs/ARCHITECTURE.md §4). O PADRÃO para
    # qualquer imagem enviada é a IDENTIFICAÇÃO DE PRODUTO (CLIP → visão
    # externa → RAG texto). O OCR é a exceção, acionado só quando o sistema
    # solicitou um comprovante/documento — sinalizado por
    # `image_intent="documento"`. O cliente nunca envia imagem para OCR sem
    # solicitação.
    image: str | None = Field(
        default=None,
        description="Imagem em base64 (PNG/JPG/WEBP). Ver image_intent para o tratamento.",
    )
    image_intent: str | None = Field(
        default=None,
        description=(
            'Tratamento da imagem: "documento" = OCR (só quando o sistema '
            'pede comprovante); ausente ou "produto" = identificação de '
            "produto (padrão)."
        ),
    )
    user_email: str | None = Field(
        default=None,
        description="E-mail do usuário autenticado no frontend (R10, Fase 7).",
    )
    auth_token: str | None = Field(
        default=None,
        description=(
            "Token retornado por POST /api/auth/login quando o visitante está "
            "logado no frontend. Verificado no servidor (nunca confiado só pelo "
            "valor) para liberar o modo admin de busca no RAG — ver "
            "verificar_admin_por_token, decisão de 2026-09-30 em "
            "docs/ARCHITECTURE.md §6. Não usar user_email sozinho para isso: é "
            "um campo livre, nunca validado contra sessão nenhuma."
        ),
    )

    @model_validator(mode="after")
    def _message_ou_audio_obrigatorio(self) -> ChatMessageRequest:
        if not self.message and not self.audio and not self.image:
            raise ValueError("Informe 'message', 'audio' e/ou 'image'.")
        return self


class ChatDoneEventData(BaseModel):
    """Payload do evento `done` do stream SSE (telemetria completa da
    resposta) — ver docs/FRONTEND.md §4 e
    docs/superpowers/specs/2026-09-17-chat-streaming-sse-design.md."""

    domain: str = Field(..., description="Domínio identificado pelo roteador (R3, R7).")
    backend_used: str = Field(..., description='"local" ou "externo".')
    escalation_reason: str = Field(
        ..., description='"nenhum", "fora_escopo", "rag_vazio" ou "complexidade_alta".'
    )
    model_name: str | None = Field(
        default=None, description="Nome do modelo de LLM que gerou a resposta."
    )
    prompt_tokens: int | None = Field(
        default=None, description="Quantidade de tokens de entrada (prompt)."
    )
    completion_tokens: int | None = Field(
        default=None, description="Quantidade de tokens de saída (resposta)."
    )
    total_tokens: int | None = Field(
        default=None, description="Quantidade total de tokens (prompt + completion)."
    )
    latency_ms: float | None = Field(
        default=None, description="Tempo total de latência da resposta em ms."
    )
    ttft_ms: float | None = Field(
        default=None, description="Tempo do primeiro token (Time To First Token) em ms."
    )
    tps: float | None = Field(
        default=None, description="Taxa de geração de tokens por segundo (Tokens/s)."
    )
    confidence: float | None = Field(
        default=None, description="Confiança na classificação do roteador."
    )
    complexity: str | None = Field(default=None, description="Complexidade estimada da mensagem.")
    cost_prompt_usd: float | None = Field(
        default=0.0, description="Custo dos tokens de entrada (prompt) em USD."
    )
    cost_completion_usd: float | None = Field(
        default=0.0, description="Custo dos tokens de saída (resposta) em USD."
    )
    estimated_cost_usd: float | None = Field(
        default=None, description="Custo estimado da requisição em USD."
    )
    rag_retrieval_ms: float | None = Field(
        default=None,
        description=(
            "Tempo do bloco de recuperação em ms — busca RAG e, em mensagens "
            "de Vendas com integração do catálogo, a consulta de vendas "
            "concorrente (as duas rodam em paralelo)."
        ),
    )
    rag_chunks_count: int | None = Field(
        default=None, description="Quantidade de chunks recuperados do RAG."
    )
    rag_avg_score: float | None = Field(
        default=None, description="Score médio de similaridade dos chunks do RAG."
    )
    rag_chunks: list[RagChunkMetric] | None = Field(
        default=None,
        description="Fonte e score de cada chunk do RAG, na ordem devolvida pela busca.",
    )
    router_provider: str | None = Field(
        default=None,
        description='Provedor de roteamento utilizado ("heuristica_llm" ou "jev_openrouter"). '
        "None quando a resposta não passou por classificação de intenção "
        "(ex.: caminho de identificação de imagem).",
    )
    perfil_usuario: Literal["cliente", "esporadico", "lead", "nao_classificado"] | None = Field(
        default=None,
        description="Classificação do visitante (R10, Fase 6). None quando a memória "
        "da conversa está indisponível ou a resposta não foi gravada.",
    )
    perfil_motivo: str | None = Field(
        default=None, description="Por que o visitante recebeu esse perfil (R10)."
    )
    vision_used: bool | None = Field(
        default=None,
        description="Indica se a resposta envolveu identificação de imagem / visão computacional.",
    )
    card: ChatCard | None = Field(
        default=None,
        description="Card rico opcional (Fase 8) — produto, cotação ou confirmação de "
        "agendamento, para o frontend renderizar em vez de/além do texto.",
    )


class ConversaMensagemOut(BaseModel):
    """Uma mensagem gravada da conversa (R9, Fase 6).

    Achado de 2026-10-06: `papel` não incluía `"atendente"` (Fase 4,
    atendimento humano) — `GET /api/chat/conversations/{id}` quebrava com
    `ValidationError` (500) assim que a conversa tinha uma mensagem do
    atendente, derrubando o histórico inteiro (não só a mensagem dele) para
    o cliente que reabria/recarregava o chat.
    """

    papel: Literal["cliente", "assistente", "atendente"]
    texto: str
    dominio: str | None = None
    criada_em: datetime
    # Só preenchido em mensagens do atendente (papel="atendente").
    atendente_nome: str | None = None
    # Conteúdo do evento `done` da resposta (só nas mensagens do assistente;
    # `None` nas gravadas antes da migração 0012).
    metricas: dict | None = None


class ConversaHistoricoOut(BaseModel):
    """Corpo de `GET /api/chat/conversations/{id}` — o widget usa para
    reexibir o histórico ao reabrir o chat (R9). Não inclui o e-mail do
    visitante; o perfil vem só dentro das métricas de cada resposta, como no
    painel ⚙️."""

    conversation_id: str
    status: str = "aberta"
    encerrada_em: datetime | None = None
    motivo_encerramento: str | None = None
    resumo: str | None = None
    mensagens: list[ConversaMensagemOut]


class ConversaCloseRequest(BaseModel):
    """Corpo opcional de `POST /api/chat/conversations/{id}/close`."""

    motivo: str = Field(
        default="manual_usuario",
        description='Motivo do encerramento ("manual_usuario", "manual_admin", "inatividade").',
    )


class ConversaCloseResponse(BaseModel):
    """Resposta de `POST /api/chat/conversations/{id}/close`."""

    conversation_id: str
    status: str
    encerrada_em: datetime | None = None
    motivo_encerramento: str | None = None
