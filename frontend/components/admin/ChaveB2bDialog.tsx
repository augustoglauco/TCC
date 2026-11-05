"use client";

import { useState } from "react";
import type { ChaveParceiroGerada } from "@/lib/api/parceirosB2b";

interface ChaveB2bDialogProps {
  chave: ChaveParceiroGerada;
  onFechar: () => void;
}

/** Mostra a chave B2B recém-gerada. O texto só existe aqui: depois de fechar, não dá para recuperá-lo. */
export function ChaveB2bDialog({ chave, onFechar }: ChaveB2bDialogProps) {
  const [copiada, setCopiada] = useState(false);

  async function copiar() {
    try {
      await navigator.clipboard.writeText(chave.chave);
      setCopiada(true);
    } catch {
      setCopiada(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="chave-b2b-titulo"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 px-4"
    >
      <div className="w-full max-w-lg space-y-4 rounded-2xl bg-white p-6 shadow-xl">
        <h2 id="chave-b2b-titulo" className="text-lg font-bold text-slate-900">
          Chave de acesso B2B gerada
        </h2>
        <p className="text-xs text-slate-600">
          Parceiro: <strong>{chave.email}</strong>. Copie a chave agora e envie ao parceiro por um
          canal seguro: <strong>ela não será mostrada de novo</strong>. Gerar outra chave revoga
          esta.
        </p>
        <div className="flex items-center gap-2">
          <input
            readOnly
            aria-label="Chave B2B"
            value={chave.chave}
            onFocus={(e) => e.currentTarget.select()}
            className="w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 font-mono text-xs text-slate-900"
          />
          <button
            type="button"
            onClick={copiar}
            className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-bold text-white hover:bg-blue-700"
          >
            {copiada ? "Copiada ✓" : "Copiar"}
          </button>
        </div>
        <p className="text-[11px] text-slate-500">
          O parceiro envia <code>Authorization: Bearer &lt;chave&gt;</code> em toda requisição ao
          MCP B2B (manual: <code>MANUAL_INTEGRACAO_MCP_B2B.md</code>). O servidor MCP aceita a chave
          assim que ela é gerada, sem reiniciar.
        </p>
        <div className="text-right">
          <button
            type="button"
            onClick={onFechar}
            className="rounded-lg border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            Já copiei, fechar
          </button>
        </div>
      </div>
    </div>
  );
}
