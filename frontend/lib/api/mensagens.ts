import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";

/** Contrato de `GET /api/admin/agentes/mensagens` (R13, caixa de entrada de agentes). */
export interface MensagemAgente {
  id: string;
  agente: string;
  tipo: string;
  severidade: "aviso" | "critico" | string;
  titulo: string;
  corpo: string;
  dados: Record<string, unknown> | null;
  lida: boolean;
  email_status: "enviado" | "nao_configurado" | "falhou" | "nao_enviado" | string;
  criado_em: string | null;
}

export interface MensagensResposta {
  mensagens: MensagemAgente[];
  nao_lidas: number;
}

function headers(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}`, "Cache-Control": "no-cache" };
}

export async function fetchMensagens(
  token: string,
  apenasNaoLidas = false,
): Promise<MensagensResposta> {
  const qs = apenasNaoLidas ? "&apenas_nao_lidas=true" : "";
  const response = await fetch(
    `${getApiBaseUrl()}/api/admin/agentes/mensagens?_t=${Date.now()}${qs}`,
    {
      headers: headers(token),
      cache: "no-store",
    },
  );
  if (!response.ok) throw new Error(`Falha ao consultar as mensagens (${response.status})`);
  return (await response.json()) as MensagensResposta;
}

export async function marcarMensagemLida(token: string, id: string): Promise<void> {
  const response = await fetch(`${getApiBaseUrl()}/api/admin/agentes/mensagens/${id}/lida`, {
    method: "POST",
    headers: headers(token),
  });
  if (!response.ok) throw new Error(`Falha ao marcar como lida (${response.status})`);
}

export async function marcarTodasLidas(token: string): Promise<void> {
  const response = await fetch(`${getApiBaseUrl()}/api/admin/agentes/mensagens/lidas`, {
    method: "POST",
    headers: headers(token),
  });
  if (!response.ok) throw new Error(`Falha ao marcar como lidas (${response.status})`);
}
