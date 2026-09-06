import json
import logging

from pydantic import BaseModel

from app.router.classifier import classify
from app.router.llm_client import LLMClient
from app.router.rag_client import RAGClient, RAGConnectionError

logger = logging.getLogger(__name__)

_DOMAINS_COM_RAG = {"vendas", "suporte", "atendimento"}


class RouterDecision(BaseModel):
    domain: str
    complexity: str
    confidence: float
    complexity_strategy_usada: str
    backend_escolhido: str  # "local" | "externo"
    motivo_escalonamento: str  # "fora_escopo" | "rag_vazio" | "complexidade_alta" | "nenhum"
    resposta: str
    latencia_ms: float
    tokens_entrada: int | None
    tokens_saida: int | None
    custo_estimado_usd: float


class LocalBackendIndisponivelError(Exception):
    """Falha de infraestrutura no backend local (Ollama) — sem fallback automático."""


class ExternalBackendIndisponivelError(Exception):
    """Falha de infraestrutura no backend externo (OpenRouter) — sem fallback automático."""


async def handle_message(
    message: str,
    recent_messages: list[str],
    local_client: LLMClient,
    external_client: LLMClient,
    rag_client: RAGClient,
    complexity_strategy: str,
) -> RouterDecision:
    classification = await classify(
        message=message,
        recent_messages=recent_messages,
        strategy=complexity_strategy,
        llm_client=local_client,
    )

    backend_escolhido = "local"
    motivo = "nenhum"

    if classification.domain == "agendamento":
        backend_escolhido = "local"
    elif classification.domain == "fora_escopo":
        backend_escolhido = "externo"
        motivo = "fora_escopo"
    else:
        try:
            documentos = await rag_client.search(message, classification.domain)
        except RAGConnectionError:
            logger.error(json.dumps({"event": "rag_indisponivel", "domain": classification.domain}))
            raise

        if not documentos:
            backend_escolhido = "externo"
            motivo = "rag_vazio"
        elif classification.complexity == "alta":
            backend_escolhido = "externo"
            motivo = "complexidade_alta"

    client = local_client if backend_escolhido == "local" else external_client
    try:
        response = await client.generate(message)
    except Exception as exc:
        logger.error(
            json.dumps(
                {
                    "event": "backend_indisponivel",
                    "backend": backend_escolhido,
                    "domain": classification.domain,
                }
            )
        )
        if backend_escolhido == "local":
            raise LocalBackendIndisponivelError(str(exc)) from exc
        raise ExternalBackendIndisponivelError(str(exc)) from exc

    decisao = RouterDecision(
        domain=classification.domain,
        complexity=classification.complexity,
        confidence=classification.confidence,
        complexity_strategy_usada=complexity_strategy,
        backend_escolhido=backend_escolhido,
        motivo_escalonamento=motivo,
        resposta=response.text,
        latencia_ms=response.total_duration_ms,
        tokens_entrada=response.prompt_tokens,
        tokens_saida=response.completion_tokens,
        custo_estimado_usd=response.estimated_cost_usd,
    )
    logger.info(json.dumps({"event": "router_decision", **decisao.model_dump()}))
    return decisao
