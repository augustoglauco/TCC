"use client";

import { CollectionFormModal } from "@/components/admin/CollectionFormModal";
import { CollectionPurposeCard } from "./CollectionPurposeCard";
import { CollectionSelector } from "./CollectionSelector";
import { DocumentDropzone } from "./DocumentDropzone";
import { useEnviarDocumento } from "./useEnviarDocumento";
import type { DocumentIngestResponse, RagCollection, RagDomain } from "@/lib/types/rag";

const DOMAIN_OPTIONS: { value: RagDomain; label: string }[] = [
  { value: "vendas", label: "Vendas" },
  { value: "suporte", label: "Suporte Técnico" },
  { value: "atendimento", label: "Atendimento ao Usuário" },
];

function IngestaoAlertas({
  result,
  error,
}: {
  result: DocumentIngestResponse | null;
  error: string | null;
}) {
  return (
    <>
      {result && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-xs text-emerald-800 space-y-1">
          <div className="flex items-center gap-2 font-bold text-sm">
            <span>✅ Ingestão concluída com sucesso!</span>
          </div>
          <p>
            Arquivo <strong>&ldquo;{result.filename}&rdquo;</strong> ingerido no domínio{" "}
            <strong>&ldquo;{result.domain}&rdquo;</strong> —{" "}
            <strong>{result.chunks} chunk(s) gravado(s).</strong>
          </p>
        </div>
      )}
      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800 space-y-1">
          <div className="flex items-center gap-2 font-bold text-sm">
            <span>❌ Falha no Envio</span>
          </div>
          <p>{error}</p>
        </div>
      )}
    </>
  );
}

function DomainSelect({
  value,
  onChange,
}: {
  value: RagDomain;
  onChange: (domain: RagDomain) => void;
}) {
  return (
    <div className="space-y-2">
      <label
        htmlFor="domain"
        className="block text-xs font-bold uppercase tracking-wider text-slate-700"
      >
        Domínio da Informação
      </label>
      <select
        id="domain"
        value={value}
        onChange={(event) => onChange(event.target.value as RagDomain)}
        className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm font-semibold text-slate-800 shadow-2xs focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
      >
        {DOMAIN_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function BotaoEnviar({ disabled, enviando }: { disabled: boolean; enviando: boolean }) {
  return (
    <div className="pt-2">
      <button
        type="submit"
        disabled={disabled}
        className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white shadow-md hover:bg-blue-700 transition-all disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
      >
        {enviando ? (
          <>
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            <span>Indexando documento...</span>
          </>
        ) : (
          <>
            <span>Enviar para ingestão</span>
          </>
        )}
      </button>
    </div>
  );
}

export function AbaEnviarDocumento({
  collections,
  onColecoesMudaram,
  onIngerido,
}: {
  collections: RagCollection[];
  onColecoesMudaram: () => Promise<RagCollection[]>;
  onIngerido: () => void;
}) {
  const s = useEnviarDocumento({ collections, onColecoesMudaram, onIngerido });

  return (
    <div className="rounded-2xl border border-slate-200/90 bg-white p-6 sm:p-8 shadow-xs space-y-6">
      <div>
        <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
          <span>📥</span> Upload &amp; Indexação de Documento
        </h2>
        <p className="mt-1 text-sm text-slate-600">
          Envie um arquivo PDF ou texto (.txt / .md) para fragmentação (chunking), vetorização e
          indexação vetorial.
        </p>
      </div>

      <form onSubmit={s.handleSubmit} className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <DomainSelect value={s.domain} onChange={s.setDomain} />
          <CollectionSelector
            collections={collections}
            value={s.collectionSelecionada}
            disabled={s.criandoCollection}
            onChange={s.handleSelectCollectionChange}
            onOpenModal={() => s.setModalCriarAberto(true)}
          />
        </div>

        <CollectionPurposeCard
          purpose={s.selectedPurpose}
          b2bCount={collections.filter((c) => c.purpose === "mcp_b2b").length}
          adminCount={collections.filter((c) => c.purpose === "admin").length}
          criando={s.criandoCollection}
          onCriarRapida={s.criarCollectionRapida}
        />

        {/* Modal de Criação Customizada */}
        <CollectionFormModal
          open={s.modalCriarAberto}
          onOpenChange={s.setModalCriarAberto}
          onCreated={async (novaCol) => {
            s.setModalCriarAberto(false);
            await onColecoesMudaram();
            s.setCollectionId(novaCol.id);
          }}
        />

        <DocumentDropzone file={s.file} onFileChange={s.handleFileChange} onError={s.setError} />

        <BotaoEnviar disabled={!s.file || s.isSubmitting} enviando={s.isSubmitting} />
      </form>

      {/* Alertas de Resultado / Erro */}
      <IngestaoAlertas result={s.result} error={s.error} />
    </div>
  );
}
