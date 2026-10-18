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
import { CollectionPurposeCard } from "./CollectionPurposeCard";
import { CollectionSelector } from "./CollectionSelector";
import { DocumentDropzone } from "./DocumentDropzone";
import { useCollectionActions } from "./useCollectionActions";
import { CrawlerPanel } from "@/components/admin/CrawlerPanel";
import { CrawlerReviewQueue } from "@/components/admin/CrawlerReviewQueue";
import { DocumentsTable } from "@/components/admin/DocumentsTable";
import { PlaygroundPanel } from "@/components/admin/playground/PlaygroundPanel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { ToastStack, useToast } from "@/components/ui/Toast";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import {
  RagApiError,
  listCollections,
  listDocuments,
  uploadDocument,
} from "@/lib/api/rag";
import { getRuntimeSettings, updateRuntimeSettings } from "@/lib/api/runtimeSettings";
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

function AbaEnviarDocumento({
  collections,
  onColecoesMudaram,
  onIngerido,
}: {
  collections: RagCollection[];
  onColecoesMudaram: () => Promise<RagCollection[]>;
  onIngerido: () => void;
}) {
  const token = useAuthStore((s) => s.token);
  const [file, setFile] = useState<File | null>(null);
  const [domain, setDomain] = useState<RagDomain>("vendas");
  const [collectionId, setCollectionId] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<DocumentIngestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const collectionAtiva = collections.find((collection) => collection.is_active);
  const collectionSelecionadaObj =
    collections.find((c) => c.id === collectionId) || collectionAtiva || collections[0];
  const collectionSelecionada = collections.some((collection) => collection.id === collectionId)
    ? collectionId
    : collectionAtiva?.id || collections[0]?.id || "";

  const {
    criandoCollection,
    modalCriarAberto,
    setModalCriarAberto,
    criarCollectionRapida,
    handleSelectCollectionChange,
  } = useCollectionActions({
    onColecoesMudaram,
    onCollectionIdChange: setCollectionId,
    onError: (msg) => setError(msg || null),
  });

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || isSubmitting || !token) return;
    setIsSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const response = await uploadDocument(token, {
        file,
        domain,
        collectionId: collectionSelecionada || undefined,
      });
      setResult(response);
      setFile(null);
      onIngerido();
    } catch (err) {
      setError(err instanceof RagApiError ? err.message : "Erro inesperado ao enviar o documento.");
    } finally {
      setIsSubmitting(false);
    }
  }

  const b2bCollections = collections.filter((c) => c.purpose === "mcp_b2b");
  const adminCollections = collections.filter((c) => c.purpose === "admin");
  const selectedPurpose = collectionSelecionadaObj?.purpose || "chat";

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

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Seletor de Domínio */}
          <div className="space-y-2">
            <label
              htmlFor="domain"
              className="block text-xs font-bold uppercase tracking-wider text-slate-700"
            >
              Domínio da Informação
            </label>
            <select
              id="domain"
              value={domain}
              onChange={(event) => setDomain(event.target.value as RagDomain)}
              className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm font-semibold text-slate-800 shadow-2xs focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            >
              {DOMAIN_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <CollectionSelector
            collections={collections}
            value={collectionSelecionada}
            disabled={criandoCollection}
            onChange={handleSelectCollectionChange}
            onOpenModal={() => setModalCriarAberto(true)}
          />
        </div>

        <CollectionPurposeCard
          purpose={selectedPurpose}
          b2bCount={b2bCollections.length}
          adminCount={adminCollections.length}
          criando={criandoCollection}
          onCriarRapida={criarCollectionRapida}
        />

        {/* Modal de Criação Customizada */}
        <CollectionFormModal
          open={modalCriarAberto}
          onOpenChange={setModalCriarAberto}
          onCreated={async (novaCol) => {
            setModalCriarAberto(false);
            await onColecoesMudaram();
            setCollectionId(novaCol.id);
          }}
        />

        <DocumentDropzone
          file={file}
          onFileChange={(f) => {
            setFile(f);
            if (f) setError(null);
          }}
          onError={setError}
        />

        {/* Botão de Envio */}
        <div className="pt-2">
          <button
            type="submit"
            disabled={!file || isSubmitting}
            className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white shadow-md hover:bg-blue-700 transition-all disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          >
            {isSubmitting ? (
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
      </form>

      {/* Alertas de Resultado / Erro */}
      <IngestaoAlertas result={result} error={error} />
    </div>
  );
}

function AbaDocumentosIngeridos({ collections }: { collections: RagCollection[] }) {
  const token = useAuthStore((s) => s.token);
  const [documentos, setDocumentos] = useState<DocumentRegistryEntry[] | null>(null);
  const { toasts, showToast, dismissToast } = useToast();

  const carregarDocumentos = useCallback(async () => {
    if (!token) return;
    try {
      setDocumentos(await listDocuments(token));
    } catch (err) {
      showToast(
        err instanceof RagApiError ? err.message : "Erro inesperado ao carregar os documentos.",
        "error",
      );
      setDocumentos([]);
    }
  }, [showToast, token]);

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
    <div className="rounded-2xl border border-slate-200/90 bg-white p-6 sm:p-8 shadow-xs space-y-4">
      {documentos === null ? (
        <p className="text-sm text-slate-600">Carregando...</p>
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

function RagSearchConfigSection({
  onError,
  onSuccess,
}: {
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}) {
  const token = useAuthStore((s) => s.token);
  const [ragFallback, setRagFallback] = useState(false);
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    if (!token) return;
    let cancelado = false;
    async function carregar() {
      try {
        const atual = await getRuntimeSettings(token!);
        if (!cancelado) setRagFallback(atual.rag_search_domain_fallback);
      } catch (err) {
        if (!cancelado) {
          onError(err instanceof Error ? err.message : "Erro ao carregar configurações de busca.");
        }
      } finally {
        if (!cancelado) setCarregando(false);
      }
    }
    carregar();
    return () => {
      cancelado = true;
    };
    // Roda só uma vez ao montar — incluir `onError` (recriada a cada render
    // do pai) reexecutaria a busca a cada render, não só no mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function handleToggle(checked: boolean) {
    if (!token) return;
    setSalvando(true);
    setRagFallback(checked);
    try {
      await updateRuntimeSettings(token, { rag_search_domain_fallback: checked });
      onSuccess("Regra de busca do RAG atualizada.");
    } catch (err) {
      setRagFallback(!checked);
      onError(err instanceof Error ? err.message : "Erro ao atualizar regra de busca.");
    } finally {
      setSalvando(false);
    }
  }

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

function AbaConfiguracao({
  collections,
  onChanged,
}: {
  collections: RagCollection[];
  onChanged: () => void;
}) {
  const [modalAberto, setModalAberto] = useState(false);
  const { toasts, showToast, dismissToast } = useToast();

  const ativaChat = collections.find((c) => c.is_active && (c.purpose || "chat") === "chat");
  const ativaB2B = collections.find((c) => c.is_active && c.purpose === "mcp_b2b");
  const ativaAdmin = collections.find((c) => c.is_active && c.purpose === "admin");

  return (
    <div className="space-y-6">
      {/* Master Card Unificando as Configurações de Busca e Coleções RAG */}
      <div className="rounded-2xl border border-slate-200/90 bg-white p-5 sm:p-6 shadow-xs space-y-6">
        {/* 1. Regras de Busca */}
        <RagSearchConfigSection
          onError={(msg) => showToast(msg, "error")}
          onSuccess={(msg) => showToast(msg, "success")}
        />

        {/* 2. Collections Ativas por Finalidade */}
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
            {/* Card Chat */}
            <div className="rounded-xl border border-blue-200/80 bg-blue-50/40 p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-blue-800 flex items-center gap-1.5">
                  <span>💬</span> Chat Público
                </span>
                {ativaChat ? (
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
                {ativaChat ? (
                  <span>Coleção ativa: {ativaChat.name}</span>
                ) : (
                  <span className="text-slate-400 font-normal italic">Nenhuma ativa</span>
                )}
              </div>
              <p className="text-[11px] text-slate-600 leading-tight">
                Consultada pelo assistente nas conversas do chat público com clientes.
              </p>
            </div>

            {/* Card MCP B2B */}
            <div className="rounded-xl border border-purple-200/80 bg-purple-50/40 p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-purple-800 flex items-center gap-1.5">
                  <span>🏢</span> MCP B2B Restrito
                </span>
                {ativaB2B ? (
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
                {ativaB2B ? (
                  <span>Coleção ativa: {ativaB2B.name}</span>
                ) : (
                  <span className="text-slate-400 font-normal italic">Nenhuma ativa</span>
                )}
              </div>
              <p className="text-[11px] text-slate-600 leading-tight">
                Consultada pelos revendedores parceiros no canal de integração MCP B2B.
              </p>
            </div>

            {/* Card Admin */}
            <div className="rounded-xl border border-rose-200/80 bg-rose-50/40 p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-rose-800 flex items-center gap-1.5">
                  <span>🛡️</span> Admin Exclusivo
                </span>
                {ativaAdmin ? (
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
                {ativaAdmin ? (
                  <span>Coleção ativa: {ativaAdmin.name}</span>
                ) : (
                  <span className="text-slate-400 font-normal italic">Nenhuma ativa</span>
                )}
              </div>
              <p className="text-[11px] text-slate-600 leading-tight">
                Consultada pelo administrador no modo seguro do chat do painel.
              </p>
            </div>
          </div>
        </div>

        {/* 3. Perfis de Coleções Qdrant */}
        <div className="border-t border-slate-100 pt-6 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-slate-900">Perfis de Coleções Qdrant</h2>
              <p className="text-xs text-slate-600">
                Perfis de collection do Qdrant usados pelo RAG.
              </p>
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
      </div>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}

function AbaCrawler() {
  const [reloadKey, setReloadKey] = useState(0);
  return (
    <div className="space-y-6">
      <CrawlerPanel onFinished={() => setReloadKey((key) => key + 1)} />
      <CrawlerReviewQueue reloadKey={reloadKey} />
    </div>
  );
}

export default function IngestaoDocumentosPage() {
  const token = useAuthStore((s) => s.token);
  const [reloadKey, setReloadKey] = useState(0);
  const [collections, setCollections] = useState<RagCollection[]>([]);
  const { toasts, showToast, dismissToast } = useToast();

  const carregarColecoes = useCallback(async (): Promise<RagCollection[]> => {
    if (!token) return [];
    try {
      const novalista = await listCollections(token);
      setCollections(novalista);
      return novalista;
    } catch (err) {
      showToast(
        err instanceof RagApiError ? err.message : "Erro inesperado ao carregar as collections.",
        "error",
      );
      return [];
    }
  }, [showToast, token]);

  useEffect(() => {
    // Falso positivo: `carregarColecoes` so toca estado depois de
    // `await listCollections` (funcao `async` importada), logo nao ha setState
    // sincrono aqui. A regra nao resolve a assincronia da chamada e assume o
    // pior caso.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void carregarColecoes();
  }, [carregarColecoes]);

  const ativaChat = collections.find((c) => c.is_active && (c.purpose || "chat") === "chat");
  const ativaB2B = collections.find((c) => c.is_active && c.purpose === "mcp_b2b");
  const ativaAdmin = collections.find((c) => c.is_active && c.purpose === "admin");

  return (
    <div className="mx-auto max-w-6xl px-4 py-4 sm:py-6 space-y-4">
      {/* Cabeçalho Visual da Página */}
      <div className="rounded-2xl border border-slate-200/90 bg-white p-5 sm:p-6 shadow-xs space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-2xl sm:text-3xl">📄</span>
              <h1 className="text-xl font-bold tracking-tight text-slate-900 sm:text-2xl">
                Ingestão de Documentos &amp; Coleções RAG
              </h1>
            </div>
            <p className="mt-1 text-xs sm:text-sm text-slate-600 max-w-2xl">
              Gestão de documentos indexados, perfis de coleção no Qdrant, varredura web com crawler
              e playground comparativo de busca semântica.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700 border border-blue-100">
              <span>🗂️</span> {collections.length}{" "}
              {collections.length === 1 ? "Collection" : "Collections"}
            </span>
            {ativaChat && (
              <span
                className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700 border border-emerald-100"
                title="Collection ativa para Chat Público"
              >
                ★ Chat: {ativaChat.name}
              </span>
            )}
            {ativaB2B && (
              <span
                className="inline-flex items-center gap-1.5 rounded-full bg-purple-50 px-3 py-1.5 text-xs font-semibold text-purple-700 border border-purple-100"
                title="Collection ativa para MCP B2B"
              >
                ★ MCP B2B: {ativaB2B.name}
              </span>
            )}
            {ativaAdmin && (
              <span
                className="inline-flex items-center gap-1.5 rounded-full bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-700 border border-rose-100"
                title="Collection ativa para Admin"
              >
                ★ Admin: {ativaAdmin.name}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Barra de Navegação em Tabs Estilizada */}
      <Tabs defaultValue="enviar" className="space-y-1.5">
        <TabsList className="p-1 bg-slate-100/90 rounded-2xl border border-slate-200/80 flex flex-wrap gap-1">
          <TabsTrigger value="enviar" aria-label="Enviar documento">
            <span aria-hidden="true">📥</span> Enviar documento
          </TabsTrigger>
          <TabsTrigger value="documentos" aria-label="Documentos ingeridos">
            <span aria-hidden="true">📚</span> Documentos ingeridos
          </TabsTrigger>
          <TabsTrigger value="configuracao" aria-label="Configuração">
            <span aria-hidden="true">⚙️</span> Configuração
          </TabsTrigger>
          <TabsTrigger value="playground" aria-label="Playground">
            <span aria-hidden="true">🧪</span> Playground
          </TabsTrigger>
          <TabsTrigger value="crawler" aria-label="Crawler">
            <span aria-hidden="true">🌐</span> Crawler
          </TabsTrigger>
        </TabsList>

        <div className="max-h-[calc(85vh-120px)] min-h-[440px] overflow-y-auto pr-1">
          <TabsContent value="enviar" className="pt-0">
            <AbaEnviarDocumento
              collections={collections}
              onColecoesMudaram={carregarColecoes}
              onIngerido={() => setReloadKey((key) => key + 1)}
            />
          </TabsContent>
          <TabsContent value="documentos" className="pt-0">
            <AbaDocumentosIngeridos key={reloadKey} collections={collections} />
          </TabsContent>
          <TabsContent value="configuracao" className="pt-0">
            <AbaConfiguracao collections={collections} onChanged={carregarColecoes} />
          </TabsContent>
          <TabsContent value="playground" className="pt-0">
            <PlaygroundPanel collections={collections} />
          </TabsContent>
          <TabsContent value="crawler" className="pt-0">
            <AbaCrawler />
          </TabsContent>
        </div>
      </Tabs>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
