// MVP: visualização ilustrativa de agendamentos via Google Calendar (ver docs/ROADMAP.md, Fase 4/7)
const SAMPLE_APPOINTMENTS = [
  {
    id: "AG-101",
    title: "Visita Técnica — Avaliação de Manutenção",
    date: "22/09/2026 às 14:30",
    location: "Planta Industrial São Paulo",
    status: "Confirmado (Google Calendar)",
  },
];

export default function AgendamentosPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:py-12 space-y-8">
      {/* Cabeçalho */}
      <div className="border-b border-slate-200 pb-6">
        <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
          <span>📅</span> Integração MCP Google Calendar
        </div>
        <h1 className="mt-3 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
          Minhas Visitas & Agendamentos
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          Agendamentos realizados automaticamente através do Assistente Virtual.
        </p>
      </div>

      {/* Agendamentos */}
      <div className="space-y-4">
        {SAMPLE_APPOINTMENTS.map((item) => (
          <div
            key={item.id}
            className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-xs"
          >
            <div className="space-y-1">
              <span className="text-xs font-semibold text-emerald-600 uppercase tracking-wider">
                {item.status}
              </span>
              <h3 className="text-base font-bold text-slate-900">{item.title}</h3>
              <p className="text-xs sm:text-sm text-slate-600">
                📍 {item.location} • 🕒 {item.date}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
