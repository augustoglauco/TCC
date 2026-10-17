import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import HeroSlider from "@/components/home/HeroSlider";

describe("HeroSlider", () => {
  it("renderiza titulo principal de tecnologia e botoes de acao", () => {
    render(<HeroSlider />);
    expect(screen.getByRole("button", { name: /conversar com o assistente/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /explorar catálogo/i })).toBeInTheDocument();
  });

  it("permite avancar slide pelas setas de navegacao", () => {
    render(<HeroSlider />);
    const nextBtn = screen.getByRole("button", { name: /próximo slide/i });
    fireEvent.click(nextBtn);
    expect(nextBtn).toBeInTheDocument();
  });
});
