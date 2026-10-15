import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import QuoteCard from "@/components/chat/cards/QuoteCard";
import { useChatStore } from "@/lib/hooks/useChatStore";
import type { ComponentProps } from "react";
import type { ChatCardCotacao } from "@/lib/types/chat";

vi.mock("next/link", () => ({
  default: ({ children, href, onClick, ...rest }: ComponentProps<"a">) => (
    <a
      href={href}
      onClick={(e) => {
        e.preventDefault();
        onClick?.(e);
      }}
      {...rest}
    >
      {children}
    </a>
  ),
}));

function makeCard(overrides: Partial<ChatCardCotacao> = {}): ChatCardCotacao {
  return {
    tipo: "cotacao",
    produto_id: 1,
    nome: "Gerador Diesel GD-15",
    quantidade: 2,
    preco_unitario: "24900.00",
    percentual_desconto: "10",
    subtotal: "44820.00",
    ...overrides,
  };
}

describe("QuoteCard", () => {
  it("renderiza produto, quantidade, preço unitário e total", () => {
    render(<QuoteCard card={makeCard()} />);

    expect(screen.getByText("Gerador Diesel GD-15")).toBeInTheDocument();
    expect(screen.getByText("2 × R$ 24.900,00")).toBeInTheDocument();
    expect(screen.getByText("Total: R$ 44.820,00")).toBeInTheDocument();
  });

  it("mostra o percentual de desconto quando maior que zero", () => {
    render(<QuoteCard card={makeCard({ percentual_desconto: "10" })} />);

    expect(screen.getByText("10% off")).toBeInTheDocument();
  });

  it("não mostra desconto quando percentual é zero", () => {
    render(<QuoteCard card={makeCard({ percentual_desconto: "0" })} />);

    expect(screen.queryByText(/% off/)).not.toBeInTheDocument();
  });

  it("linka para a página de detalhe do produto", () => {
    render(<QuoteCard card={makeCard({ produto_id: 7 })} />);

    expect(screen.getByRole("link")).toHaveAttribute("href", "/produtos/7");
  });

  it("fecha o modal do chat ao clicar no card", () => {
    useChatStore.setState({ isOpen: true });
    render(<QuoteCard card={makeCard()} />);

    fireEvent.click(screen.getByRole("link"));

    expect(useChatStore.getState().isOpen).toBe(false);
  });
});
