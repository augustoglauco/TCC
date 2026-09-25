"""Máquina de estado do agendamento de visita (R11, Fase 4A).

Lógica de domínio pura (sem I/O de LLM/MCP, sem tipos de streaming SSE) —
consumida por `app.router.orchestrator`, que faz a ponte com o protocolo de
streaming e chama o MCP de verdade. Ver
docs/superpowers/specs/2026-09-21-agendamento-mcp-calendar-design.md.

# MVP: estado de agendamento guardado em memória por `conversation_id`
(dict de processo) — perdido em restart do processo, sem persistência em
banco. As mensagens da conversa em si já ficam no Postgres (R9, Fase 6,
`app.memory.store`); só os dados parciais do agendamento em andamento
continuam em memória.
"""

import json
import re
from datetime import datetime, timedelta
from datetime import time as dt_time
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ValidationError

from app.router.llm_client import LLMClient

DURACAO_VISITA = timedelta(minutes=30)

_DIAS_SEMANA = {"seg": 0, "ter": 1, "qua": 2, "qui": 3, "sex": 4, "sab": 5, "dom": 6}


class SchedulingConfig(BaseModel):
    timezone: str
    expediente_dias: str
    expediente_inicio: str
    expediente_fim: str


class HorarioInvalidoError(Exception):
    def __init__(self, motivo: str) -> None:
        self.motivo = motivo
        super().__init__(motivo)


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


_NOMES_DIAS_SEMANA = [
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
]

