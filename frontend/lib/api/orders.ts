import { getApiBaseUrl } from "./apiBaseUrl";

export interface OrderItem {
  id?: string;
  produto_id: number;
  nome_produto?: string | null;
  quantidade: number;
  centro_distribuicao: string;
  preco_unitario: number;
  subtotal: number;
}

export interface Order {
  id: string;
  status: string;
  criado_em: string;
  user_email?: string | null;
  conversation_id?: string | null;
  itens: OrderItem[];
  valor_total: number;
}

export interface PaginatedOrdersResponse {
  items: Order[];
  total: number;
  limit: number;
  offset: number;
}

export interface CreateOrderItemPayload {
  produto_id: number;
  quantidade: number;
  centro_distribuicao: string;
}

export interface CreateOrderPayload {
  user_email?: string;
  conversation_id?: string;
  itens: CreateOrderItemPayload[];
}

export interface FreightQuotePayload {
  cep: string;
  itens: CreateOrderItemPayload[];
}

export interface FreightQuoteResult {
  cep: string;
  peso_total_kg: number;
  custo_estimado: number;
  prazo_dias: number;
}

export interface SimulationItemResult {
  produto_id: number;
  nome_produto?: string | null;
  quantidade: number;
  preco_unitario_base: number;
  percentual_desconto_aplicado: number;
  subtotal: number;
}

export interface QuoteSimulationResult {
  itens: SimulationItemResult[];
  valor_total: number;
}

export async function createOrder(payload: CreateOrderPayload): Promise<Order> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/api/orders`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Erro ao criar pedido: ${response.statusText}`);
  }

  return response.json();
}

export async function fetchOrders(params: {
  userEmail?: string;
  conversationId?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<PaginatedOrdersResponse> {
  const baseUrl = getApiBaseUrl();
  const urlParams = new URLSearchParams();

  if (params.userEmail) urlParams.set("user_email", params.userEmail);
  if (params.conversationId) urlParams.set("conversation_id", params.conversationId);
  if (params.limit) urlParams.set("limit", params.limit.toString());
  if (params.offset !== undefined) urlParams.set("offset", params.offset.toString());

  const response = await fetch(`${baseUrl}/api/orders?${urlParams.toString()}`);
  if (!response.ok) {
    throw new Error(`Erro ao buscar pedidos: ${response.statusText}`);
  }
  return response.json();
}

export async function fetchOrderById(orderId: string): Promise<Order> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/api/orders/${orderId}`);
  if (!response.ok) {
    throw new Error(`Erro ao buscar pedido: ${response.statusText}`);
  }
  return response.json();
}

export async function calculateFreight(payload: FreightQuotePayload): Promise<FreightQuoteResult> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/api/orders/freight`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Erro ao calcular frete: ${response.statusText}`);
  }

  return response.json();
}

export async function calculateQuote(payload: {
  itens: CreateOrderItemPayload[];
}): Promise<QuoteSimulationResult> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/api/orders/quote`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Erro ao simular cotação: ${response.statusText}`);
  }

  return response.json();
}
