import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import DocumentDownloadCard from "@/components/chat/cards/DocumentDownloadCard";
import type { ChatCardDocumentoDownload } from "@/lib/types/chat";

function makeCard(overrides: Partial<ChatCardDocumentoDownload> = {}): ChatCardDocumentoDownload {
  return {
    tipo: "documento_download",
    documento_id: "doc-123",
    filename: "Manual_GD30.pdf",
    domain: "suporte",
    score: 0.88,
    download_url: "/api/rag/documents/doc-123/download",
    file_size_bytes: 2450000,
    ...overrides,
  };
}

describe("DocumentDownloadCard (chat)", () => {
  it("renderiza o nome do arquivo", () => {
    render(<DocumentDownloadCard card={makeCard()} />);

    expect(screen.getByText("Manual_GD30.pdf")).toBeInTheDocument();
  });

  it("renderiza o percentual de relevância arredondado", () => {
    render(<DocumentDownloadCard card={makeCard({ score: 0.88 })} />);

    expect(screen.getByText(/88%/)).toBeInTheDocument();
  });

  it("renderiza um link de download com nome acessível 'Baixar Documento'", () => {
    render(<DocumentDownloadCard card={makeCard()} />);

    const link = screen.getByRole("link", { name: /baixar documento/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("download");
  });

  it("resolve o href para a base da API + download_url do card", () => {
    render(
      <DocumentDownloadCard
        card={makeCard({ download_url: "/api/rag/documents/doc-999/download" })}
      />,
    );

    const link = screen.getByRole("link", { name: /baixar documento/i });
    const href = link.getAttribute("href") ?? "";
    expect(href).toContain("/api/rag/documents/doc-999/download");
    expect(href.startsWith("http")).toBe(true);
  });

  it("formata o tamanho do arquivo quando file_size_bytes está presente", () => {
    render(<DocumentDownloadCard card={makeCard({ file_size_bytes: 2450000 })} />);

    expect(screen.getByText(/2[.,]3\s*MB/i)).toBeInTheDocument();
  });

  it("não renderiza tamanho nem quebra quando file_size_bytes é null", () => {
    render(<DocumentDownloadCard card={makeCard({ file_size_bytes: null })} />);

    expect(screen.getByText("Manual_GD30.pdf")).toBeInTheDocument();
    expect(screen.queryByText(/undefined/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/null/i)).not.toBeInTheDocument();
  });

  it("não renderiza tamanho nem quebra quando file_size_bytes está ausente", () => {
    const card = makeCard();
    delete card.file_size_bytes;
    render(<DocumentDownloadCard card={card} />);

    expect(screen.getByText("Manual_GD30.pdf")).toBeInTheDocument();
    expect(screen.queryByText(/undefined/i)).not.toBeInTheDocument();
  });
});
