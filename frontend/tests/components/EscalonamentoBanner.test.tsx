import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import EscalonamentoBanner from "@/components/chat/EscalonamentoBanner";

describe("EscalonamentoBanner", () => {
  it("não renderiza nada quando escalonamento é nulo", () => {
    const { container } = render(<EscalonamentoBanner escalonamento={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renderiza mensagem de urgência quando motivo é 'urgencia'", () => {
    render(<EscalonamentoBanner escalonamento={{ motivo: "urgencia", confianca: 0.9 }} />);

    expect(screen.getByTestId("escalonamento-banner")).toBeInTheDocument();
    expect(screen.getByText(/Atendimento Humano Prioritário/i)).toBeInTheDocument();
    expect(screen.getByText(/Identificamos urgência na sua solicitação/i)).toBeInTheDocument();
  });

  it("renderiza mensagem de insatisfação quando motivo é 'insatisfacao'", () => {
    render(<EscalonamentoBanner escalonamento={{ motivo: "insatisfacao", confianca: 0.85 }} />);

    expect(screen.getByTestId("escalonamento-banner")).toBeInTheDocument();
    expect(screen.getByText(/Atendimento Humano Prioritário/i)).toBeInTheDocument();
    expect(screen.getByText(/Percebemos sua insatisfação/i)).toBeInTheDocument();
  });

  it("renderiza mensagem genérica quando motivo é nulo ou outro valor", () => {
    render(<EscalonamentoBanner escalonamento={{ motivo: null }} />);

    expect(screen.getByTestId("escalonamento-banner")).toBeInTheDocument();
    expect(screen.getByText(/Sua conversa foi sinalizada para a nossa equipe humana/i)).toBeInTheDocument();
  });

  it("chama onDismiss ao clicar no botão de fechar", async () => {
    const user = userEvent.setup();
    const onDismiss = vi.fn();

    render(
      <EscalonamentoBanner
        escalonamento={{ motivo: "urgencia" }}
        onDismiss={onDismiss}
      />,
    );

    const closeButton = screen.getByRole("button", { name: /Fechar aviso de atendimento humano/i });
    await user.click(closeButton);

    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});
