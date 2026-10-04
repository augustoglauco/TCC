import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RuntimeSettingsForm } from "@/components/admin/RuntimeSettingsForm";
import type { RuntimeSettings } from "@/lib/types/runtimeSettings";

vi.mock("@/lib/api/runtimeSettings", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/runtimeSettings")>(
    "@/lib/api/runtimeSettings",
  );
  return {
    ...actual,
    getRuntimeSettings: vi.fn(),
    updateRuntimeSettings: vi.fn(),
    preloadLocalModel: vi.fn(),
    unloadLocalModel: vi.fn(),
  };
});

import {
  RuntimeSettingsApiError,
  getRuntimeSettings,
  updateRuntimeSettings,
  preloadLocalModel,
  unloadLocalModel,
} from "@/lib/api/runtimeSettings";

const mockedGet = vi.mocked(getRuntimeSettings);
const mockedUpdate = vi.mocked(updateRuntimeSettings);
const mockedPreload = vi.mocked(preloadLocalModel);
const mockedUnload = vi.mocked(unloadLocalModel);

const SETTINGS_PADRAO: RuntimeSettings = {
  local_llm_temperature: null,
  local_llm_timeout_s: 30.0,
  external_llm_timeout_s: 30.0,
  rag_search_domain_fallback: false,
  crawler_max_pages_default: 50,
  crawler_confidence_threshold: 0.8,
  external_vision_model_name: "google/gemini-flash-1.5",
  image_internal_confidence: 0.3,
  image_external_confidence: 0.7,
  intent_router_provider: "heuristica_llm",
  tone_monitor_enabled: true,
  tone_monitor_provider: "heuristica_llm",
};

