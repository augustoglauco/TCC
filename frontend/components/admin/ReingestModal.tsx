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
  const [targetId, setTargetId] = useState(destinos[0]?.id ?? "");
  const [enviando, setEnviando] = useState(false);

  async function confirmar() {
    if (!documento || !targetId) return;
    setEnviando(true);
    try {
      await reingestDocument(documento.id, targetId);
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
            value={targetId}
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
