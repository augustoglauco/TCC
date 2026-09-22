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

import json
import re
from datetime import datetime

from pydantic import BaseModel, ValidationError

from app.router.llm_client import LLMClient

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


# MVP: mesmo tratamento de `app.router.classifier._strip_code_fence` — alguns
# modelos locais envolvem o JSON pedido em um bloco de código markdown mesmo
# instruídos a responder só com JSON.
_CODE_FENCE_RE = re.compile(r"^```(?:\w+)?\s*\n?(.*?)\n?```$", re.DOTALL)


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    match = _CODE_FENCE_RE.match(stripped)
    return match.group(1) if match else stripped


class SlotExtractionResult(BaseModel):
    data_hora: datetime | None = None
    nome: str | None = None
    email: str | None = None
    telefone: str | None = None
    confirmacao: bool | None = None


_EXTRACTION_PROMPT_TEMPLATE = """\
Você está ajudando a coletar dados para agendar uma visita comercial. \
Extraia da mensagem do cliente os campos que ele informou NESTA mensagem, \
sem inventar nada e sem repetir dados que não foram ditos agora. Datas/horas \
devem vir em ISO 8601 com fuso (ex.: "2026-09-25T15:00:00-03:00").

Dados já coletados até agora: {slots_conhecidos}
O sistema está aguardando uma confirmação do cliente? {aguardando_confirmacao}

Contexto recente da conversa:
{contexto}

Mensagem atual do cliente: {mensagem}

Responda APENAS com JSON no formato: {{"data_hora": "...", "nome": "...", \
"email": "...", "telefone": "...", "confirmacao": true}} — use null para \
qualquer campo não informado NESTA mensagem. "confirmacao" só deve ser true \
se o cliente estiver claramente confirmando (ex.: "sim", "pode confirmar", \
"isso mesmo") E o sistema estiver aguardando confirmação; caso contrário, \
null."""


def _parse_extraction(raw_text: str) -> SlotExtractionResult:
    parsed = json.loads(_strip_code_fence(raw_text))
    return SlotExtractionResult(**parsed)


async def extract_booking_slots(
    message: str,
    recent_messages: list[str],
    current_slots: BookingSlots,
    llm_client: LLMClient,
) -> SlotExtractionResult:
    contexto = "\n".join(recent_messages) if recent_messages else "(nenhum)"
    prompt = _EXTRACTION_PROMPT_TEMPLATE.format(
        slots_conhecidos=current_slots.model_dump_json(exclude={"awaiting_confirmation"}),
        aguardando_confirmacao="sim" if current_slots.awaiting_confirmation else "não",
        contexto=contexto,
        mensagem=message,
    )
    response = await llm_client.generate(prompt)
    try:
        return _parse_extraction(response.text)
    except (json.JSONDecodeError, ValidationError, TypeError):
        # MVP: resposta do LLM não é JSON de extração válido — não quebra o
        # turno, trata como "nada extraído nesta mensagem" (mesmo espírito de
        # `app.router.classifier._classify_with_llm`, que cai para a
        # heurística no caso análogo; aqui não há heurística de agendamento
        # por regex, só o loop de pedir de novo no orchestrator).
        return SlotExtractionResult()


def merge_slots(current: BookingSlots, extraction: SlotExtractionResult) -> BookingSlots:
    campos_extraidos = {
        "data_hora": extraction.data_hora,
        "nome": extraction.nome,
        "email": extraction.email,
        "telefone": extraction.telefone,
    }
    atualizacoes = {campo: valor for campo, valor in campos_extraidos.items() if valor is not None}
    return current.model_copy(update=atualizacoes)
