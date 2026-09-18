"use client";

import { useState } from "react";
import type { ChatUIMessage } from "@/lib/types/chat";

// MVP: rótulo de domínio é só um mapa fixo de texto — sem i18n nem vindo do
// backend (ver docs/FRONTEND.md §3, "Indicador de domínio").
const DOMAIN_LABELS: Record<string, string> = {
  vendas: "Vendas",
  suporte: "Suporte Técnico",
  atendimento: "Atendimento ao Usuário",
  agendamento: "Agendamento",
  fora_escopo: "Fora de escopo",
};

const REASON_LABELS: Record<string, string> = {
  nenhum: "Execução Direta (Sem Escalonamento)",
  fora_escopo: "Fora do Escopo Conhecido",
  rag_vazio: "Base RAG Sem Documentos Relevantes",
  complexidade_alta: "Alta Complexidade Detectada",
};

interface MessageBubbleProps {
  message: ChatUIMessage;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const [showDetails, setShowDetails] = useState(false);

  const isUser = message.role === "user";
  const isExternalLlm = !isUser && message.backendUsed === "externo";
  const domainLabel = message.domain ? (DOMAIN_LABELS[message.domain] ?? message.domain) : null;
  const metrics = message.metrics;

  // Cálculo dinâmico de TPS caso o backend não tenha enviado explicitamente
  const calculatedTps =
    metrics?.tps ??
    (metrics?.completionTokens && metrics?.latencyMs
      ? Math.round(
          (metrics.completionTokens / Math.max((metrics.latencyMs - (metrics.ttftMs || 0)) / 1000, 0.001)) * 10
        ) / 10
      : null);

