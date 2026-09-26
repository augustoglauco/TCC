import json
import logging
import re
import unicodedata
from typing import Literal, Protocol

from pydantic import BaseModel, ValidationError

from app.models.runtime_settings import DEFAULT_INTENT_ROUTER_PROVIDER
from app.router.llm_client import LLMClient

logger = logging.getLogger(__name__)

Domain = Literal["vendas", "suporte", "atendimento", "agendamento", "fora_escopo"]
Complexity = Literal["baixa", "alta"]


class IntentClassifierClient(Protocol):
    """Contrato mínimo que `external_client` precisa satisfazer quando
    `provider="jev_openrouter"` — documenta a interface duck-typed em vez de
    `Any` (achado da revisão final; sem `mypy` configurado neste projeto,
    isso é só documentação estática para quem lê/edita, não checagem em
    runtime — a guarda real continua sendo o `hasattr` em `_classify_with_jev`,
    que cobre o caso de o chamador passar um cliente sem o método)."""

    async def classify_intent_jev(
        self, message: str, recent_messages: list[str] | None = None
    ) -> tuple[str, float]: ...


class ClassificationResult(BaseModel):
    domain: Domain
    complexity: Complexity
    confidence: float
    # Fix (revisão final, achado importante 1): qual provedor REALMENTE
    # produziu esta classificação — não confundir com o parâmetro `provider`
    # pedido pelo chamador em `classify()`. Quando o Jev falha,
    # `_classify_with_jev` degrada para `_classify_heuristic_fallback`, cujo
    # resultado tem `provider_efetivo="heuristica_llm"` mesmo que o chamador
    # tenha pedido `provider="jev_openrouter"` — é este campo, não o
    # parâmetro do chamador, que deve alimentar `RouterDecision.router_provider`
    # no orchestrator (ver docs/EVALUATION.md: comparação de acurácia/latência
    # entre provedores fica corrompida se uma resposta da heurística for
    # atribuída ao Jev).
    provider_efetivo: str = DEFAULT_INTENT_ROUTER_PROVIDER


# MVP: heurística simples de palavras-chave, sem NLP mais robusto — refinar
# contra o conjunto de teste de backend/eval/router_intents/ (docs/EVALUATION.md).
_DOMAIN_KEYWORDS: dict[Domain, list[str]] = {
    # "estoque"/"disponível" incluídos para alinhar a heurística ao
    # DOMAIN_CRITERIA["vendas"] abaixo (que já lista "estoque/disponibilidade"
    # como intenção de Vendas, R12/docs/ARCHITECTURE.md §6): sem eles, uma
    # pergunta genérica como "tem geradores no estoque?" não casava nenhuma
    # keyword de Vendas na estratégia heurística e caía em fora_escopo
    # (roteada ao externo, sem consultar o catálogo) — divergindo do
    # classificador LLM, que já a rotula como vendas.
    "vendas": ["orçamento", "comprar", "preço", "cotação", "produto", "estoque", "disponível"],
    "suporte": ["não funciona", "quebrado", "erro", "defeito", "problema"],
    "atendimento": ["nota fiscal", "troca", "devolução", "cancelamento", "reclamação"],
    "agendamento": ["agendar", "visita", "marcar", "horário"],
}


