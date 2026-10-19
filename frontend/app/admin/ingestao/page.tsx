"use client";

// MVP: página administrativa (fora da navegação pública, sem autenticação)
// para upload avulso de documento no RAG, gestão do registro de documentos
// ingeridos, configuração de perfis de collection e playground de busca
// comparativo — decisão registrada em `docs/ARCHITECTURE.md` §5 e
// `docs/FRONTEND.md` §8. Ver
// docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md e
// docs/superpowers/specs/2026-09-15-rag-collections-config-design.md.
import { useCallback, useEffect, useState } from "react";

import { AbaConfiguracao } from "./AbaConfiguracao";
import { AbaEnviarDocumento } from "./AbaEnviarDocumento";
import { IngestaoCabecalho } from "./IngestaoCabecalho";
import { useColecoesRag } from "./useColecoesRag";
import { CrawlerPanel } from "@/components/admin/CrawlerPanel";
import { CrawlerReviewQueue } from "@/components/admin/CrawlerReviewQueue";
import { DocumentsTable } from "@/components/admin/DocumentsTable";
import { PlaygroundPanel } from "@/components/admin/playground/PlaygroundPanel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { ToastStack, useToast } from "@/components/ui/Toast";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { RagApiError, listDocuments } from "@/lib/api/rag";
import type { DocumentRegistryEntry, RagCollection } from "@/lib/types/rag";

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
  const [reloadKey, setReloadKey] = useState(0);
  const { toasts, showToast, dismissToast } = useToast();
  const { collections, carregarColecoes } = useColecoesRag(showToast);

  return (
    <div className="mx-auto max-w-6xl px-4 py-4 sm:py-6 space-y-4">
      <IngestaoCabecalho collections={collections} />

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
