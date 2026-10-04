import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";

export interface MetricSummary {
  total_closed_chats: number;
  total_internal_prompt_tokens: number;
  total_internal_completion_tokens: number;
  total_external_prompt_tokens: number;
  total_external_completion_tokens: number;
  total_cost_prompt_usd: number;
  total_cost_completion_usd: number;
  total_cost_usd: number;
}

export interface DailyMetric {
  date: string;
  closed_chats_count: number;
  internal_prompt_tokens: number;
  internal_completion_tokens: number;
  external_prompt_tokens: number;
  external_completion_tokens: number;
  cost_prompt_usd: number;
  cost_completion_usd: number;
  total_cost_usd: number;
}

export interface TokenCostMetricsResponse {
  period: string;
  summary: MetricSummary;
  daily_breakdown: DailyMetric[];
}

export interface GetMetricsParams {
  period?: "today" | "7d" | "30d" | "all" | "custom" | string;
  startDate?: string;
  endDate?: string;
}

export async function fetchTokenCostMetrics(
  token: string,
  params: GetMetricsParams = {}
): Promise<TokenCostMetricsResponse> {
  const baseUrl = getApiBaseUrl();
  const query = new URLSearchParams();
  if (params.period) query.set("period", params.period);
  if (params.startDate) query.set("start_date", params.startDate);
  if (params.endDate) query.set("end_date", params.endDate);
  query.set("_t", Date.now().toString());

  const qs = query.toString();
  const url = `${baseUrl}/api/admin/metrics/tokens-and-costs${qs ? `?${qs}` : ""}`;

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
