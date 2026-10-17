/* eslint-disable @next/next/no-img-element */

interface ProcessStep {
  number: string;
  title: string;
  subtitle: string;
  description: string;
  image: string;
  staggerClass: string;
}

const STEPS: ProcessStep[] = [
  {
    number: "01",
    title: "Consulta Multimodal",
    subtitle: "Voz, Imagem & Texto",
    description:
      "Texto, foto de placa ou áudio via Whisper analisados em tempo real com identificação visual CLIP e OCR.",
    image: "/images/produtos/idface-frontal.jpg",
    staggerClass: "xl:mt-0",
  },
  {
    number: "02",
    title: "Roteamento Híbrido",
    subtitle: "Orquestrador Inteligente",
    description:
      "Decisão inteligente entre GPU local 16GB e modelo externo, combinada à busca vetorial semântica RAG.",
    image: "/images/produtos/idbox.jpg",
    staggerClass: "xl:mt-10",
  },
  {
    number: "03",
    title: "Cotação MCP B2B",
    subtitle: "Catálogo & Estoque Real",
    description:
      "Consulta de estoque em tempo real e reserva de lotes com validação automática de compatibilidade técnica.",
    image: "/images/produtos/idblock-inox.jpg",
    staggerClass: "xl:mt-20",
  },
  {
    number: "04",
    title: "Agendamento de Visita",
    subtitle: "Integração Direta",
    description:
      "Sincronização instantânea com Google Calendar e confirmação automatizada para vistoria ou implantação.",
    image: "/images/produtos/rep-idclass.jpg",
    staggerClass: "xl:mt-30",
  },
];

export default function ProcessSteps() {
  return (
    <section className="process-section relative overflow-hidden rounded-[24px] bg-[#eeeeee] border border-[#e3e3e8] px-6 py-12 sm:px-10 sm:py-16 lg:px-14 lg:py-20">
      {/* Giant M3 Glass Watermark */}
      <span
        aria-hidden="true"
        className="m3-watermark-light right-6 top-2 text-[72px] sm:text-[135px] lg:text-[180px]"
      >
        Workflow
      </span>

      <div className="relative z-10 flex flex-col md:flex-row md:items-end justify-between gap-6 border-b border-[#1c1c1d]/12 pb-8 mb-12">
        <div data-m3-reveal="left">
          <div className="inline-flex items-center gap-2.5 text-xs font-extrabold uppercase tracking-[0.22em] text-[#191919] mb-3">
            <span className="h-2.5 w-2.5 rounded-full bg-[#16c0dd] shadow-[0_0_10px_#16c0dd]" />
            Como Trabalhamos
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-[44px] font-extrabold tracking-tight text-[#191919] leading-[1.12]">
            Fluxo de Atendimento{" "}
            <span className="text-[#16c0dd]">Inteligente de Ponta a Ponta</span>
          </h2>
        </div>
        <p data-m3-reveal="right" className="text-xs sm:text-sm text-[#4d4d52] max-w-md">
          Da identificação visual do equipamento até a reserva de lote B2B ou agendamento técnico em
          4 etapas integradas.
        </p>
      </div>

      {/* Diagonal Staircase Process Grid (M3 Glass .process-item layout) */}
      <div className="relative z-10 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-6 items-start">
        {STEPS.map((step, idx) => (
          <div
            key={step.number}
            data-m3-reveal="bottom"
            data-m3-delay={idx * 110}
            className={`process-item group relative flex flex-col justify-between rounded-[16px] border border-white/80 bg-[#f8f9fb] p-5 pb-8 shadow-md hover:shadow-2xl hover:-translate-y-1.5 transition-all duration-300 ${step.staggerClass}`}
          >
            <div>
              {/* Framed product photo (.process-thumb from m3glass.com: 10px solid #fff border, rounded-9px) */}
              <div className="process-thumb m3-photo-card relative mb-6 h-[175px] w-full overflow-hidden rounded-[10px] border-[10px] border-white bg-white shadow-md">
                <img
                  src={step.image}
                  alt={step.title}
                  className="h-full w-full object-cover group-hover:scale-110 transition-transform duration-700"
                />
                <div className="absolute top-2.5 left-2.5 inline-flex items-center justify-center rounded-lg bg-[#191919]/90 backdrop-blur-xs px-2.5 py-1 font-mono text-xs font-extrabold text-[#16c0dd] shadow-sm">
                  {step.number}
                </div>
              </div>

              <div className="px-1">
                <span className="text-[11px] font-extrabold uppercase tracking-[0.16em] text-[#16c0dd]">
                  {step.subtitle}
                </span>
                <h3 className="text-lg font-extrabold text-[#191919] mt-1 group-hover:text-[#16c0dd] transition-colors">
                  {step.number}. {step.title}
                </h3>
                <p className="mt-2.5 text-xs sm:text-sm text-[#4d4d52] leading-relaxed">
                  {step.description}
                </p>
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-[#e3e3e8] px-1 flex items-center justify-between text-[11px] font-bold text-[#4d4d52] relative z-10">
              <span>Etapa {step.number} de 04</span>
              <span className="text-[#16c0dd]">● Ativo</span>
            </div>

            {/* Giant 72px Watermark Number at bottom-right (like .process-item .number in m3glass.com) */}
            <span
              aria-hidden="true"
              className="pointer-events-none select-none absolute right-4 bottom-8 text-[68px] font-black leading-none text-[#191919]/[0.05] group-hover:text-[#16c0dd]/15 transition-colors"
            >
              #{step.number}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
