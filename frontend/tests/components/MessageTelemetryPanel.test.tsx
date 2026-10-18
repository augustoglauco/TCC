import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MessageTelemetryPanel } from "@/components/chat/MessageTelemetryPanel";
import type { ChatUIMessage } from "@/lib/types/chat";

function makeMessage(overrides: Partial<ChatUIMessage> = {}): ChatUIMessage {
  return { id: "1", role: "assistant", text: "Resposta", ...overrides };
}

const BASE_PROPS = {
  domainLabel: null,
  isExternalLlm: false,
  calculatedTps: null,
  bubbleWidth: null,
};

describe("MessageTelemetryPanel — barra de métricas", () => {
  it("renderiza o data-testid message-metrics", () => {
    render(
      <MessageTelemetryPanel message={makeMessage()} {...BASE_PROPS} />,
    );
    expect(screen.getByTestId("message-metrics")).toBeInTheDocument();
  });

  it("exibe o nome do modelo quando metrics.modelName está preenchido", () => {
    render(
      <MessageTelemetryPanel
        message={makeMessage({ metrics: { modelName: "qwen3:14b" } })}
        {...BASE_PROPS}
      />,
    );
    expect(screen.getByTestId("message-metrics")).toHaveTextContent("qwen3:14b");
  });

  it("exibe 'Ollama (local)' como fallback quando não há modelName e isExternalLlm=false", () => {
    render(<MessageTelemetryPanel message={makeMessage()} {...BASE_PROPS} />);
    expect(screen.getByTestId("message-metrics")).toHaveTextContent("Ollama (local)");
  });

  it("exibe 'OpenRouter' como fallback quando isExternalLlm=true", () => {
    render(
      <MessageTelemetryPanel message={makeMessage()} {...BASE_PROPS} isExternalLlm={true} />,
    );
    expect(screen.getByTestId("message-metrics")).toHaveTextContent("OpenRouter");
  });

  it("exibe latência formatada em segundos", () => {
    render(
      <MessageTelemetryPanel
        message={makeMessage({ metrics: { latencyMs: 2340 } })}
        {...BASE_PROPS}
      />,
    );
    expect(screen.getByTestId("message-metrics")).toHaveTextContent("2.34s");
  });

  it("exibe TPS quando calculatedTps está preenchido", () => {
    render(
      <MessageTelemetryPanel
        message={makeMessage({ metrics: { modelName: "m" } })}
        {...BASE_PROPS}
        calculatedTps={42}
      />,
    );
    expect(screen.getByTestId("message-metrics")).toHaveTextContent("42 tok/s");
  });

  it("não exibe TPS quando calculatedTps é null", () => {
    render(<MessageTelemetryPanel message={makeMessage()} {...BASE_PROPS} />);
    expect(screen.getByTestId("message-metrics")).not.toHaveTextContent("tok/s");
  });
});

