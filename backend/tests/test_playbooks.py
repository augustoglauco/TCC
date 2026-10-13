"""Testes para app.router.playbooks (R7, Fase 3)."""

from app.router.playbooks import build_system_prompt, get_playbook


def test_todos_os_dominios_de_negocio_tem_playbook():
    for domain in ("vendas", "suporte", "atendimento"):
        assert get_playbook(domain) is not None


def test_agendamento_nao_tem_mais_playbook():
    # Desde a Fase 4A, o domínio "agendamento" é tratado por
    # `app.router.orchestrator._handle_agendamento` (máquina de estado
    # própria), sem passar mais por `build_system_prompt`/playbook — ver
    # docs/superpowers/specs/2026-09-21-agendamento-mcp-calendar-design.md.
    assert get_playbook("agendamento") is None


def test_fora_escopo_tem_playbook():
    assert get_playbook("fora_escopo") is not None
    prompt = build_system_prompt("fora_escopo")
    assert prompt is not None
    assert "CONVERSA GERAL E FORA DE ESCOPO" in prompt


def test_vendas_oferece_agendamento_proativo():
    prompt = build_system_prompt("vendas")
    assert prompt is not None
    assert "VENDAS" in prompt
    # A oferta proativa de agendamento é o requisito explícito do playbook de
    # Vendas (ver docs/ROADMAP.md, Fase 3).
    assert "agendamento" in prompt.lower()
    assert "visita" in prompt.lower()


def test_vendas_nao_oferece_agendamento_a_toa_nem_repete():
    # Achado de 2026-10-05 (usuário reportou o chat oferecendo agendamento
    # em praticamente toda resposta de Vendas): o playbook antigo não tinha
    # nenhum limite de frequência nem instrução para checar se já tinha
    # oferecido antes, e o gatilho (qualquer pedido de orçamento/cotação)
    # era largo demais — cobre quase toda mensagem normal de Vendas.
    prompt = build_system_prompt("vendas")
    assert prompt is not None
    prompt_lower = prompt.lower()
    assert "não repita" in prompt_lower or "nao repita" in prompt_lower
    assert "troca anterior" in prompt_lower
    # 2026-10-13: visita só na desistência, nunca durante a compra.
    assert "não ofereça durante a compra" in prompt_lower
    assert "desistência" in prompt_lower


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


def test_playbook_vendas_nao_promete_criar_pedido_e_usa_a_quantidade_da_cotacao():
    from app.router.playbooks import _VENDAS_PLAYBOOK

    assert "O chat NÃO cria nem reserva pedidos" in _VENDAS_PLAYBOOK
    assert "nunca o estoque de um CD" in _VENDAS_PLAYBOOK


def test_vendas_logado_oferece_prosseguir_com_o_fechamento():
    prompt = build_system_prompt("vendas", usuario_autenticado=True)
    assert prompt is not None
    assert "LOGADO no sistema" in prompt
    assert "prosseguir com o fechamento da venda" in prompt
    assert "NÃO LOGADO" not in prompt


def test_vendas_nao_logado_so_apresenta_proposta_e_pede_login():
    prompt = build_system_prompt("vendas")
    assert prompt is not None
    assert "NÃO LOGADO" in prompt
    assert "preciso estar logado no sistema" in prompt
    assert "prosseguir com o fechamento da venda" not in prompt


def test_regra_de_login_so_existe_no_dominio_vendas():
    for domain in ("suporte", "atendimento", "fora_escopo"):
        prompt = build_system_prompt(domain, usuario_autenticado=True)
        assert prompt is None or "LOGADO no sistema" not in prompt
