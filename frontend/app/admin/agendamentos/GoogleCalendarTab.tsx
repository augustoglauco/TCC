"use client";

import type { GoogleCalendarEvent } from "@/lib/types/agendamentos";

function formatarDataHora(dataIso: string): string {
  try {
    return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(
      new Date(dataIso),
    );
  } catch {
    return dataIso;
  }
}

interface Props {
  googleEvents: GoogleCalendarEvent[];
  loading: boolean;
  error: string | null;
  onAtualizar: () => void;
}

export function GoogleCalendarTab({ googleEvents, loading, error, onAtualizar }: Props) {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs flex items-center justify-between">
        <span className="text-sm text-slate-600">
          Eventos consultados diretamente da agenda corporativa via protocolo MCP.
        </span>
        <button
          type="button"
          onClick={onAtualizar}
          className="rounded-lg bg-slate-800 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-slate-700 cursor-pointer"
        >
          🔄 Atualizar Agenda
        </button>
      </div>

      {loading ? (
        <div className="py-12 text-center text-slate-500 text-sm">
          Consultando Google Calendar...
        </div>
      ) : error ? (
        <div className="p-4 rounded-xl border border-red-200 bg-red-50 text-red-700 text-sm">
          {error}
        </div>
      ) : googleEvents.length === 0 ? (
        <div className="py-12 text-center text-slate-500 text-sm rounded-xl border border-slate-200 bg-white">
          Nenhum evento encontrado no período consultado.
        </div>
      ) : (
        <div className="space-y-3">
          {googleEvents.map((evt) => {
            const startTime =
              evt.start_time ||
              (typeof evt.start === "string"
                ? evt.start
                : evt.start?.dateTime || evt.start?.date) ||
              "";
            return (
              <div
                key={evt.id}
                className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-xs"
              >
                <div>
                  <h4 className="font-bold text-slate-900">{evt.summary || "(Sem Título)"}</h4>
                  {startTime && (
                    <p className="text-xs text-slate-600 mt-1">🕒 {formatarDataHora(startTime)}</p>
                  )}
                  {evt.description && (
                    <p className="text-xs text-slate-500 mt-1 max-w-xl">{evt.description}</p>
                  )}
                </div>
                {evt.html_link && (
                  <a
                    href={evt.html_link}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs font-semibold text-purple-600 hover:underline shrink-0"
                  >
                    Ver no Google ↗
                  </a>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
