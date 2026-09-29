import { getApiBaseUrl } from "./apiBaseUrl";
import type {
  Agendamento,
  AgendamentoAdminFilters,
  AgendamentoManualInput,
  GoogleCalendarEvent,
} from "@/lib/types/agendamentos";

export async function fetchMeusAgendamentos(userEmail: string): Promise<Agendamento[]> {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}/api/agendamentos/meus?user_email=${encodeURIComponent(userEmail)}`;
  const response = await fetch(url);
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || "Erro ao buscar agendamentos.");
  }
  return response.json();
}

export async function cancelarAgendamento(id: string, userEmail: string): Promise<Agendamento> {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}/api/agendamentos/${id}/cancelar?user_email=${encodeURIComponent(userEmail)}`;
  const response = await fetch(url, {
    method: "POST",
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || "Erro ao cancelar agendamento.");
  }
  return response.json();
}

export async function fetchAdminAgendamentos(
  filters: AgendamentoAdminFilters = {}
): Promise<Agendamento[]> {
  const baseUrl = getApiBaseUrl();
  const params = new URLSearchParams();
  if (filters.filtroEmail) params.set("filtro_email", filters.filtroEmail);
  if (filters.status) params.set("status", filters.status);
  if (filters.dataInicio) params.set("data_inicio", filters.dataInicio);
  if (filters.dataFim) params.set("data_fim", filters.dataFim);

  const query = params.toString() ? `?${params.toString()}` : "";
  const response = await fetch(`${baseUrl}/api/agendamentos/admin${query}`);
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || "Erro ao listar agendamentos administrativos.");
  }
  return response.json();
}

export async function criarAgendamentoManual(
  payload: AgendamentoManualInput
): Promise<Agendamento> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/api/agendamentos/admin/manual`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || "Erro ao criar agendamento manual.");
  }
  return response.json();
}

export async function fetchGoogleCalendarEvents(
  params: {
    timeMin?: string;
    timeMax?: string;
  } = {}
): Promise<GoogleCalendarEvent[]> {
  const baseUrl = getApiBaseUrl();
  const searchParams = new URLSearchParams();
  if (params.timeMin) searchParams.set("time_min", params.timeMin);
  if (params.timeMax) searchParams.set("time_max", params.timeMax);

  const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
  const response = await fetch(`${baseUrl}/api/agendamentos/admin/google-events${query}`);
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || "Erro ao consultar eventos do Google Calendar.");
  }
  return response.json();
}
