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

  it("carrega e lista os modelos ao montar", async () => {
    render(<ModelosPage />);

    expect(await screen.findByText("llama3.1:8b")).toBeInTheDocument();
  });

  it("renderiza o formulário de download", async () => {
    render(<ModelosPage />);

    await screen.findByText("llama3.1:8b");
    expect(screen.getByLabelText(/nome do modelo/i)).toBeInTheDocument();
  });
});
