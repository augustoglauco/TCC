"""Schemas Pydantic do endpoint de chat (R2, R3, R5).

Contrato espelhado em `docs/FRONTEND.md` §4 (`POST /api/chat/messages`).
"""

from pydantic import BaseModel, Field, model_validator


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


class ChatMessageResponse(BaseModel):
    """Resposta de `POST /api/chat/messages`."""

    conversation_id: str
    message: str = Field(..., description="Texto da resposta do assistente.")
    domain: str = Field(..., description="Domínio identificado pelo roteador (R3, R7).")
    backend_used: str = Field(..., description='"local" ou "externo".')
    escalation_reason: str = Field(
        ..., description='"nenhum", "fora_escopo", "rag_vazio" ou "complexidade_alta".'
    )
    # MVP: só preenchido quando o request trouxe `audio` — é como o frontend
    # exibe "o texto transcrito na bolha do usuário" (docs/FRONTEND.md §3),
    # já que a transcrição só existe no backend, não no cliente.
    transcribed_message: str | None = Field(
        default=None, description="Texto transcrito do áudio enviado, quando aplicável."
    )
