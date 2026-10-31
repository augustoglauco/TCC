"use client";

import { CollectionFormModal } from "@/components/admin/CollectionFormModal";
import { CollectionPurposeCard } from "@/app/admin/ingestao/CollectionPurposeCard";
import { CollectionSelector } from "@/app/admin/ingestao/CollectionSelector";
import { useCollectionActions } from "@/app/admin/ingestao/useCollectionActions";
import type { RagCollection } from "@/lib/types/rag";

interface Props {
  collections: RagCollection[];
  onColecoesMudaram: () => Promise<RagCollection[]>;
  collectionId: string;
  onCollectionIdChange: (id: string) => void;
  review: boolean;
  onReviewChange: (review: boolean) => void;
  disabled: boolean;
}

/** Collection destino do crawl e modo de revisão (o LLM sugere o domínio; o admin decide). */
export function CrawlerDestino({
  collections,
  onColecoesMudaram,
  collectionId,
  onCollectionIdChange,
  review,
  onReviewChange,
  disabled,
}: Props) {
  const acoes = useCollectionActions({
    onColecoesMudaram,
    onCollectionIdChange,
    onError: () => {},
  });
  const purpose = collections.find((c) => c.id === collectionId)?.purpose || "chat";

  return (
    <div className="space-y-4">
      <CollectionSelector
        collections={collections}
        value={collectionId}
        disabled={disabled || acoes.criandoCollection}
        onChange={acoes.handleSelectCollectionChange}
        onOpenModal={() => acoes.setModalCriarAberto(true)}
      />
      <CollectionPurposeCard
        purpose={purpose}
        b2bCount={collections.filter((c) => c.purpose === "mcp_b2b").length}
        adminCount={collections.filter((c) => c.purpose === "admin").length}
        criando={acoes.criandoCollection}
        onCriarRapida={acoes.criarCollectionRapida}
      />
      <CollectionFormModal
        open={acoes.modalCriarAberto}
        onOpenChange={acoes.setModalCriarAberto}
        onCreated={async (novaCol) => {
          acoes.setModalCriarAberto(false);
          await onColecoesMudaram();
          onCollectionIdChange(novaCol.id);
        }}
      />
      <label className="flex items-start gap-2 text-sm text-gray-900">
        <input
          type="checkbox"
          checked={review}
          disabled={disabled}
          onChange={(event) => onReviewChange(event.target.checked)}
          className="mt-1"
        />
        <span>
          <strong>Revisar antes de ingerir</strong> — o LLM sugere o domínio de cada página e você
          confirma ou altera na fila. Desmarcado, as páginas com confiança acima do limiar entram
          direto com o domínio sugerido.
        </span>
      </label>
    </div>
  );
}