describe("MessageTelemetryPanel — SecaoRoteador", () => {
  it("exibe o backend correto para cada backendUsed", () => {
    const casos = [
      ["local", "Local (Ollama)"],
      ["externo", "Cloud (OpenRouter)"],
      ["resposta_fixa", "Resposta fixa (sem LLM)"],
      ["identificacao_imagem", "Identificação por imagem"],
    ] as const;

    for (const [backend, label] of casos) {
      const { unmount } = render(
        <MessageTelemetryPanel
          message={makeMessage({ backendUsed: backend })}
          {...BASE_PROPS}
        />,
      );
      expect(screen.getByText(label)).toBeInTheDocument();
      unmount();
    }
  });

  it("exibe o domínio quando domainLabel está preenchido", () => {
    render(
      <MessageTelemetryPanel
        message={makeMessage()}
        {...BASE_PROPS}
        domainLabel="Vendas"
      />,
    );
    expect(screen.getByText("Vendas")).toBeInTheDocument();
  });

  it("exibe '-' para domínio quando domainLabel é null", () => {
    render(<MessageTelemetryPanel message={makeMessage()} {...BASE_PROPS} />);
    // Domínio: - (há vários "-" no painel, verificamos que pelo menos um existe)
    expect(screen.getAllByText("-").length).toBeGreaterThan(0);
  });

  it("exibe o provedor TypeSafe Jev quando routerProvider=jev_openrouter", () => {
    render(
      <MessageTelemetryPanel
        message={makeMessage({ metrics: { routerProvider: "jev_openrouter" } })}
        {...BASE_PROPS}
      />,
    );
    expect(screen.getByText("TypeSafe Jev (OpenRouter)")).toBeInTheDocument();
  });

  it("exibe Heurística quando routerProvider=heuristica", () => {
    render(
      <MessageTelemetryPanel
        message={makeMessage({ metrics: { routerProvider: "heuristica" } })}
        {...BASE_PROPS}
      />,
    );
    expect(screen.getByText("Heurística (Palavras-chave)")).toBeInTheDocument();
  });

  it("não exibe linha de provedor quando routerProvider não está presente", () => {
    render(
      <MessageTelemetryPanel
        message={makeMessage({ metrics: { modelName: "m" } })}
        {...BASE_PROPS}
      />,
    );
    expect(screen.queryByText(/^Provedor:/)).not.toBeInTheDocument();
  });

  it("exibe perfil do usuário e motivo quando presentes", () => {
    render(
      <MessageTelemetryPanel
        message={makeMessage({
          metrics: { perfilUsuario: "lead", perfilMotivo: "intenção de compra" },
        })}
        {...BASE_PROPS}
      />,
    );
    expect(screen.getByText("Lead")).toBeInTheDocument();
    expect(screen.getByText("(intenção de compra)")).toBeInTheDocument();
  });

  it("não exibe linha de perfil quando perfilUsuario não está presente", () => {
    render(
      <MessageTelemetryPanel
        message={makeMessage({ metrics: { modelName: "m" } })}
        {...BASE_PROPS}
      />,
    );
    expect(screen.queryByText(/^Perfil:/)).not.toBeInTheDocument();
  });

  it("exibe confiança formatada em %", () => {
    render(
      <MessageTelemetryPanel
        message={makeMessage({ metrics: { confidence: 0.876 } })}
        {...BASE_PROPS}
      />,
    );
    expect(screen.getByText(/87\.6%/)).toBeInTheDocument();
  });
});

describe("MessageTelemetryPanel — SecaoDesempenho", () => {
  it("exibe latência total em ms", () => {
    render(
      <MessageTelemetryPanel
        message={makeMessage({ metrics: { latencyMs: 1500 } })}
        {...BASE_PROPS}
      />,
    );
    expect(screen.getByText("1500 ms")).toBeInTheDocument();
  });

  it("exibe TTFT em ms", () => {
    render(
      <MessageTelemetryPanel
        message={makeMessage({ metrics: { ttftMs: 320 } })}
        {...BASE_PROPS}
      />,
    );
    expect(screen.getByText("320 ms")).toBeInTheDocument();
  });

  it("calcula tempo de geração como latência - TTFT", () => {
    render(
      <MessageTelemetryPanel
        message={makeMessage({ metrics: { latencyMs: 2000, ttftMs: 500 } })}
        {...BASE_PROPS}
      />,
    );
    expect(screen.getByText("1500 ms")).toBeInTheDocument();
  });

  it("exibe TPS calculado no painel de desempenho", () => {
    render(
      <MessageTelemetryPanel
        message={makeMessage()}
        {...BASE_PROPS}
        calculatedTps={35}
      />,
    );
    expect(screen.getByText("35 tokens/s")).toBeInTheDocument();
  });
});

