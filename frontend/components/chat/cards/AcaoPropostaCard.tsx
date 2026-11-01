"use client";

import { useState } from "react";

import { cancelarAcao, confirmarAcao } from "@/lib/api/adminChatAcoes";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import type { ChatCardAcaoProposta } from "@/lib/types/chat";

type Estado = "pendente" | "enviando" | "executada" | "cancelada" | "erro";

function Valores({ dados }: { dados: Record<string, unknown> }) {
  return (
    <ul className="space-y-0.5 text-xs text-slate-800">
      {Object.entries(dados).map(([chave, valor]) => (
        <li key={chave}>
          <span className="text-slate-500">{chave}:</span>{" "}
          {typeof valor === "object" ? JSON.stringify(valor) : String(valor)}
        </li>
      ))}
    </ul>
  );
}

export default function AcaoPropostaCard({ card }: { card: ChatCardAcaoProposta }) {
  const token = useAuthStore((s) => s.token);
  const [estado, setEstado] = useState<Estado>("pendente");
  const [erro, setErro] = useState<string | null>(null);

  async function agir(acao: typeof confirmarAcao, final: Estado) {
    if (!token) return;
    setEstado("enviando");
    setErro(null);
    try {
      await acao(token, card.acao_id);
      setEstado(final);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro inesperado.");
      setEstado("erro");
    }
  }

  const aberto = estado === "pendente" || estado === "enviando" || estado === "erro";
  return (
    <div className="mt-2 space-y-2 rounded-lg border border-amber-200 bg-amber-50 p-3">
      <p className="text-sm font-semibold text-slate-900">{card.titulo}</p>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase text-slate-500">Antes</p>
          <Valores dados={card.antes} />
        </div>
        <div>
          <p className="text-[11px] font-semibold uppercase text-slate-500">Depois</p>
          <Valores dados={card.depois} />
        </div>
      </div>
      {card.aviso && <p className="text-xs font-semibold text-amber-800">{card.aviso}</p>}
      {erro && <p className="text-xs text-red-700">{erro}</p>}
      {estado === "executada" && <p className="text-xs font-semibold text-green-700">Ação executada.</p>}
      {estado === "cancelada" && <p className="text-xs font-semibold text-slate-600">Ação cancelada.</p>}
      {aberto && (
        <div className="flex gap-2">
          <button
            type="button"
            disabled={estado === "enviando"}
            onClick={() => agir(confirmarAcao, "executada")}
            className="rounded-md bg-gray-900 px-3 py-1.5 text-xs text-white disabled:opacity-50"
          >
            Confirmar
          </button>
          <button
            type="button"
            disabled={estado === "enviando"}
            onClick={() => agir(cancelarAcao, "cancelada")}
            className="rounded-md px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-100 disabled:opacity-50"
          >
            Cancelar
          </button>
        </div>
      )}
    </div>
  );
}
