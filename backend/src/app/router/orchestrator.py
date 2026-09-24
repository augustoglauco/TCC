import logging
import time
from collections.abc import AsyncIterator
from datetime import datetime

from pydantic import BaseModel

from app.mcp_client.google_calendar import CalendarClient, GoogleCalendarConnectionError
from app.models.chat import RagChunkMetric
from app.models.runtime_settings import (
    DEFAULT_INTENT_ROUTER_PROVIDER,
    DEFAULT_TONE_MONITOR_PROVIDER,
)
from app.router.classifier import Domain, classify
from app.router.llm_client import LLMClient, LLMStreamChunk
from app.router.playbooks import build_system_prompt
from app.router.rag_client import Document, RAGClient, RAGConnectionError
from app.router.scheduling import (
    DURACAO_VISITA,
    MSG_ERRO_MCP,
    BookingSlots,
    HorarioInvalidoError,
    SchedulingConfig,
    clear_booking_slots,
    extract_booking_slots,
    get_booking_slots,
    mensagem_campos_faltando,
    mensagem_pedir_confirmacao,
    mensagem_sucesso,
    merge_slots,
    set_booking_slots,
    validar_expediente,
)
from app.router.tone_monitor import analyze_tone, ja_escalada, marcar_escalada

logger = logging.getLogger(__name__)

# MVP: simplificações conscientes desta fase (ver docs/ROADMAP.md e
# docs/superpowers/specs/2026-09-05-roteador-basico-design.md §6):
# - os documentos devolvidos pelo RAG são usados como sinal de roteamento
#   (vazio x não-vazio) E, desde o RAG real (Qdrant, Fase 2), como contexto
#   injetado no prompt do LLM — decisão registrada em docs/ARCHITECTURE.md
#   §5 (nota após a tabela de escopo); a lógica de decisão local x externo
#   em si não muda;
# - o prompt de sistema por domínio (playbook, Fase 3) é anteposto ao prompt
#   quando há um playbook para o domínio classificado (ver
#   app/router/playbooks.py); `fora_escopo` não tem playbook;
# - não há persistência das decisões do roteador em banco — a tabela
#   `router_logs` é da Fase 6; por ora só o log estruturado;
# - o texto completo da resposta do LLM vai para o log estruturado em nível
#   INFO. Aceitável neste protótipo, mas é uma simplificação deliberada
#   (risco de PII/volume em produção) a revisitar antes de qualquer uso real.


def _build_prompt(message: str, documentos: list[Document], domain: Domain) -> str:
    """Monta o prompt final: prompt de sistema do domínio (playbook) +
    contexto de RAG (quando houver) + mensagem do cliente.

    # MVP: concatenação simples dos `content` dos documentos, sem
    # sumarização/priorização por score além da ordem já devolvida pelo RAG,
    # e sem truncar por limite de tokens do modelo (ver docs/ARCHITECTURE.md
    # §5). O playbook do domínio (ver app/router/playbooks.py) é anteposto
    # quando existe; `fora_escopo` não tem playbook.
    """
    system_prompt = build_system_prompt(domain)
    partes: list[str] = []
    if system_prompt is not None:
        partes.append(system_prompt)

    if documentos:
        contexto = "\n\n".join(f"- {documento.content}" for documento in documentos)
        partes.append(
            "Use as informações a seguir, recuperadas da base de conhecimento "
            "da empresa, para responder à mensagem do cliente. Se as "
            "informações não forem suficientes, responda com o que souber, sem "
            "inventar dados específicos (preços, prazos, números de série).\n\n"
            f"Informações recuperadas:\n{contexto}"
        )

    partes.append(f"Mensagem do cliente: {message}")
    return "\n\n".join(partes)


class RouterDecision(BaseModel):
    domain: str
    complexity: str
    confidence: float
    complexity_strategy_usada: str
    backend_escolhido: str  # "local" | "externo"
    motivo_escalonamento: str  # "fora_escopo" | "rag_vazio" | "complexidade_alta" | "nenhum"
    # | (agendamento) "coleta_dados" | "horario_invalido" | "aguardando_confirmacao"
    # | "confirmado" | "mcp_indisponivel"
    resposta: str
    latencia_ms: float
    tokens_entrada: int | None
    tokens_saida: int | None
    custo_estimado_usd: float
    modelo_usado: str | None = None
    ttft_ms: float | None = None
    tps: float | None = None
    rag_retrieval_ms: float | None = None
    rag_chunks_count: int | None = None
    rag_avg_score: float | None = None
    rag_chunks: list[RagChunkMetric] | None = None
    router_provider: str = DEFAULT_INTENT_ROUTER_PROVIDER


