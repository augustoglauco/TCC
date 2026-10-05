import { getApiBaseUrl } from "./apiBaseUrl";

export interface PedidoItemOut {
  id: string;
  produto_id: number;
  centro_distribuicao: string;
  quantidade: number;
  preco_unitario: number;
  subtotal: number;
}

export interface PedidoAdminItem {
  id: string;
  status: "reservado" | "venda_concluida" | "pagamento_divergente" | string;
  user_email: string | null;
  conversation_id: string | null;
  comprovante_url: string | null;
  tipo_conversao: string | null;
  convertido_em: string | null;
  convertido_por: string | null;
  llm_parecer: string | null;
  criado_em: string | null;
  valor_total: number;
  itens: PedidoItemOut[];
}

export interface ParecerFinanceiro {
  valido: boolean;
  valor_pago: number;
  divergencia: number;
  justificativa: string;
  codigo_transacao?: string | null;
}

export interface AnaliseComprovanteResponse {
  pedido_id: string;
  valor_devido: number;
  comprovante_url: string;
  parecer: ParecerFinanceiro;
}

function getAuthHeaders(token?: string): Record<string, string> {
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

export async function fetchPedidos(
  params?: { status?: string; limit?: number; offset?: number },
  token?: string
): Promise<PedidoAdminItem[]> {
  const baseUrl = getApiBaseUrl();
  const query = new URLSearchParams();
  if (params?.status && params.status !== "todos") {
    query.set("status", params.status);
  }
  if (params?.limit) {
    query.set("limit", String(params.limit));
  }
  if (params?.offset) {
    query.set("offset", String(params.offset));
  }

  const queryString = query.toString();
  const url = `${baseUrl}/api/admin/pedidos${queryString ? `?${queryString}` : ""}`;

  const res = await fetch(url, {
    headers: getAuthHeaders(token),
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`Erro ao carregar lista de pedidos (${res.status}).`);
  }
  return res.json();
}

export async function fetchPedido(
  pedidoId: string,
  token?: string
): Promise<PedidoAdminItem> {
  const baseUrl = getApiBaseUrl();
  const res = await fetch(`${baseUrl}/api/admin/pedidos/${pedidoId}`, {
    headers: getAuthHeaders(token),
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`Erro ao carregar pedido (${res.status}).`);
  }
  return res.json();
}

export async function converterManualSimples(
  pedidoId: string,
  payload: { convertido_por?: string; comprovante?: File },
  token?: string
): Promise<PedidoAdminItem> {
  const baseUrl = getApiBaseUrl();
  const formData = new FormData();
  if (payload.convertido_por) {
    formData.append("convertido_por", payload.convertido_por);
  }
  if (payload.comprovante) {
    formData.append("comprovante", payload.comprovante);
  }

  const res = await fetch(`${baseUrl}/api/admin/pedidos/${pedidoId}/converter-manual-simples`, {
    method: "POST",
    headers: getAuthHeaders(token),
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Erro desconhecido" }));
    throw new Error(err.detail || `Erro ao converter pedido manualmente (${res.status}).`);
  }
  return res.json();
}

export async function analisarComprovante(
  pedidoId: string,
  comprovante: File,
  token?: string
): Promise<AnaliseComprovanteResponse> {
  const baseUrl = getApiBaseUrl();
  const formData = new FormData();
  formData.append("comprovante", comprovante);

  const res = await fetch(`${baseUrl}/api/admin/pedidos/${pedidoId}/analisar-comprovante`, {
    method: "POST",
    headers: getAuthHeaders(token),
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Erro na análise" }));
    throw new Error(err.detail || `Erro ao submeter comprovante para IA (${res.status}).`);
  }
  return res.json();
}

export async function confirmarConversaoManual(
  pedidoId: string,
  payload: { comprovante_url?: string; parecer_json?: string; convertido_por?: string },
  token?: string
): Promise<PedidoAdminItem> {
  const baseUrl = getApiBaseUrl();
  const headers = getAuthHeaders(token);
  headers["Content-Type"] = "application/json";

  const res = await fetch(`${baseUrl}/api/admin/pedidos/${pedidoId}/confirmar-conversao`, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Erro ao confirmar" }));
    throw new Error(err.detail || `Erro ao confirmar conversão (${res.status}).`);
  }
  return res.json();
}

export async function converterAutoAdmin(
  pedidoId: string,
  comprovante: File,
  token?: string
): Promise<PedidoAdminItem> {
  const baseUrl = getApiBaseUrl();
  const formData = new FormData();
  formData.append("comprovante", comprovante);

  const res = await fetch(`${baseUrl}/api/admin/pedidos/${pedidoId}/converter-auto-admin`, {
    method: "POST",
    headers: getAuthHeaders(token),
    body: formData,
  });

  if (res.status === 422) {
    const err = await res.json();
    throw new Error(`Divergência detectada: ${err.justificativa || "Comprovante com divergência"}`);
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Erro na conversão automática" }));
    throw new Error(err.detail || `Erro na conversão automática (${res.status}).`);
  }
  return res.json();
}
