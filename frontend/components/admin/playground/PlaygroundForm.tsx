"use client";

import { useMemo, useState } from "react";

import { CollectionOptionCard } from "@/components/admin/playground/CollectionOptionCard";
import type { CollectionPurpose, RagCollection, RagDomain } from "@/lib/types/rag";

const DOMAIN_OPTIONS: { value: RagDomain; label: string; desc: string; icon: string }[] = [
  { value: "vendas", label: "Vendas", desc: "Catálogos, preços e propostas", icon: "💼" },
  { value: "suporte", label: "Suporte Técnico", desc: "Manuais, CFTV e troubleshooting", icon: "🛠️" },
  { value: "atendimento", label: "Atendimento ao Usuário", desc: "Políticas, trocas e FAQs", icon: "💬" },
];

const PURPOSE_OPTIONS: { value: CollectionPurpose; label: string; desc: string; icon: string }[] = [
  { value: "chat", label: "Chat (Público)", desc: "Canal público para visitantes e clientes", icon: "💬" },
  { value: "mcp_b2b", label: "MCP B2B (Parceiros)", desc: "Canal de revendedores e parceiros B2B", icon: "🤝" },
  { value: "admin", label: "Admin (Interno)", desc: "Procedimentos e relatórios internos da administração", icon: "🔒" },
];

export interface PlaygroundFormProps {
  collections: RagCollection[];
  onSubmit: (params: { query: string; domain: RagDomain; collectionIds: string[] }) => void;
  isSubmitting: boolean;
}