describe("RuntimeSettingsForm", () => {
  beforeEach(() => {
    mockedGet.mockReset();
    mockedUpdate.mockReset();
    mockedPreload.mockReset();
    mockedUnload.mockReset();
  });

  it("carrega e mostra os valores atuais", async () => {
    mockedGet.mockResolvedValueOnce(SETTINGS_PADRAO);

    render(<RuntimeSettingsForm onError={vi.fn()} onSuccess={vi.fn()} />);

    expect(await screen.findByLabelText(/timeout do modelo local/i)).toHaveValue(30);
    expect(screen.getByLabelText(/timeout do modelo externo/i)).toHaveValue(30);
    expect(screen.getByLabelText(/temperatura/i)).toHaveValue(null);
    expect(screen.getAllByLabelText(/heurística \+ llm local \(ollama\)/i)[0]).toBeChecked();
    expect(screen.getAllByLabelText(/typesafe jev \(openrouter\)/i)[0]).not.toBeChecked();
    expect(screen.getByLabelText(/monitor de tom ativo/i)).toBeChecked();
    expect(screen.getAllByLabelText(/heurística \+ llm local \(ollama\)/i)[1]).toBeChecked();
    expect(screen.getAllByLabelText(/typesafe jev \(openrouter\)/i)[1]).not.toBeChecked();
    expect(screen.getByLabelText(/modelo de visão \(openrouter\)/i)).toHaveValue(
      "google/gemini-flash-1.5",
    );
    expect(screen.getByLabelText(/limiar catálogo interno \(clip\)/i)).toHaveValue(0.3);
    expect(screen.getByLabelText(/limiar visão externa/i)).toHaveValue(0.7);
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

    expect(mockedUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        local_llm_temperature: 0.2,
        local_llm_timeout_s: 30,
        external_llm_timeout_s: 30,
        intent_router_provider: "heuristica_llm",
        tone_monitor_enabled: true,
        tone_monitor_provider: "heuristica_llm",
        external_vision_model_name: "google/gemini-flash-1.5",
        image_internal_confidence: 0.3,
        image_external_confidence: 0.7,
      }),
    );
    await vi.waitFor(() => expect(onSuccess).toHaveBeenCalled());
  });

  it("seleciona o provedor Jev do roteador e envia no payload", async () => {
    mockedGet.mockResolvedValueOnce(SETTINGS_PADRAO);
    mockedUpdate.mockResolvedValueOnce({
      ...SETTINGS_PADRAO,
      intent_router_provider: "jev_openrouter",
    });
    const onSuccess = vi.fn();
    const user = userEvent.setup();

    render(<RuntimeSettingsForm onError={vi.fn()} onSuccess={onSuccess} />);

    await screen.findAllByLabelText(/typesafe jev \(openrouter\)/i);
    await user.click(screen.getAllByLabelText(/typesafe jev \(openrouter\)/i)[0]);
    await user.click(screen.getByRole("button", { name: "Aplicar" }));

    expect(mockedUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ intent_router_provider: "jev_openrouter" }),
    );
    await vi.waitFor(() => expect(onSuccess).toHaveBeenCalled());
  });

  it("desliga o Monitor de Tom e envia no payload", async () => {
    mockedGet.mockResolvedValueOnce(SETTINGS_PADRAO);
    mockedUpdate.mockResolvedValueOnce({ ...SETTINGS_PADRAO, tone_monitor_enabled: false });
    const onSuccess = vi.fn();
    const user = userEvent.setup();

    render(<RuntimeSettingsForm onError={vi.fn()} onSuccess={onSuccess} />);

    await user.click(await screen.findByLabelText(/monitor de tom ativo/i));
    await user.click(screen.getByRole("button", { name: "Aplicar" }));

    expect(mockedUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ tone_monitor_enabled: false }),
    );
    await vi.waitFor(() => expect(onSuccess).toHaveBeenCalled());
  });

  it("seleciona o provedor Jev do Monitor de Tom e envia no payload", async () => {
    mockedGet.mockResolvedValueOnce(SETTINGS_PADRAO);
    mockedUpdate.mockResolvedValueOnce({
      ...SETTINGS_PADRAO,
      tone_monitor_provider: "jev_openrouter",
    });
    const onSuccess = vi.fn();
    const user = userEvent.setup();

    render(<RuntimeSettingsForm onError={vi.fn()} onSuccess={onSuccess} />);

    await screen.findAllByLabelText(/typesafe jev \(openrouter\)/i);
    await user.click(screen.getAllByLabelText(/typesafe jev \(openrouter\)/i)[1]);
    await user.click(screen.getByRole("button", { name: "Aplicar" }));

    expect(mockedUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ tone_monitor_provider: "jev_openrouter" }),
    );
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

  it("seleciona o provedor heurística do roteador e envia no payload", async () => {
    mockedGet.mockResolvedValueOnce(SETTINGS_PADRAO);
    mockedUpdate.mockResolvedValueOnce({
      ...SETTINGS_PADRAO,
      intent_router_provider: "heuristica",
    });
    const onSuccess = vi.fn();
    const user = userEvent.setup();

    render(<RuntimeSettingsForm onError={vi.fn()} onSuccess={onSuccess} />);

    const radioHeuristica = await screen.findByLabelText(/heurística \(palavras-chave\)/i);
    await user.click(radioHeuristica);
    await user.click(screen.getByRole("button", { name: "Aplicar" }));

    expect(mockedUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ intent_router_provider: "heuristica" }),
    );
    await vi.waitFor(() => expect(onSuccess).toHaveBeenCalled());
  });

  it("carrega e exibe campos de keep_alive, warmup e badge de VRAM", async () => {
    mockedGet.mockResolvedValueOnce({
      ...SETTINGS_PADRAO,
      local_llm_keep_alive: "24h",
      local_llm_warmup_on_startup: true,
      local_model_loaded: true,
      local_model_vram_bytes: 8589934592, // 8.00 GB
    });

    render(<RuntimeSettingsForm onError={vi.fn()} onSuccess={vi.fn()} />);

    expect(await screen.findByLabelText(/tempo de retenção na vram/i)).toHaveValue("24h");
    expect(screen.getByLabelText(/pré-carregar modelo ao inicializar o backend/i)).toBeChecked();
    expect(screen.getByText(/modelo carregado na vram \(8.00 gb\)/i)).toBeInTheDocument();
  });

  it("altera keep_alive e warmup e envia no payload de atualização", async () => {
    mockedGet.mockResolvedValueOnce(SETTINGS_PADRAO);
    mockedUpdate.mockResolvedValueOnce({
      ...SETTINGS_PADRAO,
      local_llm_keep_alive: "-1",
      local_llm_warmup_on_startup: false,
    });
    const onSuccess = vi.fn();
    const user = userEvent.setup();

    render(<RuntimeSettingsForm onError={vi.fn()} onSuccess={onSuccess} />);

    const selectKeepAlive = await screen.findByLabelText(/tempo de retenção na vram/i);
    await user.selectOptions(selectKeepAlive, "-1");

    const checkboxWarmup = screen.getByLabelText(/pré-carregar modelo ao inicializar o backend/i);
    await user.click(checkboxWarmup);

    await user.click(screen.getByRole("button", { name: "Aplicar" }));

    expect(mockedUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        local_llm_keep_alive: "-1",
        local_llm_warmup_on_startup: false,
      }),
    );
    await vi.waitFor(() => expect(onSuccess).toHaveBeenCalledWith(expect.stringMatching(/banco/i)));
  });

  it("executa ação manual de carregar na GPU via preloadLocalModel", async () => {
    mockedGet.mockResolvedValueOnce({
      ...SETTINGS_PADRAO,
      local_model_loaded: false,
      local_model_vram_bytes: null,
    });
    mockedPreload.mockResolvedValueOnce({
      ...SETTINGS_PADRAO,
      local_model_loaded: true,
      local_model_vram_bytes: 8589934592,
    });
    const onSuccess = vi.fn();
    const user = userEvent.setup();

    render(<RuntimeSettingsForm onError={vi.fn()} onSuccess={onSuccess} />);

    const btnCarregar = await screen.findByRole("button", { name: /carregar na gpu/i });
    await user.click(btnCarregar);

    expect(mockedPreload).toHaveBeenCalledTimes(1);
    await vi.waitFor(() =>
      expect(onSuccess).toHaveBeenCalledWith("Modelo local carregado na VRAM da GPU com sucesso!"),
    );
    expect(screen.getByText(/modelo carregado na vram \(8.00 gb\)/i)).toBeInTheDocument();
  });

  it("executa ação manual de liberar VRAM via unloadLocalModel", async () => {
    mockedGet.mockResolvedValueOnce({
      ...SETTINGS_PADRAO,
      local_model_loaded: true,
      local_model_vram_bytes: 8589934592,
    });
    mockedUnload.mockResolvedValueOnce({
      ...SETTINGS_PADRAO,
      local_model_loaded: false,
      local_model_vram_bytes: null,
    });
    const onSuccess = vi.fn();
    const user = userEvent.setup();

    render(<RuntimeSettingsForm onError={vi.fn()} onSuccess={onSuccess} />);

    const btnLiberar = await screen.findByRole("button", { name: /liberar vram/i });
    await user.click(btnLiberar);

    expect(mockedUnload).toHaveBeenCalledTimes(1);
    await vi.waitFor(() =>
      expect(onSuccess).toHaveBeenCalledWith("VRAM liberada com sucesso (modelo descarregado)."),
    );
    expect(screen.getByText(/modelo descarregado \(0 gb\)/i)).toBeInTheDocument();
  });
});

