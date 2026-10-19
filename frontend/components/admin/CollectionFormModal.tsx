"use client";

import { Modal } from "@/components/ui/Modal";
import { useCollectionForm } from "@/lib/hooks/useCollectionForm";
import type { RagCollection } from "@/lib/types/rag";
import {
  CollectionDistanceField,
  CollectionNameField,
  CollectionPurposeField,
} from "./CollectionBasicFields";
import { CollectionChunkingSection } from "./CollectionChunkingSection";
import { CollectionEmbeddingSection } from "./CollectionEmbeddingSection";
import { CollectionHnswSection } from "./CollectionHnswSection";
import { CollectionPayloadIndexesSection } from "./CollectionPayloadIndexesSection";
import { CollectionQuantizationSection } from "./CollectionQuantizationSection";

export interface CollectionFormModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (collection: RagCollection) => void;
}

export function CollectionFormModal({ open, onOpenChange, onCreated }: CollectionFormModalProps) {
  const f = useCollectionForm(onCreated);
  const v = f.valores;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (await f.enviar()) onOpenChange(false);
  }

  return (
    <Modal
      open={open}
      onOpenChange={(novoOpen) => {
        if (!novoOpen) f.resetar();
        onOpenChange(novoOpen);
      }}
      title="Nova collection"
      size="3xl"
    >
      <form onSubmit={handleSubmit} className="max-h-[70vh] space-y-6 overflow-y-auto pr-2">
        <CollectionNameField name={v.name} onName={(x) => f.set("name", x)} />
        <CollectionPurposeField
          purpose={v.purpose}
          ativarAposCriar={v.ativarAposCriar}
          onPurpose={(x) => f.set("purpose", x)}
          onAtivarAposCriar={(x) => f.set("ativarAposCriar", x)}
        />

        <CollectionEmbeddingSection
          modelSelecionado={v.modelSelecionado}
          modeloCustom={v.modeloCustom}
          onModelSelecionado={(x) => f.set("modelSelecionado", x)}
          onModeloCustom={(x) => f.set("modeloCustom", x)}
        />

        <CollectionDistanceField
          value={v.distanceMetric}
          onChange={(x) => f.set("distanceMetric", x)}
        />

        <CollectionChunkingSection
          chunkSize={v.chunkSize}
          chunkOverlap={v.chunkOverlap}
          onChunkSize={(x) => f.set("chunkSize", x)}
          onChunkOverlap={(x) => f.set("chunkOverlap", x)}
        />

        <CollectionHnswSection
          m={v.hnswM}
          efConstruct={v.hnswEfConstruct}
          fullScanThreshold={v.hnswFullScanThreshold}
          maxIndexingThreads={v.hnswMaxIndexingThreads}
          payloadM={v.hnswPayloadM}
          onDisk={v.hnswOnDisk}
          onM={(x) => f.set("hnswM", x)}
          onEfConstruct={(x) => f.set("hnswEfConstruct", x)}
          onFullScanThreshold={(x) => f.set("hnswFullScanThreshold", x)}
          onMaxIndexingThreads={(x) => f.set("hnswMaxIndexingThreads", x)}
          onPayloadM={(x) => f.set("hnswPayloadM", x)}
          onOnDisk={(x) => f.set("hnswOnDisk", x)}
        />

        <CollectionQuantizationSection
          quantizationType={v.quantizationType}
          scalarQuantile={v.scalarQuantile}
          scalarAlwaysRam={v.scalarAlwaysRam}
          productCompression={v.productCompression}
          productAlwaysRam={v.productAlwaysRam}
          binaryAlwaysRam={v.binaryAlwaysRam}
          onType={(x) => f.set("quantizationType", x)}
          onScalarQuantile={(x) => f.set("scalarQuantile", x)}
          onScalarAlwaysRam={(x) => f.set("scalarAlwaysRam", x)}
          onProductCompression={(x) => f.set("productCompression", x)}
          onProductAlwaysRam={(x) => f.set("productAlwaysRam", x)}
          onBinaryAlwaysRam={(x) => f.set("binaryAlwaysRam", x)}
        />

        <CollectionPayloadIndexesSection
          indexes={v.payloadIndexes}
          onUpdate={f.atualizarPayloadIndex}
          onRemove={f.removerPayloadIndex}
          onAdd={f.adicionarPayloadIndex}
        />

        {f.error && <p className="rounded-md bg-red-50 px-4 py-3 text-red-800">{f.error}</p>}

        <div className="flex justify-end gap-3 border-t border-gray-200 pt-4">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="rounded-md px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={f.isSubmitting || f.chunkingInvalido || !v.name || !f.embeddingModel}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            {f.isSubmitting ? "Criando..." : "Criar collection"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
