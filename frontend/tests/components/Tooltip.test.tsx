import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Tooltip } from "@/components/ui/Tooltip";

describe("Tooltip", () => {
  it("renderiza o botão de dica sem tooltip visível por padrão", () => {
    render(<Tooltip content="Texto de explicação" />);

    const button = screen.getByRole("button", { name: /Dica: Texto de explicação/i });
    expect(button).toBeInTheDocument();
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("exibe o tooltip ao passar o mouse e oculta ao retirar", async () => {
    const user = userEvent.setup();
    render(<Tooltip content="Texto de explicação" />);

    const button = screen.getByRole("button");
    await user.hover(button);

    expect(screen.getByRole("tooltip")).toHaveTextContent("Texto de explicação");

    await user.unhover(button);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("exibe o tooltip ao focar o botão via teclado", async () => {
    const user = userEvent.setup();
    render(<Tooltip content="Texto de explicação" />);

    const button = screen.getByRole("button");
    await user.tab();

    expect(button).toHaveFocus();
    expect(screen.getByRole("tooltip")).toHaveTextContent("Texto de explicação");
  });

  it("usa o elemento de trigger customizado em vez do botão '?' quando fornecido", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip
        content="Painel de características"
        trigger={<div data-testid="card-customizado">Meu Card</div>}
        renderContent={() => <span>Conteúdo rico</span>}
      />,
    );

    expect(screen.queryByRole("button", { name: /Dica:/i })).not.toBeInTheDocument();
    const card = screen.getByTestId("card-customizado");

    await user.hover(card);
    expect(screen.getByRole("tooltip")).toHaveTextContent("Conteúdo rico");

    await user.unhover(card);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("preserva os handlers de hover já existentes no elemento de trigger", async () => {
    const user = userEvent.setup();
    const onMouseEnter = vi.fn();
    render(
      <Tooltip
        content="x"
        trigger={
          <div data-testid="card" onMouseEnter={onMouseEnter}>
            Card
          </div>
        }
        renderContent={() => <span>Conteúdo</span>}
      />,
    );

    await user.hover(screen.getByTestId("card"));

    expect(onMouseEnter).toHaveBeenCalled();
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
  });
});
