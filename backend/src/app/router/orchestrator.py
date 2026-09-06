import logging

from pydantic import BaseModel

from app.router.classifier import classify
from app.router.llm_client import LLMClient
from app.router.rag_client import RAGClient, RAGConnectionError

logger = logging.getLogger(__name__)

# MVP: simplificações conscientes desta fase (ver docs/ROADMAP.md e
# docs/superpowers/specs/2026-09-05-roteador-basico-design.md §6):
# - os documentos devolvidos pelo RAG são usados só como sinal de roteamento
#   (vazio x não-vazio); não são injetados no prompt do LLM — isso entra na
#   Fase 2, junto do RAG real (Qdrant);
# - não há persistência das decisões do roteador em banco — a tabela
#   `router_logs` é da Fase 6; por ora só o log estruturado;
# - o texto completo da resposta do LLM vai para o log estruturado em nível
#   INFO. Aceitável neste protótipo, mas é uma simplificação deliberada
#   (risco de PII/volume em produção) a revisitar antes de qualquer uso real.


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
    # Com strategy="llm" a classificação chama o backend local. Falha aqui é
    # falha de infraestrutura local, não "conteúdo não classificável" — vira
    # LocalBackendIndisponivelError em vez de degradar em silêncio para
    # fora_escopo (que rotearia ao backend externo). O wrapping fica aqui, e
    # não dentro de `classify()`, para não criar import circular.
    try:
        classification = await classify(
            message=message,
            recent_messages=recent_messages,
            strategy=complexity_strategy,
            llm_client=local_client,
        )
    except Exception as exc:
        logger.error(
            "backend_indisponivel",
            extra={
                "router": {
                    "event": "backend_indisponivel",
                    "backend": "local",
                    "etapa": "classificacao",
                    "erro": str(exc),
                }
            },
        )
        raise LocalBackendIndisponivelError(str(exc)) from exc

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
            logger.error(
                "rag_indisponivel",
                extra={"router": {"event": "rag_indisponivel", "domain": classification.domain}},
            )
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
            "backend_indisponivel",
            extra={
                "router": {
                    "event": "backend_indisponivel",
                    "backend": backend_escolhido,
                    "domain": classification.domain,
                    "etapa": "geracao",
                    "erro": str(exc),
                }
            },
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
    logger.info(
        "router_decision",
        extra={"router": {"event": "router_decision", **decisao.model_dump()}},
    )
    return decisao
