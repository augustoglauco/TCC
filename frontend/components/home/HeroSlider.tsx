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
  metricSpecs: [string, string, string];
  mainImage: string;
  secondaryImage: string;
  productName: string;
  watermark: string;
}

const SLIDES: SlideData[] = [
  {
    id: "facial",
    badge: "FAST AND RELIABLE • BIOMETRIA 3D",
    title: "Reconhecimento Facial 3D &",
    highlight: "Identificação Ultrarrápida",
    description:
      "Terminais iDFace e iDFace Max com inteligência artificial embarcada, validação biométrica sem contato em menos de 0.2s e proteção antifraude ao vivo.",
    metricNumber: "0.2s",
    metricLabel: "Velocidade de Leitura Facial",
    metricSpecs: [
      "Especificações Técnicas RAG",
      "Interfone SIP & Display Touch",
      "Grau de Proteção IP65",
    ],
    mainImage: "/images/produtos/idface-perspectiva.jpg",
    secondaryImage: "/images/produtos/idface-max.jpg",
    productName: "Fictícia iDFace & iDFace Max",
    watermark: "iDFace",
  },
  {
    id: "catracas",
    badge: "BLOQUEIOS FÍSICOS & FLUXO CORPORATIVO",
    title: "Engenharia Robusta em",
    highlight: "Aço Inox & Design Industrial",
    description:
      "Catracas iDBlock Inox, Preta, Next Facial e PCD de altíssima durabilidade com giro suave amortecido e integração nativa com leitores faciais, biometria e QR Code.",
    metricNumber: "+50.000",
    metricLabel: "Ciclos Diários de Passagem",
    metricSpecs: [
      "Gabinete em Aço Inox 304",
      "Braços Anti-Pânico Opcionais",
      "Acessibilidade PCD Integrada",
    ],
    mainImage: "/images/produtos/idblock-facial-inox.jpg",
    secondaryImage: "/images/produtos/idblock-inox.jpg",
    productName: "Catraca iDBlock Facial Inox",
    watermark: "iDBlock",
  },
  {
    id: "ponto",
    badge: "REGULAMENTAÇÃO TRABALHISTA • MTE",
    title: "Ponto Eletrônico 100% Conforme",
    highlight: "Portaria 671 do MTE",
    description:
      "Registradores eletrônicos de ponto REP iDClass homologados, com impressora térmica de alta velocidade, guilhotina automática e sincronização contínua em nuvem.",
    metricNumber: "100%",
    metricLabel: "Homologado Portaria 671 & Inmetro",
    metricSpecs: [
      "Bobina Térmica até 400m",
      "Biometria + Proximidade + Senha",
      "Integração API & Nuvem RHiD",
    ],
    mainImage: "/images/produtos/rep-idclass.jpg",
    secondaryImage: "/images/produtos/idclass-373.jpg",
    productName: "Relógio de Ponto REP iDClass",
    watermark: "iDClass",
  },
  {
    id: "acesso",
    badge: "CONTROLE DE PORTAS & PROTOCOLO MCP",
    title: "Controladores Biométricos &",
    highlight: "Automação Inteligente B2B",
    description:
      "Linha completa iDAccess Pro, iDFlex IP65 e controladoras iDBox de 4 portas, integradas ao nosso Assistente Virtual Multimodal com consulta de estoque em tempo real.",
    metricNumber: "24/7",
    metricLabel: "Assistente IA + Cotação MCP B2B",
    metricSpecs: [
      "Identificação Visual por Foto (CLIP)",
      "Estoque Real por CD",
      "Agendamento Google Calendar",
    ],
    mainImage: "/images/produtos/idaccess-pro.jpg",
    secondaryImage: "/images/produtos/idflex-ip65.jpg",
    productName: "Controlador Biométrico iDAccess Pro",
    watermark: "iDAccess",
  },
];

