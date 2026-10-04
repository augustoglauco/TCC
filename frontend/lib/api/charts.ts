import { getApiBaseUrl } from "./apiBaseUrl";
import type { AdminChartData } from "@/components/admin/DynamicChartCard";

export async function fetchAdminCharts(token: string): Promise<AdminChartData[]> {
  const baseUrl = getApiBaseUrl();
  const res = await fetch(`${baseUrl}/api/admin/charts`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok) {
    throw new Error("Erro ao carregar dashboards.");
  }
  return res.json();
}

export async function refreshAdminChart(id: string, token: string): Promise<AdminChartData> {
  const baseUrl = getApiBaseUrl();
  const res = await fetch(`${baseUrl}/api/admin/charts/${id}/refresh`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok) {
    throw new Error("Erro ao atualizar dados do gráfico.");
  }
  return res.json();
}

export async function updateAdminChart(
  id: string,
  payload: Partial<AdminChartData>,
  token: string,
): Promise<AdminChartData> {
  const baseUrl = getApiBaseUrl();
  const res = await fetch(`${baseUrl}/api/admin/charts/${id}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error("Erro ao salvar alterações do gráfico.");
  }
  return res.json();
}

export async function deleteAdminChart(id: string, token: string): Promise<{ ok: boolean }> {
  const baseUrl = getApiBaseUrl();
  const res = await fetch(`${baseUrl}/api/admin/charts/${id}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok) {
    throw new Error("Erro ao excluir gráfico.");
  }
  return res.json();
}
