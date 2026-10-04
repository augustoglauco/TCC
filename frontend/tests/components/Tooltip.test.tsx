import { render, screen, waitFor } from "@testing-library/react";
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
    // `trigger`/hover agenda o esconder com um pequeno atraso (ver achado #2
    // da revisão final) em vez de remover sincronamente — por isso `waitFor`
    // em vez de uma asserção imediata.
    await waitFor(() => expect(screen.queryByRole("tooltip")).not.toBeInTheDocument());
  });

  it("mantém o tooltip visível quando o cursor se move do gatilho para o próprio corpo do painel", async () => {
    // Achado #2 da revisão final: o corpo do tooltip (role="tooltip") é
    // portalado com um gap de 6px abaixo do gatilho — sem o atraso de
    // esconder e sem handlers de hover no próprio corpo, mover o cursor do
    // gatilho até o painel (ex.: para clicar no botão de refresh) fechava o
    // painel no meio do caminho.
    const user = userEvent.setup();
    render(
      <Tooltip
        content="Painel de características"
        trigger={<div data-testid="card-customizado">Meu Card</div>}
        renderContent={() => <span>Conteúdo rico</span>}
      />,
    );

    await user.hover(screen.getByTestId("card-customizado"));
    expect(screen.getByRole("tooltip")).toBeInTheDocument();

    // Simula o cursor saindo do gatilho e entrando no corpo do tooltip
    // (que, por estar portalado 6px abaixo, não é um descendente DOM do
    // gatilho — por isso os dois eventos são disparados separadamente).
    await user.unhover(screen.getByTestId("card-customizado"));
    await user.hover(screen.getByRole("tooltip"));

    // Mesmo passado o atraso de esconder, o tooltip continua visível porque
    // o hover no próprio corpo cancelou o timeout agendado.
    await new Promise((resolve) => setTimeout(resolve, 200));
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
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
