import { render, screen } from "@testing-library/react";
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
});
