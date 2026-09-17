/**
 * Tipos do contrato de `POST /api/chat/messages` (ver `docs/FRONTEND.md` §4 e
 * `backend/src/app/models/chat.py`). Mantidos em sincronia manual com o
 * backend nesta etapa do protótipo.
 */

export type ChatDomain = "vendas" | "suporte" | "atendimento" | "agendamento" | "fora_escopo";

export type ChatBackendUsed = "local" | "externo";

export type ChatEscalationReason = "nenhum" | "fora_escopo" | "rag_vazio" | "complexidade_alta";

export interface ChatMessageRequest {
  // Opcional: obrigatório enviar `message` e/ou `audio` (backend valida e
  // retorna 422 se nenhum dos dois vier preenchido).
  message?: string;
  conversation_id?: string;
  // Base64 do áudio gravado pelo `AudioRecorder` (qualquer formato aceito
  // pelo backend, tipicamente audio/webm) — `null` quando a mensagem é só
  // texto.
  audio: string | null;
}

export interface ChatMetrics {
  modelName?: string;
  promptTokens?: number;
  completionTokens?: number;
  latencyMs?: number;
  ttftMs?: number;
  tps?: number;
  confidence?: number;
  complexity?: string;
  estimatedCostUsd?: number;
  ragRetrievalMs?: number;
  ragChunksCount?: number;
  ragAvgScore?: number;
  escalationReason?: ChatEscalationReason;
}

export interface ChatDoneEventData {
  domain: ChatDomain;
  backend_used: ChatBackendUsed;
  escalation_reason: ChatEscalationReason;
  model_name?: string | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  latency_ms?: number | null;
  ttft_ms?: number | null;
  tps?: number | null;
  confidence?: number | null;
  complexity?: string | null;
  estimated_cost_usd?: number | null;
  rag_retrieval_ms?: number | null;
  rag_chunks_count?: number | null;
  rag_avg_score?: number | null;
}

/** Mensagem exibida no painel do chat (estado de UI, não o payload da API). */
export interface ChatUIMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  domain?: ChatDomain;
  // Só preenchido em mensagens do assistente — origem do modelo que gerou a
  // resposta (R1/R3), usada para destacar visualmente respostas de LLM
  // externo (ver MessageBubble).
  backendUsed?: ChatBackendUsed;
  metrics?: ChatMetrics;
}

