import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import HomePage from "@/app/page";

describe("HomePage", () => {
  it("renderiza todas as secoes estruturais da Home inspirada no M3 Glass", () => {
    render(<HomePage />);
    expect(
      screen.getAllByRole("button", { name: /conversar com o assistente/i }).length,
    ).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Como Trabalhamos/i)).toBeInTheDocument();
    expect(screen.getByText("99.9%")).toBeInTheDocument();
    expect(screen.getByText(/Destaques de Engenharia/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /iniciar atendimento ia/i })).toBeInTheDocument();
  });
});
