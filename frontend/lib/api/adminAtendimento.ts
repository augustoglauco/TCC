import { getApiBaseUrl } from "./apiBaseUrl";

export interface AtendimentoFilaItem {
  id: string;
  status: string;
  prioridade: number;
  motivo_escalonamento: string | null;
  escalado_em: string | null;
  criada_em: string;
  atualizada_em: string;
  tempo_espera_segundos: number;
  mensagens_count: number;
  ultima_mensagem: string | null;
  cliente: {
    id: number;
    nome: string;
    email: string;
    perfil: string;
    perfil_motivo: string;
  } | null;
}

export interface AtendimentoMensagem {
  id: number;
  conversa_id: string;
  papel: "cliente" | "assistente" | "atendente" | string;
  texto: string;
  atendente_nome: string | null;
  dominio: string | null;
  criada_em: string;
}

export interface AtendimentoDetalhes {
  id: string;
  status: string;
  atendente_id: string | null;
  atendente_nome: string | null;
  prioridade: number;
  motivo_escalonamento: string | null;
  escalado_em: string | null;
  criada_em: string;
  atualizada_em: string;
  cliente: {
    id: number;
    nome: string;
    email: string;
    perfil: string;
    perfil_motivo: string;
    compras_count: number;
    total_gasto: number;
  } | null;
  mensagens: AtendimentoMensagem[];
}

export interface ClaimResponse {
  status: string;
  conversation_id: string;
  atendente_id: string;
  atendente_nome: string;
}

export interface MensagemAtendenteResponse {
  id: number;
  conversa_id: string;
  papel: string;
  texto: string;
  atendente_nome: string | null;
  criado_em: string | null;
}

export interface CloseResponse {
  status: string;
  conversation_id: string;
}

export interface TransbordoResponse {
  status: string;
  conversation_id: string;
}

function getAuthHeaders(token?: string): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

export async function fetchFilaEspera(token?: string): Promise<AtendimentoFilaItem[]> {
  const baseUrl = getApiBaseUrl();
  const res = await fetch(`${baseUrl}/api/admin/atendimento/fila`, {
    headers: getAuthHeaders(token),
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Erro ao carregar fila de atendimento (${res.status}).`);
  }
  return res.json();
}

export async function fetchMeusChats(
  atendenteId: string,
  token?: string,
): Promise<AtendimentoFilaItem[]> {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}/api/admin/atendimento/meus-chats?atendente_id=${encodeURIComponent(atendenteId)}`;
  const res = await fetch(url, {
    headers: getAuthHeaders(token),
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Erro ao carregar meus chats (${res.status}).`);
  }
  return res.json();
}

export async function fetchDetalhesConversa(
  conversationId: string,
  token?: string,
): Promise<AtendimentoDetalhes> {
  const baseUrl = getApiBaseUrl();
  const res = await fetch(`${baseUrl}/api/admin/atendimento/${conversationId}`, {
    headers: getAuthHeaders(token),
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Erro ao carregar detalhes da conversa (${res.status}).`);
  }
  return res.json();
}

export async function claimConversa(
  conversationId: string,
  atendenteId: string,
  atendenteNome: string,
  token?: string,
): Promise<ClaimResponse> {
  const baseUrl = getApiBaseUrl();
  const res = await fetch(`${baseUrl}/api/admin/atendimento/${conversationId}/claim`, {
    method: "POST",
    headers: getAuthHeaders(token),
    body: JSON.stringify({ atendente_id: atendenteId, atendente_nome: atendenteNome }),
  });
  if (res.status === 409) {
    const errorData = await res.json().catch(() => ({ detail: "Chat já foi assumido." }));
    throw new Error(errorData.detail || "Esta conversa já foi assumida por outro atendente.");
  }
  if (!res.ok) {
    throw new Error(`Erro ao assumir atendimento (${res.status}).`);
  }
  return res.json();
}

export async function enviarMensagemAtendente(
  conversationId: string,
  atendenteNome: string,
  texto: string,
  token?: string,
): Promise<MensagemAtendenteResponse> {
  const baseUrl = getApiBaseUrl();
  const res = await fetch(`${baseUrl}/api/admin/atendimento/${conversationId}/mensagem`, {
    method: "POST",
    headers: getAuthHeaders(token),
    body: JSON.stringify({ atendente_nome: atendenteNome, texto }),
  });
  if (!res.ok) {
    throw new Error(`Erro ao enviar mensagem do atendente (${res.status}).`);
  }
  return res.json();
}

export async function fecharAtendimento(
  conversationId: string,
  acao: "finalizar" | "devolver_ia",
  motivo?: string,
  token?: string,
): Promise<CloseResponse> {
  const baseUrl = getApiBaseUrl();
  const res = await fetch(`${baseUrl}/api/admin/atendimento/${conversationId}/close`, {
    method: "POST",
    headers: getAuthHeaders(token),
    body: JSON.stringify({ acao, motivo }),
  });
  if (!res.ok) {
    throw new Error(`Erro ao encerrar atendimento (${res.status}).`);
  }
  return res.json();
}

export async function solicitarTransbordo(
  conversationId: string,
  motivo?: string,
): Promise<TransbordoResponse> {
  const baseUrl = getApiBaseUrl();
  const res = await fetch(`${baseUrl}/api/chat/conversations/${conversationId}/transbordo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ motivo: motivo || "solicitacao_cliente" }),
  });
  if (!res.ok) {
    throw new Error(`Erro ao solicitar atendimento humano (${res.status}).`);
  }
  return res.json();
}