function SliderNav({
  slides,
  currentSlide,
  onSelect,
  onPrev,
  onNext,
}: {
  slides: SlideData[];
  currentSlide: number;
  onSelect: (idx: number) => void;
  onPrev: () => void;
  onNext: () => void;
}) {
  return (
    <div className="mt-12 pt-6 border-t border-white/15 flex flex-col sm:flex-row items-center justify-between gap-4">
      <div className="flex items-center gap-2.5">
        {slides.map((s, idx) => {
          const active = idx === currentSlide;
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => onSelect(idx)}
              aria-label={`Ir para slide ${idx + 1}: ${s.productName}`}
              className={`group flex items-center gap-2 rounded-full px-3.5 py-1.5 text-xs font-mono transition-all cursor-pointer ${
                active
                  ? "bg-[#16c0dd] text-slate-950 font-extrabold shadow-lg shadow-[#16c0dd]/30"
                  : "bg-white/10 text-white/70 hover:bg-white/20 hover:text-white"
              }`}
            >
              <span>0{idx + 1}</span>
              <span className={active ? "inline" : "hidden md:inline"}>{s.watermark}</span>
            </button>
          );
        })}
      </div>

      <div className="flex items-center gap-2.5">
        <button
          type="button"
          onClick={onPrev}
          aria-label="Slide anterior"
          className="flex h-11 w-11 items-center justify-center rounded-full border border-white/25 bg-white/10 text-white hover:bg-[#16c0dd] hover:border-[#16c0dd] hover:text-slate-950 transition-all cursor-pointer"
        >
          ‹
        </button>
        <button
          type="button"
          onClick={onNext}
          aria-label="Próximo slide"
          className="flex h-11 w-11 items-center justify-center rounded-full border border-white/25 bg-white/10 text-white hover:bg-[#16c0dd] hover:border-[#16c0dd] hover:text-slate-950 transition-all cursor-pointer"
        >
          ›
        </button>
      </div>
    </div>
  );
}

type Slide = (typeof SLIDES)[number];

function TextoSlide({ slide }: { slide: Slide }) {
  return (
    <div className="lg:col-span-7 space-y-7">
      <div
        className="antra-fadeInDown inline-flex items-center gap-2.5 rounded-full border border-white/45 bg-white/5 backdrop-blur-md px-4 py-1.5 text-xs font-bold tracking-[0.2em] text-white uppercase"
        style={{ animationDelay: "80ms" }}
      >
        <span className="h-2 w-2 rounded-full bg-[#16c0dd] animate-pulse" />
        {slide.badge}
      </div>

      <h1
        className="antra-fadeInDown text-3xl sm:text-5xl xl:text-6xl font-extrabold tracking-tight leading-[1.08] text-white"
        style={{ animationDelay: "200ms" }}
      >
        {slide.title}{" "}
        <span className="block mt-1 bg-gradient-to-r from-[#16c0dd] via-cyan-300 to-white bg-clip-text text-transparent">
          {slide.highlight}
        </span>
      </h1>

      <div
        className="antra-fadeInUp pt-2 flex flex-col sm:flex-row sm:items-end justify-between gap-6 border-t border-white/15"
        style={{ animationDelay: "340ms" }}
      >
        <p className="text-sm sm:text-base text-slate-200/90 leading-relaxed max-w-xl pt-4">
          {slide.description}
        </p>
      </div>

      {/* Botões Pílula Interativos (.tl-primary-btn.white-btn de m3glass.com) */}
      <div
        className="antra-fadeInUp flex flex-wrap items-center gap-4 pt-2"
        style={{ animationDelay: "460ms" }}
      >
        <button
          type="button"
          onClick={() => useChatStore.getState().open()}
          className="tl-primary-btn white-btn"
        >
          <span>Conversar com o Assistente</span>
          <span className="icon" aria-hidden="true">
            →
          </span>
        </button>

        <Link href="/produtos" className="tl-primary-btn white-btn">
          <span>Explorar Catálogo</span>
          <span className="icon" aria-hidden="true">
            ↗
          </span>
        </Link>
      </div>
    </div>
  );
}

