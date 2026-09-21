import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import IngestaoDocumentosPage from "@/app/admin/ingestao/page";
import { RagApiError } from "@/lib/api/rag";
import type { DocumentRegistryEntry, RagCollection } from "@/lib/types/rag";

vi.mock("@/lib/api/rag", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/rag")>("@/lib/api/rag");
  return {
    ...actual,
    uploadDocument: vi.fn(),
    listDocuments: vi.fn(),
    listCollections: vi.fn(),
    deleteCollection: vi.fn(),
  };
});

import { deleteCollection, listCollections, listDocuments, uploadDocument } from "@/lib/api/rag";

const mockedUploadDocument = vi.mocked(uploadDocument);
const mockedListDocuments = vi.mocked(listDocuments);
const mockedListCollections = vi.mocked(listCollections);
const mockedDeleteCollection = vi.mocked(deleteCollection);

const COLLECTION_ATIVA: RagCollection = {
  id: "col-1",
  name: "docs_texto",
  embedding_model: "paraphrase-multilingual-MiniLM-L12-v2",
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
  purpose: "chat",
  document_count: 0,
  created_at: new Date().toISOString(),
};

const DOCUMENTO: DocumentRegistryEntry = {
  id: "11111111-1111-1111-1111-111111111111",
  filename: "catalogo.txt",
  domain: "vendas",
  chunk_count: 3,
  collection_id: "col-1",
  collection_name: "docs_texto",
  origin: "upload",
  created_at: new Date().toISOString(),
};

const COLLECTION_TEMPORARIA: RagCollection = {
  ...COLLECTION_ATIVA,
  id: "col-2",
  name: "temporaria",
  is_active: false,
  document_count: 0,
};

describe("IngestaoDocumentosPage", () => {
  beforeEach(() => {
    mockedUploadDocument.mockReset();
    mockedListDocuments.mockReset();
    mockedListCollections.mockReset();
    mockedDeleteCollection.mockReset();
    mockedListDocuments.mockResolvedValue([]);
    mockedListCollections.mockResolvedValue([COLLECTION_ATIVA]);
  });

  it("envia o arquivo selecionado (com a collection ativa) e exibe o resultado da ingestão", async () => {
    const user = userEvent.setup();
    mockedUploadDocument.mockResolvedValueOnce({ filename: "catalogo.txt", domain: "vendas", chunks: 3 });

    render(<IngestaoDocumentosPage />);

    const file = new File(["conteudo"], "catalogo.txt", { type: "text/plain" });
    await user.upload(await screen.findByLabelText("Arquivo"), file);
    await user.click(screen.getByRole("button", { name: "Enviar para ingestão" }));

    expect(await screen.findByText(/3 chunk\(s\) gravado\(s\)/)).toBeInTheDocument();
    expect(mockedUploadDocument).toHaveBeenCalledWith({ file, domain: "vendas", collectionId: "col-1" });
  });

  it("exibe mensagem de erro quando o upload falha", async () => {
    const user = userEvent.setup();
    mockedUploadDocument.mockRejectedValueOnce(
      new RagApiError("Serviço de RAG temporariamente indisponível. Tente novamente.", 503),
    );

    render(<IngestaoDocumentosPage />);

    const file = new File(["conteudo"], "catalogo.txt", { type: "text/plain" });
    await user.upload(await screen.findByLabelText("Arquivo"), file);
    await user.click(screen.getByRole("button", { name: "Enviar para ingestão" }));

    expect(await screen.findByText(/temporariamente indisponível/)).toBeInTheDocument();
  });

  it("desabilita o envio enquanto nenhum arquivo foi selecionado", async () => {
    render(<IngestaoDocumentosPage />);

    expect(await screen.findByRole("button", { name: "Enviar para ingestão" })).toBeDisabled();
  });

  it("aba 'Documentos ingeridos' lista os documentos ao ser aberta", async () => {
    const user = userEvent.setup();
    mockedListDocuments.mockResolvedValue([DOCUMENTO]);

    render(<IngestaoDocumentosPage />);
    await user.click(screen.getByRole("tab", { name: "Documentos ingeridos" }));

    expect(await screen.findByText("catalogo.txt")).toBeInTheDocument();
  });

  it("aba 'Configuração' não fica mais desabilitada e lista as collections", async () => {
    const user = userEvent.setup();

    render(<IngestaoDocumentosPage />);
    const abaConfiguracao = await screen.findByRole("tab", { name: "Configuração" });
    expect(abaConfiguracao).not.toBeDisabled();

    await user.click(abaConfiguracao);

    expect(await screen.findByText("docs_texto")).toBeInTheDocument();
  });

  it("aba 'Playground' existe", async () => {
    render(<IngestaoDocumentosPage />);

    expect(await screen.findByRole("tab", { name: "Playground" })).toBeInTheDocument();
  });

  it("reseleciona a collection do formulário de envio quando a collection escolhida é apagada em outra aba", async () => {
    const user = userEvent.setup();
    mockedListCollections
      .mockResolvedValueOnce([COLLECTION_ATIVA, COLLECTION_TEMPORARIA])
      .mockResolvedValueOnce([COLLECTION_ATIVA]);
    mockedDeleteCollection.mockResolvedValueOnce(undefined);
    mockedUploadDocument.mockResolvedValueOnce({ filename: "catalogo.txt", domain: "vendas", chunks: 1 });

    render(<IngestaoDocumentosPage />);

    const selectCollection = await screen.findByLabelText("Collection destino");
    await user.selectOptions(selectCollection, "col-2");
    expect(selectCollection).toHaveValue("col-2");

    await user.click(screen.getByRole("tab", { name: "Configuração" }));
    const botoesExcluir = await screen.findAllByRole("button", { name: "Excluir" });
    const botaoExcluirHabilitado = botoesExcluir.find((button) => !button.hasAttribute("disabled"));
    expect(botaoExcluirHabilitado).toBeDefined();
    await user.click(botaoExcluirHabilitado!);
    await user.click(screen.getByRole("button", { name: "Confirmar exclusão" }));

    expect(mockedDeleteCollection).toHaveBeenCalledWith("col-2");

    await user.click(screen.getByRole("tab", { name: "Enviar documento" }));
    const selectAposExclusao = await screen.findByLabelText("Collection destino");
    await waitFor(() => expect(selectAposExclusao).toHaveValue("col-1"));

    const file = new File(["conteudo"], "catalogo.txt", { type: "text/plain" });
    await user.upload(screen.getByLabelText("Arquivo"), file);
    await user.click(screen.getByRole("button", { name: "Enviar para ingestão" }));

    expect(mockedUploadDocument).toHaveBeenCalledWith({ file, domain: "vendas", collectionId: "col-1" });
  });
});
