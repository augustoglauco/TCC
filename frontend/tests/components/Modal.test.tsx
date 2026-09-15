import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Modal } from "@/components/ui/Modal";

describe("Modal", () => {
  it("não renderiza o conteúdo quando `open` é false", () => {
    render(
      <Modal open={false} onOpenChange={vi.fn()} title="Título">
        Conteúdo
      </Modal>,
    );

    expect(screen.queryByText("Conteúdo")).not.toBeInTheDocument();
  });

  it("renderiza título e conteúdo quando `open` é true", () => {
    render(
      <Modal open={true} onOpenChange={vi.fn()} title="Confirmar exclusão">
        Tem certeza?
      </Modal>,
    );

    expect(screen.getByText("Confirmar exclusão")).toBeInTheDocument();
    expect(screen.getByText("Tem certeza?")).toBeInTheDocument();
  });

  it("chama onOpenChange(false) ao clicar no botão de fechar", async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    render(
      <Modal open={true} onOpenChange={onOpenChange} title="Título">
        Conteúdo
      </Modal>,
    );

    await user.click(screen.getByRole("button", { name: "Fechar" }));

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