def normalize(text: str) -> str:
    """Minúsculas sem diacríticos — usuário real escreve "nao funciona"/"preco"."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return decomposed.encode("ascii", "ignore").decode("ascii")


_DOMAIN_KEYWORDS_NORMALIZED: dict[Domain, list[str]] = {
    domain: [normalize(k) for k in keywords] for domain, keywords in _DOMAIN_KEYWORDS.items()
}

# Descrição de cada domínio, usada pelos dois classificadores LLM (o local,
# em `_CLASSIFIER_PROMPT_TEMPLATE`, e o TypeSafe Jev, como `criteria` da
# pergunta `choice` em `OpenRouterClient.classify_intent_jev`) — uma fonte só
# para os dois não divergirem. Compatibilidade e estoque ficam em vendas
# porque são intenções de Vendas do R12 (docs/ARCHITECTURE.md §6): sem isso,
# "o QTA-100 é compatível com o GD-30?" caía em suporte e o catálogo não era
# consultado (achado do teste local de 2026-09-25, cenário V4).
DOMAIN_CRITERIA: dict[Domain, str] = {
    "vendas": (
        "Interesse em comprar, orçamento, preço, cotação, estoque/disponibilidade, "
        "catálogo de produtos ou compatibilidade entre produtos antes da compra."
    ),
    "suporte": "Produto com defeito, erro ou problema técnico já adquirido.",
    "atendimento": "Nota fiscal, troca, devolução, cancelamento ou reclamação.",
    "agendamento": "Quer marcar, remarcar ou confirmar uma visita/horário.",
    "fora_escopo": "Não se encaixa claramente em nenhuma opção acima.",
}

_COMPLEXITY_LENGTH_THRESHOLD = 280
_COMPLEXITY_QUESTION_MARK_THRESHOLD = 2

_CLASSIFIER_PROMPT_TEMPLATE = """\
Classifique a mensagem do cliente em UM dos domínios abaixo. Também avalie a \
complexidade da pergunta como "baixa" ou "alta". Considere o contexto recente \
da conversa ao decidir.

Domínios:
{dominios}

Contexto recente:
{contexto}

Mensagem atual: {mensagem}

