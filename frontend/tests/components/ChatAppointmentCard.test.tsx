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

  it("mostra o link do Google Calendar quando presente", () => {
    render(<AppointmentCard card={makeCard()} />);

    const link = screen.getByRole("link", { name: "Ver no Google Calendar ↗" });
    expect(link).toHaveAttribute("href", "https://calendar.google.com/evt1");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("não mostra o link do Google Calendar quando ausente", () => {
    render(<AppointmentCard card={makeCard({ google_event_link: null })} />);

    expect(screen.queryByText("Ver no Google Calendar ↗")).not.toBeInTheDocument();
  });
});