function VitrineSlide({ slide, posicao, total }: { slide: Slide; posicao: number; total: number }) {
  return (
    <div
      className="antra-fadeInRight lg:col-span-5 relative flex flex-col sm:flex-row lg:flex-col xl:flex-row items-center justify-end gap-5"
      style={{ animationDelay: "280ms" }}
    >
      {/* Moldura Fotográfica Principal do Produto com Brilho e Flutuação */}
      <div className="m3-photo-card relative w-full max-w-[330px] aspect-4/5 rounded-[24px] bg-gradient-to-b from-white/95 via-slate-50 to-slate-200 p-5 shadow-[0_25px_70px_rgba(0,0,0,0.55)] border border-white/30 flex flex-col justify-between group">
        <div className="flex items-center justify-between text-[11px] font-mono uppercase tracking-wider text-slate-500">
          <span className="inline-flex items-center gap-1.5 font-bold text-slate-900">
            <span className="h-2 w-2 rounded-full bg-[#16c0dd]" />
            Fictícia Oficial
          </span>
          <span>
            0{posicao + 1} / 0{total}
          </span>
        </div>

        <div className="relative my-auto py-3 flex items-center justify-center h-56 sm:h-64">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={slide.mainImage}
            alt={slide.productName}
            className="max-h-full max-w-full object-contain drop-shadow-[0_18px_28px_rgba(15,23,42,0.25)] transition-transform duration-500 group-hover:scale-108"
          />
        </div>

        {/* Miniatura Secundária Flutuante + Nome */}
        <div className="flex items-center justify-between gap-3 rounded-2xl bg-slate-950/90 px-3.5 py-2.5 text-white backdrop-blur-md">
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-widest text-[#16c0dd] font-bold">
              Hardware em Destaque
            </p>
            <p className="text-xs font-bold truncate">{slide.productName}</p>
          </div>
          <div className="h-10 w-10 shrink-0 overflow-hidden rounded-xl bg-white p-1 border border-white/20">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={slide.secondaryImage}
              alt={`${slide.productName} vista complementar`}
              className="h-full w-full object-contain"
            />
          </div>
        </div>
      </div>

      {/* Card Frosted Glass autêntico do M3 Glass (.slider-element: backdrop-filter: blur(29px)) */}
      <div className="w-full sm:w-64 rounded-[24px] border border-white/20 bg-white/16 p-7 backdrop-blur-[29px] shadow-2xl text-white">
        <div className="text-4xl sm:text-5xl font-extrabold tracking-tight text-white">
          {slide.metricNumber}
        </div>
        <span className="mt-1.5 block text-xs font-semibold uppercase tracking-wider text-[#16c0dd]">
          {slide.metricLabel}
        </span>

        <div className="mt-7 pt-5 border-t border-white/20 space-y-2 text-xs text-white/90">
          {slide.metricSpecs.map((spec) => (
            <p key={spec} className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-[#16c0dd]" />
              <span>{spec}</span>
            </p>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function HeroSlider() {
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isPaused, setIsPaused] = useState(false);

  useEffect(() => {
    if (isPaused) return;
    const interval = setInterval(() => {
      setCurrentSlide((prev) => (prev + 1) % SLIDES.length);
    }, 6500);
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
      className="relative overflow-hidden bg-[#100d0b] text-white min-h-[600px] lg:min-h-[700px] flex items-center border-b border-white/10"
    >
      {/* Camada de Fundo Dinâmica com Ken Burns Zoom sobre a Foto do Equipamento */}
      <div key={`bg-${slide.id}`} className="absolute inset-0 z-0 overflow-hidden">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={slide.mainImage}
          alt=""
          aria-hidden="true"
          className="h-full w-full object-cover object-right opacity-25 blur-[2px] animate-ken-burns select-none"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-[#0b0f17] via-[#0b0f17]/92 to-[#0b0f17]/55" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_75%_42%,rgba(22,192,221,0.24),transparent_55%)]" />
      </div>

      {/* Marca d'água gigante ao fundo estilo M3 Glass (.slider-text) */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute bottom-4 left-1/2 -translate-x-1/2 z-0 hidden lg:block"
      >
        <span className="m3-watermark-dark text-[180px] xl:text-[250px] uppercase tracking-tighter">
          {slide.watermark}
        </span>
      </div>

      <div className="relative z-10 mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8 py-14 sm:py-20 lg:py-24">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-12 items-center">
          <TextoSlide key={`content-${slide.id}`} slide={slide} />

          <VitrineSlide
            key={`visual-${slide.id}`}
            slide={slide}
            posicao={currentSlide}
            total={SLIDES.length}
          />
        </div>

        {/* Barra Inferior de Navegação dos Slides */}
        <SliderNav
          slides={SLIDES}
          currentSlide={currentSlide}
          onSelect={setCurrentSlide}
          onPrev={handlePrev}
          onNext={handleNext}
        />
      </div>
    </section>
  );
}