describe("MessageTelemetryPanel — SecaoTokens", () => {
  it("exibe tokens de prompt e completion", () => {
    render(
      <MessageTelemetryPanel
        message={makeMessage({ metrics: { promptTokens: 800, completionTokens: 120 } })}
        {...BASE_PROPS}
      />,
    );
    expect(screen.getByText(/800 tokens/)).toBeInTheDocument();
    expect(screen.getByText(/120 tokens/)).toBeInTheDocument();
  });

  it("exibe total de tokens como soma de prompt + completion", () => {
    render(
      <MessageTelemetryPanel
        message={makeMessage({ metrics: { promptTokens: 800, completionTokens: 120 } })}
        {...BASE_PROPS}
      />,
    );
    expect(screen.getByText("920 tokens")).toBeInTheDocument();
  });

  it("exibe custo estimado formatado", () => {
    render(
      <MessageTelemetryPanel
        message={makeMessage({ metrics: { estimatedCostUsd: 0.0072 } })}
        {...BASE_PROPS}
      />,
    );
    expect(screen.getByText("$0.007200")).toBeInTheDocument();
  });

  it("exibe '$0.000000 (Local)' quando estimatedCostUsd é undefined", () => {
    render(<MessageTelemetryPanel message={makeMessage()} {...BASE_PROPS} />);
    expect(screen.getByText("$0.000000 (Local)")).toBeInTheDocument();
  });

  it("exibe custos segregados de entrada e saída quando presentes", () => {
    render(
      <MessageTelemetryPanel
        message={makeMessage({
          metrics: { costPromptUsd: 0.006, costCompletionUsd: 0.0012 },
        })}
        {...BASE_PROPS}
      />,
    );
    expect(screen.getByText("$0.006000")).toBeInTheDocument();
    expect(screen.getByText("$0.001200")).toBeInTheDocument();
  });

  it("não exibe custos segregados quando não estão presentes", () => {
    render(<MessageTelemetryPanel message={makeMessage()} {...BASE_PROPS} />);
    expect(screen.queryByText("Custo Entrada (IN):")).not.toBeInTheDocument();
    expect(screen.queryByText("Custo Saída (OUT):")).not.toBeInTheDocument();
  });
});

describe("MessageTelemetryPanel — SecaoRag", () => {
  it("exibe tempo de busca RAG em ms", () => {
    render(
      <MessageTelemetryPanel
        message={makeMessage({ metrics: { ragRetrievalMs: 45 } })}
        {...BASE_PROPS}
      />,
    );
    expect(screen.getByText("45 ms")).toBeInTheDocument();
  });

  it("exibe 'N/A' quando ragRetrievalMs não está presente", () => {
    render(<MessageTelemetryPanel message={makeMessage()} {...BASE_PROPS} />);
    expect(screen.getAllByText("N/A").length).toBeGreaterThan(0);
  });

  it("exibe chunks usados e score médio", () => {
    render(
      <MessageTelemetryPanel
        message={makeMessage({ metrics: { ragChunksCount: 3, ragAvgScore: 0.8765 } })}
        {...BASE_PROPS}
      />,
    );
    expect(screen.getByText(/3\s+trechos/)).toBeInTheDocument();
    expect(screen.getByText("0.8765")).toBeInTheDocument();
  });

  it("lista as fontes dos chunks quando ragChunks está preenchido", () => {
    render(
      <MessageTelemetryPanel
        message={makeMessage({
          metrics: {
            ragChunks: [
              { source: "manual_v2.pdf", score: 0.91 },
              { source: "faq.pdf", score: 0.85 },
            ],
          },
        })}
        {...BASE_PROPS}
      />,
    );
    expect(screen.getByText(/manual_v2\.pdf/)).toBeInTheDocument();
    expect(screen.getByText(/faq\.pdf/)).toBeInTheDocument();
  });

  it("não exibe seção de fontes quando ragChunks está vazio", () => {
    render(
      <MessageTelemetryPanel
        message={makeMessage({ metrics: { ragChunks: [] } })}
        {...BASE_PROPS}
      />,
    );
    expect(screen.queryByText("Fontes:")).not.toBeInTheDocument();
  });
});

describe("MessageTelemetryPanel — layout", () => {
  it("aplica width inline quando bubbleWidth está preenchido", () => {
    const { container } = render(
      <MessageTelemetryPanel
        message={makeMessage()}
        {...BASE_PROPS}
        bubbleWidth={400}
      />,
    );
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.style.width).toBe("400px");
  });

  it("não aplica width inline quando bubbleWidth é null", () => {
    const { container } = render(
      <MessageTelemetryPanel message={makeMessage()} {...BASE_PROPS} />,
    );
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.style.width).toBe("");
  });
});
