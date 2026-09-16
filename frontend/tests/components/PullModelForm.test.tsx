import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PullModelForm } from "@/components/admin/PullModelForm";

vi.mock("@/lib/api/localModels", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/localModels")>("@/lib/api/localModels");
  return { ...actual, pullModel: vi.fn(), getPullStatus: vi.fn() };
});

import { LocalModelsApiError, getPullStatus, pullModel } from "@/lib/api/localModels";

const mockedPullModel = vi.mocked(pullModel);
const mockedGetPullStatus = vi.mocked(getPullStatus);

const STORAGE_KEY = "gerenciador-modelos-locais:pull-em-andamento";

describe("PullModelForm", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mockedPullModel.mockReset();
    mockedGetPullStatus.mockReset();
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("botão Baixar fica desabilitado com o campo vazio", () => {
    render(<PullModelForm onPulled={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Baixar" })).toBeDisabled();
  });

  it("submete, faz polling do status até 'done', e chama onPulled", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockedPullModel.mockResolvedValueOnce(undefined);
    mockedGetPullStatus
      .mockResolvedValueOnce({ status: "pulling", percent: 30, detail: "baixando..." })
      .mockResolvedValueOnce({ status: "done", percent: 100, detail: "concluído" });
    const onPulled = vi.fn();

    render(<PullModelForm onPulled={onPulled} />);

    await user.type(screen.getByLabelText(/nome do modelo/i), "llama3.1:8b");
    await user.click(screen.getByRole("button", { name: "Baixar" }));

    expect(mockedPullModel).toHaveBeenCalledWith("llama3.1:8b");
    expect(await screen.findByText(/30/)).toBeInTheDocument();
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe("llama3.1:8b");

    await vi.advanceTimersByTimeAsync(1500);

    await waitFor(() => expect(onPulled).toHaveBeenCalled());
    expect(screen.getByText(/concluído/i)).toBeInTheDocument();
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it("status 'error' para o polling e mostra a mensagem", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockedPullModel.mockResolvedValueOnce(undefined);
    mockedGetPullStatus.mockResolvedValueOnce({
      status: "error",
      percent: null,
      detail: "pull model manifest: file does not exist",
    });

    render(<PullModelForm onPulled={vi.fn()} />);

    await user.type(screen.getByLabelText(/nome do modelo/i), "nome-invalido");
    await user.click(screen.getByRole("button", { name: "Baixar" }));

    expect(await screen.findByText(/file does not exist/)).toBeInTheDocument();
  });

  it("erro ao disparar o pull mostra a mensagem da API", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockedPullModel.mockRejectedValueOnce(new LocalModelsApiError("Não foi possível iniciar o download."));

    render(<PullModelForm onPulled={vi.fn()} />);

    await user.type(screen.getByLabelText(/nome do modelo/i), "llama3.1:8b");
    await user.click(screen.getByRole("button", { name: "Baixar" }));

    expect(await screen.findByText("Não foi possível iniciar o download.")).toBeInTheDocument();
    expect(mockedGetPullStatus).not.toHaveBeenCalled();
  });

  it("retoma um download em andamento salvo no localStorage após remount", async () => {
    window.localStorage.setItem(STORAGE_KEY, "llama3.1:8b");
    mockedGetPullStatus.mockResolvedValueOnce({ status: "pulling", percent: 40, detail: "baixando..." });

    render(<PullModelForm onPulled={vi.fn()} />);

    expect(await screen.findByDisplayValue("llama3.1:8b")).toBeInTheDocument();
    expect(await screen.findByText(/40/)).toBeInTheDocument();
    expect(mockedPullModel).not.toHaveBeenCalled();
  });

  it("não retoma e limpa o localStorage quando o download salvo já terminou", async () => {
    window.localStorage.setItem(STORAGE_KEY, "llama3.1:8b");
    mockedGetPullStatus.mockResolvedValueOnce({ status: "done", percent: 100, detail: "concluído" });

    render(<PullModelForm onPulled={vi.fn()} />);

    await waitFor(() => expect(mockedGetPullStatus).toHaveBeenCalledWith("llama3.1:8b"));
    expect(screen.queryByDisplayValue("llama3.1:8b")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Baixar" })).toBeDisabled();
    await waitFor(() => expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull());
  });
});
