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

export interface ChatMessageResponse {
  conversation_id: string;
  message: string;
  domain: ChatDomain;
  backend_used: ChatBackendUsed;
  escalation_reason: ChatEscalationReason;
  // Preenchido apenas quando o request trouxe `audio` — texto transcrito
  // pelo STT do backend, usado para exibir "o que a pessoa falou" na bolha
  // do usuário (o cliente não tem como saber isso sozinho).
  transcribed_message: string | null;
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
}
