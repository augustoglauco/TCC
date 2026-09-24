"""Schema Pydantic do endpoint de listagem do Monitor de Tom (R8, Fase 4B)
— ver docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md §6.2.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class EscalonamentoResponse(BaseModel):
    id: UUID
    conversation_id: str
    mensagem: str
    motivo: str | None
    confianca: float
    provider_efetivo: str
    criado_em: datetime
