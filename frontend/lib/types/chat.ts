/**
 * Tipos do contrato de `POST /api/chat/messages` (ver `docs/FRONTEND.md` §4 e
 * `backend/src/app/models/chat.py`). Mantidos em sincronia manual com o
 * backend nesta etapa do protótipo.
 */

export type ChatDomain = "vendas" | "suporte" | "atendimento" | "agendamento" | "fora_escopo";

export type ChatBackendUsed = "local" | "externo";

export type ChatEscalationReason = "nenhum" | "fora_escopo" | "rag_vazio" | "complexidade_alta";

export interface ChatMessageRequest {
  message: string;
  conversation_id?: string;
  // MVP: áudio ainda não é capturado pelo widget nesta etapa (texto apenas);
  // o campo é sempre `null`, aceito e ignorado pelo backend (ver
  // docs/FRONTEND.md §4, R5 pendente).
  audio: null;
}

export interface ChatMessageResponse {
  conversation_id: string;
  message: string;
  domain: ChatDomain;
  backend_used: ChatBackendUsed;
  escalation_reason: ChatEscalationReason;
}

/** Mensagem exibida no painel do chat (estado de UI, não o payload da API). */
export interface ChatUIMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  domain?: ChatDomain;
}
