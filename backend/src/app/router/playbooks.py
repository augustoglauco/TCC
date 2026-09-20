"""Playbooks e prompts de sistema por domínio de atendimento (R7, Fase 3).

Cada domínio de atendimento tem um "playbook" — um bloco de instruções de
sistema que orienta o tom e o procedimento da resposta do LLM. O
orchestrator antepõe o playbook do domínio classificado ao prompt (com ou
sem contexto de RAG) antes de chamar o modelo.

# MVP: playbooks são strings estáticas por domínio, sem versionamento nem
# edição em runtime (ver docs/ARCHITECTURE.md §3-4 — assimetria intencional
# entre domínios). Suporte Técnico e Atendimento ao Usuário são resolvidos
# por LLM + RAG, sem camada de ação (ticketing é evolução futura). Vendas e
# Agendamento terão ferramentas de ação (MCP B2B e Google Calendar) nas
# Fases 4-5; por ora o playbook de Vendas apenas *oferece proativamente* o
# agendamento de visita quando há intenção de compra (a criação real do
# evento é R11, Fase 4).
"""

from app.router.classifier import Domain

# Regras comuns a todos os domínios — não repetir em cada playbook.
_BASE_INSTRUCTIONS = (
    "Você é o assistente virtual de atendimento da empresa. Responda em "
    "português do Brasil, de forma clara, cordial e objetiva. Baseie-se "
    "apenas nas informações recuperadas da base de conhecimento e no "
    "histórico da conversa; nunca invente dados específicos (preços, prazos, "
    "números de série, disponibilidade de estoque)."
)

_VENDAS_PLAYBOOK = (
    "Domínio: VENDAS.\n"
    "- Ajude o cliente a encontrar produtos adequados à necessidade dele, "
    "destacando características e compatibilidade quando a informação estiver "
    "disponível na base.\n"
    "- Quando a conversa indicar intenção de compra (ex.: pedir orçamento, "
    "cotação, condições de pagamento, ou comparar produtos para decidir) e "
    "houver um produto compatível no portfólio, ofereça proativamente o "
    "agendamento de uma visita para fechar negócio ou ver o produto de "
    "perto. Faça a oferta como uma pergunta curta ao final da resposta "
    "(ex.: 'Posso agendar uma visita para você conhecer o equipamento?').\n"
    "- Não confirme o agendamento nem invente data/hora: apenas ofereça. A "
    "marcação em si é feita em outro passo do atendimento."
)

_SUPORTE_PLAYBOOK = (
    "Domínio: SUPORTE TÉCNICO.\n"
    "- Ajude o cliente a resolver dúvidas e problemas técnicos com base nos "
    "manuais, guias de instalação e documentação recuperados.\n"
    "- Prefira instruções em passos numerados, curtos e acionáveis.\n"
    "- Se as informações recuperadas não cobrirem o problema, diga isso com "
    "honestidade e oriente o cliente a fornecer mais detalhes (modelo, "
    "mensagem de erro, o que já tentou) em vez de inventar uma solução."
)

_ATENDIMENTO_PLAYBOOK = (
    "Domínio: ATENDIMENTO AO USUÁRIO.\n"
    "- Responda dúvidas institucionais, sobre políticas da empresa, notas "
    "fiscais, trocas, devoluções e procedimentos gerais, com base nas "
    "informações recuperadas.\n"
    "- Seja acolhedor e direto; explique o procedimento aplicável passo a "
    "passo quando houver um.\n"
    "- Se o pedido do cliente fugir do que a base cobre, oriente-o sobre o "
    "canal correto em vez de inventar uma política."
)

# Agendamento tem tratamento próprio no orchestrator (sempre local, R11 na
# Fase 4). Mantido aqui por completude, mas hoje o orchestrator roteia
# agendamento sem passar por contexto de RAG.
_AGENDAMENTO_PLAYBOOK = (
    "Domínio: AGENDAMENTO DE VISITA.\n"
    "- Ajude o cliente a marcar uma visita, coletando de forma cordial a "
    "data/horário de preferência e os dados básicos necessários.\n"
    "- Não confirme um evento nem invente confirmações: a criação real do "
    "agendamento é feita em outro passo do atendimento."
)

_PLAYBOOKS: dict[Domain, str] = {
    "vendas": _VENDAS_PLAYBOOK,
    "suporte": _SUPORTE_PLAYBOOK,
    "atendimento": _ATENDIMENTO_PLAYBOOK,
    "agendamento": _AGENDAMENTO_PLAYBOOK,
}


def get_playbook(domain: Domain) -> str | None:
    """Retorna o bloco de instruções de sistema do domínio, ou None.

    Retorna None para `fora_escopo` (sem playbook — a mensagem vai ao modelo
    externo sem instrução de domínio específica).
    """
    return _PLAYBOOKS.get(domain)


def build_system_prompt(domain: Domain) -> str | None:
    """Monta o prompt de sistema completo (base + playbook) para o domínio.

    Retorna None quando não há playbook para o domínio (`fora_escopo`), para
    o chamador poder decidir não anexar cabeçalho de sistema algum.
    """
    playbook = get_playbook(domain)
    if playbook is None:
        return None
    return f"{_BASE_INSTRUCTIONS}\n\n{playbook}"
