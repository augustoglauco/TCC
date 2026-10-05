/**
 * Tipos do contrato de `POST /api/chat/messages` (ver `docs/FRONTEND.md` §4 e
 * `backend/src/app/models/chat.py`). Mantidos em sincronia manual com o
 * backend nesta etapa do protótipo.
 */

export type ChatDomain = "vendas" | "suporte" | "atendimento" | "agendamento" | "fora_escopo";

// "resposta_fixa": mensagem só com e-mail, respondida sem LLM (R10);
// "identificacao_imagem": fluxo de identificação de produto por imagem.
export type ChatBackendUsed = "local" | "externo" | "resposta_fixa" | "identificacao_imagem";

export type ChatEscalationReason = "nenhum" | "fora_escopo" | "rag_vazio" | "complexidade_alta";

export interface ChatMessageRequest {
  // Opcional: obrigatório enviar `message`, `audio` e/ou `image` (backend valida e
  // retorna 422 se nenhum dos três vier preenchido).
  message?: string;
  conversation_id?: string;
  // Base64 do áudio gravado pelo `AudioRecorder` (qualquer formato aceito
  // pelo backend, tipicamente audio/webm) — `null` quando a mensagem é só
  // texto.
  audio: string | null;
  // Base64 da imagem (PNG/JPG/WEBP) — OCR extrai o texto no backend (R6).
  image?: string | null;
  // E-mail do usuário autenticado no frontend (R10, Fase 7).
  user_email?: string | null;
  // Token de POST /api/auth/login quando o usuário está logado — verificado
  // no servidor para liberar o modo admin de busca no RAG (decisão de
  // 2026-09-30, docs/ARCHITECTURE.md §6). Nunca usar user_email sozinho
  // para isso.
  auth_token?: string | null;
}

/** Fonte (arquivo de origem) e score de um chunk usado no contexto do RAG. */
export interface ChatRagChunk {
  source: string;
  score: number;
}

/** Classificação do visitante (R10, Fase 6) — ver docs/ARCHITECTURE.md §5. */
export type ChatPerfilUsuario = "cliente" | "esporadico" | "lead" | "nao_classificado";

/** Alerta de escalonamento disparado pelo Monitor de Tom (R8, Fase 4B/8). */
export interface ChatEscalonamentoData {
  motivo?: "urgencia" | "insatisfacao" | string | null;
  confianca?: number | null;
}

/**
 * Cards ricos (Fase 8, correção de 2026-09-29) — dados estruturados vindos
 * junto do evento `done`, para renderizar em vez de/além do texto puro.
 * Discriminados por `tipo`, mesmo padrão do backend (`app.models.chat.ChatCard`).
 */
export interface ChatCardProduto {
  tipo: "produto";
  produto_id: number;
  nome: string;
  preco: string;
  imagem_url?: string | null;
  estoque_total: number;
}

export interface ChatCardCotacao {
  tipo: "cotacao";
  produto_id: number;
  nome: string;
  quantidade: number;
  preco_unitario: string;
  percentual_desconto: string;
  subtotal: string;
}

export interface ChatCardAgendamento {
  tipo: "agendamento";
  data_hora_inicio: string;
  data_hora_fim: string;
  google_event_link?: string | null;
}

export interface ChatCardGrafico {
  tipo: "grafico";
  chart_id: string;
  titulo: string;
  tipo_grafico: "bar" | "line" | "pie" | "area" | "donut";
  config: {
    x_key?: string;
    y_keys?: string[];
    labels?: Record<string, string>;
    format?: "currency" | "number" | "percent";
    palette?: string[];
    [key: string]: unknown;
  };
  dados: Array<Record<string, unknown>>;
  fixado?: boolean;
}

/** Card de download de documento-fonte do RAG (Fase 8) — só emitido pelo
 * backend para documentos cuja coleção de origem tem `purpose="chat"`, ou
 * seja, o link de download nunca exige token (ver
 * `_construir_card_documento_download` em `backend/src/app/router/orchestrator.py`). */
export interface ChatCardDocumentoDownload {
  tipo: "documento_download";
  documento_id: string;
  filename: string;
  domain: string;
  score: number;
  download_url: string;
  file_size_bytes?: number | null;
}

export type ChatCard =
  | ChatCardProduto
  | ChatCardCotacao
  | ChatCardAgendamento
  | ChatCardGrafico
  | ChatCardDocumentoDownload;

export interface ChatMetrics {
  modelName?: string;
  promptTokens?: number;
  completionTokens?: number;
  latencyMs?: number;
  ttftMs?: number;
  tps?: number;
  confidence?: number;
  complexity?: string;
  costPromptUsd?: number;
  costCompletionUsd?: number;
  estimatedCostUsd?: number;
  ragRetrievalMs?: number;
  ragChunksCount?: number;
  ragAvgScore?: number;
  ragChunks?: ChatRagChunk[];
  escalationReason?: ChatEscalationReason;
  routerProvider?: string;
  perfilUsuario?: ChatPerfilUsuario;
  perfilMotivo?: string;
  visionUsed?: boolean;
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
  cost_prompt_usd?: number | null;
  cost_completion_usd?: number | null;
  estimated_cost_usd?: number | null;
  rag_retrieval_ms?: number | null;
  rag_chunks_count?: number | null;
  rag_avg_score?: number | null;
  rag_chunks?: ChatRagChunk[] | null;
  router_provider?: string | null;
  perfil_usuario?: ChatPerfilUsuario | null;
  perfil_motivo?: string | null;
  vision_used?: boolean | null;
  card?: ChatCard | null;
  conversa_status?: string | null;
  atendente_nome?: string | null;
}

/** Mensagem exibida no painel do chat (estado de UI, não o payload da API). */
export interface ChatUIMessage {
  id: string;
  role: "user" | "assistant" | "atendente";
  text: string;
  domain?: ChatDomain;
  // Só preenchido em mensagens do assistente — origem do modelo que gerou a
  // resposta (R1/R3), usada para destacar visualmente respostas de LLM
  // externo (ver MessageBubble).
  backendUsed?: ChatBackendUsed;
  metrics?: ChatMetrics;
  atendenteNome?: string;
  // Card rico (Fase 8) — produto, cotação ou confirmação de agendamento.
  card?: ChatCard;
}

/** Uma mensagem gravada da conversa — `GET /api/chat/conversations/{id}` (R9). */
export interface ConversaMensagem {
  papel: "cliente" | "assistente" | "atendente";
  texto: string;
  dominio: ChatDomain | null;
  criada_em: string;
  atendente_nome?: string | null;
  /** Evento `done` da resposta (só do assistente); `null` em mensagens antigas. */
  metricas: ChatDoneEventData | null;
}

/** Corpo de `GET /api/chat/conversations/{id}` (R9). */
export interface ConversaHistorico {
  conversation_id: string;
  resumo: string | null;
  mensagens: ConversaMensagem[];
}
