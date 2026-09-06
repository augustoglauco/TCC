import json
from typing import Literal

from pydantic import BaseModel, ValidationError

from app.router.llm_client import LLMClient

Domain = Literal["vendas", "suporte", "atendimento", "agendamento", "fora_escopo"]
Complexity = Literal["baixa", "alta"]


class ClassificationResult(BaseModel):
    domain: Domain
    complexity: Complexity
    confidence: float


# MVP: heurística simples de palavras-chave, sem NLP mais robusto — refinar
# contra o conjunto de teste de backend/eval/router_intents/ (docs/EVALUATION.md).
_DOMAIN_KEYWORDS: dict[Domain, list[str]] = {
    "vendas": ["orçamento", "comprar", "preço", "cotação", "produto"],
    "suporte": ["não funciona", "quebrado", "erro", "defeito", "problema"],
    "atendimento": ["nota fiscal", "troca", "devolução", "cancelamento", "reclamação"],
    "agendamento": ["agendar", "visita", "marcar", "horário"],
}

_COMPLEXITY_LENGTH_THRESHOLD = 280
_COMPLEXITY_QUESTION_MARK_THRESHOLD = 2

_CLASSIFIER_PROMPT_TEMPLATE = """\
Classifique a mensagem do cliente em UM dos domínios: vendas, suporte, \
atendimento, agendamento, fora_escopo. Também avalie a complexidade da \
pergunta como "baixa" ou "alta". Considere o contexto recente da conversa \
ao decidir.

Contexto recente:
{contexto}

Mensagem atual: {mensagem}

Responda apenas com JSON no formato: \
{{"domain": "...", "complexity": "...", "confidence": 0.0}}"""


def _match_domain_by_keywords(message: str) -> Domain | None:
    lowered = message.lower()
    matched = [
        domain
        for domain, keywords in _DOMAIN_KEYWORDS.items()
        if any(k in lowered for k in keywords)
    ]
    if len(matched) == 1:
        return matched[0]
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
        domain=domain, complexity=_heuristic_complexity(message), confidence=0.3
    )


async def _classify_with_llm(
    message: str, recent_messages: list[str], llm_client: LLMClient
) -> ClassificationResult:
    contexto = "\n".join(recent_messages) if recent_messages else "(nenhum)"
    prompt = _CLASSIFIER_PROMPT_TEMPLATE.format(contexto=contexto, mensagem=message)
    response = await llm_client.generate(prompt)
    parsed = json.loads(response.text)
    return ClassificationResult(**parsed)


async def classify(
    message: str,
    recent_messages: list[str] | None = None,
    strategy: str = "heuristic",
    llm_client: LLMClient | None = None,
) -> ClassificationResult:
    recent_messages = recent_messages or []

    domain = _match_domain_by_keywords(message)
    if domain is not None:
        return ClassificationResult(
            domain=domain, complexity=_heuristic_complexity(message), confidence=0.6
        )

    if strategy == "heuristic":
        return _classify_heuristic_fallback(message, recent_messages)

    if llm_client is None:
        raise ValueError("llm_client é obrigatório quando strategy='llm'")

    try:
        return await _classify_with_llm(message, recent_messages, llm_client)
    except (json.JSONDecodeError, ValidationError):
        return _classify_heuristic_fallback(message, recent_messages)
