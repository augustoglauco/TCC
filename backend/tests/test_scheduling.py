from datetime import datetime

from app.router.scheduling import (
    BookingSlots,
    clear_booking_slots,
    get_booking_slots,
    reset_all_booking_slots,
    set_booking_slots,
)


def setup_function():
    reset_all_booking_slots()


def test_booking_slots_incompletos_por_padrao():
    slots = BookingSlots()
    assert not slots.is_complete()
    assert set(slots.missing_fields()) == {"data_hora", "nome", "email", "telefone"}


def test_booking_slots_completos_quando_todos_os_campos_preenchidos():
    slots = BookingSlots(
        data_hora=datetime(2026, 9, 25, 15, 0),
        nome="Maria",
        email="maria@example.com",
        telefone="11999999999",
    )
    assert slots.is_complete()
    assert slots.missing_fields() == []


def test_get_booking_slots_devolve_vazio_para_conversa_desconhecida():
    slots = get_booking_slots("conversa-inexistente")
    assert slots == BookingSlots()


def test_set_e_get_booking_slots_por_conversation_id():
    slots = BookingSlots(nome="Maria")
    set_booking_slots("conversa-1", slots)

    assert get_booking_slots("conversa-1") == slots
    assert get_booking_slots("conversa-2") == BookingSlots()


def test_clear_booking_slots_remove_apenas_a_conversa_informada():
    set_booking_slots("conversa-1", BookingSlots(nome="Maria"))
    set_booking_slots("conversa-2", BookingSlots(nome="João"))

    clear_booking_slots("conversa-1")

    assert get_booking_slots("conversa-1") == BookingSlots()
    assert get_booking_slots("conversa-2") == BookingSlots(nome="João")


# Task 2 tests
import pytest

from app.router.llm_client import LLMResponse
from app.router.scheduling import (
    SlotExtractionResult,
    extract_booking_slots,
    merge_slots,
)


class _FakeLLMClient:
    def __init__(self, text: str) -> None:
        self._text = text
        self.last_prompt: str | None = None

    async def generate(self, prompt: str) -> LLMResponse:
        self.last_prompt = prompt
        return LLMResponse(text=self._text, total_duration_ms=10.0)

    async def is_model_ready(self) -> bool:
        return True

    def generate_stream(self, prompt: str):
        raise NotImplementedError


async def test_extract_booking_slots_parseia_json_da_resposta():
    llm = _FakeLLMClient(
        '{"data_hora": "2026-09-25T15:00:00-03:00", "nome": "Maria", '
        '"email": null, "telefone": null, "confirmacao": null}'
    )

    resultado = await extract_booking_slots(
        message="quero marcar dia 25 de setembro às 15h, meu nome é Maria",
        recent_messages=[],
        current_slots=BookingSlots(),
        llm_client=llm,
    )

    assert resultado.nome == "Maria"
    assert resultado.email is None
    assert resultado.confirmacao is None
    assert "quero marcar dia 25" in llm.last_prompt


async def test_extract_booking_slots_aceita_json_em_bloco_de_codigo():
    llm = _FakeLLMClient(
        '```json\n{"data_hora": null, "nome": null, "email": "a@b.com", '
        '"telefone": null, "confirmacao": true}\n```'
    )

    resultado = await extract_booking_slots(
        message="pode confirmar, meu email é a@b.com",
        recent_messages=[],
        current_slots=BookingSlots(nome="Maria", awaiting_confirmation=True),
        llm_client=llm,
    )

    assert resultado.email == "a@b.com"
    assert resultado.confirmacao is True


async def test_extract_booking_slots_resposta_invalida_nao_quebra_o_turno():
    llm = _FakeLLMClient("não sei responder isso")

    resultado = await extract_booking_slots(
        message="oi",
        recent_messages=[],
        current_slots=BookingSlots(),
        llm_client=llm,
    )

    assert resultado == SlotExtractionResult()


