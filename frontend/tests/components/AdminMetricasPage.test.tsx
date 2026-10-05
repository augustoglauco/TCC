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
        total_vision_calls: 2,
        total_vision_tokens: 1500,
        total_vision_cost_usd: 0.0025,
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
          vision_calls_count: 2,
          vision_cost_usd: 0.0025,
        },
      ],
    };

    const spy = vi.spyOn(metricsApi, "fetchTokenCostMetrics").mockResolvedValue(mockResponse);

    render(<AdminMetricasPage />);

    await waitFor(() => {
      expect(screen.getByText("Métricas & Custos de IA")).toBeInTheDocument();
      expect(screen.getByText("Tokens Internos (GPU Local)")).toBeInTheDocument();
      expect(screen.getByText("Tokens Externos (OpenRouter)")).toBeInTheDocument();
      expect(screen.getByText("Visão Computacional (Imagens)")).toBeInTheDocument();
      expect(screen.getByText("$0.0025")).toBeInTheDocument();
      expect(screen.getByText("Visão (Imagens / Custo)")).toBeInTheDocument();
      expect(screen.getByText("2 imagens")).toBeInTheDocument();
      expect(screen.getByText("$0.0077")).toBeInTheDocument();
      expect(screen.getByText("2026-10-03")).toBeInTheDocument();
    });

    expect(spy).toHaveBeenCalledWith("mock-token", { period: "7d" });
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
      expect(spy).toHaveBeenCalledWith("mock-token", { period: "today" });
    });
  });

  it("ignora resposta desatualizada quando a requisição mais antiga resolve depois da mais nova", async () => {
    // Achado da revisão de 2026-10-04: sem controle de sequência, uma
    // requisição mais antiga ("7d", disparada no mount) que demora mais do
    // que a requisição mais nova ("Hoje", disparada pelo clique) podia
    // resolver depois e sobrescrever a tela com dados do período errado.
    useAuthStore.setState({
      user: {
        id: 1,
        nome: "Admin Teste",
        email: "admin@example.com",
        perfil: "Admin",
      },
      token: "mock-token",
    });

    function buildResponse(totalClosedChats: number): metricsApi.TokenCostMetricsResponse {
      return {
        period: "x",
        summary: {
          total_closed_chats: totalClosedChats,
          total_internal_prompt_tokens: 0,
          total_internal_completion_tokens: 0,
          total_external_prompt_tokens: 0,
          total_external_completion_tokens: 0,
          total_cost_prompt_usd: 0,
          total_cost_completion_usd: 0,
          total_cost_usd: 0,
        },
        daily_breakdown: [],
      };
    }

    let resolveOld: (v: metricsApi.TokenCostMetricsResponse) => void;
    const oldRequest = new Promise<metricsApi.TokenCostMetricsResponse>((resolve) => {
      resolveOld = resolve;
    });

    const spy = vi
      .spyOn(metricsApi, "fetchTokenCostMetrics")
      .mockImplementationOnce(() => oldRequest) // requisição inicial (7d, mount)
      .mockResolvedValueOnce(buildResponse(99)); // requisição disparada pelo clique em "Hoje"

    render(<AdminMetricasPage />);

    await waitFor(() => {
      expect(spy).toHaveBeenCalledTimes(1);
    });

    const hojeButton = screen.getByRole("button", { name: "Hoje" });
    fireEvent.click(hojeButton);

    await waitFor(() => {
      expect(screen.getByText("99")).toBeInTheDocument();
    });

    // A requisição antiga ("7d") só resolve agora — não deve sobrescrever
    // os dados de "Hoje" já exibidos.
    resolveOld!(buildResponse(1));

    await new Promise((r) => setTimeout(r, 50));
    expect(screen.getByText("99")).toBeInTheDocument();
    expect(screen.queryByText("1")).not.toBeInTheDocument();
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

    const dateInput = screen.getByLabelText(/escolher data específica/i);
    expect(dateInput).toBeInTheDocument();
    expect(screen.getByText("Calendário")).toBeInTheDocument();

    fireEvent.click(dateInput);
    fireEvent.change(dateInput, { target: { value: "2026-10-02" } });

    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith("mock-token", {
        period: "custom",
        startDate: "2026-10-02",
        endDate: "2026-10-02",
      });
      expect(screen.getAllByText(/02\/10\/2026/).length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("2026-10-02")).toBeInTheDocument();
    });
  });

  it("exibe segregação financeira de visão computacional no card de resumo e coluna da tabela", async () => {
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
        total_closed_chats: 4,
        total_internal_prompt_tokens: 1000,
        total_internal_completion_tokens: 500,
        total_external_prompt_tokens: 3500,
        total_external_completion_tokens: 1200,
        total_cost_prompt_usd: 0.0035,
        total_cost_completion_usd: 0.0020,
        total_cost_usd: 0.0055,
        total_vision_calls: 3,
        total_vision_tokens: 2800,
        total_vision_cost_usd: 0.0042,
      },
      daily_breakdown: [
        {
          date: "2026-10-04",
          closed_chats_count: 4,
          internal_prompt_tokens: 1000,
          internal_completion_tokens: 500,
          external_prompt_tokens: 3500,
          external_completion_tokens: 1200,
          cost_prompt_usd: 0.0035,
          cost_completion_usd: 0.0020,
          total_cost_usd: 0.0055,
          vision_calls_count: 3,
          vision_cost_usd: 0.0042,
        },
      ],
    };

    vi.spyOn(metricsApi, "fetchTokenCostMetrics").mockResolvedValue(mockResponse);

    render(<AdminMetricasPage />);

    await waitFor(() => {
      // Card de Visão
      expect(screen.getByText("Visão Computacional (Imagens)")).toBeInTheDocument();
      expect(screen.getByText("$0.0042")).toBeInTheDocument();
      expect(screen.getByText("Imagens: 3")).toBeInTheDocument();
      expect(screen.getByText("Tokens: 2.800")).toBeInTheDocument();

      // Coluna e linha da tabela diária
      expect(screen.getByText("Visão (Imagens / Custo)")).toBeInTheDocument();
      expect(screen.getByText("3 imagens")).toBeInTheDocument();
      expect(screen.getByText("($0.0042)")).toBeInTheDocument();
    });
  });

  it("exibe card de ingestão de dados e consolidação do custo total da infraestrutura", async () => {
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
        total_closed_chats: 4,
        total_internal_prompt_tokens: 1000,
        total_internal_completion_tokens: 500,
        total_external_prompt_tokens: 3500,
        total_external_completion_tokens: 1200,
        total_cost_prompt_usd: 0.0035,
        total_cost_completion_usd: 0.0020,
        total_cost_usd: 0.0055,
        total_vision_calls: 3,
        total_vision_tokens: 2800,
        total_vision_cost_usd: 0.0042,
        total_ingestion_calls: 5,
        total_ingestion_tokens: 3500,
        total_ingestion_cost_usd: 0.0050,
        grand_total_cost_usd: 0.0105,
      },
      daily_breakdown: [
        {
          date: "2026-10-04",
          closed_chats_count: 4,
          internal_prompt_tokens: 1000,
          internal_completion_tokens: 500,
          external_prompt_tokens: 3500,
          external_completion_tokens: 1200,
          cost_prompt_usd: 0.0035,
          cost_completion_usd: 0.0020,
          total_cost_usd: 0.0055,
          vision_calls_count: 3,
          vision_cost_usd: 0.0042,
          ingestion_calls_count: 5,
          ingestion_cost_usd: 0.0050,
        },
      ],
    };

    vi.spyOn(metricsApi, "fetchTokenCostMetrics").mockResolvedValue(mockResponse);

    render(<AdminMetricasPage />);

    await waitFor(() => {
      // Card Ingestão & Dados
      expect(screen.getByText("Ingestão & Dados (Crawler/Catálogo)")).toBeInTheDocument();
      expect(screen.getByText("$0.0050")).toBeInTheDocument();
      expect(screen.getByText("Operações: 5")).toBeInTheDocument();
      expect(screen.getByText("Tokens: 3.500")).toBeInTheDocument();

      // Card Custo Total Geral Consolidado (Atendimentos + Ingestão)
      expect(screen.getByText("Custo Total Geral (Infraestrutura)")).toBeInTheDocument();
      expect(screen.getByText("$0.0105")).toBeInTheDocument();
      expect(screen.getByText("Atendimento: $0.0055")).toBeInTheDocument();
      expect(screen.getByText("Ingestão: $0.0050")).toBeInTheDocument();

      // Tabela diária: coluna de ingestão
      expect(screen.getByText("Ingestão (Op / Custo)")).toBeInTheDocument();
      expect(screen.getByText("5 ops")).toBeInTheDocument();
    });
  });

  it("preenche todas as linhas do período selecionado e exibe data formatada com dia da semana sem corte", async () => {
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
        total_closed_chats: 2,
        total_internal_prompt_tokens: 500,
        total_internal_completion_tokens: 200,
        total_external_prompt_tokens: 0,
        total_external_completion_tokens: 0,
        total_cost_prompt_usd: 0,
        total_cost_completion_usd: 0,
        total_cost_usd: 0,
      },
      daily_breakdown: [
        {
          date: "2026-10-05",
          closed_chats_count: 2,
          internal_prompt_tokens: 500,
          internal_completion_tokens: 200,
          external_prompt_tokens: 0,
          external_completion_tokens: 0,
          cost_prompt_usd: 0,
          cost_completion_usd: 0,
          total_cost_usd: 0,
        },
      ],
    };

    vi.spyOn(metricsApi, "fetchTokenCostMetrics").mockResolvedValue(mockResponse);

    render(<AdminMetricasPage />);

    await waitFor(() => {
      // Badge indicando 7 dias na tabela
      expect(screen.getByText("7 dias")).toBeInTheDocument();

      // Data formatada em padrão brasileiro (05/10/2026) e ISO
      expect(screen.getByText("05/10/2026")).toBeInTheDocument();
      expect(screen.getByText("2026-10-05")).toBeInTheDocument();
      expect(screen.getByText(/Segunda/)).toBeInTheDocument();

      // Linhas dos dias anteriores preenchidas
      expect(screen.getByText("04/10/2026")).toBeInTheDocument();
      expect(screen.getByText("03/10/2026")).toBeInTheDocument();
      expect(screen.getByText("02/10/2026")).toBeInTheDocument();
      expect(screen.getByText("01/10/2026")).toBeInTheDocument();
      expect(screen.getByText("30/09/2026")).toBeInTheDocument();
      expect(screen.getByText("29/09/2026")).toBeInTheDocument();
    });
  });
});
