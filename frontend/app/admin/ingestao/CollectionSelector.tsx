"use client";

import type { RagCollection } from "@/lib/types/rag";

interface Props {
  collections: RagCollection[];
  value: string;
  disabled: boolean;
  onChange: (val: string) => void;
  onOpenModal: () => void;
}

export function CollectionSelector({ collections, value, disabled, onChange, onOpenModal }: Props) {
  const chatCollections = collections.filter((c) => (c.purpose || "chat") === "chat");
  const b2bCollections = collections.filter((c) => c.purpose === "mcp_b2b");
  const adminCollections = collections.filter((c) => c.purpose === "admin");

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label
          htmlFor="collection"
          className="block text-xs font-bold uppercase tracking-wider text-slate-700"
        >
          Collection destino
        </label>
        <button
          type="button"
          onClick={onOpenModal}
          className="text-xs text-blue-600 font-semibold hover:underline cursor-pointer"
        >
          + Nova customizada
        </button>
      </div>
      <select
        id="collection"
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm font-semibold text-slate-800 shadow-2xs focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 disabled:opacity-50"
      >
        <optgroup label="💬 Chat Público (purpose: chat)">
          {chatCollections.length > 0 ? (
            chatCollections.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} {c.is_active ? "★ (ativa no Chat)" : ""}
              </option>
            ))
          ) : (
            <option value="__create_chat__">
              ⚡ Criar coleção inicial para Chat Público (docs_chat)
            </option>
          )}
        </optgroup>

        <optgroup label="🏢 MCP B2B Restrito (purpose: mcp_b2b)">
          {b2bCollections.length > 0 ? (
            b2bCollections.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} {c.is_active ? "★ (ativa no MCP B2B)" : "[MCP B2B]"}
              </option>
            ))
          ) : (
            <option value="__create_mcp_b2b__">
              ⚡ Criar coleção inicial para MCP B2B (docs_mcp_b2b)
            </option>
          )}
        </optgroup>

        <optgroup label="🛡️ Admin Exclusivo (purpose: admin)">
          {adminCollections.length > 0 ? (
            adminCollections.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} {c.is_active ? "★ (ativa no Admin)" : "[Admin]"}
              </option>
            ))
          ) : (
            <option value="__create_admin__">
              ⚡ Criar coleção inicial para Admin (docs_admin)
            </option>
          )}
        </optgroup>
      </select>
    </div>
  );
}
