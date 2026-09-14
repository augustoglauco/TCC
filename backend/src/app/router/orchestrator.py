import logging

from pydantic import BaseModel

from app.router.classifier import classify
from app.router.llm_client import LLMClient
from app.router.rag_client import Document, RAGClient, RAGConnectionError

logger = logging.getLogger(__name__)

# MVP: simplificações conscientes desta fase (ver docs/ROADMAP.md e
# docs/superpowers/specs/2026-09-05-roteador-basico-design.md §6):
# - os documentos devolvidos pelo RAG são usados como sinal de roteamento
#   (vazio x não-vazio) E, desde o RAG real (Qdrant, Fase 2), como contexto
#   injetado no prompt do LLM — decisão registrada em docs/ARCHITECTURE.md
#   §5 (nota após a tabela de escopo); a lógica de decisão local x externo
#   em si não muda;
# - não há persistência das decisões do roteador em banco — a tabela
#   `router_logs` é da Fase 6; por ora só o log estruturado;
# - o texto completo da resposta do LLM vai para o log estruturado em nível
#   INFO. Aceitável neste protótipo, mas é uma simplificação deliberada
#   (risco de PII/volume em produção) a revisitar antes de qualquer uso real.


def _build_prompt(message: str, documentos: list[Document]) -> str:
    """Injeta o conteúdo dos documentos recuperados como contexto no prompt.

    # MVP: concatenação simples dos `content` dos documentos, sem
    # sumarização/priorização por score além da ordem já devolvida pelo RAG,
    # e sem truncar por limite de tokens do modelo (ver docs/ARCHITECTURE.md
    # §5). Só é chamada quando `documentos` não é vazio.
    """
    contexto = "\n\n".join(f"- {documento.content}" for documento in documentos)
    return (
        "Use as informações a seguir, recuperadas da base de conhecimento da "
        "empresa, para responder à mensagem do cliente. Se as informações não "
        "forem suficientes, responda com o que souber, sem inventar dados "
        "específicos (preços, prazos, números de série).\n\n"
        f"Informações recuperadas:\n{contexto}\n\n"
        f"Mensagem do cliente: {message}"
    )


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
    documentos: list[Document] = []

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

    # A decisão de roteamento (backend_escolhido/motivo) usa só o sinal
    # vazio x não-vazio acima, sem mudar aqui; o conteúdo dos documentos
    # (quando houver) só entra a partir deste ponto, no prompt em si.
    prompt = _build_prompt(message, documentos) if documentos else message

    client = local_client if backend_escolhido == "local" else external_client
    try:
        response = await client.generate(prompt)
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
