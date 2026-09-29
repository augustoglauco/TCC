export interface Agendamento {
  id: string;
  user_email: string;
  nome_cliente: string;
  telefone?: string | null;
  data_hora_inicio: string;
  data_hora_fim: string;
  descricao?: string | null;
  status: "confirmado" | "cancelado" | string;
  origem: "chat" | "manual_admin" | string;
  google_event_id?: string | null;
  google_event_link?: string | null;
  conversation_id?: string | null;
  criado_em: string;
  atualizado_em: string;
}

export interface AgendamentoManualInput {
  user_email: string;
  nome_cliente: string;
  telefone?: string | null;
  data_hora_inicio: string;
  data_hora_fim?: string | null;
  descricao?: string | null;
  forcar_sem_validacao?: boolean;
}

export interface AgendamentoAdminFilters {
  filtroEmail?: string;
  status?: string;
  dataInicio?: string;
  dataFim?: string;
}

export interface GoogleCalendarEvent {
  id: string;
  summary?: string;
  description?: string;
  start_time?: string;
  end_time?: string;
  start?: string | { dateTime?: string; date?: string };
  end?: string | { dateTime?: string; date?: string };
  html_link?: string;
  attendees?: Array<string | { email: string; displayName?: string }>;
}
