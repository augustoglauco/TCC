import React from "react";
import Link from "next/link";
import ChartRenderer from "@/components/charts/ChartRenderer";
import type { ChatCardGrafico } from "@/lib/types/chat";

interface ChatChartCardProps {
  card: ChatCardGrafico;
}

const TIPO_LABELS: Record<string, string> = {
  bar: "Barras",
  line: "Linhas",
  pie: "Pizza",
  area: "Área",
  donut: "Donut",
};

export default function ChatChartCard({ card }: ChatChartCardProps) {
  const tipoLabel = TIPO_LABELS[card.tipo_grafico] || card.tipo_grafico;

  return (
    <div className="my-2.5 w-full max-w-lg overflow-hidden rounded-xl border border-slate-200 bg-white p-3.5 shadow-xs transition-shadow hover:shadow-md">
      <div className="mb-2 flex items-center justify-between gap-2 border-b border-slate-100 pb-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="text-base">📊</span>
          <h4 className="truncate text-sm font-semibold text-slate-800" title={card.titulo}>
            {card.titulo}
          </h4>
        </div>
        <span className="shrink-0 rounded-md bg-blue-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-blue-700">
          {tipoLabel}
        </span>
      </div>

      <div className="py-1">
        <ChartRenderer
          tipo_grafico={card.tipo_grafico}
          config={card.config}
          dados={card.dados}
          height={200}
        />
      </div>

      <div className="mt-2.5 flex items-center justify-between border-t border-slate-100 pt-2 text-xs">
        <span className="text-[11px] text-slate-400">Salvo no painel permanente</span>
        <Link
          href="/admin/dashboards"
          className="inline-flex items-center gap-1 font-semibold text-blue-600 hover:text-blue-700 hover:underline"
        >
          Ver no painel de dashboards →
        </Link>
      </div>
    </div>
  );
}
