"""Máquina de estado do agendamento de visita (R11, Fase 4A).

Lógica de domínio pura (sem I/O de LLM/MCP, sem tipos de streaming SSE) —
consumida por `app.router.orchestrator`, que faz a ponte com o protocolo de
streaming e chama o MCP de verdade. Ver
docs/superpowers/specs/2026-09-21-agendamento-mcp-calendar-design.md.

# MVP: estado de agendamento guardado em memória por `conversation_id`
(dict de processo), mesmo padrão MVP de `_conversation_history` em
`app.api.chat` — perdido em restart do processo, sem persistência em banco
(a persistência de conversa é Fase 6, ainda não implementada).
"""

from datetime import datetime

from pydantic import BaseModel

_CAMPOS_OBRIGATORIOS = ("data_hora", "nome", "email", "telefone")


class BookingSlots(BaseModel):
    data_hora: datetime | None = None
    nome: str | None = None
    email: str | None = None
    telefone: str | None = None
    awaiting_confirmation: bool = False

    def is_complete(self) -> bool:
        return all(getattr(self, campo) is not None for campo in _CAMPOS_OBRIGATORIOS)

    def missing_fields(self) -> list[str]:
        return [campo for campo in _CAMPOS_OBRIGATORIOS if getattr(self, campo) is None]


_booking_slots: dict[str, BookingSlots] = {}


def get_booking_slots(conversation_id: str) -> BookingSlots:
    return _booking_slots.get(conversation_id, BookingSlots())


def set_booking_slots(conversation_id: str, slots: BookingSlots) -> None:
    _booking_slots[conversation_id] = slots


def clear_booking_slots(conversation_id: str) -> None:
    _booking_slots.pop(conversation_id, None)


def reset_all_booking_slots() -> None:
    """Limpa o estado em memória — usado pelos testes para isolar casos."""
    _booking_slots.clear()
