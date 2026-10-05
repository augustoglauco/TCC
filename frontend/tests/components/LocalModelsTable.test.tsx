import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LocalModelsTable } from "@/components/admin/LocalModelsTable";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import type { LocalModel } from "@/lib/types/localModels";

vi.mock("@/lib/api/localModels", async () => {
  const actual =
    await vi.importActual<typeof import("@/lib/api/localModels")>("@/lib/api/localModels");
  return { ...actual, activateModel: vi.fn() };
});

import { activateModel, LocalModelsApiError } from "@/lib/api/localModels";

vi.mock("@/lib/hooks/useModelCharacteristics", () => ({
  useModelCharacteristics: vi.fn(() => ({
    data: {
      source: "ollama",
      tag: "qwen2.5:7b",
      is_multimodal: true,
      input_modalities: ["text", "image"],
      output_modalities: ["text"],
      context_length: 32768,
      parameter_size: "7B",
      quantization: "Q4_0",
      pricing_prompt_per_1k: null,
      pricing_completion_per_1k: null,
      knowledge_cutoff: null,
      fetched_at: new Date().toISOString(),
    },
    loading: false,
    error: null,
    refresh: vi.fn(),
  })),
}));

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
    useAuthStore.setState({
      user: { id: 1, nome: "Admin Teste", email: "admin@empresa.com", perfil: "Admin" },
      token: "mock-token-1",
    });
  });

  it("renderiza uma linha por modelo, com badge 'Ativo'", () => {
    render(
      <LocalModelsTable
        models={[MODELO_ATIVO, MODELO_INATIVO]}
        onChanged={vi.fn()}
        onError={vi.fn()}
        onSuccess={vi.fn()}
      />,
    );

    expect(screen.getAllByText("llama3.1:8b").length).toBeGreaterThan(0);
    expect(screen.getAllByText("qwen2.5:7b").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Ativo").length).toBeGreaterThan(0);
  });

  it("não mostra botão Ativar na linha já ativa", () => {
    render(
      <LocalModelsTable
        models={[MODELO_ATIVO]}
        onChanged={vi.fn()}
        onError={vi.fn()}
        onSuccess={vi.fn()}
      />,
    );

    expect(screen.queryByRole("button", { name: "Ativar" })).not.toBeInTheDocument();
  });

  it("clicar em Ativar chama a API e notifica onChanged/onSuccess", async () => {
    const user = userEvent.setup();
    mockedActivate.mockResolvedValueOnce(undefined);
    const onChanged = vi.fn();
    const onSuccess = vi.fn();
    render(
      <LocalModelsTable
        models={[MODELO_INATIVO]}
        onChanged={onChanged}
        onError={vi.fn()}
        onSuccess={onSuccess}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Ativar" }));

    expect(mockedActivate).toHaveBeenCalledWith("mock-token-1", "qwen2.5:7b");
    expect(onChanged).toHaveBeenCalled();
    expect(onSuccess).toHaveBeenCalled();
  });

  it("erro ao ativar chama onError com a mensagem da API", async () => {
    const user = userEvent.setup();
    mockedActivate.mockRejectedValueOnce(
      new LocalModelsApiError("Modelo não encontrado entre os já baixados."),
    );
    const onError = vi.fn();
    render(
      <LocalModelsTable
        models={[MODELO_INATIVO]}
        onChanged={vi.fn()}
        onError={onError}
        onSuccess={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Ativar" }));

    expect(onError).toHaveBeenCalledWith("Modelo não encontrado entre os já baixados.");
  });

  it("mostra a data de download com o timestamp completo no title", () => {
    render(
      <LocalModelsTable
        models={[MODELO_ATIVO]}
        onChanged={vi.fn()}
        onError={vi.fn()}
        onSuccess={vi.fn()}
      />,
    );

    // Não asserta o texto relativo exato (ex.: "há N dias") pois depende da
    // data em que o teste roda e ficaria flaky/errado com o tempo — o
    // atributo `title` com o ISO completo é estável e determinístico.
    const celulaData = screen.getByTitle(MODELO_ATIVO.modified_at);
    expect(celulaData).toBeInTheDocument();
    expect(celulaData.textContent).toMatch(/hoje|há \d+ dia/);
  });

  it("sem modelos, mostra mensagem vazia", () => {
    render(
      <LocalModelsTable models={[]} onChanged={vi.fn()} onError={vi.fn()} onSuccess={vi.fn()} />,
    );

    expect(screen.getByText(/nenhum modelo/i)).toBeInTheDocument();
  });

  it("mostra as características ao passar o mouse sobre um modelo instalado", async () => {
    const user = userEvent.setup();
    render(
      <LocalModelsTable
        models={[
          {
            name: "qwen2.5:7b",
            size_bytes: 4_700_000_000,
            modified_at: new Date().toISOString(),
            // is_active: false (desvio deliberado do brief) para evitar que o
            // mesmo texto apareça duplicado no banner "Modelo Local Ativo" —
            // getByText falharia com "multiple elements" por um motivo não
            // relacionado à feature testada aqui (hover/tooltip).
            is_active: false,
          },
        ]}
        onChanged={vi.fn()}
        onError={vi.fn()}
        onSuccess={vi.fn()}
      />,
    );

    const card = screen.getByText("qwen2.5:7b").closest("div")!;
    await user.hover(card);

    expect(await screen.findByText("Imagem")).toBeInTheDocument();
  });
});
