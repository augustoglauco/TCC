import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { OpenRouterModelCard } from "@/components/admin/OpenRouterModelCard";
import { getRuntimeSettings, updateRuntimeSettings } from "@/lib/api/runtimeSettings";
import { useAuthStore } from "@/lib/hooks/useAuthStore";

vi.mock("@/lib/api/runtimeSettings", () => ({
  getRuntimeSettings: vi.fn(),
  updateRuntimeSettings: vi.fn(),
}));

vi.mock("@/lib/hooks/useModelCharacteristics", () => ({
  useModelCharacteristics: vi.fn(() => ({
    data: {
      source: "openrouter",
      tag: "openai/gpt-4o-mini",
      is_multimodal: true,
      input_modalities: ["text", "image"],
      output_modalities: ["text"],
      context_length: 128000,
      parameter_size: null,
      quantization: null,
      pricing_prompt_per_1k: 0.00015,
      pricing_completion_per_1k: 0.0006,
      knowledge_cutoff: "2023-10-31",
      fetched_at: new Date().toISOString(),
    },
    loading: false,
    error: null,
    refresh: vi.fn(),
  })),
}));

const mockGetSettings = vi.mocked(getRuntimeSettings);
const mockUpdateSettings = vi.mocked(updateRuntimeSettings);

describe("OpenRouterModelCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    useAuthStore.setState({
      user: { id: 1, nome: "Admin Teste", email: "admin@empresa.com", perfil: "Admin" },
      token: "mock-token-1",
    });

    mockGetSettings.mockResolvedValue({
      local_llm_temperature: null,
      local_llm_timeout_s: 30,
      external_llm_timeout_s: 30,
      rag_search_domain_fallback: false,
      crawler_max_pages_default: 20,
      crawler_confidence_threshold: 0.7,
      external_model_name: "openai/gpt-4o-mini",
      external_vision_model_name: "",
    });
  });

  it("renderiza o modelo ativo e os grupos de modelos populares e gratuitos", async () => {
    const onError = vi.fn();
    const onSuccess = vi.fn();

    render(<OpenRouterModelCard onError={onError} onSuccess={onSuccess} />);

    await waitFor(() => {
      expect(screen.getAllByText("openai/gpt-4o-mini").length).toBeGreaterThan(0);
    });

    expect(screen.getByText(/Modelos Populares no OpenRouter/)).toBeInTheDocument();
    expect(screen.getByText(/Modelos Gratuitos/)).toBeInTheDocument();
    expect(screen.getByText("Claude 3.5 Sonnet")).toBeInTheDocument();
    expect(screen.getByText("Llama 3.1 8B Free")).toBeInTheDocument();
  });

  it("ativa um modelo selecionado e guarda no histórico", async () => {
    const onError = vi.fn();
    const onSuccess = vi.fn();

    mockUpdateSettings.mockResolvedValue({
      local_llm_temperature: null,
      local_llm_timeout_s: 30,
      external_llm_timeout_s: 30,
      rag_search_domain_fallback: false,
      crawler_max_pages_default: 20,
      crawler_confidence_threshold: 0.7,
      external_model_name: "anthropic/claude-3.5-sonnet",
      external_vision_model_name: "",
    });

    render(<OpenRouterModelCard onError={onError} onSuccess={onSuccess} />);

    await waitFor(() => {
      expect(screen.getAllByText("openai/gpt-4o-mini").length).toBeGreaterThan(0);
    });

    // Clica para ativar o Claude 3.5 Sonnet
    const claudeHeader = screen.getByText("Claude 3.5 Sonnet");
    const claudeCard = claudeHeader.closest("div")?.parentElement;
    const activateBtn = claudeCard?.querySelector("button");
    if (activateBtn) {
      fireEvent.click(activateBtn);
    }

    await waitFor(() => {
      expect(mockUpdateSettings).toHaveBeenCalledWith("mock-token-1", {
        external_model_name: "anthropic/claude-3.5-sonnet",
      });
      expect(onSuccess).toHaveBeenCalledWith(
        expect.stringContaining("anthropic/claude-3.5-sonnet"),
      );
    });

    // Verifica que foi salvo no localStorage
    const saved = localStorage.getItem("openrouter_model_history");
    expect(saved).toContain("anthropic/claude-3.5-sonnet");
  });

  it("mostra as características do modelo ao passar o mouse sobre o card", async () => {
    const user = userEvent.setup();
    render(<OpenRouterModelCard onError={vi.fn()} onSuccess={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getAllByText("openai/gpt-4o-mini").length).toBeGreaterThan(0);
    });

    const cardGptMini = screen.getByText("GPT-4o Mini").closest("div")!;
    await user.hover(cardGptMini);

    expect(await screen.findByText("Imagem")).toBeInTheDocument();
  });
});
