"use client";

import { useState } from "react";

import type { RagCollection, RagDomain } from "@/lib/types/rag";

const DOMAIN_OPTIONS: { value: RagDomain; label: string }[] = [
  { value: "vendas", label: "Vendas" },
  { value: "suporte", label: "Suporte Técnico" },
  { value: "atendimento", label: "Atendimento ao Usuário" },
];

export interface PlaygroundFormProps {
  collections: RagCollection[];
  onSubmit: (params: { query: string; domain: RagDomain; collectionIds: string[] }) => void;
  isSubmitting: boolean;
}

export function PlaygroundForm({ collections, onSubmit, isSubmitting }: PlaygroundFormProps) {
  const [query, setQuery] = useState("");
  const [domain, setDomain] = useState<RagDomain>("vendas");
  const [selecionadas, setSelecionadas] = useState<string[]>([]);

  function alternarCollection(id: string) {
    setSelecionadas((atual) => (atual.includes(id) ? atual.filter((item) => item !== id) : [...atual, id]));
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim() || selecionadas.length === 0 || isSubmitting) return;
    onSubmit({ query, domain, collectionIds: selecionadas });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="playground-query" className="block text-sm font-medium text-gray-900">
          Pergunta de teste
        </label>
        <textarea
          id="playground-query"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          rows={3}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
        />
      </div>

      <div>
        <label htmlFor="playground-domain" className="block text-sm font-medium text-gray-900">
          Domínio
        </label>
        <select
          id="playground-domain"
          value={domain}
          onChange={(e) => setDomain(e.target.value as RagDomain)}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
        >
          {DOMAIN_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium text-gray-900">Collections a comparar</legend>
        {collections.map((collection) => (
          <label key={collection.id} className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={selecionadas.includes(collection.id)}
              onChange={() => alternarCollection(collection.id)}
            />
            {collection.name}
          </label>
        ))}
      </fieldset>

      <button
        type="submit"
        disabled={!query.trim() || selecionadas.length === 0 || isSubmitting}
        className="rounded-md bg-gray-900 px-4 py-2 text-sm text-white disabled:opacity-50"
      >
        {isSubmitting ? "Comparando..." : "Comparar"}
      </button>
    </form>
  );
}
