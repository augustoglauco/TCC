interface ProcessStep {
  number: string;
  title: string;
  subtitle: string;
  description: string;
}

const STEPS: ProcessStep[] = [
  {
    number: "01",
    title: "Consulta Multimodal",
    subtitle: "Voz, Imagem & Texto",
    description:
      "Texto, foto de placa ou áudio via Whisper analisados em tempo real com identificação visual CLIP e OCR.",
  },
  {
    number: "02",
    title: "Roteamento Híbrido",
    subtitle: "Orquestrador Inteligente",
    description:
      "Decisão inteligente entre GPU local 16GB e modelo externo, combinada à busca vetorial semântica RAG.",
  },
  {
    number: "03",
    title: "Cotação MCP B2B",
    subtitle: "Catálogo & Estoque Real",
    description:
      "Consulta de estoque em tempo real e reserva de lotes com validação automática de compatibilidade técnica.",
  },
  {
    number: "04",
    title: "Agendamento de Visita",
    subtitle: "Integração Direta",
    description:
      "Sincronização instantânea com Google Calendar e confirmação automatizada para vistoria ou implantação.",
  },
];

export default function ProcessSteps() {
  return (
    <section className="space-y-8 py-6 sm:py-10">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <span className="text-xs font-bold uppercase tracking-widest text-blue-600">
            Como Trabalhamos
          </span>
          <h2 className="text-2xl sm:text-4xl font-extrabold tracking-tight text-slate-900 mt-1">
            Fluxo de Atendimento{" "}
            <span className="bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
              Inteligente de Ponta a Ponta
            </span>
          </h2>
        </div>
        <p className="text-xs sm:text-sm text-slate-500 max-w-md">
          Da identificação visual do equipamento até a reserva de lote B2B ou agendamento técnico em
          4 etapas integradas.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {STEPS.map((step, idx) => (
          <div
            key={step.number}
            className="group relative flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-6 shadow-xs hover:shadow-lg hover:border-blue-400 transition-all"
          >
            <div>
              <div className="flex items-center justify-between gap-2 mb-5">
                <span className="inline-flex items-center justify-center rounded-xl bg-slate-950 px-3 py-1.5 font-mono text-sm font-extrabold text-blue-400 group-hover:bg-blue-600 group-hover:text-white transition-colors">
                  {step.number}
                </span>
                {idx < STEPS.length - 1 && (
                  <span
                    aria-hidden="true"
                    className="hidden lg:inline-block text-xs font-mono text-slate-300 group-hover:text-blue-400 transition-colors"
                  >
                    ───▸
                  </span>
                )}
              </div>

              <span className="text-[11px] font-bold uppercase tracking-wider text-blue-600">
                {step.subtitle}
              </span>
              <h3 className="text-base sm:text-lg font-bold text-slate-900 mt-1">
                {step.number}. {step.title}
              </h3>
              <p className="mt-2.5 text-xs text-slate-600 leading-relaxed">{step.description}</p>
            </div>

            <div className="mt-6 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] font-semibold text-slate-400">
              <span>Etapa {step.number} de 04</span>
              <span className="text-blue-600">● Ativo</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