class StatusEvent(BaseModel):
    status: str


class TokenEvent(BaseModel):
    text: str


class EscalonamentoEvent(BaseModel):
    motivo: str | None
    confianca: float
    provider_efetivo: str


class LocalBackendIndisponivelError(Exception):
    """Falha de infraestrutura no backend local (Ollama) — sem fallback automático."""


class ExternalBackendIndisponivelError(Exception):
    """Falha de infraestrutura no backend externo (OpenRouter) — sem fallback automático."""


class _AgendamentoFalhaValidacao(Exception):
    """Carrega a resposta já pronta para o visitante quando
    `_validar_horario_para_agendamento` falha — motivo é sempre
    "horario_invalido" (expediente ou conflito de agenda) ou
    "mcp_indisponivel" (falha ao consultar disponibilidade)."""

    def __init__(self, texto: str, motivo: str) -> None:
        self.texto = texto
        self.motivo = motivo
        super().__init__(texto)


async def _validar_horario_para_agendamento(
    slots: BookingSlots,
    scheduling_config: SchedulingConfig,
    calendar_client: CalendarClient,
) -> datetime:
    """Valida expediente e disponibilidade de agenda para `slots.data_hora`.

    Devolve o `datetime` com fuso horário aplicado (mesmo valor devolvido por
    `validar_expediente`, para persistir de volta em `slots.data_hora` — sem
    isso, um `datetime` naive chegaria às chamadas do MCP, ver Fix 3). Em
    falha, levanta `_AgendamentoFalhaValidacao` já com o texto de resposta e
    o motivo de escalonamento prontos.

    Compartilhado pelos dois pontos do fluxo que precisam desta validação: a
    validação original antes de pedir confirmação, E a revalidação
    obrigatória logo antes de `create_event`, mesmo quando a mensagem atual
    confirma — uma confirmação que também muda a data (ou uma confirmação
    tardia sobre um horário que ficou stale) não pode pular a checagem de
    expediente/conflito só porque `slots.awaiting_confirmation` já era
    `True`.
    """
    try:
        dh = validar_expediente(slots.data_hora, scheduling_config)
    except HorarioInvalidoError as exc:
        raise _AgendamentoFalhaValidacao(exc.motivo, "horario_invalido") from exc

    fim = dh + DURACAO_VISITA
    try:
        disponivel = await calendar_client.is_time_available(dh, fim)
    except GoogleCalendarConnectionError as exc:
        logger.error(
            "google_calendar_indisponivel",
            extra={
                "router": {
                    "event": "google_calendar_indisponivel",
                    "etapa": "checagem_disponibilidade",
                    "erro": str(exc),
                }
            },
        )
        raise _AgendamentoFalhaValidacao(MSG_ERRO_MCP, "mcp_indisponivel") from exc

    if not disponivel:
        raise _AgendamentoFalhaValidacao(
            "Esse horário já está reservado. Pode sugerir outro horário?", "horario_invalido"
        )
    return dh


async def _emitir_resposta_agendamento(
    texto: str, motivo: str, *, intent_router_provider: str
) -> AsyncIterator[TokenEvent | RouterDecision]:
    yield TokenEvent(text=texto)
    yield RouterDecision(
        domain="agendamento",
        complexity="baixa",
        confidence=1.0,
        complexity_strategy_usada="agendamento",
        backend_escolhido="local",
        motivo_escalonamento=motivo,
        resposta=texto,
        latencia_ms=0.0,
        tokens_entrada=None,
        tokens_saida=None,
        custo_estimado_usd=0.0,
        router_provider=intent_router_provider,
    )


