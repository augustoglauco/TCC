interface MetricItem {
  value: string;
  label: string;
  detail: string;
  tag: string;
}

const METRICS: MetricItem[] = [
  {
    value: "99.9%",
    label: "Precisão em Reconhecimento Facial",
    detail: "Algoritmo Biométrico Neural",
    tag: "BIOMETRIA 3D",
  },
  {
    value: "< 0.2s",
    label: "Velocidade de Leitura e Autenticação",
    detail: "Validação instantânea sem contato físico",
    tag: " TEMPO REAL",
  },
  {
    value: "100%",
    label: "Conformidade Portaria 671 MTE & LGPD",
    detail: "Segurança jurídica e homologação oficial",
    tag: "HOMOLOGADO",
  },
  {
    value: "24/7",
    label: "Assistente de IA & RAG Local",
    detail: "Inferência dedicada em GPU 16GB + Protocolo MCP",
    tag: "IA MULTIMODAL",
  },
];

export default function MetricCounters() {
  return (
    <section className="rounded-3xl bg-slate-950 border border-slate-800 p-6 sm:p-10 lg:p-12 text-white shadow-xl">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-slate-800/80 pb-6 mb-8">
        <div>
          <span className="text-xs font-bold uppercase tracking-widest text-blue-400">
            Indicadores Operacionais
          </span>
          <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white mt-1">
            Performance Industrial &amp; Confiabilidade Comprovada
          </h2>
        </div>
        <p className="text-xs sm:text-sm text-slate-400 max-w-md">
          Métricas técnicas de operação dos terminais Control iD combinadas à arquitetura agêntica
          local.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {METRICS.map((item) => (
          <div
            key={item.label}
            className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 flex flex-col justify-between hover:border-blue-500/50 transition-colors"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-[10px] font-bold uppercase tracking-widest text-blue-400 bg-blue-500/10 border border-blue-500/20 px-2.5 py-0.5 rounded-full">
                {item.tag}
              </span>
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
            </div>

            <div className="my-5">
              <div className="text-3xl sm:text-4xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-100 to-blue-200 bg-clip-text text-transparent">
                {item.value}
              </div>
              <h3 className="text-sm font-bold text-slate-100 mt-2 leading-snug">{item.label}</h3>
            </div>

            <p className="text-xs text-slate-400 border-t border-slate-800/80 pt-3 leading-relaxed">
              {item.detail}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
