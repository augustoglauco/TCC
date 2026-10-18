"use client";

import { useRef } from "react";
import { formatarDataPtBr } from "@/lib/format/metricas";

export type Period = "today" | "7d" | "30d" | "all" | "custom";

interface PeriodSelectorProps {
  period: Period;
  selectedDate: string;
  lastUpdated: Date | null;
  onPeriodChange: (p: Period) => void;
  onDateChange: (date: string) => void;
}

const PERIOD_BUTTONS: { value: Exclude<Period, "custom">; label: string }[] = [
  { value: "today", label: "Hoje" },
  { value: "7d", label: "7 Dias" },
  { value: "30d", label: "30 Dias" },
  { value: "all", label: "Tudo" },
];

const btnCls = (active: boolean) =>
  `rounded-lg px-2.5 sm:px-3 py-1.5 text-xs font-semibold transition-colors shrink-0 whitespace-nowrap ${
    active
      ? "bg-blue-600 text-white shadow-2xs"
      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
  }`;

export function PeriodSelector({
  period,
  selectedDate,
  lastUpdated,
  onPeriodChange,
  onDateChange,
}: PeriodSelectorProps) {
  const dateInputRef = useRef<HTMLInputElement | null>(null);

  const handleDateChange = (newDate: string) => {
    if (newDate) {
      onDateChange(newDate);
      if (period !== "custom") onPeriodChange("custom");
    }
  };

  return (
    <div className="flex flex-col sm:items-end gap-2 self-start sm:self-auto shrink-0">
      <div className="flex items-center gap-2 flex-nowrap overflow-x-auto max-w-full">
        <div className="flex items-center gap-1 sm:gap-1.5 rounded-xl border border-slate-200 bg-white p-1 shadow-2xs shrink-0 flex-nowrap">
          {/* Date-picker */}
          <label
            className={`relative inline-flex items-center gap-1.5 rounded-lg px-2.5 sm:px-3 py-1.5 text-xs font-semibold transition-colors shrink-0 whitespace-nowrap cursor-pointer select-none focus-within:ring-2 focus-within:ring-blue-500 ${
              period === "custom"
                ? "bg-blue-600 text-white shadow-2xs"
                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
            }`}
            title="Filtrar por data no calendário"
          >
            <span aria-hidden="true">📅</span>
            <span>
              {period === "custom" && selectedDate ? formatarDataPtBr(selectedDate) : "Calendário"}
            </span>
            <input
              ref={dateInputRef}
              type="date"
              max={new Date().toLocaleDateString("en-CA")}
              value={selectedDate}
              onChange={(e) => handleDateChange(e.target.value)}
              onClick={(e) => {
                if (period !== "custom") onPeriodChange("custom");
                try {
                  (e.target as HTMLInputElement).showPicker?.();
                } catch {}
              }}
              className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
              aria-label="Escolher data específica"
            />
          </label>

          {/* Period buttons */}
          {PERIOD_BUTTONS.map(({ value, label }) => (
            <button
              key={value}
              type="button"
              onClick={() => onPeriodChange(value)}
              className={btnCls(period === value)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {period === "custom" && (
          <span className="text-[11px] text-blue-700 font-semibold bg-blue-50 px-2 py-0.5 rounded-md border border-blue-200">
            Visualizando dia: {formatarDataPtBr(selectedDate)}
          </span>
        )}
        {lastUpdated && (
          <span className="text-[11px] text-slate-500 font-medium">
            Última atualização: {lastUpdated.toLocaleTimeString("pt-BR")}
          </span>
        )}
      </div>
    </div>
  );
}