def test_merge_slots_preserva_campos_ja_coletados():
    atual = BookingSlots(nome="Maria", email="maria@example.com")
    extraido = SlotExtractionResult(telefone="11999999999")

    resultado = merge_slots(atual, extraido)

    assert resultado.nome == "Maria"
    assert resultado.email == "maria@example.com"
    assert resultado.telefone == "11999999999"


def test_merge_slots_sobrescreve_quando_novo_valor_vem_preenchido():
    atual = BookingSlots(nome="Maria")
    extraido = SlotExtractionResult(nome="Maria Silva")

    resultado = merge_slots(atual, extraido)

    assert resultado.nome == "Maria Silva"


# Task 3 tests
from datetime import timedelta

from app.router.scheduling import (
    DURACAO_VISITA,
    MSG_ERRO_MCP,
    HorarioInvalidoError,
    SchedulingConfig,
    mensagem_campos_faltando,
    mensagem_pedir_confirmacao,
    mensagem_sucesso,
    validar_expediente,
)

_CONFIG = SchedulingConfig(
    timezone="America/Sao_Paulo",
    expediente_dias="seg-sex",
    expediente_inicio="09:00",
    expediente_fim="18:00",
)


def test_duracao_visita_e_30_minutos():
    assert DURACAO_VISITA == timedelta(minutes=30)


def test_validar_expediente_aceita_horario_valido():
    # 2026-09-24 é uma quinta-feira, 10h — dentro do expediente seg-sex 9-18h.
    validar_expediente(datetime(2026, 9, 24, 10, 0), _CONFIG)  # não levanta


def test_validar_expediente_rejeita_data_no_passado():
    with pytest.raises(HorarioInvalidoError):
        validar_expediente(datetime(2020, 1, 1, 10, 0), _CONFIG)


def test_validar_expediente_rejeita_fim_de_semana():
    # 2026-09-26 é sábado.
    with pytest.raises(HorarioInvalidoError) as exc_info:
        validar_expediente(datetime(2026, 9, 26, 10, 0), _CONFIG)
    assert "expediente" in exc_info.value.motivo.lower()


def test_validar_expediente_rejeita_fora_do_horario():
    # 2026-09-24 é quinta, 20h — fora do expediente até 18h.
    with pytest.raises(HorarioInvalidoError):
        validar_expediente(datetime(2026, 9, 24, 20, 0), _CONFIG)


def test_mensagem_campos_faltando_lista_um_campo():
    slots = BookingSlots(data_hora=datetime(2026, 9, 24, 10, 0), nome="Maria", email="m@x.com")
    texto = mensagem_campos_faltando(slots)
    assert "telefone" in texto.lower()


def test_mensagem_campos_faltando_lista_varios_campos():
    slots = BookingSlots()
    texto = mensagem_campos_faltando(slots)
    assert "nome" in texto.lower()
    assert "e-mail" in texto.lower()
    assert "telefone" in texto.lower()


def test_mensagem_pedir_confirmacao_inclui_dados_coletados():
    slots = BookingSlots(
        data_hora=datetime(2026, 9, 24, 10, 0),
        nome="Maria",
        email="maria@example.com",
        telefone="11999999999",
    )
    texto = mensagem_pedir_confirmacao(slots, "America/Sao_Paulo")
    assert "Maria" in texto
    assert "maria@example.com" in texto
    assert "confirmar" in texto.lower()


def test_mensagem_sucesso_menciona_email():
    slots = BookingSlots(
        data_hora=datetime(2026, 9, 24, 10, 0),
        nome="Maria",
        email="maria@example.com",
        telefone="11999999999",
    )
    texto = mensagem_sucesso(slots, "America/Sao_Paulo")
    assert "maria@example.com" in texto


def test_msg_erro_mcp_nao_promete_confirmacao_automatica():
    assert "não consegui confirmar" in MSG_ERRO_MCP.lower()
