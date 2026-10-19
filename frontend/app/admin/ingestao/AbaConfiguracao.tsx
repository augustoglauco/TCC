"use client";

import { useState } from "react";

import { CollectionFormModal } from "@/components/admin/CollectionFormModal";
import { CollectionsTable } from "@/components/admin/CollectionsTable";
import { ToastStack, useToast } from "@/components/ui/Toast";
import { colecoesAtivasPorFinalidade } from "./colecoesAtivas";
import { useRagSearchConfig } from "./useRagSearchConfig";
import type { RagCollection } from "@/lib/types/rag";

function RagSearchConfigSection({
  onError,
  onSuccess,
}: {
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}) {
  const { ragFallback, carregando, salvando, handleToggle } = useRagSearchConfig({
    onError,
    onSuccess,
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
        <span className="text-xl">🔍</span>
        <div>
          <h2 className="text-base font-bold text-slate-900">
            Regras de Busca &amp; Isolamento de Domínios RAG
          </h2>
          <p className="text-xs text-slate-500">
            Configuração do comportamento de busca vetorial no Qdrant
          </p>
        </div>
      </div>

      <div className="flex items-start gap-3 rounded-xl border border-amber-200/80 bg-amber-50/50 p-4">
        <input
          id="rt-rag-fallback"
          type="checkbox"
          checked={ragFallback}
          disabled={carregando || salvando}
          onChange={(e) => handleToggle(e.target.checked)}
          className="mt-0.5 h-4 w-4 rounded border-amber-300 text-amber-600 focus:ring-amber-500 cursor-pointer disabled:opacity-50"
        />
        <div className="space-y-0.5">
          <label
            htmlFor="rt-rag-fallback"
            className="text-xs font-semibold text-amber-900 cursor-pointer"
          >
            RAG: buscar sem filtro de domínio quando a busca filtrada vem vazia
          </label>
          <p className="text-[11px] text-amber-700 leading-relaxed">
            Desligado por padrão (recomendado) para preservar o isolamento estrito entre domínios
            (vendas, suporte, atendimento) e manter a precisão do roteador de escalonamento.
          </p>
        </div>
      </div>
    </div>
  );
}

function CollectionPurposeStatusCard({
  icon,
  label,
  colorClass,
  ativa,
  descricao,
}: {
  icon: string;
  label: string;
  colorClass: { border: string; bg: string; text: string };
  ativa: RagCollection | undefined;
  descricao: string;
}) {
  return (
    <div className={`rounded-xl border ${colorClass.border} ${colorClass.bg} p-4 space-y-2`}>
      <div className="flex items-center justify-between">
        <span
          className={`text-xs font-bold uppercase tracking-wider ${colorClass.text} flex items-center gap-1.5`}
        >
          <span>{icon}</span> {label}
        </span>
        {ativa ? (
          <span className="rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-bold px-2 py-0.5 border border-emerald-300">
            Ativa
          </span>
        ) : (
          <span className="rounded-full bg-amber-100 text-amber-800 text-[10px] font-bold px-2 py-0.5 border border-amber-300">
            Sem ativa
          </span>
        )}
      </div>
      <div className="text-sm font-bold text-slate-900 truncate">
        {ativa ? (
          <span>Coleção ativa: {ativa.name}</span>
        ) : (
          <span className="text-slate-400 font-normal italic">Nenhuma ativa</span>
        )}
      </div>
      <p className="text-[11px] text-slate-600 leading-tight">{descricao}</p>
    </div>
  );
}

function ColecoesAtivasSection({ collections }: { collections: RagCollection[] }) {
  const ativas = colecoesAtivasPorFinalidade(collections);
  return (
    <div className="border-t border-slate-100 pt-6 space-y-4">
      <div>
        <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
          <span>⭐</span> Collections Ativas por Finalidade (Purpose)
        </h2>
        <p className="text-xs text-slate-600">
          Cada canal do sistema possui exatamente uma collection ativa independente para buscas
          vetoriais.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <CollectionPurposeStatusCard
          icon="💬"
          label="Chat Público"
          colorClass={{ border: "border-blue-200/80", bg: "bg-blue-50/40", text: "text-blue-800" }}
          ativa={ativas.chat}
          descricao="Consultada pelo assistente nas conversas do chat público com clientes."
        />
        <CollectionPurposeStatusCard
          icon="🏢"
          label="MCP B2B Restrito"
          colorClass={{
            border: "border-purple-200/80",
            bg: "bg-purple-50/40",
            text: "text-purple-800",
          }}
          ativa={ativas.b2b}
          descricao="Consultada pelos revendedores parceiros no canal de integração MCP B2B."
        />
        <CollectionPurposeStatusCard
          icon="🛡️"
          label="Admin Exclusivo"
          colorClass={{ border: "border-rose-200/80", bg: "bg-rose-50/40", text: "text-rose-800" }}
          ativa={ativas.admin}
          descricao="Consultada pelo administrador no modo seguro do chat do painel."
        />
      </div>
    </div>
  );
}

function PerfisColecoesSection({
  collections,
  onChanged,
  showToast,
}: {
  collections: RagCollection[];
  onChanged: () => void;
  showToast: (message: string, kind: "success" | "error") => void;
}) {
  const [modalAberto, setModalAberto] = useState(false);

  return (
    <div className="border-t border-slate-100 pt-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-slate-900">Perfis de Coleções Qdrant</h2>
          <p className="text-xs text-slate-600">Perfis de collection do Qdrant usados pelo RAG.</p>
        </div>
        <button
          type="button"
          onClick={() => setModalAberto(true)}
          className="rounded-xl bg-slate-900 px-4 py-2 text-xs sm:text-sm font-semibold text-white shadow-xs hover:bg-slate-800 transition-colors cursor-pointer"
        >
          + Nova Collection
        </button>
      </div>

      <div className="mt-4">
        <CollectionsTable
          collections={collections}
          onChanged={onChanged}
          onError={(message) => showToast(message, "error")}
          onSuccess={(message) => showToast(message, "success")}
        />
      </div>

      <CollectionFormModal
        open={modalAberto}
        onOpenChange={setModalAberto}
        onCreated={() => {
          setModalAberto(false);
          showToast("Collection criada com sucesso.", "success");
          onChanged();
        }}
      />
    </div>
  );
}

export function AbaConfiguracao({
  collections,
  onChanged,
}: {
  collections: RagCollection[];
  onChanged: () => void;
}) {
  const { toasts, showToast, dismissToast } = useToast();

  return (
    <div className="space-y-6">
      {/* Master Card Unificando as Configurações de Busca e Coleções RAG */}
      <div className="rounded-2xl border border-slate-200/90 bg-white p-5 sm:p-6 shadow-xs space-y-6">
        <RagSearchConfigSection
          onError={(msg) => showToast(msg, "error")}
          onSuccess={(msg) => showToast(msg, "success")}
        />
        <ColecoesAtivasSection collections={collections} />
        <PerfisColecoesSection
          collections={collections}
          onChanged={onChanged}
          showToast={showToast}
        />
      </div>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
