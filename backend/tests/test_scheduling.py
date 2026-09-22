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
