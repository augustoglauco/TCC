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
  disabled: boolean;
}

/** Collection destino do crawl. O domínio de cada página é decidido na fila de revisão. */
export function CrawlerDestino({
  collections,
  onColecoesMudaram,
  collectionId,
  onCollectionIdChange,
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
    </div>
  );
}
