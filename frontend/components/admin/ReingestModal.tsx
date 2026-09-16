"use client";

import { useState } from "react";

import { Modal } from "@/components/ui/Modal";
import { RagApiError, reingestDocument } from "@/lib/api/rag";
import type { DocumentRegistryEntry, RagCollection } from "@/lib/types/rag";

export interface ReingestModalProps {
  documento: DocumentRegistryEntry | null;
  collections: RagCollection[];
  onOpenChange: (open: boolean) => void;
  onReingested: () => void;
  onError: (message: string) => void;
}

export function ReingestModal({ documento, collections, onOpenChange, onReingested, onError }: ReingestModalProps) {
  const destinos = collections.filter((collection) => collection.id !== documento?.collection_id);
  // Este componente fica permanentemente montado dentro de DocumentsTable (visibilidade
  // controlada pela prop `documento`/`open`, não por mount/unmount) — o inicializador do
  // useState só roda uma vez, antes de `documento` existir, então `targetId` pode ficar
  // "preso" em um valor que não é mais um destino válido (inclusive a própria collection de
  // origem do documento atual). Por isso o valor efetivamente usado é derivado a cada render,
  // caindo em destinos[0] sempre que o `targetId` guardado não é (mais) um destino válido —
  // ver finding #2 da revisão final.
  const [targetId, setTargetId] = useState(destinos[0]?.id ?? "");
  const targetIdEfetivo = destinos.some((c) => c.id === targetId) ? targetId : (destinos[0]?.id ?? "");
  const [enviando, setEnviando] = useState(false);

  async function confirmar() {
    if (!documento || !targetIdEfetivo) return;
    setEnviando(true);
    try {
      await reingestDocument(documento.id, targetIdEfetivo);
      onReingested();
    } catch (err) {
      onError(err instanceof RagApiError ? err.message : "Erro inesperado ao reingerir o documento.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal
      open={documento !== null}
      onOpenChange={onOpenChange}
      title="Reingerir em outra collection"
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
            disabled={enviando || destinos.length === 0}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            {enviando ? "Reingerindo..." : "Reingerir"}
          </button>
        </>
      }
    >
      {destinos.length === 0 ? (
        <p className="text-sm text-gray-600">Não há outra collection para reingerir este documento.</p>
      ) : (
        <label className="block text-sm text-gray-700">
          Collection destino
          <select
            value={targetIdEfetivo}
            onChange={(e) => setTargetId(e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
          >
            {destinos.map((collection) => (
              <option key={collection.id} value={collection.id}>
                {collection.name}
              </option>
            ))}
          </select>
        </label>
      )}
    </Modal>
  );
}
