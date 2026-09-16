"use client";

// MVP: página administrativa (fora da navegação pública, sem autenticação)
// para upload avulso de documento no RAG, gestão do registro de documentos
// ingeridos, configuração de perfis de collection e playground de busca
// comparativo — decisão registrada em `docs/ARCHITECTURE.md` §5 e
// `docs/FRONTEND.md` §8. Ver
// docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md e
// docs/superpowers/specs/2026-09-15-rag-collections-config-design.md.
import { useCallback, useEffect, useState } from "react";

import { CollectionFormModal } from "@/components/admin/CollectionFormModal";
import { CollectionsTable } from "@/components/admin/CollectionsTable";
import { DocumentsTable } from "@/components/admin/DocumentsTable";
import { PlaygroundPanel } from "@/components/admin/playground/PlaygroundPanel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { ToastStack, useToast } from "@/components/ui/Toast";
import { RagApiError, listCollections, listDocuments, uploadDocument } from "@/lib/api/rag";
import type {
  DocumentIngestResponse,
  DocumentRegistryEntry,
  RagCollection,
  RagDomain,
} from "@/lib/types/rag";

const DOMAIN_OPTIONS: { value: RagDomain; label: string }[] = [
  { value: "vendas", label: "Vendas" },
  { value: "suporte", label: "Suporte Técnico" },
  { value: "atendimento", label: "Atendimento ao Usuário" },
];

const ACCEPTED_EXTENSIONS = ".txt,.md,.pdf";

function AbaEnviarDocumento({
  collections,
  onIngerido,
}: {
  collections: RagCollection[];
  onIngerido: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [domain, setDomain] = useState<RagDomain>("vendas");
  const [collectionId, setCollectionId] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<DocumentIngestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const collectionAtiva = collections.find((collection) => collection.is_active);
  // `collectionId` pode ficar "preso" no id de uma collection que foi apagada em outra aba
  // (ex.: via "Configuração") sem que este formulário seja remontado — por isso o valor
  // efetivamente usado é derivado a cada render, caindo no mesmo fallback do valor padrão
  // (collection ativa, senão a primeira da lista) sempre que `collectionId` não é (mais) uma
  // collection válida. Mesmo padrão usado em `ReingestModal.tsx` para `targetIdEfetivo`.
  const collectionSelecionada = collections.some((collection) => collection.id === collectionId)
    ? collectionId
    : collectionAtiva?.id || collections[0]?.id || "";

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || isSubmitting) {
      return;
    }
    const form = event.currentTarget;

    setIsSubmitting(true);
    setError(null);
    setResult(null);

    try {
      const response = await uploadDocument({
        file,
        domain,
        collectionId: collectionSelecionada || undefined,
      });
      setResult(response);
      setFile(null);
      form.reset();
      onIngerido();
    } catch (err) {
      setError(err instanceof RagApiError ? err.message : "Erro inesperado ao enviar o documento.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      <p className="text-gray-600">
        Envie um PDF ou texto (.txt/.md) para indexação no domínio escolhido.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 space-y-6">
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
          <label htmlFor="collection" className="block text-sm font-medium text-gray-900">
            Collection destino
          </label>
          <select
            id="collection"
            value={collectionSelecionada}
            onChange={(event) => setCollectionId(event.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
          >
            {collections.map((collection) => (
              <option key={collection.id} value={collection.id}>
                {collection.name}
                {collection.is_active ? " (ativa)" : ""}
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

function AbaDocumentosIngeridos({ collections }: { collections: RagCollection[] }) {
  const [documentos, setDocumentos] = useState<DocumentRegistryEntry[] | null>(null);
  const { toasts, showToast, dismissToast } = useToast();

  const carregarDocumentos = useCallback(async () => {
    try {
      setDocumentos(await listDocuments());
    } catch (err) {
      showToast(
        err instanceof RagApiError ? err.message : "Erro inesperado ao carregar os documentos.",
        "error",
      );
      setDocumentos([]);
    }
  }, [showToast]);

  useEffect(() => {
    // `carregarDocumentos` só chama `setDocumentos`/`showToast` depois do
    // `await` (assíncrono, não durante a execução síncrona do efeito) —
    // falso positivo conhecido de `react-hooks/set-state-in-effect` para o
    // padrão usual de "buscar dados ao montar".
    // eslint-disable-next-line react-hooks/set-state-in-effect
    carregarDocumentos();
  }, [carregarDocumentos]);

  function handleDeleted(id: string) {
    setDocumentos((atual) => atual?.filter((documento) => documento.id !== id) ?? null);
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      {documentos === null ? (
        <p className="text-sm text-gray-600">Carregando...</p>
      ) : (
        <DocumentsTable
          documents={documentos}
          collections={collections}
          onDeleted={handleDeleted}
          onReingested={carregarDocumentos}
        />
      )}
      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}

function AbaConfiguracao({
  collections,
  onChanged,
}: {
  collections: RagCollection[];
  onChanged: () => void;
}) {
  const [modalAberto, setModalAberto] = useState(false);
  const { toasts, showToast, dismissToast } = useToast();

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <p className="text-gray-600">Perfis de collection do Qdrant usados pelo RAG.</p>
        <button
          type="button"
          onClick={() => setModalAberto(true)}
          className="rounded-md bg-gray-900 px-4 py-2 text-sm text-white"
        >
          Nova collection
        </button>
      </div>

      <div className="mt-6">
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
          showToast("Collection criada.", "success");
          onChanged();
        }}
      />

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}

export default function IngestaoDocumentosPage() {
  const [reloadKey, setReloadKey] = useState(0);
  const [collections, setCollections] = useState<RagCollection[]>([]);
  const { toasts, showToast, dismissToast } = useToast();

  const carregarColecoes = useCallback(async () => {
    try {
      setCollections(await listCollections());
    } catch (err) {
      showToast(
        err instanceof RagApiError ? err.message : "Erro inesperado ao carregar as collections.",
        "error",
      );
    }
  }, [showToast]);

  useEffect(() => {
    // `carregarColecoes` só chama `setCollections`/`showToast` depois do
    // `await` (assíncrono, não durante a execução síncrona do efeito) —
    // falso positivo conhecido de `react-hooks/set-state-in-effect` para o
    // padrão usual de "buscar dados ao montar".
    // eslint-disable-next-line react-hooks/set-state-in-effect
    carregarColecoes();
  }, [carregarColecoes]);

  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <h1 className="text-2xl font-semibold text-gray-900">Ingestão de documentos (RAG)</h1>
      <p className="mt-2 text-gray-600">Página interna, sem impacto na navegação pública do site.</p>

      <Tabs defaultValue="enviar" className="mt-8">
        <TabsList>
          <TabsTrigger value="enviar">Enviar documento</TabsTrigger>
          <TabsTrigger value="documentos">Documentos ingeridos</TabsTrigger>
          <TabsTrigger value="configuracao">Configuração</TabsTrigger>
          <TabsTrigger value="playground">Playground</TabsTrigger>
        </TabsList>
        <TabsContent value="enviar">
          <AbaEnviarDocumento collections={collections} onIngerido={() => setReloadKey((key) => key + 1)} />
        </TabsContent>
        <TabsContent value="documentos">
          <AbaDocumentosIngeridos key={reloadKey} collections={collections} />
        </TabsContent>
        <TabsContent value="configuracao">
          <AbaConfiguracao collections={collections} onChanged={carregarColecoes} />
        </TabsContent>
        <TabsContent value="playground">
          <PlaygroundPanel collections={collections} />
        </TabsContent>
      </Tabs>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