_EXTRACTION_PROMPT_TEMPLATE = """\
Você está ajudando a coletar dados para agendar uma visita comercial. \
Extraia da mensagem do cliente os campos que ele informou NESTA mensagem, \
sem inventar nada e sem repetir dados que não foram ditos agora. Datas/horas \
devem vir em ISO 8601 com fuso (ex.: "2026-09-25T15:00:00-03:00").

Hoje é {hoje_dia_semana}, {hoje_data}. Próximos dias, para consultar em vez \
de calcular datas relativas ("amanhã", "quarta-feira que vem", "daqui a 3 \
dias" etc.) — nunca assuma um ano diferente do ano corrente sem o cliente \
dizer explicitamente:
{proximos_dias}

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


_DIAS_TABELA_REFERENCIA = 14


def _formatar_proximos_dias(hoje: datetime) -> str:
    # Achado real (2026-09-23): mesmo informando a data de hoje, o modelo
    # errava o dia da semana ao CALCULAR datas relativas ("quarta-feira que
    # vem" virou uma quinta-feira). Uma tabela de referência pronta troca
    # "fazer conta" por "consultar" — bem mais confiável para LLMs.
    linhas = []
    for offset in range(1, _DIAS_TABELA_REFERENCIA + 1):
        dia = hoje + timedelta(days=offset)
        linhas.append(f"{dia.strftime('%Y-%m-%d')}: {_NOMES_DIAS_SEMANA[dia.weekday()]}")
    return "\n".join(linhas)


async def extract_booking_slots(
    message: str,
    recent_messages: list[str],
    current_slots: BookingSlots,
    llm_client: LLMClient,
    timezone: str,
) -> SlotExtractionResult:
    # Achado real (2026-09-23): sem a data de hoje no prompt, o modelo não
    # tem como calcular corretamente datas relativas ("quarta-feira que
    # vem") — às vezes extraía um ano errado (ex.: 2024 em vez do ano
    # corrente), fazendo a validação de horário rejeitar como "já passou"
    # uma data que na verdade era futura.
    agora = datetime.now(ZoneInfo(timezone))
    contexto = "\n".join(recent_messages) if recent_messages else "(nenhum)"
    prompt = _EXTRACTION_PROMPT_TEMPLATE.format(
        hoje_dia_semana=_NOMES_DIAS_SEMANA[agora.weekday()],
        proximos_dias=_formatar_proximos_dias(agora),
        hoje_data=agora.strftime("%Y-%m-%d"),
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


def _parse_dias_expediente(dias_str: str) -> set[int]:
    # MVP: só o formato "seg-sex" (intervalo contíguo) ou "seg,qua,sex"
    # (lista) — sem combinações mais ricas (ex. "seg-qua,sex").
    dias_str = dias_str.strip().lower()
    if "-" in dias_str:
        inicio_str, fim_str = dias_str.split("-", 1)
        inicio, fim = _DIAS_SEMANA[inicio_str.strip()], _DIAS_SEMANA[fim_str.strip()]
        if inicio <= fim:
            return set(range(inicio, fim + 1))
        return set(range(inicio, 7)) | set(range(0, fim + 1))
    return {_DIAS_SEMANA[dia.strip()] for dia in dias_str.split(",")}


def validar_expediente(data_hora: datetime, config: SchedulingConfig) -> datetime:
    """Valida `data_hora` contra o expediente configurado e devolve a versão
    com fuso horário aplicado (`config.timezone`).

    Devolve (em vez de descartar) o `datetime` aware usado internamente para
    a checagem — o chamador deve persistir esse valor de volta nos slots
    (`slots.data_hora = validar_expediente(...)`) antes de passá-lo ao MCP: um
    `datetime` naive não carrega offset UTC, e `.isoformat()` nele não é um
    RFC3339 válido para a API do Google Calendar.
    """
    tz = ZoneInfo(config.timezone)
    agora = datetime.now(tz)
    dh = data_hora if data_hora.tzinfo else data_hora.replace(tzinfo=tz)
    dh = dh.astimezone(tz)

    if dh <= agora:
        raise HorarioInvalidoError("Esse horário já passou. Pode sugerir uma data e hora futuras?")

    dias_validos = _parse_dias_expediente(config.expediente_dias)
    if dh.weekday() not in dias_validos:
        raise HorarioInvalidoError(
            f"Nosso expediente inclui apenas {config.expediente_dias}. Pode escolher outro dia?"
        )

    hora_inicio = dt_time.fromisoformat(config.expediente_inicio)
    hora_fim = dt_time.fromisoformat(config.expediente_fim)
    if not (hora_inicio <= dh.time() < hora_fim):
        raise HorarioInvalidoError(
            f"Nosso expediente para visitas é das {config.expediente_inicio} às "
            f"{config.expediente_fim}. Pode escolher outro horário nessa faixa?"
        )

    return dh


_ROTULOS_CAMPOS = {
    "data_hora": "a data e o horário desejados para a visita",
    "nome": "seu nome",
    "email": "seu e-mail",
    "telefone": "seu telefone",
}


def mensagem_campos_faltando(slots: BookingSlots) -> str:
    faltando = [_ROTULOS_CAMPOS[campo] for campo in slots.missing_fields()]
    if len(faltando) == 1:
        pedido = faltando[0]
    else:
        pedido = ", ".join(faltando[:-1]) + " e " + faltando[-1]
    return f"Para agendar sua visita, ainda preciso de: {pedido}."


def _formatar_data_hora(data_hora: datetime, timezone: str) -> str:
    tz = ZoneInfo(timezone)
    dh = data_hora if data_hora.tzinfo else data_hora.replace(tzinfo=tz)
    return dh.astimezone(tz).strftime("%d/%m/%Y às %H:%M")


def mensagem_pedir_confirmacao(slots: BookingSlots, timezone: str) -> str:
    data_formatada = _formatar_data_hora(slots.data_hora, timezone)
    return (
        f"Só confirmando antes de agendar: visita em {data_formatada}, em nome "
        f"de {slots.nome}, e-mail {slots.email}, telefone {slots.telefone}. "
        "Posso confirmar?"
    )


def mensagem_sucesso(slots: BookingSlots, timezone: str) -> str:
    data_formatada = _formatar_data_hora(slots.data_hora, timezone)
    return (
        f"Prontinho! Sua visita foi agendada para {data_formatada}. Você vai "
        f"receber a confirmação por e-mail em {slots.email}."
    )


MSG_ERRO_MCP = (
    "No momento não consegui confirmar o agendamento automaticamente. Um "
    "atendente da nossa equipe vai entrar em contato para confirmar os "
    "detalhes. Pedimos desculpas pelo transtorno."
)
