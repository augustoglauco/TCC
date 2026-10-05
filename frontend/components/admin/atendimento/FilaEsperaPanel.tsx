"use client";

import React from "react";
import type { AtendimentoFilaItem } from "@/lib/api/adminAtendimento";

interface FilaEsperaPanelProps {
  fila: AtendimentoFilaItem[];
  loading: boolean;
  claimingId: string | null;
  onClaim: (conversationId: string) => Promise<void>;
  onRefresh: () => void;
}

function formatEspera(segundos: number): string {
  if (segundos < 60) return `${segundos}s`;
  const mins = Math.floor(segundos / 60);
  if (mins < 60) return `${mins} min`;
  const horas = Math.floor(mins / 60);
  return `${horas}h ${mins % 60}m`;
}

export default function FilaEsperaPanel({
  fila,
  loading,
  claimingId,
  onClaim,
  onRefresh,
}: FilaEsperaPanelProps) {
  return (
    <div className="flex flex-col h-full bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-slate-50/80">
        <div className="flex items-center gap-2">
          <span className="text-lg">⏳</span>
          <h2 className="text-sm font-semibold text-slate-900">Fila de Espera</h2>
          <span className="px-2 py-0.5 text-xs font-bold rounded-full bg-amber-100 text-amber-800">
            {fila.length}
          </span>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          title="Atualizar fila"
          aria-label="Atualizar fila"
          className="p-1 rounded text-slate-500 hover:text-slate-800 hover:bg-slate-200/60 transition-colors disabled:opacity-50"
        >
          🔄
        </button>
      </div>

      {/* Conteúdo da Fila */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {loading && fila.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-slate-400 text-xs">
            <span className="animate-spin text-xl mb-2">⏳</span>
            Carregando fila...
          </div>
        ) : fila.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-center p-4">
            <span className="text-2xl mb-1 text-slate-300">🎉</span>
            <p className="text-xs font-medium text-slate-600">Nenhum chat aguardando atendimento</p>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Todos os clientes estão sendo atendidos pela IA ou operadores.
            </p>
          </div>
        ) : (
          fila.map((item) => {
            const isTomFrustrado = item.motivo_escalonamento === "tom_frustrado";
            const isClaiming = claimingId === item.id;

            return (
              <div
                key={item.id}
                className={`p-3 rounded-lg border transition-all ${
                  isTomFrustrado
                    ? "border-red-200 bg-red-50/40 hover:border-red-300"
                    : "border-amber-200 bg-amber-50/30 hover:border-amber-300"
                }`}
              >
                {/* Badges do item */}
                <div className="flex items-center justify-between gap-1 mb-1.5 flex-wrap">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {isTomFrustrado ? (
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-red-100 text-red-800 border border-red-200">
                        🔥 Tom Frustrado
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-200">
                        🙋 Solicitação Direta
                      </span>
                    )}

                    {item.prioridade > 1 && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-200 text-slate-700">
                        P{item.prioridade}
                      </span>
                    )}
                  </div>

                  <span className="text-[11px] text-slate-500 font-mono" title="Tempo na fila">
                    ⏱️ {formatEspera(item.tempo_espera_segundos)}
                  </span>
                </div>

                {/* Info do Cliente */}
                <div className="mb-2">
                  <div className="text-xs font-semibold text-slate-800 truncate">
                    {item.cliente?.nome || "Cliente Visitante"}
                  </div>
                  {item.cliente?.email && (
                    <div className="text-[11px] text-slate-500 truncate">
                      {item.cliente.email}
                    </div>
                  )}
                </div>

                {/* Última mensagem */}
                {item.ultima_mensagem && (
                  <p className="text-xs text-slate-600 line-clamp-2 italic bg-white/70 p-2 rounded border border-slate-100 mb-2.5">
                    &ldquo;{item.ultima_mensagem}&rdquo;
                  </p>
                )}

                {/* Botão de Claim */}
                <button
                  type="button"
                  onClick={() => onClaim(item.id)}
                  disabled={isClaiming}
                  className="w-full py-1.5 px-3 rounded-md bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-xs transition-colors flex items-center justify-center gap-1.5 disabled:opacity-50 cursor-pointer"
                >
                  {isClaiming ? (
                    <>
                      <span className="animate-spin text-xs">⏳</span>
                      <span>Assumindo...</span>
                    </>
                  ) : (
                    <>
                      <span>🎧</span>
                      <span>Assumir Chat</span>
                    </>
                  )}
                </button>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
