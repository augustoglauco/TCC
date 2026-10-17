/* eslint-disable @next/next/no-img-element */

interface MetricItem {
  value: string;
  label: string;
  detail: string;
  tag: string;
  image: string;
}

const METRICS: MetricItem[] = [
  {
    value: "99.9%",
    label: "Precisão em Reconhecimento Facial",
    detail: "Algoritmo Biométrico Neural com Anti-Spoofing 3D",
    tag: "BIOMETRIA 3D",
    image: "/images/produtos/idface-max.jpg",
  },
  {
    value: "< 0.2s",
    label: "Velocidade de Leitura e Autenticação",
    detail: "Validação instantânea sem contato físico em alto fluxo",
    tag: "TEMPO REAL",
    image: "/images/produtos/idblock-next-facial.jpg",
  },
  {
    value: "100%",
    label: "Conformidade Portaria 671 MTE & LGPD",
    detail: "Segurança jurídica, INMETRO e homologação oficial",
    tag: "HOMOLOGADO",
    image: "/images/produtos/rep-idclass.jpg",
  },
  {
    value: "24/7",
    label: "Assistente de IA & RAG Local",
    detail: "Inferência dedicada em GPU 16GB + Protocolo MCP",
    tag: "IA MULTIMODAL",
    image: "/images/produtos/idaccess-pro.jpg",
  },
];

export default function MetricCounters() {
  return (
    <section className="counter-section relative overflow-hidden rounded-[24px] bg-[#f1f2f5] border border-[#e3e3e8] px-6 py-12 sm:px-10 sm:py-16 lg:px-14 lg:py-20">
      {/* Giant M3 Glass Watermark Text */}
      <span
        aria-hidden="true"
        className="m3-watermark-light right-6 -top-4 text-[72px] sm:text-[130px] lg:text-[175px]"
      >
        Performance
      </span>

      {/* Top row: Heading + Scroll-scrubbed horizontal product showcase */}
      <div className="relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-8 items-center mb-12 lg:mb-16">
        <div data-m3-reveal="left" className="lg:col-span-6">
          <div className="inline-flex items-center gap-2.5 text-xs font-extrabold uppercase tracking-[0.22em] text-[#191919] mb-3">
            <span className="h-2.5 w-2.5 rounded-full bg-[#16c0dd] shadow-[0_0_10px_#16c0dd]" />
            Indicadores Operacionais
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-[42px] font-extrabold tracking-tight text-[#191919] leading-[1.12]">
            Performance Industrial &amp;{" "}
            <span className="text-[#16c0dd]">Confiabilidade Comprovada</span>
          </h2>
          <p className="text-sm sm:text-base text-[#4d4d52] mt-4 max-w-xl leading-relaxed">
            Métricas técnicas de operação dos terminais Fictícia combinadas à arquitetura agêntica
            local com busca vetorial híbrida.
          </p>
        </div>

        {/* Scroll-scrubbed horizontal banner image (like .scroll-img in m3glass.com) */}
        <div className="lg:col-span-6 overflow-hidden py-2">
          <div
            data-m3-scroll-x="-0.12"
            className="flex items-center gap-4 will-change-transform transition-transform duration-150 ease-out"
          >
            <div className="m3-photo-card shrink-0 w-[260px] sm:w-[320px] h-[165px] rounded-[16px] border-[8px] border-white bg-white shadow-xl overflow-hidden">
              <img
                src="/images/produtos/idblock-pcd.jpg"
                alt="iDBlock PcD Inox"
                className="h-full w-full object-cover"
              />
            </div>
            <div className="m3-photo-card shrink-0 w-[220px] sm:w-[260px] h-[165px] rounded-[16px] border-[8px] border-white bg-white shadow-xl overflow-hidden">
              <img
                src="/images/produtos/idface-perspectiva.jpg"
                alt="iDFace Perspectiva"
                className="h-full w-full object-cover"
              />
            </div>
          </div>
        </div>
      </div>

      {/* 4 Sculptural Counter Columns (M3 Glass .counter-item style) */}
      <div className="relative z-10 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
        {METRICS.map((item, idx) => (
          <div
            key={item.label}
            data-m3-reveal="bottom"
            data-m3-delay={idx * 100}
            className="counter-item group relative border-b-2 border-[#1c1c1d]/18 pb-8 hover:border-[#16c0dd] transition-colors"
          >
            <div className="flex items-center justify-between gap-3 mb-5">
              <span className="text-[11px] font-extrabold uppercase tracking-[0.16em] text-[#191919] bg-white border border-[#e3e3e8] px-3 py-1 rounded-full shadow-2xs group-hover:border-[#16c0dd] group-hover:text-[#16c0dd] transition-colors">
                {item.tag}
              </span>
              <div className="h-11 w-11 rounded-xl border-2 border-white bg-white shadow-sm overflow-hidden shrink-0">
                <img
                  src={item.image}
                  alt={item.label}
                  className="h-full w-full object-cover group-hover:scale-110 transition-transform duration-500"
                />
              </div>
            </div>

            <div className="text-5xl sm:text-[56px] font-extrabold tracking-tight text-[#191919] leading-none group-hover:text-[#16c0dd] transition-colors">
              {item.value}
            </div>

            <h3 className="text-base font-extrabold text-[#191919] mt-4 leading-snug">
              {item.label}
            </h3>

            <p className="text-xs sm:text-sm text-[#4d4d52] mt-2 leading-relaxed">{item.detail}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
