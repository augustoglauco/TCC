import type { ChatDoneEventData, ChatMetrics } from "@/lib/types/chat";

/**
 * Converte o evento `done` do SSE nas métricas do painel ⚙️. Usado ao receber
 * a resposta (`ChatModal`) e ao recarregar o histórico gravado
 * (`fetchConversationHistory`, R9), para o painel ficar igual nos dois casos.
 */
export function metricsFromDone(data: ChatDoneEventData): ChatMetrics {
  return {
    modelName: data.model_name ?? undefined,
    promptTokens: data.prompt_tokens ?? undefined,
    completionTokens: data.completion_tokens ?? undefined,
    latencyMs: data.latency_ms ?? undefined,
    ttftMs: data.ttft_ms ?? undefined,
    tps: data.tps ?? undefined,
    confidence: data.confidence ?? undefined,
    complexity: data.complexity ?? undefined,
    estimatedCostUsd: data.estimated_cost_usd ?? undefined,
    ragRetrievalMs: data.rag_retrieval_ms ?? undefined,
    ragChunksCount: data.rag_chunks_count ?? undefined,
    ragAvgScore: data.rag_avg_score ?? undefined,
    ragChunks: data.rag_chunks ?? undefined,
    escalationReason: data.escalation_reason,
    routerProvider: data.router_provider ?? undefined,
    perfilUsuario: data.perfil_usuario ?? undefined,
    perfilMotivo: data.perfil_motivo ?? undefined,
  };
}