export function PlaygroundForm({ collections, onSubmit, isSubmitting }: PlaygroundFormProps) {
  const [query, setQuery] = useState("");
  const [domain, setDomain] = useState<RagDomain>("vendas");
  const [purpose, setPurpose] = useState<CollectionPurpose>(() => {
    return collections.find((c) => c.purpose === "chat") ? "chat" : collections[0]?.purpose ?? "chat";
  });
  const [selecionadas, setSelecionadas] = useState<string[]>([]);

  // Coleções filtradas estritamente pelo purpose selecionado
  const collectionsDoPurpose = useMemo(() => {
    return collections.filter((c) => c.purpose === purpose);
  }, [collections, purpose]);

  function handleSelectPurpose(novoPurpose: CollectionPurpose) {
    if (novoPurpose === purpose) return;
    setPurpose(novoPurpose);
    setSelecionadas([]);
  }

  function alternarCollection(id: string) {
    setSelecionadas((atual) =>
      atual.includes(id) ? atual.filter((item) => item !== id) : [...atual, id],
    );
  }

  function selecionarTodas() {
    setSelecionadas(collectionsDoPurpose.map((c) => c.id));
  }

  function limparSelecao() {
    setSelecionadas([]);
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim() || selecionadas.length === 0 || isSubmitting) return;
    onSubmit({ query, domain, collectionIds: selecionadas });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* 1. Seleção de Purpose / Finalidade */}
      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <span className="block text-xs font-semibold uppercase tracking-wider text-slate-700">
              Finalidade / Canal (Purpose)
            </span>
            <p className="text-[11px] text-slate-500">
              O teste comparativo só é válido entre collections de mesma finalidade.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {PURPOSE_OPTIONS.map((opt) => {
            const isSelected = purpose === opt.value;
            const count = collections.filter((c) => c.purpose === opt.value).length;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => handleSelectPurpose(opt.value)}
                className={`inline-flex items-center gap-2 rounded-xl px-3.5 py-2 text-xs font-semibold transition-all cursor-pointer ${
                  isSelected
                    ? "bg-blue-600 text-white shadow-xs ring-2 ring-blue-600/30"
                    : "bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 hover:border-slate-300"
                }`}
              >
                <span>{opt.icon}</span>
                <span>{opt.label}</span>
                <span
                  className={`rounded-full px-1.5 py-0.5 text-[10px] ${
                    isSelected ? "bg-blue-500/80 text-white" : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12 border-t border-slate-100 pt-4">
        {/* Pergunta de teste */}
        <div className="lg:col-span-8 space-y-1.5">
          <div className="flex items-center justify-between">
            <label
              htmlFor="playground-query"
              className="block text-xs font-semibold uppercase tracking-wider text-slate-700"
            >
              Pergunta de teste
            </label>
            <span className="text-[11px] text-slate-400">
              {query.length} caracteres
            </span>
          </div>
          <div className="relative">
            <textarea
              id="playground-query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              rows={3}
              placeholder="Ex.: Qual é a política de trocas para itens com defeito de fábrica após 7 dias?"
              className="w-full rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 shadow-2xs resize-none"
            />
          </div>
        </div>

        {/* Domínio */}
        <div className="lg:col-span-4 space-y-1.5">
          <label
            htmlFor="playground-domain"
            className="block text-xs font-semibold uppercase tracking-wider text-slate-700"
          >
            Domínio
          </label>
          <div className="relative">
            <select
              id="playground-domain"
              value={domain}
              onChange={(e) => setDomain(e.target.value as RagDomain)}
              className="w-full appearance-none rounded-xl border border-slate-200 bg-white py-2.5 pl-3 pr-8 text-sm font-medium text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 shadow-2xs cursor-pointer"
            >
              {DOMAIN_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.icon} {option.label}
                </option>
              ))}
            </select>
            <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-xs text-slate-400">
              ▼
            </span>
          </div>

          <p className="text-[11px] text-slate-500 leading-relaxed pt-1">
            {DOMAIN_OPTIONS.find((opt) => opt.value === domain)?.desc}
          </p>
        </div>
      </div>

      {/* Seleção de Collections */}
      <fieldset className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-4">
          <div>
            <legend className="text-xs font-semibold uppercase tracking-wider text-slate-700">
              Collections a comparar ({PURPOSE_OPTIONS.find((p) => p.value === purpose)?.label})
            </legend>
            <p className="text-[11px] text-slate-500">
              Selecione as collections com finalidade &ldquo;{purpose}&rdquo; que serão consultadas em paralelo.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={selecionarTodas}
              disabled={collectionsDoPurpose.length === 0}
              className="text-xs font-medium text-blue-600 hover:text-blue-800 disabled:opacity-40 transition-colors"
            >
              Selecionar todas
            </button>
            <span className="text-slate-300">•</span>
            <button
              type="button"
              onClick={limparSelecao}
              disabled={selecionadas.length === 0}
              className="text-xs font-medium text-slate-500 hover:text-slate-700 disabled:opacity-40 transition-colors"
            >
              Limpar seleção
            </button>
          </div>
        </div>

        {collectionsDoPurpose.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-200 p-6 text-center text-sm text-slate-500">
            Nenhuma collection cadastrada com a finalidade &ldquo;{PURPOSE_OPTIONS.find((p) => p.value === purpose)?.label}&rdquo;.
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {collectionsDoPurpose.map((collection) => (
              <CollectionOptionCard
                key={collection.id}
                collection={collection}
                isSelected={selecionadas.includes(collection.id)}
                onToggle={alternarCollection}
              />
            ))}
          </div>
        )}
      </fieldset>

      {/* Rodapé com botão de ação */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
        <div className="text-xs text-slate-500">
          {selecionadas.length === 0 ? (
            <span className="text-amber-600">⚠️ Selecione ao menos uma collection de mesmo propósito para comparar.</span>
          ) : (
            <span>
              <span className="font-semibold text-slate-700">{selecionadas.length}</span>{" "}
              {selecionadas.length === 1 ? "collection selecionada" : "collections selecionadas"} ({purpose})
            </span>
          )}
        </div>

        <button
          type="submit"
          aria-label={isSubmitting ? "Comparando..." : "Comparar"}
          disabled={!query.trim() || selecionadas.length === 0 || isSubmitting}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-xs font-semibold text-white shadow-xs transition-all hover:bg-blue-700 active:scale-[0.99] disabled:pointer-events-none disabled:opacity-50 cursor-pointer"
        >
          {isSubmitting ? (
            <>
              <span className="animate-spin text-xs">⏳</span>
              <span>Comparando...</span>
            </>
          ) : (
            <>
              <span>⚡</span>
              <span>Comparar</span>
            </>
          )}
        </button>
      </div>
    </form>
  );
}