async def _handle_agendamento(
    conversation_id: str,
    message: str,
    recent_messages: list[str],
    local_client: LLMClient,
    calendar_client: CalendarClient,
    scheduling_config: SchedulingConfig,
    intent_router_provider: str,
) -> AsyncIterator[TokenEvent | RouterDecision]:
    slots = get_booking_slots(conversation_id)
    try:
        extraction = await extract_booking_slots(
            message, recent_messages, slots, local_client, scheduling_config.timezone
        )
    except Exception as exc:
        logger.error(
            "backend_indisponivel",
            extra={
                "router": {
                    "event": "backend_indisponivel",
                    "backend": "local",
                    "etapa": "extracao_agendamento",
                    "erro": str(exc),
                }
            },
        )
        raise LocalBackendIndisponivelError(str(exc)) from exc
    slots = merge_slots(slots, extraction)

    if not slots.is_complete():
        set_booking_slots(conversation_id, slots)
        async for evento in _emitir_resposta_agendamento(
            mensagem_campos_faltando(slots),
            "coleta_dados",
            intent_router_provider=intent_router_provider,
        ):
            yield evento
        return

    if slots.awaiting_confirmation:
        if extraction.confirmacao:
            # Fix (revisão final, achado crítico 1): mesmo já confirmado,
            # revalida expediente/disponibilidade antes de criar o evento de
            # verdade — `merge_slots` já aplicou qualquer `data_hora` nova
            # extraída desta mesma mensagem ANTES deste ponto, então uma
            # mensagem que muda a data e confirma ao mesmo tempo (ou uma
            # confirmação tardia sobre um horário que ficou stale) não pode
            # pular a checagem só porque `awaiting_confirmation` já era
            # `True`.
            try:
                slots.data_hora = await _validar_horario_para_agendamento(
                    slots, scheduling_config, calendar_client
                )
            except _AgendamentoFalhaValidacao as falha:
                if falha.motivo == "horario_invalido":
                    slots.data_hora = None
                slots.awaiting_confirmation = False
                set_booking_slots(conversation_id, slots)
                async for evento in _emitir_resposta_agendamento(
                    falha.texto,
                    falha.motivo,
                    intent_router_provider=intent_router_provider,
                ):
                    yield evento
                return

            try:
                fim = slots.data_hora + DURACAO_VISITA
                await calendar_client.create_event(
                    summary=f"Visita — {slots.nome}",
                    start=slots.data_hora,
                    end=fim,
                    attendee_email=slots.email,
                    attendee_name=slots.nome,
                    description=f"Telefone: {slots.telefone}",
                )
            except GoogleCalendarConnectionError as exc:
                logger.error(
                    "google_calendar_indisponivel",
                    extra={
                        "router": {
                            "event": "google_calendar_indisponivel",
                            "etapa": "criacao_evento",
                            "erro": str(exc),
                        }
                    },
                )
                slots.awaiting_confirmation = False
                set_booking_slots(conversation_id, slots)
                async for evento in _emitir_resposta_agendamento(
                    MSG_ERRO_MCP,
                    "mcp_indisponivel",
                    intent_router_provider=intent_router_provider,
                ):
                    yield evento
                return

            texto = mensagem_sucesso(slots, scheduling_config.timezone)
            clear_booking_slots(conversation_id)
            async for evento in _emitir_resposta_agendamento(
                texto,
                "confirmado",
                intent_router_provider=intent_router_provider,
            ):
                yield evento
            return

        # Resposta ambígua durante awaiting_confirmation=True (ex.: o
        # visitante mudou data/hora em vez de confirmar claramente): volta
        # a "não confirmado ainda" em vez de só repetir a pergunta, para
        # cair no bloco de validação abaixo NO MESMO turno — se a
        # data_hora mudou para algo inválido (fora do expediente/em
        # conflito), o visitante não recebe "posso confirmar?" de novo
        # sobre um horário que na verdade não é mais válido (spec §4.1
        # passo 7).
        slots.awaiting_confirmation = False

    try:
        slots.data_hora = await _validar_horario_para_agendamento(
            slots, scheduling_config, calendar_client
        )
    except _AgendamentoFalhaValidacao as falha:
        if falha.motivo == "horario_invalido":
            slots.data_hora = None
        set_booking_slots(conversation_id, slots)
        async for evento in _emitir_resposta_agendamento(
            falha.texto,
            falha.motivo,
            intent_router_provider=intent_router_provider,
        ):
            yield evento
        return

    slots.awaiting_confirmation = True
    set_booking_slots(conversation_id, slots)
    async for evento in _emitir_resposta_agendamento(
        mensagem_pedir_confirmacao(slots, scheduling_config.timezone),
        "aguardando_confirmacao",
        intent_router_provider=intent_router_provider,
    ):
        yield evento


