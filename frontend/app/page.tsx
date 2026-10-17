"use client";
/* eslint-disable @next/next/no-img-element */

import Link from "next/link";
import { useChatStore } from "@/lib/hooks/useChatStore";
import M3PageEffects from "@/components/home/M3PageEffects";
import HeroSlider from "@/components/home/HeroSlider";
import TechMarquee from "@/components/home/TechMarquee";
import CapabilitiesGrid from "@/components/home/CapabilitiesGrid";
import HardwareReveal from "@/components/home/HardwareReveal";
import MetricCounters from "@/components/home/MetricCounters";
import ProcessSteps from "@/components/home/ProcessSteps";
import ProductGalleryShowcase from "@/components/home/ProductGalleryShowcase";

export default function HomePage() {
  return (
    <div className="space-y-0 bg-[#f6f6f6]">
      {/* M3 Glass Preloader Curtain, Scroll-Reveal, Scroll-Scrubbing & Conic Ring */}
      <M3PageEffects />

      {/* Full-bleed M3 Glass Hero Slider */}
      <HeroSlider />

      {/* M3 Glass Running Text Marquee */}
      <TechMarquee />

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-12 sm:py-20 space-y-16 sm:space-y-24">
        <CapabilitiesGrid />

        <HardwareReveal />

        <MetricCounters />

        <ProcessSteps />

        <ProductGalleryShowcase />

        {/* Seção de CTA Final — Estilo M3 Glass Dark Banner + Frosted Glass */}
        <section className="relative overflow-hidden rounded-[24px] bg-[#100d0b] border border-white/10 p-8 sm:p-14 lg:p-16 text-white shadow-2xl">
          {/* Background Product Photo with Ken Burns & Dark Gradient */}
          <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
            <img
              src="/images/produtos/idblock-next-facial.jpg"
              alt=""
              className="h-full w-full object-cover object-center opacity-20 scale-105"
            />
            <div className="absolute inset-0 bg-gradient-to-r from-[#100d0b] via-[#100d0b]/92 to-[#100d0b]/75" />
          </div>

          {/* Giant Watermark */}
          <span
            aria-hidden="true"
            className="m3-watermark-dark right-6 -bottom-6 text-[80px] sm:text-[150px] lg:text-[200px]"
          >
            Contato
          </span>

          <div className="relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
            <div data-m3-reveal="left" className="lg:col-span-7 space-y-4">
              <div className="inline-flex items-center gap-2.5 rounded-full border border-[#16c0dd]/40 bg-[#16c0dd]/10 px-4 py-1.5 text-xs font-extrabold tracking-[0.2em] text-[#16c0dd] uppercase">
                <span className="h-2 w-2 rounded-full bg-[#16c0dd] shadow-[0_0_8px_#16c0dd]" />
                Atendimento Multimodal Instantâneo
              </div>
              <h2 className="text-3xl sm:text-4xl lg:text-[44px] font-extrabold tracking-tight leading-[1.12] text-white">
                Pronto para especificar ou cotar seu{" "}
                <span className="text-[#16c0dd]">projeto de controle de acesso?</span>
              </h2>
              <p className="text-sm sm:text-base text-white/75 leading-relaxed max-w-2xl">
                Converse com nosso assistente virtual por texto, áudio ou foto do equipamento para
                consultar estoque por Centro de Distribuição, validar compatibilidade via MCP B2B ou
                agendar visita técnica.
              </p>

              <div className="pt-3 flex flex-wrap items-center gap-4">
                <button
                  type="button"
                  onClick={() => useChatStore.getState().open()}
                  className="tl-primary-btn white-btn cursor-pointer"
                >
                  <span>Iniciar Atendimento IA</span>
                  <span className="icon" aria-hidden="true">
                    💬
                  </span>
                </button>

                <Link
                  href="/produtos"
                  className="inline-flex items-center gap-2.5 rounded-full border border-white/25 bg-white/10 backdrop-blur-md px-6 py-3.5 text-sm font-bold text-white hover:bg-[#16c0dd] hover:border-[#16c0dd] hover:text-[#191919] transition-all"
                >
                  <span>Ver Catálogo Completo</span>
                  <span aria-hidden="true">↗</span>
                </Link>
              </div>
            </div>

            {/* Frosted Glass Product Showcase Card on the Right */}
            <div data-m3-reveal="right" className="lg:col-span-5">
              <div className="rounded-[20px] border border-white/20 bg-white/10 backdrop-blur-[29px] p-5 shadow-2xl">
                <div className="grid grid-cols-2 gap-3">
                  <div className="m3-photo-card h-36 rounded-xl border-4 border-white bg-white overflow-hidden">
                    <img
                      src="/images/produtos/idface-max.jpg"
                      alt="iDFace Max"
                      className="h-full w-full object-cover"
                    />
                  </div>
                  <div className="m3-photo-card h-36 rounded-xl border-4 border-white bg-white overflow-hidden">
                    <img
                      src="/images/produtos/idblock-facial-inox.jpg"
                      alt="iDBlock Facial Inox"
                      className="h-full w-full object-cover"
                    />
                  </div>
                </div>
                <div className="mt-4 flex items-center justify-between border-t border-white/15 pt-3 text-xs text-white/80">
                  <span className="font-bold text-[#16c0dd]">● RAG + MCP B2B Online</span>
                  <span>Catálogo Fictícia Oficial</span>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
