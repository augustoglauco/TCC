import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import type { ReactNode } from "react";
import AvaliacaoPage from "@/app/avaliacao/page";
import * as avaliacaoApi from "@/lib/api/avaliacao";
import type { ResultadosAvaliacao } from "@/lib/api/avaliacao";

vi.mock("recharts", async () => {
  const original = await vi.importActual<typeof import("recharts")>("recharts");
  return {
    ...original,
    ResponsiveContainer: ({ children }: { children?: ReactNode }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
  };
});

const PROPORCAO_PADRAO: avaliacaoApi.Proporcao = {
  acertos: 80,
  total: 100,
  taxa: 0.8,
  ic_inf: 0.71,
  ic_sup: 0.87,
};

const DADOS_COMPLETOS: ResultadosAvaliacao = {
  roteador: {
    dominios: ["vendas", "suporte", "atendimento", "agendamento"],
    provedores: [
      {
        provider: "heuristica",
        acuracia: PROPORCAO_PADRAO,
        latencia_media_s: 0.12,
        degradacoes: 0,
        matriz_confusao: {
          vendas: { vendas: 18, suporte: 2 },
          suporte: { suporte: 20 },
          atendimento: { atendimento: 19, vendas: 1 },
          agendamento: { agendamento: 20 },
        },
      },
      {
        provider: "jev_openrouter",
        acuracia: { acertos: 90, total: 100, taxa: 0.9, ic_inf: 0.82, ic_sup: 0.95 },
        latencia_media_s: 1.4,
        degradacoes: 1,
        matriz_confusao: {
          vendas: { vendas: 20 },
          suporte: { suporte: 20 },
          atendimento: { atendimento: 20 },
          agendamento: { agendamento: 20 },
        },
      },
    ],
  },
  rag: {
    total: 180,
    nota_media: 3.8,
    fonte_correta: PROPORCAO_PADRAO,
    nota_media_fonte_certa: 4.2,
    nota_media_fonte_errada: 2.1,
    distribuicao_notas: { "1": 5, "2": 10, "3": 40, "4": 80, "5": 45 },
    por_dificuldade: [
      { dificuldade: "facil", total: 60, nota_media: 4.5 },
      { dificuldade: "medio", total: 80, nota_media: 3.7 },
      { dificuldade: "dificil", total: 40, nota_media: 2.9 },
    ],
  },
  chunk_size: {
    pontos: [
      { chunk_size: 400, nota_media: 3.2, fonte_correta_taxa: 0.7 },
      { chunk_size: 800, nota_media: 3.8, fonte_correta_taxa: 0.8 },
      { chunk_size: 1200, nota_media: 3.5, fonte_correta_taxa: 0.75 },
    ],
    melhor_chunk_size: 800,
  },
  injecao: {
    clientes: [
      {
        cliente: "heuristica",
        resistencia: PROPORCAO_PADRAO,
        por_categoria: [
          { categoria: "role_override", total: 10, comprometidos: 2 },
          { categoria: "data_exfil", total: 10, comprometidos: 1 },
        ],
      },
    ],
  },
  modelos: [
    {
      modelo: "qwen3:14b-q4",
      gerado_em: "2026-10-17T10:00:00Z",
      config: {},
      metricas: {
        latencia_p95_s: 4.2,
        rag_nota_media: 3.9,
        roteador_acuracia: 0.85,
        injecao_resistencia: 0.9,
      },
    },
    {
      modelo: "gemma4:12b-q4",
      gerado_em: "2026-10-17T11:00:00Z",
      config: {},
      metricas: {
        latencia_p95_s: 3.1,
        rag_nota_media: 3.7,
        roteador_acuracia: 0.82,
        injecao_resistencia: null,
      },
    },
  ],
};

const DADOS_VAZIOS: ResultadosAvaliacao = {
  roteador: null,
  rag: null,
  chunk_size: null,
  injecao: null,
  modelos: [],
};

describe("AvaliacaoPage — estados de carregamento e erro", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("exibe 'Carregando resultados' enquanto a requisição está pendente", () => {
    vi.spyOn(avaliacaoApi, "fetchResultadosAvaliacao").mockReturnValue(new Promise(() => {}));
    render(<AvaliacaoPage />);
    expect(screen.getByText(/Carregando resultados/)).toBeInTheDocument();
  });

  it("exibe a mensagem de erro quando fetchResultadosAvaliacao rejeita", async () => {
    vi.spyOn(avaliacaoApi, "fetchResultadosAvaliacao").mockRejectedValue(
      new Error("Falha ao carregar os resultados (HTTP 500)."),
    );
    render(<AvaliacaoPage />);
    expect(
      await screen.findByText("Falha ao carregar os resultados (HTTP 500)."),
    ).toBeInTheDocument();
  });

  it("exibe o título principal após carregar com sucesso", async () => {
    vi.spyOn(avaliacaoApi, "fetchResultadosAvaliacao").mockResolvedValue(DADOS_COMPLETOS);
    render(<AvaliacaoPage />);
    expect(
      await screen.findByText("Resultados da avaliação experimental"),
    ).toBeInTheDocument();
  });
});

