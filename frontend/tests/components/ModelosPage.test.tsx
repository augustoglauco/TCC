import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ModelosPage from "@/app/admin/modelos/page";
import type { LocalModelsListResponse } from "@/lib/types/localModels";

vi.mock("@/lib/api/localModels", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/localModels")>("@/lib/api/localModels");
  return { ...actual, listLocalModels: vi.fn() };
});

import { listLocalModels } from "@/lib/api/localModels";

const mockedListLocalModels = vi.mocked(listLocalModels);

const RESPOSTA: LocalModelsListResponse = {
  models: [
    { name: "llama3.1:8b", size_bytes: 4_920_000_000, modified_at: "2026-09-01T10:00:00Z", is_active: true },
  ],
  active_model: "llama3.1:8b",
};

describe("ModelosPage", () => {
  beforeEach(() => {
    mockedListLocalModels.mockReset();
    mockedListLocalModels.mockResolvedValue(RESPOSTA);
  });

  it("carrega e exibe o título 'Administração Geral' e a lista de modelos", async () => {
    render(<ModelosPage />);

    expect(screen.getByRole("heading", { level: 1, name: "Administração Geral" })).toBeInTheDocument();
    expect(await screen.findByText("llama3.1:8b")).toBeInTheDocument();
  });

  it("renderiza as abas de 'Modelos' e 'Parâmetros de execução'", async () => {
    render(<ModelosPage />);

    expect(screen.getByRole("tab", { name: /modelos/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /parâmetros de execução/i })).toBeInTheDocument();
  });

  it("renderiza o formulário de download na aba de Modelos", async () => {
    render(<ModelosPage />);

    await screen.findByText("llama3.1:8b");
    expect(screen.getByLabelText(/nome do modelo/i)).toBeInTheDocument();
  });

  it("mostra qual é o modelo ativo no chat", async () => {
    render(<ModelosPage />);

    await screen.findByText("llama3.1:8b");
    expect(screen.getByText(/modelo ativo no chat/i)).toBeInTheDocument();
    expect(screen.getAllByText("llama3.1:8b").length).toBeGreaterThan(0);
  });

  it("mostra 'Nenhum' quando não há modelo ativo", async () => {
    mockedListLocalModels.mockResolvedValue({ models: [], active_model: "" });

    render(<ModelosPage />);

    expect(await screen.findByText(/modelo ativo no chat/i)).toBeInTheDocument();
    expect(screen.getByText("Nenhum")).toBeInTheDocument();
  });
});
