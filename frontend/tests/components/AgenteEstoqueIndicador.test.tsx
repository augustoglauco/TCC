import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AgenteEstoqueIndicador } from "@/components/admin/products/AgenteEstoqueIndicador";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import type { StatusAgenteEstoque } from "@/lib/api/estoqueAgente";

vi.mock("@/lib/api/estoqueAgente", async () => {
  const actual =
    await vi.importActual<typeof import("@/lib/api/estoqueAgente")>("@/lib/api/estoqueAgente");
  return { ...actual, fetchStatusAgenteEstoque: vi.fn() };
});

import { fetchStatusAgenteEstoque } from "@/lib/api/estoqueAgente";

const mockedFetch = vi.mocked(fetchStatusAgenteEstoque);

const AGORA = new Date("2026-10-31T12:00:00Z");

function status(sobrescrever: Partial<StatusAgenteEstoque>): StatusAgenteEstoque {
  return {
    modo: "deterministico",
    llm: null,
    ultima_execucao: null,
    ultimo_alerta_em: null,
    ...sobrescrever,
  };
}

function execucao(sobrescrever: Partial<NonNullable<StatusAgenteEstoque["ultima_execucao"]>>) {
  return {
    criado_em: "2026-10-31T10:00:00Z",
    modo: "deterministico",
    produtos_avaliados: 3,
    alertas_criados: 1,
    erro: null,
    ...sobrescrever,
  };
}

describe("AgenteEstoqueIndicador", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"], now: AGORA });
    mockedFetch.mockReset();
    useAuthStore.setState({
      user: { id: 1, nome: "Admin Teste", email: "admin@empresa.com", perfil: "Admin" },
      token: "mock-token-1",
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("verde: ativo, com a última avaliação e o resultado", async () => {
    mockedFetch.mockResolvedValue(status({ ultima_execucao: execucao({}) }));

    render(<AgenteEstoqueIndicador />);

    const indicador = await screen.findByTestId("agente-estoque-indicador");
    expect(indicador).toHaveAttribute("data-estado", "ok");
    expect(indicador).toHaveTextContent("Agente de estoque ativo (determinístico)");
    expect(indicador).toHaveTextContent("última avaliação há 2 h");
    expect(indicador).toHaveTextContent("3 produtos avaliados, 1 alerta");
  });

  it("rodada sem alerta novo ainda mostra quando foi o último alerta (deduplicação de 24 h)", async () => {
    mockedFetch.mockResolvedValue(
      status({
        ultima_execucao: execucao({ produtos_avaliados: 1, alertas_criados: 0 }),
        ultimo_alerta_em: "2026-10-31T11:55:00Z",
      }),
    );

    render(<AgenteEstoqueIndicador />);

    const indicador = await screen.findByTestId("agente-estoque-indicador");
    expect(indicador).toHaveTextContent("1 produto avaliado, 0 alertas novos");
    expect(indicador).toHaveTextContent("último alerta há 5 min");
  });

  it("cinza: desativado, com o caminho para ativar", async () => {
    mockedFetch.mockResolvedValue(status({ modo: "desativado" }));

    render(<AgenteEstoqueIndicador />);

    const indicador = await screen.findByTestId("agente-estoque-indicador");
    expect(indicador).toHaveAttribute("data-estado", "desativado");
    expect(indicador).toHaveTextContent("Agente de estoque desativado");
    expect(screen.getByRole("link", { name: /Ativar/ })).toHaveAttribute("href", "/admin/modelos");
  });

  it("amarelo: ativo, mas ainda sem nenhuma avaliação", async () => {
    mockedFetch.mockResolvedValue(status({ ultima_execucao: null }));

    render(<AgenteEstoqueIndicador />);

    const indicador = await screen.findByTestId("agente-estoque-indicador");
    expect(indicador).toHaveAttribute("data-estado", "aguardando");
    expect(indicador).toHaveTextContent("aguardando o primeiro pedido");
  });

  it("vermelho: a última avaliação falhou, com o motivo", async () => {
    mockedFetch.mockResolvedValue(
      status({ ultima_execucao: execucao({ erro: "RuntimeError: banco fora do ar" }) }),
    );

    render(<AgenteEstoqueIndicador />);

    const indicador = await screen.findByTestId("agente-estoque-indicador");
    expect(indicador).toHaveAttribute("data-estado", "erro");
    expect(indicador).toHaveTextContent("última avaliação falhou");
    expect(indicador).toHaveAttribute("title", expect.stringContaining("banco fora do ar"));
  });

  it("mostra o LLM quando o modo é IA", async () => {
    mockedFetch.mockResolvedValue(
      status({ modo: "ia", llm: "externo", ultima_execucao: execucao({}) }),
    );

    render(<AgenteEstoqueIndicador />);

    expect(await screen.findByTestId("agente-estoque-indicador")).toHaveTextContent(
      "ativo (IA externa)",
    );
  });

  it("cinza: status indisponível quando a consulta falha", async () => {
    mockedFetch.mockRejectedValue(new Error("rede"));

    render(<AgenteEstoqueIndicador />);

    const indicador = await screen.findByTestId("agente-estoque-indicador");
    expect(indicador).toHaveAttribute("data-estado", "indisponivel");
  });
});
