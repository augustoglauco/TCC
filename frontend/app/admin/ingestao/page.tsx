"use client";

// MVP: página administrativa simples (fora da navegação pública, sem
// autenticação) para upload avulso de documento no RAG — complementa
// `backend/scripts/ingest_sample_docs.py` (ingestão em lote). Decisão
// registrada em `docs/ARCHITECTURE.md` §5 e `docs/FRONTEND.md` §8.
import { useState } from "react";

import { RagApiError, uploadDocument } from "@/lib/api/rag";
import type { DocumentIngestResponse, RagDomain } from "@/lib/types/rag";

const DOMAIN_OPTIONS: { value: RagDomain; label: string }[] = [
  { value: "vendas", label: "Vendas" },
  { value: "suporte", label: "Suporte Técnico" },
  { value: "atendimento", label: "Atendimento ao Usuário" },
];

const ACCEPTED_EXTENSIONS = ".txt,.md,.pdf";

export default function IngestaoDocumentosPage() {
  const [file, setFile] = useState<File | null>(null);
  const [domain, setDomain] = useState<RagDomain>("vendas");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<DocumentIngestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || isSubmitting) {
      return;
    }
    // React anula `event.currentTarget` assim que o handler síncrono
    // termina — precisa capturar a referência do form antes do `await`
    // abaixo, senão `form.reset()` falha com "Cannot read properties of
    // null" depois que a resposta chega.
    const form = event.currentTarget;

    setIsSubmitting(true);
    setError(null);
    setResult(null);

    try {
      const response = await uploadDocument({ file, domain });
      setResult(response);
      setFile(null);
      form.reset();
    } catch (err) {
      setError(err instanceof RagApiError ? err.message : "Erro inesperado ao enviar o documento.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-16">
      <h1 className="text-2xl font-semibold text-gray-900">Ingestão de documentos (RAG)</h1>
      <p className="mt-2 text-gray-600">
        Envie um PDF ou texto (.txt/.md) para indexação no domínio escolhido. Página interna, sem
        impacto na navegação pública do site.
      </p>

      <form onSubmit={handleSubmit} className="mt-8 space-y-6">
        <div>
          <label htmlFor="domain" className="block text-sm font-medium text-gray-900">
            Domínio
          </label>
          <select
            id="domain"
            value={domain}
            onChange={(event) => setDomain(event.target.value as RagDomain)}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
          >
            {DOMAIN_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="file" className="block text-sm font-medium text-gray-900">
            Arquivo
          </label>
          <input
            id="file"
            type="file"
            accept={ACCEPTED_EXTENSIONS}
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="mt-1 block w-full text-gray-900"
          />
        </div>

        <button
          type="submit"
          disabled={!file || isSubmitting}
          className="rounded-md bg-gray-900 px-4 py-2 text-white disabled:opacity-50"
        >
          {isSubmitting ? "Enviando..." : "Enviar para ingestão"}
        </button>
      </form>

      {result && (
        <p className="mt-6 rounded-md bg-green-50 px-4 py-3 text-green-800">
          &ldquo;{result.filename}&rdquo; ingerido no domínio &ldquo;{result.domain}&rdquo; —{" "}
          {result.chunks} chunk(s) gravado(s).
        </p>
      )}
      {error && <p className="mt-6 rounded-md bg-red-50 px-4 py-3 text-red-800">{error}</p>}
    </div>
  );
}
