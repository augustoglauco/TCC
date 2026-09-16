import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ReingestModal } from "@/components/admin/ReingestModal";
import type { DocumentRegistryEntry, RagCollection } from "@/lib/types/rag";

vi.mock("@/lib/api/rag", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/rag")>("@/lib/api/rag");
  return { ...actual, reingestDocument: vi.fn() };
});

import { RagApiError, reingestDocument } from "@/lib/api/rag";

const mockedReingest = vi.mocked(reingestDocument);

const COLLECTION_ORIGEM: RagCollection = {
  id: "origem",
  name: "origem",
  embedding_model: "modelo",
  vector_dimension: 384,
  distance_metric: "cosine",
  chunk_size: 800,
  chunk_overlap: 100,
  hnsw_m: 16,
  hnsw_ef_construct: 100,
  hnsw_full_scan_threshold: 10000,
  hnsw_max_indexing_threads: 0,
  hnsw_on_disk: false,
  hnsw_payload_m: null,
  quantization_type: "none",
  quantization_config: {},
  payload_indexes: [],
  is_active: true,
  document_count: 1,
  created_at: new Date().toISOString(),
};

const COLLECTION_DESTINO: RagCollection = { ...COLLECTION_ORIGEM, id: "destino", name: "destino", is_active: false };

const DOCUMENTO: DocumentRegistryEntry = {
  id: "doc-1",
  filename: "catalogo.txt",
  domain: "vendas",
  chunk_count: 1,
  collection_id: "origem",
  collection_name: "origem",
  origin: "upload",
  created_at: new Date().toISOString(),
};

describe("ReingestModal", () => {
  beforeEach(() => {
    mockedReingest.mockReset();
  });

  it("não mostra a collection de origem entre os destinos", () => {
    render(
      <ReingestModal
        documento={DOCUMENTO}
        collections={[COLLECTION_ORIGEM, COLLECTION_DESTINO]}
        onOpenChange={vi.fn()}
        onReingested={vi.fn()}
        onError={vi.fn()}
      />,
    );

    expect(screen.queryByRole("option", { name: "origem" })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "destino" })).toBeInTheDocument();
  });

  it("confirmar chama a API com o documento e a collection destino selecionada", async () => {
    const user = userEvent.setup();
    mockedReingest.mockResolvedValueOnce({ ...DOCUMENTO, id: "doc-2", collection_id: "destino" });
    const onReingested = vi.fn();

    render(
      <ReingestModal
        documento={DOCUMENTO}
        collections={[COLLECTION_ORIGEM, COLLECTION_DESTINO]}
        onOpenChange={vi.fn()}
        onReingested={onReingested}
        onError={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Reingerir" }));

    expect(mockedReingest).toHaveBeenCalledWith("doc-1", "destino");
    expect(onReingested).toHaveBeenCalled();
  });

  it("exibe erro da API quando a reingestão falha", async () => {
    const user = userEvent.setup();
    mockedReingest.mockRejectedValueOnce(new RagApiError("Documento sem arquivo salvo."));
    const onError = vi.fn();

    render(
      <ReingestModal
        documento={DOCUMENTO}
        collections={[COLLECTION_ORIGEM, COLLECTION_DESTINO]}
        onOpenChange={vi.fn()}
        onReingested={vi.fn()}
        onError={onError}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Reingerir" }));

    expect(onError).toHaveBeenCalledWith("Documento sem arquivo salvo.");
  });

  it("componente permanentemente montado com documento inicial nulo nunca oferece a própria collection de origem como destino (regressão do finding #2)", async () => {
    // ReingestModal fica sempre montado dentro de DocumentsTable — o `documento` começa
    // como null e só é preenchido depois, via re-render (não via um novo mount). O
    // useState de targetId, inicializado nesse primeiro render (documento=null, então
    // `destinos` inclui todas as collections, inclusive a que depois será a de origem),
    // não deve "vazar" para o valor de destino depois que um documento real é setado.
    const user = userEvent.setup();
    mockedReingest.mockResolvedValueOnce({ ...DOCUMENTO, id: "doc-2", collection_id: "destino" });

    const { rerender } = render(
      <ReingestModal
        documento={null}
        collections={[COLLECTION_ORIGEM, COLLECTION_DESTINO]}
        onOpenChange={vi.fn()}
        onReingested={vi.fn()}
        onError={vi.fn()}
      />,
    );

    rerender(
      <ReingestModal
        documento={DOCUMENTO}
        collections={[COLLECTION_ORIGEM, COLLECTION_DESTINO]}
        onOpenChange={vi.fn()}
        onReingested={vi.fn()}
        onError={vi.fn()}
      />,
    );

    const select = screen.getByRole("combobox") as HTMLSelectElement;
    expect(select.value).not.toBe(DOCUMENTO.collection_id);
    expect(select.value).toBe("destino");

    await user.click(screen.getByRole("button", { name: "Reingerir" }));

    expect(mockedReingest).toHaveBeenCalledWith("doc-1", "destino");
    expect(mockedReingest).not.toHaveBeenCalledWith("doc-1", DOCUMENTO.collection_id);
  });

  it("sem outra collection disponível, mostra aviso e desabilita o botão", () => {
    render(
      <ReingestModal
        documento={DOCUMENTO}
        collections={[COLLECTION_ORIGEM]}
        onOpenChange={vi.fn()}
        onReingested={vi.fn()}
        onError={vi.fn()}
      />,
    );

    expect(screen.getByText(/não há outra collection/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reingerir" })).toBeDisabled();
  });
});
