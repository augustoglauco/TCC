import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LocalModelsTable } from "@/components/admin/LocalModelsTable";
import type { LocalModel } from "@/lib/types/localModels";

vi.mock("@/lib/api/localModels", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/localModels")>("@/lib/api/localModels");
  return { ...actual, activateModel: vi.fn() };
});

import { activateModel, LocalModelsApiError } from "@/lib/api/localModels";

const mockedActivate = vi.mocked(activateModel);

const MODELO_ATIVO: LocalModel = {
  name: "llama3.1:8b",
  size_bytes: 4_920_000_000,
  modified_at: "2026-09-01T10:00:00Z",
  is_active: true,
};

const MODELO_INATIVO: LocalModel = {
  name: "qwen2.5:7b",
  size_bytes: 4_100_000_000,
  modified_at: "2026-08-15T09:00:00Z",
  is_active: false,
};

describe("LocalModelsTable", () => {
  beforeEach(() => {
    mockedActivate.mockReset();
  });

  it("renderiza uma linha por modelo, com badge 'Ativo'", () => {
    render(<LocalModelsTable models={[MODELO_ATIVO, MODELO_INATIVO]} onChanged={vi.fn()} onError={vi.fn()} onSuccess={vi.fn()} />);

    expect(screen.getByText("llama3.1:8b")).toBeInTheDocument();
    expect(screen.getByText("qwen2.5:7b")).toBeInTheDocument();
    expect(screen.getByText("Ativo")).toBeInTheDocument();
  });

  it("não mostra botão Ativar na linha já ativa", () => {
    render(<LocalModelsTable models={[MODELO_ATIVO]} onChanged={vi.fn()} onError={vi.fn()} onSuccess={vi.fn()} />);

    expect(screen.queryByRole("button", { name: "Ativar" })).not.toBeInTheDocument();
  });

  it("clicar em Ativar chama a API e notifica onChanged/onSuccess", async () => {
    const user = userEvent.setup();
    mockedActivate.mockResolvedValueOnce(undefined);
    const onChanged = vi.fn();
    const onSuccess = vi.fn();
    render(<LocalModelsTable models={[MODELO_INATIVO]} onChanged={onChanged} onError={vi.fn()} onSuccess={onSuccess} />);

    await user.click(screen.getByRole("button", { name: "Ativar" }));

    expect(mockedActivate).toHaveBeenCalledWith("qwen2.5:7b");
    expect(onChanged).toHaveBeenCalled();
    expect(onSuccess).toHaveBeenCalled();
  });

  it("erro ao ativar chama onError com a mensagem da API", async () => {
    const user = userEvent.setup();
    mockedActivate.mockRejectedValueOnce(new LocalModelsApiError("Modelo não encontrado entre os já baixados."));
    const onError = vi.fn();
    render(<LocalModelsTable models={[MODELO_INATIVO]} onChanged={vi.fn()} onError={onError} onSuccess={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Ativar" }));

    expect(onError).toHaveBeenCalledWith("Modelo não encontrado entre os já baixados.");
  });

  it("sem modelos, mostra mensagem vazia", () => {
    render(<LocalModelsTable models={[]} onChanged={vi.fn()} onError={vi.fn()} onSuccess={vi.fn()} />);

    expect(screen.getByText(/nenhum modelo/i)).toBeInTheDocument();
  });
});
