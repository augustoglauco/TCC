import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import AdminGearMenu from "@/components/layout/AdminGearMenu";

describe("AdminGearMenu", () => {
  it("renderiza o botão de engrenagem sem o menu aberto por padrão", () => {
    render(<AdminGearMenu />);

    const button = screen.getByRole("button", { name: /configurações de administração/i });
    expect(button).toBeInTheDocument();
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("abre o menu dropdown ao clicar no botão de engrenagem", async () => {
    const user = userEvent.setup();
    render(<AdminGearMenu />);

    const button = screen.getByRole("button", { name: /configurações de administração/i });
    await user.click(button);

    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("menu")).toBeInTheDocument();

    const ingestaoLink = screen.getByRole("menuitem", { name: /ingestão de documentos/i });
    const modelosLink = screen.getByRole("menuitem", { name: /modelos locais/i });

    expect(ingestaoLink).toHaveAttribute("href", "/admin/ingestao");
    expect(modelosLink).toHaveAttribute("href", "/admin/modelos");
  });

  it("fecha o menu ao clicar em um link", async () => {
    const user = userEvent.setup();
    render(<AdminGearMenu />);

    const button = screen.getByRole("button", { name: /configurações de administração/i });
    await user.click(button);

    const ingestaoLink = screen.getByRole("menuitem", { name: /ingestão de documentos/i });
    await user.click(ingestaoLink);

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(button).toHaveAttribute("aria-expanded", "false");
  });

  it("fecha o menu ao pressionar a tecla Escape", async () => {
    const user = userEvent.setup();
    render(<AdminGearMenu />);

    const button = screen.getByRole("button", { name: /configurações de administração/i });
    await user.click(button);
    expect(screen.getByRole("menu")).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });
});