  return (
    <div className={`flex flex-col ${isUser ? "items-end" : "items-start"} space-y-1.5 w-full`}>
      <div
        data-testid="message-bubble"
        className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm shadow-xs ${
          isUser
            ? "bg-gradient-to-br from-blue-600 to-indigo-600 text-white rounded-tr-xs"
            : isExternalLlm
              ? "bg-blue-50 text-blue-950 border border-blue-200/80 rounded-tl-xs"
              : "bg-slate-100 text-slate-900 border border-slate-200/60 rounded-tl-xs"
        }`}
      >
        {!isUser && domainLabel && (
          <span
            data-testid="message-domain-label"
            className="mb-1 block text-[10px] font-bold uppercase tracking-wider text-blue-600"
          >
            {domainLabel}
          </span>
        )}
        <p className="leading-relaxed whitespace-pre-wrap">{message.text}</p>
      </div>

      {!isUser && (
        <div className="flex flex-col max-w-full items-start space-y-1">
          {/* Main dynamic metrics bar */}
          <div
            data-testid="message-metrics"
            className="flex flex-wrap items-center gap-x-2.5 gap-y-1 rounded-xl border border-slate-800 bg-slate-900/90 px-3 py-1.5 font-mono text-[11px] text-slate-300 shadow-md backdrop-blur-xs"
          >
            <span className="flex items-center gap-1 font-semibold text-slate-100">
              🤖 <span className="text-blue-400">{metrics?.modelName || (isExternalLlm ? "OpenRouter" : "Ollama (local)")}</span>
            </span>

            <span className="text-slate-700">|</span>

            <span className="flex items-center gap-1">
              🔤 <span className="text-emerald-400">IN:</span> {metrics?.promptTokens ?? "-"} <span className="text-emerald-400">OUT:</span> {metrics?.completionTokens ?? "-"}
            </span>

            <span className="text-slate-700">|</span>

            <span className="flex items-center gap-1">
              ⏱️ <span className="text-amber-400">Latência:</span> {metrics?.latencyMs ? `${(metrics.latencyMs / 1000).toFixed(2)}s` : "-"}
            </span>

            <span className="text-slate-700">|</span>

            <span className="flex items-center gap-1">
              ⚡ <span className="text-cyan-400">1º Token:</span> {metrics?.ttftMs ? `${Math.round(metrics.ttftMs)}ms` : "-"}
            </span>

            {calculatedTps !== null && (
              <>
                <span className="text-slate-700">|</span>
                <span className="flex items-center gap-1">
                  🚀 <span className="text-purple-400">TPS:</span> {calculatedTps} tok/s
                </span>
              </>
            )}

            <span className="text-slate-700">|</span>

            <button
              type="button"
              onClick={() => setShowDetails((prev) => !prev)}
              aria-label="Alternar telemetria detalhada"
              className="flex items-center gap-1 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-sans font-medium text-slate-200 hover:bg-slate-700 hover:text-white transition-colors cursor-pointer"
            >
              📊 {showDetails ? "Ocultar" : "Detalhes"}
            </button>
          </div>

          {/* Extended Telemetry Panel */}
          {showDetails && (
            <div className="w-full max-w-lg rounded-xl border border-slate-700/60 bg-slate-900/95 p-3 text-xs text-slate-200 shadow-xl space-y-2.5 font-mono animate-in fade-in slide-in-from-top-1 duration-200">
              <div className="flex items-center justify-between border-b border-slate-800 pb-1.5">
                <span className="font-semibold text-slate-100 flex items-center gap-1.5">
                  🔍 Telemetria & Diagnóstico LLM
                </span>
                <span className="text-[10px] text-slate-400">TCC Performance Analytics</span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-[11px]">
                {/* Roteador e Modelo */}
                <div className="rounded-lg bg-slate-800/60 p-2 space-y-1">
                  <div className="font-sans font-semibold text-blue-400 text-[10px] uppercase tracking-wider">
                    🤖 Roteador & Modelo
                  </div>
                  <div><span className="text-slate-400">Backend:</span> {message.backendUsed === "externo" ? "Cloud (OpenRouter)" : "Local (Ollama)"}</div>
                  <div><span className="text-slate-400">Modelo:</span> {metrics?.modelName || "-"}</div>
                  <div><span className="text-slate-400">Domínio:</span> {domainLabel || "-"}</div>
                  <div><span className="text-slate-400">Complexidade:</span> {metrics?.complexity || "baixa"}</div>
                  {metrics?.confidence !== undefined && metrics.confidence !== null && (
                    <div><span className="text-slate-400">Confiança Rota:</span> {(metrics.confidence * 100).toFixed(1)}%</div>
                  )}
                  {metrics?.escalationReason && (
                    <div className="text-[10px] text-slate-400 truncate" title={REASON_LABELS[metrics.escalationReason] ?? metrics.escalationReason}>
                      Motivo: {metrics.escalationReason}
                    </div>
                  )}
                </div>

                {/* Desempenho */}
                <div className="rounded-lg bg-slate-800/60 p-2 space-y-1">
                  <div className="font-sans font-semibold text-amber-400 text-[10px] uppercase tracking-wider">
                    ⏱️ Desempenho
                  </div>
                  <div><span className="text-slate-400">Latência Total:</span> {metrics?.latencyMs ? `${Math.round(metrics.latencyMs)} ms` : "-"}</div>
                  <div><span className="text-slate-400">1º Token (TTFT):</span> {metrics?.ttftMs ? `${Math.round(metrics.ttftMs)} ms` : "-"}</div>
                  <div>
                    <span className="text-slate-400">Tempo Geração:</span>{" "}
                    {metrics?.latencyMs && metrics?.ttftMs
                      ? `${Math.max(Math.round(metrics.latencyMs - metrics.ttftMs), 0)} ms`
                      : "-"}
                  </div>
                  <div><span className="text-slate-400">Velocidade (TPS):</span> {calculatedTps !== null ? `${calculatedTps} tokens/s` : "-"}</div>
                </div>

                {/* Tokens & Custo */}
                <div className="rounded-lg bg-slate-800/60 p-2 space-y-1">
                  <div className="font-sans font-semibold text-emerald-400 text-[10px] uppercase tracking-wider">
                    🔤 Tokens & Custo
                  </div>
                  <div><span className="text-slate-400">Prompt (IN):</span> {metrics?.promptTokens ?? 0} tokens</div>
                  <div><span className="text-slate-400">Resposta (OUT):</span> {metrics?.completionTokens ?? 0} tokens</div>
                  <div><span className="text-slate-400">Total Tokens:</span> {(metrics?.promptTokens ?? 0) + (metrics?.completionTokens ?? 0)} tokens</div>
                  <div>
                    <span className="text-slate-400">Custo Estimado:</span>{" "}
                    {metrics?.estimatedCostUsd !== undefined && metrics.estimatedCostUsd !== null
                      ? `$${metrics.estimatedCostUsd.toFixed(6)}`
                      : "$0.000000 (Local)"}
                  </div>
                </div>

                {/* RAG */}
                <div className="rounded-lg bg-slate-800/60 p-2 space-y-1">
                  <div className="font-sans font-semibold text-cyan-400 text-[10px] uppercase tracking-wider">
                    📚 RAG & Recuperação
                  </div>
                  <div><span className="text-slate-400">Tempo Busca RAG:</span> {metrics?.ragRetrievalMs !== undefined && metrics.ragRetrievalMs !== null ? `${metrics.ragRetrievalMs} ms` : "N/A"}</div>
                  <div><span className="text-slate-400">Chunks Usados:</span> {metrics?.ragChunksCount ?? 0} trechos</div>
                  <div>
                    <span className="text-slate-400">Score Médio:</span>{" "}
                    {metrics?.ragAvgScore !== undefined && metrics.ragAvgScore !== null
                      ? metrics.ragAvgScore.toFixed(4)
                      : "N/A"}
                  </div>
                  {metrics?.ragChunks && metrics.ragChunks.length > 0 && (
                    <div className="pt-1 space-y-0.5">
                      <div className="text-slate-400">Fontes:</div>
                      {metrics.ragChunks.map((chunk, idx) => (
                        <div key={`${chunk.source}-${idx}`} className="truncate pl-2" title={chunk.source}>
                          {chunk.source} <span className="text-slate-500">({chunk.score.toFixed(4)})</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
