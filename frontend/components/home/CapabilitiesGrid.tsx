"use client";

import Link from "next/link";
import { useChatStore } from "@/lib/hooks/useChatStore";

interface Capability {
  title: string;
  subtitle: string;
  description: string;
  features: string[];
  href: string;
  productImage: string;
  productLabel: string;
  revealDir: "left" | "up" | "right";
}

const CAPABILITIES: Capability[] = [
  {
    title: "Controle de Acesso",
    subtitle: "Facial & Biometria",
    description:
      "Terminais de alta tecnologia com reconhecimento facial 3D, biometria digital e leitor de cartões RFID para máxima segurança de ambientes corporativos.",
    features: ["Validação sem contato", "Anti-fraude com IA", "Gestão em rede TCP/IP"],
    href: "/produtos",
    productImage: "/images/produtos/idface-frontal.jpg",
    productLabel: "iDFace",
    revealDir: "left",
  },
  {
    title: "Bloqueios & Catracas",
    subtitle: "Aço Inox & Torniquetes",
    description:
      "Sistemas físicos de retenção e liberação de fluxo com mecanismo silencioso, amortecimento suave e design industrial em aço inox escovado.",
    features: ["Aço inox 304", "Braços escamoteáveis", "Passagem acessível PCD"],
    href: "/produtos",
    productImage: "/images/produtos/idblock-inox.jpg",
    productLabel: "iDBlock Inox",
    revealDir: "up",
  },
  {
    title: "Ponto Eletrônico",
    subtitle: "Portaria 671 MTE",
    description:
      "Registradores eletrônicos de ponto certificados e aderentes às normas vigentes, com comprovante impresso térmico e integração em nuvem.",
    features: ["100% legalizado MTE", "Guilhotina integrada", "Sincronização em nuvem"],
    href: "/produtos",
    productImage: "/images/produtos/rep-idclass.jpg",
    productLabel: "REP iDClass",
    revealDir: "up",
  },
  {
    title: "Automação & Protocolo MCP",
    subtitle: "Assistente IA & B2B",
    description:
      "Integração do catálogo e estoque com parceiros via Model Context Protocol (MCP) e agendamento automatizado integrado ao Google Calendar.",
    features: [
      "Consulta de estoque em tempo real",
      "Cotação automatizada",
      "Visitas no Google Calendar",
    ],
    href: "/suporte",
    productImage: "/images/produtos/idbox.jpg",
    productLabel: "Controladora iDBox",
    revealDir: "right",
  },
];