describe("AvaliacaoPage — seções vazias (dados null / modelos [])", () => {
  beforeEach(() => {
    vi.spyOn(avaliacaoApi, "fetchResultadosAvaliacao").mockResolvedValue(DADOS_VAZIOS);
  });

  it("exibe o comando de benchmark quando modelos está vazio", async () => {
    render(<AvaliacaoPage />);
    await screen.findByText("Resultados da avaliação experimental");
    expect(
      screen.getByText(/python eval\/model_benchmark\/run_benchmark\.py/),
    ).toBeInTheDocument();
  });

  it("exibe o comando do roteador quando roteador é null", async () => {
    render(<AvaliacaoPage />);
    await screen.findByText("Resultados da avaliação experimental");
    expect(screen.getByText(/python eval\/router_intents\/run_eval\.py/)).toBeInTheDocument();
  });

  it("exibe o comando do RAG quando rag é null", async () => {
    render(<AvaliacaoPage />);
    await screen.findByText("Resultados da avaliação experimental");
    expect(screen.getByText(/python eval\/rag_quality\/run_eval\.py/)).toBeInTheDocument();
  });

  it("exibe o comando de chunk_size quando chunk_size é null", async () => {
    render(<AvaliacaoPage />);
    await screen.findByText("Resultados da avaliação experimental");
    expect(
      screen.getByText(/python eval\/rag_quality\/chunk_size_search\.py/),
    ).toBeInTheDocument();
  });

  it("exibe o comando de injeção quando injecao é null", async () => {
    render(<AvaliacaoPage />);
    await screen.findByText("Resultados da avaliação experimental");
    expect(
      screen.getByText(/python eval\/prompt_injection\/run_eval\.py/),
    ).toBeInTheDocument();
  });
});

describe("AvaliacaoPage — seção Roteador com dados", () => {
  beforeEach(() => {
    vi.spyOn(avaliacaoApi, "fetchResultadosAvaliacao").mockResolvedValue(DADOS_COMPLETOS);
  });

  it("renderiza os gráficos do roteador (ResponsiveContainer)", async () => {
    render(<AvaliacaoPage />);
    await screen.findByText("Roteador de intenções");
    expect(screen.getAllByTestId("responsive-container").length).toBeGreaterThan(0);
  });

  it("exibe o select de provedor com os dois provedores", async () => {
    render(<AvaliacaoPage />);
    await screen.findByText("Roteador de intenções");
    const select = screen.getByRole("combobox");
    expect(select).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "heuristica" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "jev_openrouter" })).toBeInTheDocument();
  });

  it("o último provedor fica selecionado por padrão", async () => {
    render(<AvaliacaoPage />);
    await screen.findByText("Roteador de intenções");
    expect(screen.getByRole("combobox")).toHaveValue("jev_openrouter");
  });

  it("trocar o select de provedor atualiza a seleção", async () => {
    const user = userEvent.setup();
    render(<AvaliacaoPage />);
    await screen.findByText("Roteador de intenções");
    await user.selectOptions(screen.getByRole("combobox"), "heuristica");
    expect(screen.getByRole("combobox")).toHaveValue("heuristica");
  });

  it("renderiza a matriz de confusão com os domínios como cabeçalhos", async () => {
    render(<AvaliacaoPage />);
    await screen.findByText("Roteador de intenções");
    // Os 4 domínios aparecem como th na tabela
    expect(screen.getAllByText("vendas").length).toBeGreaterThan(0);
    expect(screen.getAllByText("suporte").length).toBeGreaterThan(0);
  });
});

