"""Testes para app.router.playbooks (R7, Fase 3)."""

from app.router.playbooks import build_system_prompt, get_playbook


def test_todos_os_dominios_de_negocio_tem_playbook():
    for domain in ("vendas", "suporte", "atendimento", "agendamento"):
        assert get_playbook(domain) is not None


def test_fora_escopo_nao_tem_playbook():
    assert get_playbook("fora_escopo") is None
    assert build_system_prompt("fora_escopo") is None


def test_vendas_oferece_agendamento_proativo():
    prompt = build_system_prompt("vendas")
    assert prompt is not None
    assert "VENDAS" in prompt
    # A oferta proativa de agendamento é o requisito explícito do playbook de
    # Vendas (ver docs/ROADMAP.md, Fase 3).
    assert "agendamento" in prompt.lower()
    assert "visita" in prompt.lower()


def test_suporte_pede_passos_e_honestidade():
    prompt = build_system_prompt("suporte")
    assert prompt is not None
    assert "SUPORTE" in prompt
    assert "passos" in prompt.lower()


def test_atendimento_cobre_politicas_e_procedimentos():
    prompt = build_system_prompt("atendimento")
    assert prompt is not None
    assert "ATENDIMENTO" in prompt


def test_system_prompt_inclui_regras_base():
    # As instruções base (não inventar dados, responder em pt-BR) devem
    # aparecer em todos os prompts de sistema de domínios de negócio.
    for domain in ("vendas", "suporte", "atendimento"):
        prompt = build_system_prompt(domain)
        assert prompt is not None
        assert "não invente" in prompt.lower() or "nunca invente" in prompt.lower()
