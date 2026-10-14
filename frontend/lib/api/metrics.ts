import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";

/**
 * Contrato de `GET /api/admin/metrics/ai-usage` (item E do ledger de uso
 * de IA). Substituiu `/tokens-and-costs`.
 *
 * `tokens_entrada`/`tokens_saida`/`custo_usd` são `number | null`: `null`
 * é "não medido", `0` é "grátis". Nunca normalize `null` para `0` aqui —
 * use os helpers de `@/lib/format/metricas` na renderização.
 */

export interface BlocoMetricas {
  chamadas: number;
  tokens_entrada: number | null;
  tokens_saida: number | null;
  custo_usd: number | null;
  chamadas_sem_custo_medido: number;
}

export interface MetricasPorOrigem extends BlocoMetricas {
  origem: string;
}

export interface MetricasPorAmbiente extends BlocoMetricas {
  ambiente: string;
}

export interface MetricasPorModelo extends BlocoMetricas {
  modelo: string;
  ambiente: string;
}

export interface MetricasPorOperacao extends BlocoMetricas {
  operacao: string;
  origem: string;
  ambiente: string;
}

export interface DiaUsoIa {
  data: string;
  chats_encerrados: number;
  totais: BlocoMetricas;
  por_origem: MetricasPorOrigem[];
}

export interface AiUsageReport {
  period: string;
  atendimento: { chats_encerrados: number };
  totais: BlocoMetricas;
  por_origem: MetricasPorOrigem[];
  por_ambiente: MetricasPorAmbiente[];
  por_modelo: MetricasPorModelo[];
  por_operacao: MetricasPorOperacao[];
  diario: DiaUsoIa[];
}

export interface GetMetricsParams {
  period?: "today" | "7d" | "30d" | "all" | "custom" | string;
  startDate?: string;
  endDate?: string;
}

export async function fetchAiUsageMetrics(
  token: string,
  params: GetMetricsParams = {},
): Promise<AiUsageReport> {
  const baseUrl = getApiBaseUrl();
  const query = new URLSearchParams();
  if (params.period) query.set("period", params.period);
  if (params.startDate) query.set("start_date", params.startDate);
  if (params.endDate) query.set("end_date", params.endDate);
  query.set("_t", Date.now().toString());

  const qs = query.toString();
  const url = `${baseUrl}/api/admin/metrics/ai-usage${qs ? `?${qs}` : ""}`;

  const response = await fetch(url, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-cache",
      Pragma: "no-cache",
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Falha ao obter métricas (${response.status})`);
  }

  return response.json();
}