async def handle_message(
    message: str,
    recent_messages: list[str],
    local_client: LLMClient,
    external_client: LLMClient,
    rag_client: RAGClient,
    complexity_strategy: str,
    conversation_id: str = "",
    calendar_client: CalendarClient | None = None,
    scheduling_config: SchedulingConfig | None = None,
    intent_router_provider: str = DEFAULT_INTENT_ROUTER_PROVIDER,
    tone_monitor_enabled: bool = True,
    tone_monitor_provider: str = DEFAULT_TONE_MONITOR_PROVIDER,
) -> AsyncIterator[StatusEvent | TokenEvent | RouterDecision | EscalonamentoEvent]:
    # Monitor de Tom (R8, Fase 4B) — roda antes da classificação de
    # domínio, transversal a todo domínio (ver
    # docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md §2). Nunca
    # substitui a resposta normal: só adiciona um evento a mais no stream.
    if tone_monitor_enabled:
        tone_result = await analyze_tone(
            message=message,
            recent_messages=recent_messages,
            strategy_provider=tone_monitor_provider,
            llm_client=local_client,
            external_client=external_client,
        )
        if tone_result.escalate and not ja_escalada(conversation_id):
            marcar_escalada(conversation_id)
            yield EscalonamentoEvent(
                motivo=tone_result.motivo,
                confianca=tone_result.confidence,
                provider_efetivo=tone_result.provider_efetivo,
            )

    # Com strategy="llm" a classificação chama o backend local. Falha aqui é
    # falha de infraestrutura local, não "conteúdo não classificável" — vira
    # LocalBackendIndisponivelError em vez de degradar em silêncio para
    # fora_escopo (que rotearia ao backend externo). O wrapping fica aqui, e
    # não dentro de `classify()`, para não criar import circular.
    try:
        # No Ollama real, é a primeira chamada bloqueante ao modelo — aqui,
        # `classify()` com strategy="llm" — que paga o cold-start, não a
        # geração da resposta em si. Sem este check aqui (só existia antes
        # de `generate_stream`, mais abaixo), o cold-start acontecia em
        # silêncio durante a classificação: quando o check de depois rodava,
        # o modelo já estava carregado e o evento `status` nunca era
        # emitido, apesar da espera real ter ocorrido (bug relatado pelo
        # usuário: "a mensagem para aguardar não aparece").
        if (
            intent_router_provider == DEFAULT_INTENT_ROUTER_PROVIDER
            and complexity_strategy == "llm"
            and not await local_client.is_model_ready()
        ):
            yield StatusEvent(status="carregando_modelo")

        classification = await classify(
            message=message,
            recent_messages=recent_messages,
            strategy=complexity_strategy,
            llm_client=local_client,
            provider=intent_router_provider,
            external_client=external_client,
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

    # MVP: o ramo de agendamento só roda quando (a) o chamador forneceu
    # `calendar_client`/`scheduling_config` para esta chamada E (b) a
    # classificação por palavra-chave disse "agendamento" OU já existe
    # estado parcial de agendamento salvo para `conversation_id`. A
    # condição (b) sozinha não basta: `classify()` não tem memória de
    # conversa — mensagens de continuação do fluxo (ex.: "meu nome é
    # Maria", "sim, pode confirmar") não contêm nenhuma palavra-chave de
    # domínio, então o estado parcial salvo (b, segunda metade) é quem
    # mantém a conversa no fluxo depois do primeiro turno. A condição (a)
    # sozinha também não basta: assim que `app.api.chat` (Task 10/11)
    # passar a injetar esses dois objetos como singletons de vida da
    # aplicação em toda chamada, (a) por si só viraria sempre-verdadeiro e
    # roubaria vendas/suporte/atendimento/fora_escopo para este ramo — por
    # isso a combinação com (b). Hoje (antes da Task 10/11), `app.api.chat`
    # ainda não passa `calendar_client`/`scheduling_config`, então (a) é
    # sempre falso e o comportamento de todo domínio (inclusive mensagens
    # com palavra-chave de agendamento) permanece o do fluxo genérico até
    # a integração ser ligada — ver
    # docs/superpowers/specs/2026-09-21-agendamento-mcp-calendar-design.md
    # §4.1.
    slots_existentes = get_booking_slots(conversation_id)
    agendamento_em_andamento = (
        classification.domain == "agendamento" or slots_existentes != BookingSlots()
    )
    # MVP: limitação aceita (ver docs/ARCHITECTURE.md §7) — uma vez que uma
    # conversa entra no fluxo de agendamento (por palavra-chave OU por já
    # ter estado parcial salvo, condição `agendamento_em_andamento` acima),
    # não há como sair dele a não ser completando um agendamento com
    # sucesso: os ramos de `horario_invalido` e falha de MCP preservam os
    # slots de propósito (para permitir nova tentativa), o que mantém
    # `slots_existentes != BookingSlots()` verdadeiro indefinidamente — e o
    # classificador por palavra-chave (`ROUTER_COMPLEXITY_STRATEGY=heuristic`
    # em produção) inclui a palavra isolada "horário" entre as palavras-chave
    # de agendamento, então uma pergunta como "qual o horário de
    # funcionamento?" pode entrar no fluxo por falso positivo. Sem
    # mecanismo de abandono/timeout nesta fase — decisão do controlador:
    # ajuste de palavras-chave do classificador fica para a Fase 10 (ver
    # docs/ROADMAP.md, Fase 1) e um mecanismo de abandono pertence a uma
    # futura fase de memória/gestão de sessão, não a esta.
    if calendar_client is not None and scheduling_config is not None and agendamento_em_andamento:
        async for evento in _handle_agendamento(
            conversation_id=conversation_id,
            message=message,
            recent_messages=recent_messages,
            local_client=local_client,
            calendar_client=calendar_client,
            scheduling_config=scheduling_config,
            intent_router_provider=intent_router_provider,
        ):
            yield evento
        return

    backend_escolhido = "local"
    motivo = "nenhum"
    documentos: list[Document] = []
    rag_retrieval_ms: float | None = None
    rag_chunks_count: int | None = None
    rag_avg_score: float | None = None
    rag_chunks: list[RagChunkMetric] | None = None

    if classification.domain == "fora_escopo":
        backend_escolhido = "externo"
        motivo = "fora_escopo"
    else:
        t_rag_start = time.perf_counter()
        try:
            documentos = await rag_client.search(message, classification.domain)
            if not documentos and recent_messages:
                # MVP: mensagem de acompanhamento sem match no RAG (ex.:
                # "quais outras opções?" logo após perguntar sobre câmeras)
                # — tenta de novo com o histórico recente concatenado à
                # mensagem atual. Só dispara quando a busca direta veio
                # vazia, para não diluir o embedding com contexto
                # desnecessário no caso comum de pergunta autocontida (ver
                # docs/ARCHITECTURE.md §5).
                texto_busca = "\n".join([*recent_messages, message])
                documentos = await rag_client.search(texto_busca, classification.domain)
        except RAGConnectionError:
            logger.error(
                "rag_indisponivel",
                extra={"router": {"event": "rag_indisponivel", "domain": classification.domain}},
            )
            raise
        t_rag_end = time.perf_counter()
        rag_retrieval_ms = round((t_rag_end - t_rag_start) * 1000.0, 2)
        rag_chunks_count = len(documentos)
        if documentos:
            rag_avg_score = round(sum(d.score for d in documentos) / len(documentos), 4)
            rag_chunks = [
                RagChunkMetric(source=d.source, score=round(d.score, 4)) for d in documentos
            ]

        if not documentos:
            backend_escolhido = "externo"
            motivo = "rag_vazio"
        elif classification.complexity == "alta":
            backend_escolhido = "externo"
            motivo = "complexidade_alta"

    # A decisão de roteamento (backend_escolhido/motivo) usa só o sinal
    # vazio x não-vazio acima, sem mudar aqui; o conteúdo dos documentos
    # (quando houver) só entra a partir deste ponto, no prompt em si.
    # _build_prompt é sempre chamado para anexar o playbook do domínio (Fase
    # 3); para `fora_escopo` (sem playbook) e sem documentos, ele reduz a
    # apenas "Mensagem do cliente: ...".
    prompt = _build_prompt(message, documentos, classification.domain)

    client = local_client if backend_escolhido == "local" else external_client

    # `is_model_ready()` faz uma chamada de rede (ex.: GET /api/ps do Ollama)
    # tão sujeita a falha de infraestrutura quanto `generate_stream` — por
    # isso fica dentro do mesmo try/except abaixo, em vez de solta antes
    # dele (correção de revisão: antes, uma falha aqui propagava crua até o
    # endpoint, sem virar `LocalBackendIndisponivelError`/
    # `ExternalBackendIndisponivelError` nem o evento SSE `error`).
    texto_partes: list[str] = []
    chunk_final: LLMStreamChunk | None = None
    try:
        if not await client.is_model_ready():
            yield StatusEvent(status="carregando_modelo")

        async for chunk in client.generate_stream(prompt):
            if chunk.text:
                texto_partes.append(chunk.text)
                yield TokenEvent(text=chunk.text)
            if chunk.done:
                chunk_final = chunk

        if chunk_final is None:
            # generate_stream terminou (loop `async for` esgotou) sem nunca
            # emitir um chunk `done=True` — mesma família de falha de
            # infraestrutura que uma exceção explícita, por isso fica dentro
            # deste try/except (correção de revisão: antes, um
            # `assert` fora do try deixava esse caso escapar como
            # AssertionError cru em vez de virar `LocalBackendIndisponivelError`/
            # `ExternalBackendIndisponivelError` e o evento SSE `error`).
            raise RuntimeError("generate_stream terminou sem chunk final (done=True)")
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

    # TPS usa `eval_duration` (tempo de geração pura) — `total_duration`
    # inclui também `load_duration` (carregar o modelo) e
    # `prompt_eval_duration` (processar o prompt), então usar o total
    # subestimaria a taxa de geração de tokens.
    tps: float | None = None
    if chunk_final.completion_tokens and chunk_final.eval_duration_ms:
        gen_duration_s = max(chunk_final.eval_duration_ms / 1000.0, 0.001)
        tps = round(chunk_final.completion_tokens / gen_duration_s, 2)

    resposta_completa = "".join(texto_partes)

    decisao = RouterDecision(
        domain=classification.domain,
        complexity=classification.complexity,
        confidence=classification.confidence,
        complexity_strategy_usada=complexity_strategy,
        backend_escolhido=backend_escolhido,
        motivo_escalonamento=motivo,
        resposta=resposta_completa,
        latencia_ms=chunk_final.total_duration_ms or 0.0,
        tokens_entrada=chunk_final.prompt_tokens,
        tokens_saida=chunk_final.completion_tokens,
        custo_estimado_usd=chunk_final.estimated_cost_usd,
        modelo_usado=chunk_final.model_name or getattr(client, "model", None),
        ttft_ms=chunk_final.prompt_eval_duration_ms,
        tps=tps,
        rag_retrieval_ms=rag_retrieval_ms,
        rag_chunks_count=rag_chunks_count,
        rag_avg_score=rag_avg_score,
        rag_chunks=rag_chunks,
        # Fix (revisão final, achado importante 1): usa o provedor QUE
        # REALMENTE classificou (`classification.provider_efetivo`), não o
        # parâmetro bruto `intent_router_provider` pedido pelo chamador —
        # senão uma falha silenciosa do Jev (que degrada para a heurística
        # dentro de `_classify_with_jev`) ficaria atribuída ao Jev na
        # telemetria, corrompendo a comparação entre provedores (ver
        # docs/EVALUATION.md). O sub-fluxo de agendamento em
        # `_emitir_resposta_agendamento` NÃO chama `classify()` (tem sua
        # própria lógica de extração/estado), então continua usando o
        # parâmetro bruto — não há `ClassificationResult` de onde tirar um
        # valor efetivo ali.
        router_provider=classification.provider_efetivo,
    )
    logger.info(
        "router_decision",
        extra={"router": {"event": "router_decision", **decisao.model_dump()}},
    )
    yield decisao
