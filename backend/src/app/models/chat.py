"""Schemas Pydantic do endpoint de chat (R2, R3, R5).

Contrato espelhado em `docs/FRONTEND.md` §4 (`POST /api/chat/messages`).
"""

from pydantic import BaseModel, Field, model_validator


class RagChunkMetric(BaseModel):
    """Fonte (arquivo ingerido) e score de um chunk usado no contexto do RAG."""

    source: str = Field(..., description="Nome do arquivo de origem do chunk.")
    score: float = Field(..., description="Score de similaridade do chunk na busca vetorial.")


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

    @model_validator(mode="after")
    def _message_ou_audio_obrigatorio(self) -> "ChatMessageRequest":
        if not self.message and not self.audio:
            raise ValueError("Informe 'message' e/ou 'audio'.")
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
    estimated_cost_usd: float | None = Field(
        default=None, description="Custo estimado da requisição em USD."
    )
    rag_retrieval_ms: float | None = Field(
        default=None, description="Tempo de busca vetorial no RAG em ms."
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