export default function CapabilitiesGrid() {
  return (
    <div className="space-y-16 sm:space-y-24">
      {/* Parte 1: .service-section estilo M3 Glass */}
      <section className="relative py-6 sm:py-10">
        {/* Cabeçalho em 2 Colunas (4/12 + 8/12) idêntico ao .section-heading-wrap do M3 Glass */}
        <div
          data-m3-reveal="up"
          className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start pb-10 sm:pb-14 border-b border-[#e3e3e8]"
        >
          <div className="lg:col-span-4">
            <span className="inline-flex items-center gap-2 rounded-full border border-[#191919]/25 bg-white px-4 py-1.5 text-xs font-bold uppercase tracking-[0.2em] text-[#191919]">
              <span className="h-2 w-2 rounded-full bg-[#16c0dd]" />
              Nossos Domínios
            </span>
          </div>

          <div className="lg:col-span-8 space-y-4">
            <h2 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-[#191919] leading-[1.1]">
              Soluções Integradas de <span className="text-[#16c0dd]">Segurança e Gestão</span>
            </h2>
            <p className="text-sm sm:text-base text-[#4d4d52] max-w-2xl leading-relaxed">
              Engenharia de precisão da linha Fictícia combinada à inteligência artificial
              multimodal para especificação técnica, cotação B2B e suporte com manuais oficiais.
            </p>
          </div>
        </div>

        {/* Grade de 4 Cards .service-item (border-radius: 24px, padding: 40px, .service-top) */}
        <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-6">
          {CAPABILITIES.map((cap, idx) => (
            <Link
              key={cap.title}
              href={cap.href}
              data-m3-reveal={cap.revealDir}
              data-m3-delay={`${idx * 90}ms`}
              className="group flex flex-col justify-between rounded-[24px] border border-[#e3e3e8] bg-white p-7 sm:p-9 shadow-[0_3px_18px_rgba(0,0,0,0.03)] hover:shadow-[0_20px_50px_rgba(22,192,221,0.14)] hover:border-[#16c0dd] hover:-translate-y-2 transition-all duration-300"
            >
              <div>
                {/* .service-top com título à esquerda e miniatura real do produto à direita */}
                <div className="flex items-start justify-between gap-4 pb-8 mb-6 border-b border-[#e3e3e8]">
                  <div>
                    <span className="text-[11px] font-bold uppercase tracking-widest text-[#16c0dd] block mb-1.5">
                      {cap.subtitle}
                    </span>
                    <h3 className="text-xl sm:text-2xl font-extrabold text-[#191919] group-hover:text-[#16c0dd] transition-colors leading-snug">
                      {cap.title}
                    </h3>
                  </div>

                  <div className="relative h-16 w-16 shrink-0 rounded-2xl border border-slate-200 bg-slate-50 p-1.5 shadow-inner group-hover:border-[#16c0dd] group-hover:scale-110 transition-all duration-300">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={cap.productImage}
                      alt={cap.productLabel}
                      className="h-full w-full object-contain"
                    />
                  </div>
                </div>

                <p className="text-xs sm:text-sm text-[#4d4d52] leading-relaxed">
                  {cap.description}
                </p>
              </div>

              <div className="mt-7 pt-5 border-t border-slate-100 space-y-2">
                {cap.features.map((feat) => (
                  <div key={feat} className="flex items-center gap-2 text-xs text-[#4d4d52]">
                    <span className="h-1.5 w-1.5 rounded-full bg-[#16c0dd]" />
                    <span>{feat}</span>
                  </div>
                ))}

                <div className="pt-3 flex items-center justify-between text-xs font-extrabold text-[#191919] group-hover:text-[#16c0dd] transition-colors">
                  <span>Explorar Linha {cap.productLabel}</span>
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-100 text-[#191919] group-hover:bg-[#16c0dd] group-hover:text-white transition-all">
                    →
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* Parte 2: Banner Escuro Full-Bleed (.about-section de m3glass.com) */}
      <section className="relative overflow-hidden rounded-[32px] bg-[#14161b] px-6 py-12 sm:px-12 sm:py-16 lg:p-20 text-white shadow-2xl border border-white/10">
        {/* Foto de Fundo com Overlay Escuro (.about-bg) */}
        <div className="absolute inset-0 z-0">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/images/produtos/idblock-next-facial.jpg"
            alt=""
            aria-hidden="true"
            className="h-full w-full object-cover object-center opacity-15 blur-[1px]"
          />
          <div className="absolute inset-0 bg-gradient-to-r from-[#0e1117] via-[#0e1117]/95 to-[#0e1117]/75" />
        </div>

        {/* Marca d'água gigante na base (.about-text: Design Glass -> Control iD) */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-6 left-1/2 -translate-x-1/2 z-0"
        >
          <span className="m3-watermark-dark text-[90px] sm:text-[170px] lg:text-[240px]">
            Fictícia
          </span>
        </div>

        <div className="relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-12 items-center">
          {/* Coluna Esquerda (.about-content slide-anim left) */}
          <div data-m3-reveal="left" className="lg:col-span-6 space-y-6">
            <span className="inline-flex items-center gap-2 rounded-full border border-white/35 bg-white/5 px-4 py-1.5 text-xs font-bold uppercase tracking-[0.2em] text-[#16c0dd]">
              Ecossistema Completo de Hardware &amp; IA
            </span>

            <h2 className="text-3xl sm:text-5xl font-extrabold tracking-tight leading-[1.1] text-white">
              Onde os Espaços Corporativos ganham{" "}
              <span className="text-[#16c0dd]">Segurança Viva</span>
            </h2>

            {/* Lista 2x2 (.about-list de m3glass.com) */}
            <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 pt-2 text-sm font-semibold text-white">
              <li className="flex items-center gap-3 rounded-xl bg-white/5 border border-white/10 px-4 py-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#16c0dd] text-slate-950 text-xs font-black">
                  ✓
                </span>
                <span>Biometria Facial 3D ao Vivo</span>
              </li>
              <li className="flex items-center gap-3 rounded-xl bg-white/5 border border-white/10 px-4 py-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#16c0dd] text-slate-950 text-xs font-black">
                  ✓
                </span>
                <span>Catracas Inox 304 &amp; PCD</span>
              </li>
              <li className="flex items-center gap-3 rounded-xl bg-white/5 border border-white/10 px-4 py-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#16c0dd] text-slate-950 text-xs font-black">
                  ✓
                </span>
                <span>Identificação por Foto (CLIP)</span>
              </li>
              <li className="flex items-center gap-3 rounded-xl bg-white/5 border border-white/10 px-4 py-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#16c0dd] text-slate-950 text-xs font-black">
                  ✓
                </span>
                <span>RAG em Manuais Técnicos</span>
              </li>
            </ul>

            <p className="text-sm sm:text-base text-slate-300 leading-relaxed">
              Envie uma foto de qualquer equipamento no chat para identificarmos o modelo via CLIP,
              consultarmos o datasheet oficial no Qdrant e verificarmos disponibilidade imediata nos
              Centros de Distribuição.
            </p>

            <div className="pt-2 flex flex-wrap gap-4">
              <button
                type="button"
                onClick={() => useChatStore.getState().open()}
                className="tl-primary-btn white-btn"
              >
                <span>Testar Identificação por Foto</span>
                <span className="icon" aria-hidden="true">
                  →
                </span>
              </button>
            </div>
          </div>

          {/* Coluna Direita: Composição Fotográfica Multi-Produto (.about-img slide-anim right) */}
          <div
            data-m3-reveal="right"
            className="lg:col-span-6 grid grid-cols-12 gap-4 items-center"
          >
            <div className="col-span-7 m3-photo-card bg-white rounded-[24px] p-5 shadow-2xl border border-white/20">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/images/produtos/idblock-next-facial.jpg"
                alt="Catraca iDBlock Next Facial"
                className="h-64 sm:h-80 w-full object-contain transition-transform duration-500 hover:scale-105"
              />
              <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-900">
                <span className="font-extrabold">iDBlock Next Facial</span>
                <span className="rounded-full bg-[#16c0dd]/15 text-[#0e7490] px-2.5 py-0.5 font-bold">
                  Totem Inox + Facial
                </span>
              </div>
            </div>

            <div className="col-span-5 space-y-4">
              <div className="m3-photo-card bg-white rounded-[24px] p-4 shadow-xl border border-white/20">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src="/images/produtos/idface-max.jpg"
                  alt="Terminal iDFace Max"
                  className="h-32 sm:h-40 w-full object-contain transition-transform duration-500 hover:scale-105"
                />
                <p className="mt-2 text-center text-xs font-extrabold text-slate-900">
                  iDFace Max (8&quot; HD)
                </p>
              </div>

              <div className="m3-photo-card bg-white rounded-[24px] p-4 shadow-xl border border-white/20">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src="/images/produtos/printid-touch.jpg"
                  alt="Impressora Térmica Print iD Touch"
                  className="h-32 sm:h-40 w-full object-contain transition-transform duration-500 hover:scale-105"
                />
                <p className="mt-2 text-center text-xs font-extrabold text-slate-900">
                  Print iD Touch
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
