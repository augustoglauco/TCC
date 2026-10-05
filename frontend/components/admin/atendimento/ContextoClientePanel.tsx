"use client";

import React from "react";
import type { AtendimentoDetalhes } from "@/lib/api/adminAtendimento";

interface ContextoClientePanelProps {
  detalhes: AtendimentoDetalhes | null;
}

export default function ContextoClientePanel({ detalhes }: ContextoClientePanelProps) {
  if (!detalhes) {
    return (
      <div className="flex flex-col h-full bg-white rounded-xl border border-slate-200 shadow-xs p-4 text-center items-center justify-center text-slate-400">
        <span className="text-2xl mb-1">👤</span>
        <p className="text-xs font-medium text-slate-600">Contexto do Cliente</p>
        <p className="text-[11px] text-slate-400 mt-0.5">
          Selecione uma conversa para visualizar os dados cadastrais e histórico de compras.
        </p>
      </div>
    );
  }

  const { cliente } = detalhes;

  return (
    <div className="flex flex-col h-full bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-200 bg-slate-50/80 flex items-center gap-2">
        <span className="text-base">📋</span>
        <h2 className="text-sm font-semibold text-slate-900">Contexto do Cliente</h2>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Identificação */}
        <div className="p-3 rounded-lg border border-slate-200 bg-slate-50/50 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-900 truncate">
              {cliente?.nome || "Visitante Anônimo"}
            </span>
            {cliente?.perfil && (
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-800">
                {cliente.perfil}
              </span>
            )}
          </div>

          {cliente?.email && (
            <div className="text-xs text-slate-600 break-all flex items-center gap-1">
              <span>✉️</span>
              <span>{cliente.email}</span>
            </div>
          )}

          {cliente?.perfil_motivo && (
            <p className="text-[11px] text-slate-500 italic bg-white p-2 rounded border border-slate-100">
              {cliente.perfil_motivo}
            </p>
          )}
        </div>

        {/* Histórico Comercial / Compras */}
        <div className="p-3 rounded-lg border border-slate-200 space-y-2">
          <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
            Histórico de Compras
          </h3>

          <div className="grid grid-cols-2 gap-2 pt-1">
            <div className="p-2 rounded bg-slate-100/70 text-center">
              <span className="block text-[10px] text-slate-500 uppercase font-semibold">
                Pedidos Feitos
              </span>
              <span className="text-sm font-bold text-slate-800">
                {cliente?.compras_count ?? 0}
              </span>
            </div>

            <div className="p-2 rounded bg-slate-100/70 text-center">
              <span className="block text-[10px] text-slate-500 uppercase font-semibold">
                Total Gasto
              </span>
              <span className="text-sm font-bold text-emerald-700">
                R$ {(cliente?.total_gasto ?? 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
              </span>
            </div>
          </div>
        </div>

        {/* Metadados da Conversa e Transbordo */}
        <div className="p-3 rounded-lg border border-slate-200 space-y-2.5">
          <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
            Dados do Atendimento
          </h3>

          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Status:</span>
              <span className="font-semibold text-slate-800 capitalize">
                {detalhes.status.replace(/_/g, " ")}
              </span>
            </div>

            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Prioridade:</span>
              <span className="font-bold text-slate-800">P{detalhes.prioridade}</span>
            </div>

            {detalhes.motivo_escalonamento && (
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Motivo:</span>
                <span className="font-semibold text-amber-700 capitalize">
                  {detalhes.motivo_escalonamento.replace(/_/g, " ")}
                </span>
              </div>
            )}

            {detalhes.escalado_em && (
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Escalado em:</span>
                <span className="font-mono text-[11px] text-slate-700">
                  {new Date(detalhes.escalado_em).toLocaleTimeString("pt-BR")}
                </span>
              </div>
            )}

            {detalhes.atendente_nome && (
              <div className="flex justify-between py-1">
                <span className="text-slate-500">Atendente:</span>
                <span className="font-semibold text-emerald-700">
                  {detalhes.atendente_nome}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
