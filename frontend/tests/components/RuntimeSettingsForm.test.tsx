import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RuntimeSettingsForm } from "@/components/admin/RuntimeSettingsForm";
import type { RuntimeSettings } from "@/lib/types/runtimeSettings";

vi.mock("@/lib/api/runtimeSettings", async () => {
  const actual =
    await vi.importActual<typeof import("@/lib/api/runtimeSettings")>("@/lib/api/runtimeSettings");
  return { ...actual, getRuntimeSettings: vi.fn(), updateRuntimeSettings: vi.fn() };
});

import { RuntimeSettingsApiError, getRuntimeSettings, updateRuntimeSettings } from "@/lib/api/runtimeSettings";

const mockedGet = vi.mocked(getRuntimeSettings);
const mockedUpdate = vi.mocked(updateRuntimeSettings);

const SETTINGS_PADRAO: RuntimeSettings = {
  local_llm_temperature: null,
  local_llm_timeout_s: 30.0,
  external_llm_timeout_s: 30.0,
  rag_search_domain_fallback: false,
  crawler_max_pages_default: 50,
  crawler_confidence_threshold: 0.8,
};

describe("RuntimeSettingsForm", () => {
  beforeEach(() => {
    mockedGet.mockReset();
    mockedUpdate.mockReset();
  });

  it("carrega e mostra os valores atuais", async () => {
    mockedGet.mockResolvedValueOnce(SETTINGS_PADRAO);

    render(<RuntimeSettingsForm onError={vi.fn()} onSuccess={vi.fn()} />);

    expect(await screen.findByLabelText(/timeout do modelo local/i)).toHaveValue(30);
    expect(screen.getByLabelText(/timeout do modelo externo/i)).toHaveValue(30);
    expect(screen.getByLabelText(/temperatura/i)).toHaveValue(null);
    expect(screen.getByLabelText(/buscar sem filtro de domínio/i)).not.toBeChecked();
  });

  it("mostra erro via onError quando o carregamento falha", async () => {
    mockedGet.mockRejectedValueOnce(new RuntimeSettingsApiError("Erro ao carregar."));
    const onError = vi.fn();

    render(<RuntimeSettingsForm onError={onError} onSuccess={vi.fn()} />);

    await screen.findByText(/carregando/i);
    await vi.waitFor(() => expect(onError).toHaveBeenCalledWith("Erro ao carregar."));
  });

  it("envia os valores editados e chama onSuccess", async () => {
    mockedGet.mockResolvedValueOnce(SETTINGS_PADRAO);
    mockedUpdate.mockResolvedValueOnce({ ...SETTINGS_PADRAO, local_llm_temperature: 0.2 });
    const onSuccess = vi.fn();
    const user = userEvent.setup();

    render(<RuntimeSettingsForm onError={vi.fn()} onSuccess={onSuccess} />);

    const campoTemperatura = await screen.findByLabelText(/temperatura/i);
    fireEvent.change(campoTemperatura, { target: { value: "0.2" } });
    await user.click(screen.getByRole("button", { name: "Aplicar" }));

    expect(mockedUpdate).toHaveBeenCalledWith({
      local_llm_temperature: 0.2,
      local_llm_timeout_s: 30,
      external_llm_timeout_s: 30,
      rag_search_domain_fallback: false,
    });
    await vi.waitFor(() => expect(onSuccess).toHaveBeenCalled());
  });

  it("campo de temperatura vazio manda null explícito (reseta pro default do modelo)", async () => {
    mockedGet.mockResolvedValueOnce({ ...SETTINGS_PADRAO, local_llm_temperature: 0.5 });
    mockedUpdate.mockResolvedValueOnce(SETTINGS_PADRAO);
    const user = userEvent.setup();

    render(<RuntimeSettingsForm onError={vi.fn()} onSuccess={vi.fn()} />);

    const campoTemperatura = await screen.findByLabelText(/temperatura/i);
    expect(campoTemperatura).toHaveValue(0.5);

    await user.clear(campoTemperatura);
    await user.click(screen.getByRole("button", { name: "Aplicar" }));

    expect(mockedUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ local_llm_temperature: null }),
    );
  });
});
