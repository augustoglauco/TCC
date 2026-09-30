import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AppointmentCard from "@/components/chat/cards/AppointmentCard";
import type { ChatCardAgendamento } from "@/lib/types/chat";

function makeCard(overrides: Partial<ChatCardAgendamento> = {}): ChatCardAgendamento {
  return {
    tipo: "agendamento",
    data_hora_inicio: "2026-10-01T14:30:00-03:00",
    data_hora_fim: "2026-10-01T15:30:00-03:00",
    google_event_link: "https://calendar.google.com/evt1",
    ...overrides,
  };
}

describe("AppointmentCard", () => {
  it("renderiza a data/hora formatada e o link para meus agendamentos", () => {
    render(<AppointmentCard card={makeCard()} />);

    expect(screen.getByText("Visita agendada")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ver meus agendamentos →" })).toHaveAttribute(
      "href",
      "/agendamentos",
    );
  });

  it("nunca mostra link para o Google Calendar, mesmo com google_event_link presente", () => {
    // Pedido explícito: o card não deve expor o link do Google ao cliente
    // (correção de 2026-09-29) — o campo continua no contrato de dados
    // (usado em `/admin/agendamentos`), só não aparece neste card.
    render(<AppointmentCard card={makeCard()} />);

    expect(screen.queryByText(/Google Calendar/)).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Google/ })).not.toBeInTheDocument();
  });
});
