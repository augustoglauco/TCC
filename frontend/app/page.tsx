"use client";

import Link from "next/link";
import { useChatStore } from "@/lib/hooks/useChatStore";
import HeroSlider from "@/components/home/HeroSlider";
import TechMarquee from "@/components/home/TechMarquee";
import CapabilitiesGrid from "@/components/home/CapabilitiesGrid";
import HardwareReveal from "@/components/home/HardwareReveal";
import MetricCounters from "@/components/home/MetricCounters";
import ProcessSteps from "@/components/home/ProcessSteps";

export default function HomePage() {
  return (
    <div className="space-y-0">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 pt-6 pb-8 sm:pt-10 sm:pb-12">
        <HeroSlider />
      </div>

      <TechMarquee />

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8 sm:py-12 space-y-12 sm:space-y-16">
        <CapabilitiesGrid />

        <HardwareReveal />

        <MetricCounters />

        <ProcessSteps />

        {/* Seção de CTA Final */}
        <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 border border-slate-800 p-8 sm:p-12 text-white shadow-2xl">
          <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-8">
            <div className="space-y-3 max-w-2xl">
              <span className="inline-flex items-center gap-2 rounded-full border border-blue-500/30 bg-blue-500/10 px-3.5 py-1 text-xs font-bold tracking-widest text-blue-400 uppercase">
                Atendimento Multimodal Instantâneo
              </span>
              <h2 className="text-2xl sm:text-4xl font-extrabold tracking-tight leading-tight">
                Pronto para especificar ou cotar seu{" "}
                <span className="bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">
                  projeto de controle de acesso?
                </span>
              </h2>
              <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
                Converse com nosso assistente virtual por texto, áudio ou foto do equipamento para
                consultar estoque por Centro de Distribuição, validar compatibilidade via MCP B2B ou
                agendar visita técnica.
              </p>
            </div>

            <div className="flex flex-col sm:flex-row lg:flex-col xl:flex-row gap-3.5 shrink-0">
              <button
                type="button"
                onClick={() => useChatStore.getState().open()}
                className="inline-flex items-center justify-center gap-2.5 rounded-xl bg-gradient-to-r from-blue-600 via-indigo-600 to-blue-500 px-6 py-3.5 text-sm font-bold text-white shadow-lg shadow-blue-600/30 hover:shadow-blue-600/50 hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-blue-400 transition-all cursor-pointer"
              >
                <span>Iniciar Atendimento IA</span>
                <span>💬</span>
              </button>

              <Link
                href="/produtos"
                className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-700 bg-slate-900/80 px-6 py-3.5 text-sm font-semibold text-slate-200 hover:bg-slate-800 hover:text-white hover:border-slate-600 transition-all"
              >
                <span>Ver Catálogo Completo</span>
                <span>📦</span>
              </Link>
            </div>
          </div>

          <div
            aria-hidden="true"
            className="pointer-events-none absolute -right-24 -bottom-24 h-80 w-80 rounded-full bg-blue-600/15 blur-3xl"
          />
        </section>
      </div>
    </div>
  );
}
