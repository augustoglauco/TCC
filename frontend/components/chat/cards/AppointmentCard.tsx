import Link from "next/link";
import type { ChatCardAgendamento } from "@/lib/types/chat";

function formatarDataHora(dataIso: string): string {
  try {
    return new Intl.DateTimeFormat("pt-BR", { dateStyle: "full", timeStyle: "short" }).format(
      new Date(dataIso),
    );
  } catch {
    return dataIso;
  }
}

/** Card rico de confirmação de agendamento (Fase 8, R11) — só aparece
 * quando o evento é criado de verdade no Google Calendar. */
export default function AppointmentCard({ card }: { card: ChatCardAgendamento }) {
  return (
    <div className="flex w-full max-w-[85%] flex-col gap-2 rounded-xl border border-blue-200 bg-blue-50/60 p-3 shadow-xs">
      <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-blue-700">
        <span>📅</span> Visita agendada
      </div>
      <p className="text-sm font-semibold text-slate-900">
        {formatarDataHora(card.data_hora_inicio)}
      </p>
      <div className="flex flex-wrap gap-3 text-xs font-semibold">
        <Link href="/agendamentos" className="text-blue-700 hover:underline">
          Ver meus agendamentos →
        </Link>
        {card.google_event_link && (
          <a
            href={card.google_event_link}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-700 hover:underline"
          >
            Ver no Google Calendar ↗
          </a>
        )}
      </div>
    </div>
  );
}
