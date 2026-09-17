import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

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
});
