"""Schemas Pydantic do endpoint de chat (R2, R3).

Contrato espelhado em `docs/FRONTEND.md` §4 (`POST /api/chat/messages`).
"""

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    """Corpo de `POST /api/chat/messages`."""

    message: str = Field(..., min_length=1, description="Texto da mensagem do usuário.")
    conversation_id: str | None = Field(
        default=None,
        description="ID da conversa a retomar; se omitido, uma nova conversa é criada.",
    )
    # MVP: campo de áudio reservado, processamento (STT) ainda não implementado
    # (ver backend/src/app/stt/__init__.py e docs/ROADMAP.md, Fase 2). O valor
    # é aceito para não quebrar o contrato do frontend, mas é ignorado pelo
    # orchestrator — nenhum STT é executado sobre ele nesta tarefa.
    audio: str | None = Field(
        default=None,
        description=(
            "Áudio da mensagem (ex.: base64), reservado para STT — não processado nesta fase."
        ),
    )


class ChatMessageResponse(BaseModel):
    """Resposta de `POST /api/chat/messages`."""

    conversation_id: str
    message: str = Field(..., description="Texto da resposta do assistente.")
    domain: str = Field(..., description="Domínio identificado pelo roteador (R3, R7).")
    backend_used: str = Field(..., description='"local" ou "externo".')
    escalation_reason: str = Field(
        ..., description='"nenhum", "fora_escopo", "rag_vazio" ou "complexidade_alta".'
    )
