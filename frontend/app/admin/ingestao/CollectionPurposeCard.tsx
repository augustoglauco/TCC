"use client";

import type { CollectionPurpose } from "@/lib/types/rag";

interface Props {
  purpose: CollectionPurpose | "chat";
  b2bCount: number;
  adminCount: number;
  criando: boolean;
  onCriarRapida: (purpose: CollectionPurpose) => void;
}

const DESCRICOES: Record<string, string> = {
  chat: "Os documentos desta collection estarão disponíveis para consulta e resposta no assistente virtual do chat público.",
  mcp_b2b:
    "Conteúdo restrito ao canal MCP B2B para parceiros comerciais homologados. Não é pesquisado no chat público.",
  admin:
    "Documentação restrita de uso exclusivo da administração. Acessível somente em pesquisas no modo admin seguro.",
};

export function CollectionPurposeCard({
  purpose,
  b2bCount,
  adminCount,
  criando,
  onCriarRapida,
}: Props) {
  return (
    <div className="rounded-xl border border-slate-200/80 bg-slate-50/80 p-4 space-y-1">
      <div className="flex items-center gap-2">
        <span className="text-xs font-bold text-slate-700">Finalidades Previstas no Projeto:</span>
        {purpose === "chat" && (
          <span className="rounded-full bg-blue-100 text-blue-800 text-[10px] font-bold px-2.5 py-0.5">
            💬 Chat Público
          </span>
        )}
        {purpose === "mcp_b2b" && (
          <span className="rounded-full bg-purple-100 text-purple-800 text-[10px] font-bold px-2.5 py-0.5">
            🏢 MCP B2B Restrito
          </span>
        )}
        {purpose === "admin" && (
          <span className="rounded-full bg-amber-100 text-amber-800 text-[10px] font-bold px-2.5 py-0.5">
            🛡️ Admin Exclusivo
          </span>
        )}
      </div>
      <p className="text-xs text-slate-600 leading-relaxed pt-1">{DESCRICOES[purpose]}</p>

      {purpose === "mcp_b2b" && b2bCount === 0 && (
        <div className="mt-3 pt-2 border-t border-purple-200/80 flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs text-purple-900 font-medium">
            Nenhuma coleção MCP B2B existente.
          </span>
          <button
            type="button"
            disabled={criando}
            onClick={() => onCriarRapida("mcp_b2b")}
            className="rounded-lg bg-purple-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-purple-700 disabled:opacity-50 cursor-pointer shadow-2xs transition-all"
          >
            {criando ? "Criando..." : "⚡ Criar coleção docs_mcp_b2b agora"}
          </button>
        </div>
      )}

      {purpose === "admin" && adminCount === 0 && (
        <div className="mt-3 pt-2 border-t border-amber-200/80 flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs text-amber-900 font-medium">
            Nenhuma coleção Admin existente.
          </span>
          <button
            type="button"
            disabled={criando}
            onClick={() => onCriarRapida("admin")}
            className="rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-amber-700 disabled:opacity-50 cursor-pointer shadow-2xs transition-all"
          >
            {criando ? "Criando..." : "⚡ Criar coleção docs_admin agora"}
          </button>
        </div>
      )}
    </div>
  );
}
