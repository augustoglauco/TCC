import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CrawlerReviewQueue } from "@/components/admin/CrawlerReviewQueue";
import type { PendingPage } from "@/lib/types/crawler";

vi.mock("@/lib/api/crawler", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/crawler")>("@/lib/api/crawler");
  return { ...actual, listPendingPages: vi.fn(), approvePendingPage: vi.fn(), rejectPendingPage: vi.fn() };
});

import { approvePendingPage, listPendingPages, rejectPendingPage } from "@/lib/api/crawler";

const mockedList = vi.mocked(listPendingPages);
const mockedApprove = vi.mocked(approvePendingPage);
const mockedReject = vi.mocked(rejectPendingPage);

const PAGINA: PendingPage = {
  id: "pagina-1",
  url: "https://exemplo.com/ambiguo",
  text_snippet: "trecho do conteúdo",
  domain_proposed: "vendas",
  confidence: 0.42,
  created_at: new Date().toISOString(),
};

describe("CrawlerReviewQueue", () => {
  beforeEach(() => {
    mockedList.mockReset();
    mockedApprove.mockReset();
    mockedReject.mockReset();
  });

  it("mostra a mensagem de fila vazia quando não há páginas pendentes", async () => {
    mockedList.mockResolvedValueOnce([]);

    render(<CrawlerReviewQueue reloadKey={0} />);

    expect(await screen.findByText("Nenhuma página pendente de revisão.")).toBeInTheDocument();
  });

  it("aprova a página com o domain selecionado e remove da lista", async () => {
    const user = userEvent.setup();
    mockedList.mockResolvedValueOnce([PAGINA]);
    mockedApprove.mockResolvedValueOnce({ url: PAGINA.url, domain: "suporte", chunks: 1 });

    render(<CrawlerReviewQueue reloadKey={0} />);

    await screen.findByText(PAGINA.url);
    await user.selectOptions(screen.getByRole("combobox"), "suporte");
    await user.click(screen.getByRole("button", { name: "Aprovar" }));

    expect(mockedApprove).toHaveBeenCalledWith(PAGINA.id, { domain: "suporte" });
    expect(screen.queryByText(PAGINA.url)).not.toBeInTheDocument();
  });

  it("rejeita a página e remove da lista", async () => {
    const user = userEvent.setup();
    mockedList.mockResolvedValueOnce([PAGINA]);
    mockedReject.mockResolvedValueOnce(undefined);

    render(<CrawlerReviewQueue reloadKey={0} />);

    await screen.findByText(PAGINA.url);
    await user.click(screen.getByRole("button", { name: "Rejeitar" }));

    expect(mockedReject).toHaveBeenCalledWith(PAGINA.id);
    expect(screen.queryByText(PAGINA.url)).not.toBeInTheDocument();
  });
});
