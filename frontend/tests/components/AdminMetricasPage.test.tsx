import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import AdminMetricasPage from "@/app/admin/metricas/page";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import * as metricsApi from "@/lib/api/metrics";

describe("AdminMetricasPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({ user: null, token: null });
  });

  it("renderiza aviso de acesso restrito se o usuário não for Administrador", () => {
    useAuthStore.setState({
      user: {
        id: 2,
        nome: "João Cliente",
        email: "joao@example.com",
        perfil: "Cliente",
      },
      token: "mock-token",
    });

    render(<AdminMetricasPage />);
    expect(screen.getByText("Acesso Restrito ao Administrador")).toBeInTheDocument();
  });

  it("renderiza cards de resumo e tabela diária quando logado como admin", async () => {
    useAuthStore.setState({
      user: {
        id: 1,
        nome: "Admin Teste",
        email: "admin@example.com",
        perfil: "Admin",
      },
      token: "mock-token",
    });

    const mockResponse: metricsApi.TokenCostMetricsResponse = {
      period: "7d",
      summary: {
        total_closed_chats: 12,
        total_internal_prompt_tokens: 5000,
        total_internal_completion_tokens: 2000,
        total_external_prompt_tokens: 1500,
        total_external_completion_tokens: 800,
        total_cost_prompt_usd: 0.0045,
        total_cost_completion_usd: 0.0032,
        total_cost_usd: 0.0077,
      },
      daily_breakdown: [
        {
          date: "2026-10-03",
          closed_chats_count: 5,
          internal_prompt_tokens: 2000,
          internal_completion_tokens: 800,
          external_prompt_tokens: 600,
          external_completion_tokens: 300,
          cost_prompt_usd: 0.0018,
          cost_completion_usd: 0.0012,
          total_cost_usd: 0.0030,
        },
      ],
    };

    const spy = vi.spyOn(metricsApi, "fetchTokenCostMetrics").mockResolvedValue(mockResponse);

    render(<AdminMetricasPage />);

    await waitFor(() => {
      expect(screen.getByText("Métricas & Custos de IA")).toBeInTheDocument();
      expect(screen.getByText("Tokens Internos (GPU Local)")).toBeInTheDocument();
      expect(screen.getByText("Tokens Externos (OpenRouter)")).toBeInTheDocument();
      expect(screen.getByText("$0.0077")).toBeInTheDocument();
      expect(screen.getByText("2026-10-03")).toBeInTheDocument();
    });

    expect(spy).toHaveBeenCalledWith({ period: "7d" });
  });

  it("permite alternar período de filtro", async () => {
    useAuthStore.setState({
      user: {
        id: 1,
        nome: "Admin Teste",
        email: "admin@example.com",
        perfil: "Admin",
      },
      token: "mock-token",
    });

    const mockResponse: metricsApi.TokenCostMetricsResponse = {
      period: "today",
      summary: {
        total_closed_chats: 2,
        total_internal_prompt_tokens: 1000,
        total_internal_completion_tokens: 400,
        total_external_prompt_tokens: 200,
        total_external_completion_tokens: 100,
        total_cost_prompt_usd: 0.0006,
        total_cost_completion_usd: 0.0004,
        total_cost_usd: 0.0010,
      },
      daily_breakdown: [],
    };

    const spy = vi.spyOn(metricsApi, "fetchTokenCostMetrics").mockResolvedValue(mockResponse);

    render(<AdminMetricasPage />);

    await waitFor(() => {
      expect(screen.getByText("Métricas & Custos de IA")).toBeInTheDocument();
    });

    const hojeButton = screen.getByRole("button", { name: "Hoje" });
    fireEvent.click(hojeButton);

    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith({ period: "today" });
    });
  });

  it("atualiza métricas ao clicar no botão Atualizar e exibe feedback de sucesso e timestamp", async () => {
    useAuthStore.setState({
      user: {
        id: 1,
        nome: "Admin Teste",
        email: "admin@example.com",
        perfil: "Admin",
      },
      token: "mock-token",
    });

    const mockResponse: metricsApi.TokenCostMetricsResponse = {
      period: "7d",
      summary: {
        total_closed_chats: 5,
        total_internal_prompt_tokens: 100,
        total_internal_completion_tokens: 50,
        total_external_prompt_tokens: 0,
        total_external_completion_tokens: 0,
        total_cost_prompt_usd: 0,
        total_cost_completion_usd: 0,
        total_cost_usd: 0,
      },
      daily_breakdown: [],
    };

    const spy = vi.spyOn(metricsApi, "fetchTokenCostMetrics").mockResolvedValue(mockResponse);

    render(<AdminMetricasPage />);

    await waitFor(() => {
      expect(screen.getByText("Métricas & Custos de IA")).toBeInTheDocument();
    });

    expect(spy).toHaveBeenCalledTimes(1);

    const atualizarButtons = screen.getAllByRole("button", { name: /atualizar métricas/i });
    expect(atualizarButtons.length).toBeGreaterThan(0);

    fireEvent.click(atualizarButtons[0]);

    await waitFor(() => {
      expect(spy).toHaveBeenCalledTimes(2);
      expect(screen.getByText("Métricas atualizadas com sucesso!")).toBeInTheDocument();
      expect(screen.getByText(/Última atualização:/i)).toBeInTheDocument();
    });
  });

  it("exibe feedback de erro ao falhar na atualização manual", async () => {
    useAuthStore.setState({
      user: {
        id: 1,
        nome: "Admin Teste",
        email: "admin@example.com",
        perfil: "Admin",
      },
      token: "mock-token",
    });

    const mockResponse: metricsApi.TokenCostMetricsResponse = {
      period: "7d",
      summary: {
        total_closed_chats: 1,
        total_internal_prompt_tokens: 10,
        total_internal_completion_tokens: 10,
        total_external_prompt_tokens: 0,
        total_external_completion_tokens: 0,
        total_cost_prompt_usd: 0,
        total_cost_completion_usd: 0,
        total_cost_usd: 0,
      },
      daily_breakdown: [],
    };

    const spy = vi
      .spyOn(metricsApi, "fetchTokenCostMetrics")
      .mockResolvedValueOnce(mockResponse)
      .mockRejectedValueOnce(new Error("Falha de conexão com a API"));

    render(<AdminMetricasPage />);

    await waitFor(() => {
      expect(screen.getByText("Métricas & Custos de IA")).toBeInTheDocument();
    });

    const atualizarBtn = screen.getByRole("button", { name: "Atualizar métricas" });
    fireEvent.click(atualizarBtn);

    await waitFor(() => {
      expect(screen.getAllByText("Falha de conexão com a API").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("permite filtrar por dia específico abrindo seletor de data e calendário", async () => {
    useAuthStore.setState({
      user: {
        id: 1,
        nome: "Admin Teste",
        email: "admin@example.com",
        perfil: "Admin",
      },
      token: "mock-token",
    });

    const mockInitial: metricsApi.TokenCostMetricsResponse = {
      period: "7d",
      summary: {
        total_closed_chats: 10,
        total_internal_prompt_tokens: 500,
        total_internal_completion_tokens: 200,
        total_external_prompt_tokens: 100,
        total_external_completion_tokens: 50,
        total_cost_prompt_usd: 0.001,
        total_cost_completion_usd: 0.0005,
        total_cost_usd: 0.0015,
      },
      daily_breakdown: [],
    };

    const mockDay: metricsApi.TokenCostMetricsResponse = {
      period: "custom",
      summary: {
        total_closed_chats: 3,
        total_internal_prompt_tokens: 150,
        total_internal_completion_tokens: 60,
        total_external_prompt_tokens: 30,
        total_external_completion_tokens: 15,
        total_cost_prompt_usd: 0.0003,
        total_cost_completion_usd: 0.0001,
        total_cost_usd: 0.0004,
      },
      daily_breakdown: [
        {
          date: "2026-10-02",
          closed_chats_count: 3,
          internal_prompt_tokens: 150,
          internal_completion_tokens: 60,
          external_prompt_tokens: 30,
          external_completion_tokens: 15,
          cost_prompt_usd: 0.0003,
          cost_completion_usd: 0.0001,
          total_cost_usd: 0.0004,
        },
      ],
    };

    const spy = vi
      .spyOn(metricsApi, "fetchTokenCostMetrics")
      .mockResolvedValueOnce(mockInitial)
      .mockResolvedValue(mockDay);

    render(<AdminMetricasPage />);

    await waitFor(() => {
      expect(screen.getByText("Métricas & Custos de IA")).toBeInTheDocument();
    });

    const porDiaBtn = screen.getByRole("button", { name: /por dia/i });
    fireEvent.click(porDiaBtn);

    const dateInput = await screen.findByLabelText(/escolher data específica/i);
    expect(dateInput).toBeInTheDocument();

    fireEvent.change(dateInput, { target: { value: "2026-10-02" } });

    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith({
        period: "custom",
        startDate: "2026-10-02",
        endDate: "2026-10-02",
      });
      expect(screen.getByText("Visualizando dia: 02/10/2026")).toBeInTheDocument();
      expect(screen.getByText("2026-10-02")).toBeInTheDocument();
    });
  });
});
