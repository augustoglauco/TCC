import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import AdminMetricasPage from "@/app/admin/metricas/page";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import * as metricsApi from "@/lib/api/metrics";

function bloco(over: Partial<metricsApi.BlocoMetricas> = {}): metricsApi.BlocoMetricas {
  return {
    chamadas: 1,
    tokens_entrada: 100,
    tokens_saida: 10,
    custo_usd: 0.001,
    chamadas_sem_custo_medido: 0,
    ...over,
  };
}

const mockResponse: metricsApi.AiUsageReport = {
  period: "7d",
  atendimento: { chats_encerrados: 12 },
  totais: bloco({ chamadas: 7, custo_usd: 0.0065, tokens_entrada: 2400, tokens_saida: 190, chamadas_sem_custo_medido: 1 }),
  por_origem: [
    { origem: "chat", ...bloco({ chamadas: 4, custo_usd: 0.0025 }) },
    { origem: "b2b", ...bloco({ chamadas: 1, custo_usd: 0.0 }) },
    { origem: "admin", ...bloco({ chamadas: 2, custo_usd: 0.004 }) },
  ],
  por_ambiente: [
    { ambiente: "interno", ...bloco({ chamadas: 3, custo_usd: 0.0, tokens_entrada: null, tokens_saida: null }) },
    { ambiente: "externo", ...bloco({ chamadas: 4, custo_usd: 0.0065 }) },
  ],
  por_modelo: [
    { modelo: "gemma-vision", ambiente: "externo", ...bloco({ chamadas: 2, custo_usd: 0.0065 }) },
    { modelo: "clip", ambiente: "interno", ...bloco({ chamadas: 2, custo_usd: 0.0, tokens_entrada: null, tokens_saida: null }) },
    { modelo: "gpt-desconhecido", ambiente: "externo", ...bloco({ chamadas: 1, custo_usd: null, chamadas_sem_custo_medido: 1 }) },
  ],
  por_operacao: [
    { operacao: "identificacao_imagem_clip", origem: "chat", ambiente: "interno", ...bloco({ chamadas: 2, custo_usd: 0.0 }) },
    { operacao: "identificacao_imagem_visao_externa", origem: "chat", ambiente: "externo", ...bloco({ chamadas: 1, custo_usd: 0.0025 }) },
    { operacao: "classificacao_crawler", origem: "admin", ambiente: "externo", ...bloco({ chamadas: 2, custo_usd: 0.004 }) },
  ],
  diario: [
    {
      data: "2026-10-08",
      chats_encerrados: 7,
      totais: bloco({ chamadas: 5, custo_usd: 0.005 }),
      por_origem: [{ origem: "chat", ...bloco({ chamadas: 5, custo_usd: 0.005 }) }],
    },
    {
      data: "2026-10-07",
      chats_encerrados: 5,
      totais: bloco({ chamadas: 2, custo_usd: 0.0015 }),
      por_origem: [{ origem: "admin", ...bloco({ chamadas: 2, custo_usd: 0.0015 }) }],
    },
  ],
};

function logarComoAdmin() {
  useAuthStore.setState({
    user: { id: 1, nome: "Admin Teste", email: "admin@example.com", perfil: "Admin" },
    token: "mock-token",
  });
}

describe("AdminMetricasPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({ user: null, token: null });
  });

  it("renderiza aviso de acesso restrito se o usuário não for Administrador", () => {
    useAuthStore.setState({
      user: { id: 2, nome: "João Cliente", email: "joao@example.com", perfil: "Cliente" },
      token: "mock-token",
    });

    render(<AdminMetricasPage />);
    expect(screen.getByText("Acesso Restrito ao Administrador")).toBeInTheDocument();
  });

  it("renderiza as cinco seções do painel de uso de IA", async () => {
    logarComoAdmin();
    vi.spyOn(metricsApi, "fetchAiUsageMetrics").mockResolvedValue(mockResponse);

    render(<AdminMetricasPage />);

    await waitFor(() => {
      expect(screen.getByText(/Por Origem/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/Por Ambiente/i)).toBeInTheDocument();
    expect(screen.getByText(/Por Modelo/i)).toBeInTheDocument();
    expect(screen.getByText(/Por Operação/i)).toBeInTheDocument();
    expect(screen.getByText(/Detalhamento Diário/i)).toBeInTheDocument();
  });

  it("mostra custo não medido como traço e grátis como $0.0000", async () => {
    logarComoAdmin();
    vi.spyOn(metricsApi, "fetchAiUsageMetrics").mockResolvedValue(mockResponse);

    render(<AdminMetricasPage />);

    // `clip` (interno) tem custo 0.0 medido => $0.0000
    await waitFor(() => {
      expect(screen.getByTestId("custo-modelo-clip-interno")).toHaveTextContent("$0.0000");
    });
    // `gpt-desconhecido` tem custo null => traço, não "$0.0000"
    expect(screen.getByTestId("custo-modelo-gpt-desconhecido-externo")).toHaveTextContent("—");
  });

  it("mostra tokens não medidos como traço", async () => {
    logarComoAdmin();
    vi.spyOn(metricsApi, "fetchAiUsageMetrics").mockResolvedValue(mockResponse);

    render(<AdminMetricasPage />);

    await waitFor(() => {
      expect(screen.getByTestId("tokens-entrada-ambiente-interno")).toHaveTextContent("—");
    });
  });

  it("exibe as origens, operações e o volume de chats encerrados", async () => {
    logarComoAdmin();
    vi.spyOn(metricsApi, "fetchAiUsageMetrics").mockResolvedValue(mockResponse);

    render(<AdminMetricasPage />);

    await waitFor(() => {
      expect(screen.getByTestId("custo-origem-chat")).toHaveTextContent("$0.0025");
    });
    expect(screen.getByTestId("custo-origem-admin")).toHaveTextContent("$0.0040");
    expect(screen.getByText("classificacao_crawler")).toBeInTheDocument();
    expect(screen.getByTestId("chats-encerrados")).toHaveTextContent("12");
  });

  it("sinaliza quantas chamadas ficaram sem custo medido", async () => {
    logarComoAdmin();
    vi.spyOn(metricsApi, "fetchAiUsageMetrics").mockResolvedValue(mockResponse);

    render(<AdminMetricasPage />);

    await waitFor(() => {
      expect(screen.getByTestId("sem-custo-medido")).toHaveTextContent("1");
    });
  });

  it("mostra mensagem de erro quando a requisição falha", async () => {
    logarComoAdmin();
    vi.spyOn(metricsApi, "fetchAiUsageMetrics").mockRejectedValue(new Error("Falha ao obter métricas (503)"));

    render(<AdminMetricasPage />);

    await waitFor(() => {
      expect(screen.getByText(/Falha ao obter métricas/i)).toBeInTheDocument();
    });
  });
});