describe("AvaliacaoPage — seção RAG com dados", () => {
  beforeEach(() => {
    vi.spyOn(avaliacaoApi, "fetchResultadosAvaliacao").mockResolvedValue(DADOS_COMPLETOS);
  });

  it("exibe o total de perguntas no cartão", async () => {
    render(<AvaliacaoPage />);
    await screen.findByText("Qualidade do RAG");
    expect(screen.getByText("180")).toBeInTheDocument();
  });

  it("exibe a nota média formatada com 2 casas", async () => {
    render(<AvaliacaoPage />);
    await screen.findByText("Qualidade do RAG");
    expect(screen.getByText("3.80")).toBeInTheDocument();
  });

  it("exibe a taxa de fonte correta em %", async () => {
    render(<AvaliacaoPage />);
    await screen.findByText("Qualidade do RAG");
    // pct(0.8) = 80.0 → "80%"
    expect(screen.getByText("80%")).toBeInTheDocument();
  });

  it("exibe notas com/sem fonte correta no cartão combinado", async () => {
    render(<AvaliacaoPage />);
    await screen.findByText("Qualidade do RAG");
    // "4.2 × 2.1"
    expect(screen.getByText("4.2 × 2.1")).toBeInTheDocument();
  });
});

describe("AvaliacaoPage — seção Modelos com dados", () => {
  beforeEach(() => {
    vi.spyOn(avaliacaoApi, "fetchResultadosAvaliacao").mockResolvedValue(DADOS_COMPLETOS);
  });

  it("renderiza gráficos de scatter e barras para os modelos", async () => {
    render(<AvaliacaoPage />);
    await screen.findByText("Comparativo de modelos locais");
    expect(screen.getAllByTestId("responsive-container").length).toBeGreaterThanOrEqual(2);
  });
});

describe("AvaliacaoPage — seção Injeção com dados", () => {
  beforeEach(() => {
    vi.spyOn(avaliacaoApi, "fetchResultadosAvaliacao").mockResolvedValue(DADOS_COMPLETOS);
  });

  it("exibe as categorias da tabela de injeção", async () => {
    render(<AvaliacaoPage />);
    await screen.findByText("Resistência a prompt injection");
    expect(screen.getByText("role_override")).toBeInTheDocument();
    expect(screen.getByText("data_exfil")).toBeInTheDocument();
  });

  it("exibe o cliente e os comprometidos na tabela", async () => {
    render(<AvaliacaoPage />);
    await screen.findByText("Resistência a prompt injection");
    expect(screen.getAllByText("heuristica").length).toBeGreaterThan(0);
    expect(screen.getByText("2")).toBeInTheDocument(); // comprometidos role_override
  });
});

describe("AvaliacaoPage — seção Chunk Size com dados", () => {
  beforeEach(() => {
    vi.spyOn(avaliacaoApi, "fetchResultadosAvaliacao").mockResolvedValue(DADOS_COMPLETOS);
  });

  it("renderiza o gráfico de linha para chunk_size", async () => {
    render(<AvaliacaoPage />);
    await screen.findByText("Tamanho de chunk");
    expect(screen.getAllByTestId("responsive-container").length).toBeGreaterThan(0);
  });
});

describe("AvaliacaoPage — RAG com nota_media null", () => {
  it("exibe '—' quando nota_media é null", async () => {
    vi.spyOn(avaliacaoApi, "fetchResultadosAvaliacao").mockResolvedValue({
      ...DADOS_COMPLETOS,
      rag: { ...DADOS_COMPLETOS.rag!, nota_media: null },
    });
    render(<AvaliacaoPage />);
    await screen.findByText("Qualidade do RAG");
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});

describe("AvaliacaoPage — fetchResultadosAvaliacao chamado ao montar", () => {
  it("chama fetchResultadosAvaliacao ao montar e exibe o título", async () => {
    vi.restoreAllMocks();
    const spy = vi
      .spyOn(avaliacaoApi, "fetchResultadosAvaliacao")
      .mockResolvedValue(DADOS_VAZIOS);
    render(<AvaliacaoPage />);
    await screen.findByText("Resultados da avaliação experimental");
    expect(spy).toHaveBeenCalled();
  });
});
