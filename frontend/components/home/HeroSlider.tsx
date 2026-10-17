"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useChatStore } from "@/lib/hooks/useChatStore";

interface SlideData {
  id: string;
  badge: string;
  title: string;
  highlight: string;
  description: string;
  metricNumber: string;
  metricLabel: string;
  metricDetail: string;
}

const SLIDES: SlideData[] = [
  {
    id: "facial",
    badge: "TECNOLOGIA SEM CONTATO",
    title: "Reconhecimento Facial 3D &",
    highlight: "Identificação Ultrarrápida",
    description:
      "Terminais com inteligência artificial embarcada, validação biométrica em menos de 0.2s e proteção avançada antifraude contra fotos e vídeos.",
    metricNumber: "0.2s",
    metricLabel: "Velocidade de Leitura",
    metricDetail: "99.9% de precisão biométrica em qualquer ângulo",
  },
  {
    id: "catracas",
    badge: "BLOQUEIOS FÍSICOS & CONTROLE DE FLUXO",
    title: "Engenharia Robusta em",
    highlight: "Aço Inox & Design Industrial",
    description:
      "Catracas de pedestal e torniquetes de alta durabilidade com giro suave, amortecimento motorizado e suporte a múltiplos métodos de identificação.",
    metricNumber: "+50.000",
    metricLabel: "Acessos Diários",
    metricDetail: "Construção em aço inox 304 escovado de longa vida útil",
  },
  {
    id: "ponto",
    badge: "REGULAMENTAÇÃO TRABALHISTA",
    title: "Ponto Eletrônico 100% Conforme",
    highlight: "Portaria 671 do MTE",
    description:
      "Registradores eletrônicos de ponto homologados, com impressão térmica de comprovante, conectividade em nuvem e gestão integrada de jornada de trabalho.",
    metricNumber: "100%",
    metricLabel: "Conforme Portaria 671",
    metricDetail: "Certificação fiscal completa e sincronização contínua",
  },
];

export default function HeroSlider() {
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isPaused, setIsPaused] = useState(false);

  useEffect(() => {
    if (isPaused) return;
    const interval = setInterval(() => {
      setCurrentSlide((prev) => (prev + 1) % SLIDES.length);
    }, 6000);
    return () => clearInterval(interval);
  }, [isPaused]);

  const slide = SLIDES[currentSlide];

  const handlePrev = () => {
    setCurrentSlide((prev) => (prev === 0 ? SLIDES.length - 1 : prev - 1));
  };

  const handleNext = () => {
    setCurrentSlide((prev) => (prev + 1) % SLIDES.length);
  };

  return (
    <section
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
      className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 p-6 sm:p-10 lg:p-14 text-white shadow-2xl border border-slate-800"
    >
      <div className="relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
        {/* Lado Esquerdo: Conteúdo Editorial */}
        <div className="lg:col-span-7 space-y-6">
          <div className="inline-flex items-center gap-2 rounded-full border border-blue-500/30 bg-blue-500/10 px-3.5 py-1 text-xs font-bold tracking-widest text-blue-400 uppercase">
            <span className="h-2 w-2 rounded-full bg-blue-400 animate-pulse" />
            {slide.badge}
          </div>

          <h1 className="text-3xl sm:text-5xl lg:text-5xl font-extrabold tracking-tight leading-tight">
            {slide.title}{" "}
            <span className="bg-gradient-to-r from-blue-400 via-sky-300 to-cyan-300 bg-clip-text text-transparent">
              {slide.highlight}
            </span>
          </h1>

          <p className="text-sm sm:text-base text-slate-300 leading-relaxed max-w-2xl">
            {slide.description}
          </p>

          {/* Botões de Ação */}
          <div className="pt-2 flex flex-wrap gap-3 sm:gap-4">
            <button
              type="button"
              onClick={() => useChatStore.getState().open()}
              className="inline-flex items-center justify-center gap-2.5 rounded-xl bg-gradient-to-r from-blue-600 via-indigo-600 to-blue-500 px-6 py-3.5 text-sm font-bold text-white shadow-lg shadow-blue-600/30 hover:shadow-blue-600/50 hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-blue-400 transition-all cursor-pointer"
            >
              <span>Conversar com o Assistente</span>
              <span className="text-lg">💬</span>
            </button>

            <Link
              href="/produtos"
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-700 bg-slate-900/80 px-6 py-3.5 text-sm font-semibold text-slate-200 backdrop-blur-md transition-all hover:bg-slate-800 hover:text-white hover:border-slate-600"
            >
              <span>Explorar Catálogo</span>
              <span className="text-base">📦</span>
            </Link>
          </div>
        </div>

        {/* Lado Direito: Card Lateral Flutuante estilo M3 Glass */}
        <div className="lg:col-span-5 flex flex-col justify-center">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 sm:p-8 backdrop-blur-xl shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <span className="text-xs font-semibold uppercase tracking-widest text-slate-400">
                Performance &amp; Dados
              </span>
              <span className="text-xs font-mono text-blue-400">
                0{currentSlide + 1} / 0{SLIDES.length}
              </span>
            </div>

            <div>
              <div className="text-4xl sm:text-5xl font-extrabold tracking-tight text-white bg-gradient-to-r from-white via-slate-100 to-slate-300 bg-clip-text">
                {slide.metricNumber}
              </div>
              <h3 className="text-base font-bold text-blue-400 mt-1">{slide.metricLabel}</h3>
              <p className="text-xs text-slate-400 mt-2 leading-relaxed">{slide.metricDetail}</p>
            </div>

            <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-500">
              <span>Tecnologia Oficial Control iD</span>
              <span className="text-emerald-400 font-medium">● Pronta Entrega</span>
            </div>
          </div>
        </div>
      </div>

      {/* Controles de Navegação do Slider */}
      <div className="mt-8 pt-4 border-t border-slate-800/60 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {SLIDES.map((s, idx) => (
            <button
              key={s.id}
              type="button"
              onClick={() => setCurrentSlide(idx)}
              aria-label={`Ir para slide ${idx + 1}`}
              className={`h-2 transition-all rounded-full cursor-pointer ${
                idx === currentSlide ? "w-8 bg-blue-500" : "w-2 bg-slate-700 hover:bg-slate-500"
              }`}
            />
          ))}
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handlePrev}
            aria-label="Slide anterior"
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-800 bg-slate-900 text-slate-300 hover:bg-slate-800 hover:text-white transition-colors cursor-pointer"
          >
            ‹
          </button>
          <button
            type="button"
            onClick={handleNext}
            aria-label="Próximo slide"
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-800 bg-slate-900 text-slate-300 hover:bg-slate-800 hover:text-white transition-colors cursor-pointer"
          >
            ›
          </button>
        </div>
      </div>

      {/* Efeitos de Luz de Fundo */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 rounded-full bg-blue-600/15 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -left-24 -bottom-24 h-96 w-96 rounded-full bg-indigo-600/15 blur-3xl"
      />
    </section>
  );
}
