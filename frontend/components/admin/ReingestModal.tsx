"use client";

import { useState } from "react";

import { DOMAIN_OPTIONS } from "@/components/admin/DocumentsFilterBar";
import { Modal } from "@/components/ui/Modal";
import { RagApiError, reingestDocument } from "@/lib/api/rag";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import type { DocumentRegistryEntry, RagCollection, RagDomain } from "@/lib/types/rag";

export interface ReingestModalProps {
  documento: DocumentRegistryEntry | null;
  collections: RagCollection[];
  onOpenChange: (open: boolean) => void;
  onReingested: () => void;
  onError: (message: string) => void;
}

export function ReingestModal({
  documento,
  collections,
  onOpenChange,
  onReingested,
  onError,
}: ReingestModalProps) {
  const token = useAuthStore((s) => s.token);
  // A própria collection de origem também é destino válido: com outro domínio, vira um
  // segundo documento na mesma collection. Por padrão aparece selecionada a primeira
  // collection diferente da de origem (o caso comum), se houver.
  const destinos = collections;
  const padrao = collections.find((c) => c.id !== documento?.collection_id) ?? collections[0];
  // Este componente fica permanentemente montado dentro de DocumentsTable (visibilidade
  // controlada pela prop `documento`/`open`, não por mount/unmount) — o inicializador do
  // useState só roda uma vez, antes de `documento` existir. Por isso os valores usados são
  // derivados a cada render: o `targetId` guardado só vale se ainda for uma collection
  // existente, e o domínio escolhido só vale para o documento em que foi escolhido (finding
  // #2 da revisão final).
  const [targetId, setTargetId] = useState("");
  const targetIdEfetivo = destinos.some((c) => c.id === targetId) ? targetId : (padrao?.id ?? "");
  const [escolhaDominio, setEscolhaDominio] = useState<{ docId: string; dominio: RagDomain }>();
  const dominioEfetivo: RagDomain =
    escolhaDominio && escolhaDominio.docId === documento?.id
      ? escolhaDominio.dominio
      : (documento?.domain ?? "vendas");
  const semMudanca =
    targetIdEfetivo === documento?.collection_id && dominioEfetivo === documento?.domain;
  const [enviando, setEnviando] = useState(false);

  async function confirmar() {
    if (!documento || !targetIdEfetivo || !token) return;
    setEnviando(true);
    try {
      await reingestDocument(token, documento.id, targetIdEfetivo, dominioEfetivo);
      onReingested();
    } catch (err) {
      onError(
        err instanceof RagApiError ? err.message : "Erro inesperado ao reingerir o documento.",
      );
    } finally {
      setEnviando(false);
    }
  }

  const chatDestinos = destinos.filter((c) => (c.purpose || "chat") === "chat");
  const b2bDestinos = destinos.filter((c) => c.purpose === "mcp_b2b");
  const adminDestinos = destinos.filter((c) => c.purpose === "admin");

  return (
    <Modal
      open={documento !== null}
      onOpenChange={onOpenChange}
      title="Reingerir (collection e/ou domínio)"
      footer={
        <>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="rounded-md px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={confirmar}
            disabled={enviando || destinos.length === 0 || semMudanca}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            {enviando ? "Reingerindo..." : "Reingerir"}
          </button>
        </>
      }
    >
      {destinos.length === 0 ? (
        <p className="text-sm text-gray-600">Não há collection para reingerir este documento.</p>
      ) : (
        <div className="space-y-4">
          <label className="block text-sm text-gray-700">
            Collection destino
            <select
              value={targetIdEfetivo}
              onChange={(e) => setTargetId(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
            >
              {chatDestinos.length > 0 && (
                <optgroup label="💬 Chat Público (purpose: chat)">
                  {chatDestinos.map((collection) => (
                    <option key={collection.id} value={collection.id}>
                      {collection.name} {collection.is_active ? " (ativa)" : ""}
                    </option>
                  ))}
                </optgroup>
              )}
              {b2bDestinos.length > 0 && (
                <optgroup label="🏢 MCP B2B Restrito (purpose: mcp_b2b)">
                  {b2bDestinos.map((collection) => (
                    <option key={collection.id} value={collection.id}>
                      {collection.name} [MCP B2B]
                    </option>
                  ))}
                </optgroup>
              )}
              {adminDestinos.length > 0 && (
                <optgroup label="🛡️ Admin Exclusivo (purpose: admin)">
                  {adminDestinos.map((collection) => (
                    <option key={collection.id} value={collection.id}>
                      {collection.name} [Admin]
                    </option>
                  ))}
                </optgroup>
              )}
            </select>
          </label>
          <label className="block text-sm text-gray-700">
            Domínio
            <select
              value={dominioEfetivo}
              onChange={(e) =>
                documento &&
                setEscolhaDominio({ docId: documento.id, dominio: e.target.value as RagDomain })
              }
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
            >
              {DOMAIN_OPTIONS.map((opcao) => (
                <option key={opcao.value} value={opcao.value}>
                  {opcao.label}
                </option>
              ))}
            </select>
          </label>
          <p className="text-xs text-gray-500">Cria um documento novo; o original é mantido.</p>
        </div>
      )}
    </Modal>
  );
}
