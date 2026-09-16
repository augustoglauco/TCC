import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PullModelForm } from "@/components/admin/PullModelForm";
import type { PullStatusResponse } from "@/lib/types/localModels";

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

  it("não vaza um segundo interval quando a retomada resolve depois de um submit manual concorrente", async () => {
    // Regressão: `iniciarPolling` antes não chamava `pararPolling()` no
    // início, então se o efeito de retomada (assíncrono, dispara no mount)
    // resolvesse DEPOIS de um submit manual já ter iniciado o polling de um
    // outro modelo, o segundo `setInterval` sobrescrevia `intervalRef.current`
    // sem nunca dar `clearInterval` no primeiro — o interval do primeiro
    // modelo ficava rodando pra sempre, "brigando" com o estado do segundo.
    //
    // Aqui: localStorage tem "modelo-b" salvo (== em download no servidor),
    // mas a checagem de retomada (`getPullStatus("modelo-b")`) fica presa
    // numa Promise controlada manualmente — só resolve depois que o usuário
    // já submeteu "modelo-a" pelo formulário e o polling dele já foi
    // iniciado. Isso reproduz exatamente a corrida do achado da revisão.
    window.localStorage.setItem(STORAGE_KEY, "modelo-b");

    let resolverRetomada: (status: PullStatusResponse) => void = () => {};
    const statusDeRetomadaPendente = new Promise<PullStatusResponse>((resolve) => {
      resolverRetomada = resolve;
    });
    let chamadaDeRetomadaJaConsumida = false;
    mockedGetPullStatus.mockImplementation((nome: string) => {
      if (nome === "modelo-b" && !chamadaDeRetomadaJaConsumida) {
        chamadaDeRetomadaJaConsumida = true;
        return statusDeRetomadaPendente;
      }
      // Chamadas de polling seguintes (depois que cada modelo já está com
      // seu interval rodando) — respostas "pulling" genéricas, só para o
      // interval continuar vivo e não terminar sozinho antes da asserção.
      return Promise.resolve({
        status: "pulling" as const,
        percent: nome === "modelo-b" ? 60 : 10,
        detail: `baixando ${nome}...`,
      });
    });
    mockedPullModel.mockResolvedValueOnce(undefined);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    render(<PullModelForm onPulled={vi.fn()} />);

    // A checagem de retomada de "modelo-b" já foi disparada no mount (e está
    // presa na Promise pendente) — antes dela resolver, o usuário submete um
    // modelo diferente pelo formulário.
    await user.type(screen.getByLabelText(/nome do modelo/i), "modelo-a");
    await user.click(screen.getByRole("button", { name: "Baixar" }));
    expect(mockedPullModel).toHaveBeenCalledWith("modelo-a");
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe("modelo-a");

    // Só agora a retomada de "modelo-b" resolve — com o polling de
    // "modelo-a" já iniciado (interval A vivo em `intervalRef.current`). Como
    // o submit manual já começou, a retomada deve descartar seu resultado em
    // vez de sobrescrever o estado/interval de "modelo-a" — senão o download
    // de "modelo-b", que continua rodando no servidor, fica órfão da UI.
    resolverRetomada({ status: "pulling", percent: 60, detail: "baixando modelo-b..." });
    await vi.advanceTimersByTimeAsync(0);

    expect(screen.getByDisplayValue("modelo-a")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("modelo-b")).not.toBeInTheDocument();
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe("modelo-a");

    // Avança um ciclo de polling. Sem o fix, tanto o interval de "modelo-a"
    // quanto o de "modelo-b" (aplicado pela retomada) disparariam juntos; com
    // o fix, só o interval de "modelo-a" (o único vivo) deve ter dado tick.
    await vi.advanceTimersByTimeAsync(1500);

    const chamadasParaModeloA = mockedGetPullStatus.mock.calls.filter(([nome]) => nome === "modelo-a");
    const chamadasParaModeloB = mockedGetPullStatus.mock.calls.filter(([nome]) => nome === "modelo-b");
    expect(chamadasParaModeloA.length).toBeGreaterThan(0);
    // Única chamada para "modelo-b" = a checagem de retomada; nenhum tick de
    // polling seguinte deve ter sido disparado para ele.
    expect(chamadasParaModeloB).toHaveLength(1);
  });

  it("tolera falhas transitórias isoladas de polling e não interrompe o download", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockedPullModel.mockResolvedValueOnce(undefined);
    mockedGetPullStatus
      .mockResolvedValueOnce({ status: "pulling", percent: 10, detail: "baixando..." })
      // 2 falhas transitórias seguidas (ex.: instabilidade de rede) — não
      // devem, sozinhas, interromper o polling nem marcar erro.
      .mockRejectedValueOnce(new LocalModelsApiError("Falha transitória 1"))
      .mockRejectedValueOnce(new LocalModelsApiError("Falha transitória 2"))
      // Uma resposta de sucesso no meio reseta o contador de falhas
      // consecutivas a zero.
      .mockResolvedValueOnce({ status: "pulling", percent: 50, detail: "baixando..." })
      .mockResolvedValueOnce({ status: "done", percent: 100, detail: "concluído" });
    const onPulled = vi.fn();

    render(<PullModelForm onPulled={onPulled} />);

    await user.type(screen.getByLabelText(/nome do modelo/i), "llama3.1:8b");
    await user.click(screen.getByRole("button", { name: "Baixar" }));

    expect(await screen.findByText(/10/)).toBeInTheDocument();

    // Duas falhas consecutivas: o polling continua vivo, sem erro exibido, e
    // o download não é dado como abortado (localStorage/enviando mantidos).
    await vi.advanceTimersByTimeAsync(2500);
    expect(screen.queryByText(/Falha transitória/)).not.toBeInTheDocument();
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe("llama3.1:8b");
    expect(screen.getByRole("button", { name: "Baixando..." })).toBeInTheDocument();

    // A resposta de sucesso seguinte reseta o contador; o polling segue até
    // "done" normalmente.
    await vi.advanceTimersByTimeAsync(2000);
    await waitFor(() => expect(onPulled).toHaveBeenCalled());
    expect(screen.getByText(/concluído/i)).toBeInTheDocument();
  });

  it("marca erro fatal após N falhas consecutivas de polling", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockedPullModel.mockResolvedValueOnce(undefined);
    mockedGetPullStatus
      .mockResolvedValueOnce({ status: "pulling", percent: 10, detail: "baixando..." })
      .mockRejectedValueOnce(new LocalModelsApiError("Falha 1"))
      .mockRejectedValueOnce(new LocalModelsApiError("Falha 2"))
      .mockRejectedValueOnce(new LocalModelsApiError("Falha 3"));

    render(<PullModelForm onPulled={vi.fn()} />);

    await user.type(screen.getByLabelText(/nome do modelo/i), "llama3.1:8b");
    await user.click(screen.getByRole("button", { name: "Baixar" }));

    expect(await screen.findByText(/10/)).toBeInTheDocument();

    await vi.advanceTimersByTimeAsync(3500);

    expect(await screen.findByText("Falha 3")).toBeInTheDocument();
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull();
    // `enviando` volta a `false` — o formulário libera uma nova tentativa.
    expect(screen.getByRole("button", { name: "Baixar" })).not.toBeDisabled();
  });
});