Responda apenas com JSON no formato: \
{{"domain": "...", "complexity": "...", "confidence": 0.0}}"""


_DOMINIOS_FORMATADOS = "\n".join(
    f"- {dominio}: {descricao}" for dominio, descricao in DOMAIN_CRITERIA.items()
)


def _match_domain_by_keywords(message: str) -> Domain | None:
    normalized = normalize(message)
    matched = [
        domain
        for domain, keywords in _DOMAIN_KEYWORDS_NORMALIZED.items()
        if any(k in normalized for k in keywords)
    ]
    if len(matched) == 1:
        return matched[0]
    # MVP: qualquer ambiguidade (0 ou 2+ domínios) colapsa para o fallback
    # `fora_escopo`, que escala ao modelo externo (lado seguro). Revisitar a
    # ordem de prioridade entre domínios quando o conjunto rotulado de
    # `eval/router_intents/` existir (ver docs/ROADMAP.md, Fase 1).
    return None


def _heuristic_complexity(message: str) -> Complexity:
    if len(message) > _COMPLEXITY_LENGTH_THRESHOLD:
        return "alta"
    if message.count("?") >= _COMPLEXITY_QUESTION_MARK_THRESHOLD:
        return "alta"
    return "baixa"


def _classify_heuristic_fallback(message: str, recent_messages: list[str]) -> ClassificationResult:
    # MVP: histórico simples (lista de strings), sem distinguir papel
    # usuário/assistente — suficiente para resolver confirmações curtas a
    # ofertas do próprio assistente; refinar quando a memória da Fase 6
    # existir.
    combined = " ".join([*recent_messages, message])
    domain = _match_domain_by_keywords(combined) or "fora_escopo"
    return ClassificationResult(
        domain=domain,
        complexity=_heuristic_complexity(message),
        confidence=0.3,
        provider_efetivo=DEFAULT_INTENT_ROUTER_PROVIDER,
    )


# MVP: alguns modelos locais (ex.: gemma) envolvem o JSON pedido em um bloco
# de código markdown mesmo quando instruídos a responder só com JSON. Isso só
# remove um fence que envolve a resposta inteira — não tenta extrair JSON em
# meio a texto livre; sem esse tratamento, `json.loads` falhava e a
# classificação correta do LLM era descartada silenciosamente para a
# heurística (ver `_classify_with_llm`).
_CODE_FENCE_RE = re.compile(r"^```(?:\w+)?\s*\n?(.*?)\n?```$", re.DOTALL)


def strip_code_fence(text: str) -> str:
    stripped = text.strip()
    match = _CODE_FENCE_RE.match(stripped)
    return match.group(1) if match else stripped


def _parse_llm_classification(raw_text: str) -> ClassificationResult:
    parsed = json.loads(strip_code_fence(raw_text))
    return ClassificationResult(**parsed, provider_efetivo=DEFAULT_INTENT_ROUTER_PROVIDER)


async def _classify_with_llm(
    message: str, recent_messages: list[str], llm_client: LLMClient
) -> ClassificationResult:
    contexto = "\n".join(recent_messages) if recent_messages else "(nenhum)"
    prompt = _CLASSIFIER_PROMPT_TEMPLATE.format(
        dominios=_DOMINIOS_FORMATADOS, contexto=contexto, mensagem=message
    )

    # A chamada de rede fica FORA do try/except abaixo de propósito: qualquer
    # exceção dela é falha de infraestrutura do backend local (inclusive o
    # ValidationError que o OllamaClient levanta com payload malformado) e
    # deve propagar para o orchestrator virar LocalBackendIndisponivelError,
    # nunca degradar em silêncio para a heurística (spec §2.4).
    response = await llm_client.generate(prompt)

    try:
        return _parse_llm_classification(response.text)
    except (json.JSONDecodeError, ValidationError, TypeError):
        # O LLM respondeu, mas o conteúdo não é JSON de classificação válido:
        # aí sim cai para a heurística só nesta requisição (spec §2.2).
        return _classify_heuristic_fallback(message, recent_messages)


async def _classify_with_jev(
    message: str,
    recent_messages: list[str],
    external_client: IntentClassifierClient | None,
) -> ClassificationResult:
    try:
        if external_client is None or not hasattr(external_client, "classify_intent_jev"):
            raise ValueError("external_client inválido para Jev")
        domain, confidence = await external_client.classify_intent_jev(message, recent_messages)
        return ClassificationResult(
            domain=domain,
            complexity=_heuristic_complexity(message),
            confidence=confidence,
            provider_efetivo="jev_openrouter",
        )
    except Exception as exc:
        # MVP: qualquer falha do provedor Jev (timeout, cliente ausente,
        # resposta malformada) degrada silenciosamente para a heurística
        # local — nunca deve derrubar a requisição de chat.
        logger.warning(
            "jev_classificacao_falhou_fallback_heuristica",
            extra={
                "router": {
                    "event": "jev_falha_fallback",
                    "erro": str(exc),
                }
            },
        )
        return _classify_heuristic_fallback(message, recent_messages)


async def classify(
    message: str,
    recent_messages: list[str] | None = None,
    strategy: str = "heuristic",
    llm_client: LLMClient | None = None,
    provider: str = DEFAULT_INTENT_ROUTER_PROVIDER,
    external_client: IntentClassifierClient | None = None,
) -> ClassificationResult:
    recent_messages = recent_messages or []

    if provider == "jev_openrouter":
        return await _classify_with_jev(message, recent_messages, external_client)

    if provider != DEFAULT_INTENT_ROUTER_PROVIDER:
        # MVP: hoje inalcançável pelo único chamador real (validado por
        # Literal a montante), mas evita que um valor futuro digitado errado
        # caia em silêncio no caminho clássico sem nenhum diagnóstico.
        logger.warning(
            "classify_provider_desconhecido",
            extra={
                "router": {
                    "event": "classify_provider_desconhecido",
                    "provider": provider,
                }
            },
        )

    domain = _match_domain_by_keywords(message)
    if domain is not None:
        return ClassificationResult(
            domain=domain,
            complexity=_heuristic_complexity(message),
            confidence=0.6,
            provider_efetivo=DEFAULT_INTENT_ROUTER_PROVIDER,
        )

    if strategy == "heuristic":
        return _classify_heuristic_fallback(message, recent_messages)

    if llm_client is None:
        raise ValueError("llm_client é obrigatório quando strategy='llm'")

    return await _classify_with_llm(message, recent_messages, llm_client)
