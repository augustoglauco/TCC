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
