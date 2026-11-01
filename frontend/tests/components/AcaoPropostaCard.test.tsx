import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AcaoPropostaCard from "@/components/chat/cards/AcaoPropostaCard";
import { useAuthStore } from "@/lib/hooks/useAuthStore";

vi.mock("@/lib/api/adminChatAcoes", () => ({
  confirmarAcao: vi.fn().mockResolvedValue({ status: "executada", depois: { estoque: 35 } }),
  cancelarAcao: vi.fn().mockResolvedValue({ status: "cancelada" }),
}));
import { cancelarAcao, confirmarAcao } from "@/lib/api/adminChatAcoes";

const CARD = {
  tipo: "acao_proposta" as const,
  acao_id: "a-1",
  titulo: "Baixa de estoque",
  antes: { estoque: 40 },
  depois: { estoque: 35 },
  aviso: null,
  expira_em: "2026-11-01T12:00:00Z",
};

describe("AcaoPropostaCard", () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: { id: 1, nome: "Admin", email: "a@b.c", perfil: "Admin" },
      token: "mock-token-1",
    });
  });

  it("mostra antes e depois e confirma com o token do admin", async () => {
    const user = userEvent.setup();
    render(<AcaoPropostaCard card={CARD} />);
    expect(screen.getByText("Baixa de estoque")).toBeInTheDocument();
    expect(screen.getByText(/40/)).toBeInTheDocument();
    expect(screen.getByText(/35/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Confirmar" }));
    expect(confirmarAcao).toHaveBeenCalledWith("mock-token-1", "a-1");
    expect(await screen.findByText(/executada/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Confirmar" })).not.toBeInTheDocument();
  });

  it("cancelar chama a API e esconde os botões", async () => {
    const user = userEvent.setup();
    render(<AcaoPropostaCard card={CARD} />);
    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(cancelarAcao).toHaveBeenCalledWith("mock-token-1", "a-1");
    expect(await screen.findByText(/cancelada/i)).toBeInTheDocument();
  });

  it("mostra o erro e mantém os botões quando a API falha", async () => {
    vi.mocked(confirmarAcao).mockRejectedValueOnce(new Error("Proposta expirada; peça de novo."));
    const user = userEvent.setup();
    render(<AcaoPropostaCard card={CARD} />);
    await user.click(screen.getByRole("button", { name: "Confirmar" }));
    expect(await screen.findByText(/Proposta expirada/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirmar" })).toBeEnabled();
  });
});
