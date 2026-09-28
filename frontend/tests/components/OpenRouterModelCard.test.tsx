import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { OpenRouterModelCard } from "@/components/admin/OpenRouterModelCard";
import { getRuntimeSettings, updateRuntimeSettings } from "@/lib/api/runtimeSettings";

vi.mock("@/lib/api/runtimeSettings", () => ({
  getRuntimeSettings: vi.fn(),
  updateRuntimeSettings: vi.fn(),
}));

const mockGetSettings = vi.mocked(getRuntimeSettings);
const mockUpdateSettings = vi.mocked(updateRuntimeSettings);

describe("OpenRouterModelCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();

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
      expect(mockUpdateSettings).toHaveBeenCalledWith({
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
});
