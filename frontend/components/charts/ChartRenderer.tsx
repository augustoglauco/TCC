"use client";

import React from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface ChartConfig {
  x_key?: string;
  y_keys?: string[];
  labels?: Record<string, string>;
  format?: "currency" | "number" | "percent";
  palette?: string[];
  [key: string]: unknown;
}

interface ChartRendererProps {
  tipo_grafico: "bar" | "line" | "pie" | "area" | "donut" | string;
  config: ChartConfig;
  dados: Array<Record<string, any>>;
  height?: number;
}

const DEFAULT_PALETTE = [
  "#3b82f6", // blue-500
  "#10b981", // emerald-500
  "#f59e0b", // amber-500
  "#ef4444", // red-500
  "#8b5cf6", // violet-500
  "#06b6d4", // cyan-500
  "#ec4899", // pink-500
];

function formatValue(value: any, fmt?: "currency" | "number" | "percent"): string {
  const num = typeof value === "number" ? value : parseFloat(value);
  if (isNaN(num)) return String(value ?? "");

  if (fmt === "currency") {
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
    }).format(num);
  }
  if (fmt === "percent") {
    return `${num.toFixed(1)}%`;
  }
  return new Intl.NumberFormat("pt-BR").format(num);
}

export default function ChartRenderer({
  tipo_grafico,
  config = {},
  dados = [],
  height = 280,
}: ChartRendererProps) {
  if (!dados || dados.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded-lg border border-dashed border-slate-200 bg-slate-50/50 p-6 text-sm text-slate-400"
        style={{ height }}
      >
        <span>📊 Nenhum dado disponível para visualização</span>
      </div>
    );
  }

  const palette = config.palette && config.palette.length > 0 ? config.palette : DEFAULT_PALETTE;
  const xKey = config.x_key || Object.keys(dados[0])[0];
  const yKeys =
    config.y_keys && config.y_keys.length > 0
      ? config.y_keys
      : Object.keys(dados[0]).filter((k) => k !== xKey && typeof dados[0][k] === "number");

  const effectiveYKeys = yKeys.length > 0 ? yKeys : [Object.keys(dados[0])[1] || "total"];

  const renderTooltip = (props: any) => {
    const { active, payload, label } = props;
    if (!active || !payload || !payload.length) return null;

    return (
      <div className="rounded-lg border border-slate-200 bg-white/95 px-3 py-2 text-xs shadow-md backdrop-blur-sm">
        <p className="font-semibold text-slate-700">{label}</p>
        <div className="mt-1 space-y-0.5">
          {payload.map((entry: any, index: number) => {
            const labelKey = entry.dataKey || entry.name;
            const displayLabel = config.labels?.[labelKey] || labelKey;
            return (
              <p key={`tooltip-${index}`} className="flex items-center gap-1.5 text-slate-600">
                <span
                  className="inline-block h-2 w-2 rounded-full"
                  style={{ backgroundColor: entry.color || entry.fill }}
                />
                <span className="font-medium">{displayLabel}:</span>
                <span className="font-bold text-slate-900">
                  {formatValue(entry.value, config.format)}
                </span>
              </p>
            );
          })}
        </div>
      </div>
    );
  };

  if (tipo_grafico === "pie" || tipo_grafico === "donut") {
    const isDonut = tipo_grafico === "donut";
    const valueKey = effectiveYKeys[0];

    return (
      <div className="w-full" style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Tooltip content={renderTooltip} />
            <Legend
              formatter={(value) => (
                <span className="text-xs font-medium text-slate-600">
                  {config.labels?.[value] || value}
                </span>
              )}
            />
            <Pie
              data={dados}
              dataKey={valueKey}
              nameKey={xKey}
              cx="50%"
              cy="50%"
              innerRadius={isDonut ? 55 : 0}
              outerRadius={85}
              paddingAngle={isDonut ? 3 : 1}
            >
              {dados.map((_, index) => (
                <Cell key={`cell-${index}`} fill={palette[index % palette.length]} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (tipo_grafico === "line") {
    return (
      <div className="w-full" style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={dados} margin={{ top: 10, right: 15, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
            <XAxis
              dataKey={xKey}
              tickLine={false}
              axisLine={{ stroke: "#cbd5e1" }}
              tick={{ fill: "#64748b", fontSize: 11 }}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              tick={{ fill: "#64748b", fontSize: 11 }}
              tickFormatter={(v) => formatValue(v, config.format)}
            />
            <Tooltip content={renderTooltip} />
            {effectiveYKeys.length > 1 && (
              <Legend
                formatter={(value) => (
                  <span className="text-xs font-medium text-slate-600">
                    {config.labels?.[value] || value}
                  </span>
                )}
              />
            )}
            {effectiveYKeys.map((key, index) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={palette[index % palette.length]}
                strokeWidth={2.5}
                dot={{ r: 3, fill: palette[index % palette.length] }}
                activeDot={{ r: 5 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (tipo_grafico === "area") {
    return (
      <div className="w-full" style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={dados} margin={{ top: 10, right: 15, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
            <XAxis
              dataKey={xKey}
              tickLine={false}
              axisLine={{ stroke: "#cbd5e1" }}
              tick={{ fill: "#64748b", fontSize: 11 }}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              tick={{ fill: "#64748b", fontSize: 11 }}
              tickFormatter={(v) => formatValue(v, config.format)}
            />
            <Tooltip content={renderTooltip} />
            {effectiveYKeys.length > 1 && (
              <Legend
                formatter={(value) => (
                  <span className="text-xs font-medium text-slate-600">
                    {config.labels?.[value] || value}
                  </span>
                )}
              />
            )}
            {effectiveYKeys.map((key, index) => (
              <Area
                key={key}
                type="monotone"
                dataKey={key}
                stroke={palette[index % palette.length]}
                fill={palette[index % palette.length]}
                fillOpacity={0.2}
                strokeWidth={2}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // Default: "bar"
  return (
    <div className="w-full" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={dados} margin={{ top: 10, right: 15, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
          <XAxis
            dataKey={xKey}
            tickLine={false}
            axisLine={{ stroke: "#cbd5e1" }}
            tick={{ fill: "#64748b", fontSize: 11 }}
          />
          <YAxis
            tickLine={false}
            axisLine={false}
            tick={{ fill: "#64748b", fontSize: 11 }}
            tickFormatter={(v) => formatValue(v, config.format)}
          />
          <Tooltip content={renderTooltip} />
          {effectiveYKeys.length > 1 && (
            <Legend
              formatter={(value) => (
                <span className="text-xs font-medium text-slate-600">
                  {config.labels?.[value] || value}
                </span>
              )}
            />
          )}
          {effectiveYKeys.map((key, index) => (
            <Bar
              key={key}
              dataKey={key}
              fill={palette[index % palette.length]}
              radius={[4, 4, 0, 0]}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
