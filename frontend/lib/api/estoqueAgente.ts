import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";

/** Contrato de `GET /api/admin/agentes/estoque/status` (R13, indicador do catálogo). */
export interface ExecucaoAgenteEstoque {
  criado_em: string | null;
  modo: string;
  produtos_avaliados: number;
  alertas_criados: number;
  erro: string | null;
}

export interface StatusAgenteEstoque {
  modo: "desativado" | "deterministico" | "ia" | string;
  llm: "local" | "externo" | null;
  ultima_execucao: ExecucaoAgenteEstoque | null;
  ultimo_alerta_em: string | null;
}

export async function fetchStatusAgenteEstoque(token: string): Promise<StatusAgenteEstoque> {
  const response = await fetch(`${getApiBaseUrl()}/api/admin/agentes/estoque/status`, {
    headers: { Authorization: `Bearer ${token}`, "Cache-Control": "no-cache" },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Falha ao consultar o agente de estoque (${response.status})`);
  }
  return (await response.json()) as StatusAgenteEstoque;
}
