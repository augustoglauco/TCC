import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import MessageBubble from "@/components/chat/MessageBubble";
import type { ChatUIMessage } from "@/lib/types/chat";

function makeMessage(overrides: Partial<ChatUIMessage> = {}): ChatUIMessage {
  return {
    id: "1",
    role: "user",
    text: "Olá",
    ...overrides,
  };
}

describe("MessageBubble", () => {
  it("renderiza mensagem do usuário sem rótulo de domínio", () => {
    render(<MessageBubble message={makeMessage({ role: "user", text: "Quero um orçamento" })} />);

    expect(screen.getByText("Quero um orçamento")).toBeInTheDocument();
    expect(screen.queryByTestId("message-domain-label")).not.toBeInTheDocument();
  });

  it("renderiza mensagem do assistente com rótulo de domínio", () => {
    render(
      <MessageBubble
        message={makeMessage({
          role: "assistant",
          text: "Posso te ajudar com o pedido X",
          domain: "vendas",
        })}
      />,
    );

    expect(screen.getByText("Posso te ajudar com o pedido X")).toBeInTheDocument();
    expect(screen.getByTestId("message-domain-label")).toHaveTextContent("Vendas");
  });

  it("usa o valor bruto do domínio quando não há rótulo mapeado", () => {
    render(
      <MessageBubble
        message={makeMessage({ role: "assistant", text: "Resposta", domain: "outro" as never })}
      />,
    );

    expect(screen.getByTestId("message-domain-label")).toHaveTextContent("outro");
  });

  it("não mostra rótulo de domínio quando o assistente não retorna domínio", () => {
    render(<MessageBubble message={makeMessage({ role: "assistant", text: "Oi" })} />);

    expect(screen.queryByTestId("message-domain-label")).not.toBeInTheDocument();
  });

  it("mantém o painel de métricas escondido por padrão", () => {
    render(
      <MessageBubble
        message={makeMessage({
          role: "assistant",
          text: "Posso te ajudar com o pedido X",
          domain: "vendas",
          metrics: { modelName: "llama3.1:8b" },
        })}
      />,
    );

    expect(screen.queryByTestId("message-metrics")).not.toBeInTheDocument();
  });

  it("mostra o painel de métricas ao clicar na engrenagem ao lado do domínio", async () => {
    const user = userEvent.setup();
    render(
      <MessageBubble
        message={makeMessage({
          role: "assistant",
          text: "Posso te ajudar com o pedido X",
          domain: "vendas",
          metrics: { modelName: "llama3.1:8b" },
        })}
      />,
    );

    const toggle = screen.getByRole("button", { name: "Mostrar métricas da resposta" });
    await user.click(toggle);

    expect(screen.getByTestId("message-metrics")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ocultar métricas da resposta" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Ocultar métricas da resposta" }));

    expect(screen.queryByTestId("message-metrics")).not.toBeInTheDocument();
  });

  it("mostra o provedor TypeSafe Jev quando routerProvider é jev_openrouter", async () => {
    const user = userEvent.setup();
    render(
      <MessageBubble
        message={makeMessage({
          role: "assistant",
          text: "Resposta",
          domain: "vendas",
          metrics: { modelName: "jev", routerProvider: "jev_openrouter" },
        })}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Mostrar métricas da resposta" }));

    expect(screen.getByText("TypeSafe Jev (OpenRouter)")).toBeInTheDocument();
  });

  it("mostra o provedor Heurística + LLM Local quando routerProvider é heuristica_llm", async () => {
    const user = userEvent.setup();
    render(
      <MessageBubble
        message={makeMessage({
          role: "assistant",
          text: "Resposta",
          domain: "vendas",
          metrics: { modelName: "llama3.1:8b", routerProvider: "heuristica_llm" },
        })}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Mostrar métricas da resposta" }));

    expect(screen.getByText("Heurística + LLM Local")).toBeInTheDocument();
  });

  it("não mostra a linha de provedor quando routerProvider não vem no metrics", async () => {
    const user = userEvent.setup();
    render(
      <MessageBubble
        message={makeMessage({
          role: "assistant",
          text: "Resposta",
          domain: "vendas",
          metrics: { modelName: "llama3.1:8b" },
        })}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Mostrar métricas da resposta" }));

    expect(screen.queryByText(/^Provedor:/)).not.toBeInTheDocument();
  });

  it("destaca em azul a resposta do assistente quando vem de LLM externo", () => {
    render(
      <MessageBubble
        message={makeMessage({ role: "assistant", text: "Resposta externa", backendUsed: "externo" })}
      />,
    );

    expect(screen.getByTestId("message-bubble")).toHaveClass("bg-blue-50");
  });

  it("não destaca em azul a resposta do assistente quando vem do modelo local", () => {
    render(
      <MessageBubble
        message={makeMessage({ role: "assistant", text: "Resposta local", backendUsed: "local" })}
      />,
    );

    expect(screen.getByTestId("message-bubble")).not.toHaveClass("bg-blue-50");
  });
});
