import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminMensagensPage from "@/app/admin/mensagens/page";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import * as api from "@/lib/api/mensagens";

const msg = (over: Partial<api.MensagemAgente> = {}): api.MensagemAgente => ({
  id: "m1",
  agente: "estoque_preditivo",
  tipo: "previsao_falta_estoque",
  severidade: "aviso",
  titulo: "Risco de falta: Gerador GD-15 (~4 dias de estoque)",
  corpo: "Nesse ritmo o estoque acaba em cerca de 4 dia(s).",
  dados: null,
  lida: false,
  email_status: "enviado",
  criado_em: "2026-10-15T12:00:00Z",
  ...over,
});

describe("AdminMensagensPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useAuthStore.setState({
      token: "t",
      user: { perfil: "admin" } as never,
    } as never);
  });

  it("lista as mensagens e marca como lida", async () => {
    const fetchSpy = vi
      .spyOn(api, "fetchMensagens")
      .mockResolvedValueOnce({ mensagens: [msg()], nao_lidas: 1 })
      .mockResolvedValueOnce({ mensagens: [msg({ lida: true })], nao_lidas: 0 });
    const lidaSpy = vi.spyOn(api, "marcarMensagemLida").mockResolvedValue();

    render(<AdminMensagensPage />);

    expect(await screen.findByText(/Risco de falta: Gerador GD-15/)).toBeInTheDocument();
    expect(screen.getByTestId("nao-lidas")).toHaveTextContent("1 não lida");
    expect(screen.getByText("E-mail enviado")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Marcar como lida" }));

    await waitFor(() => expect(lidaSpy).toHaveBeenCalledWith("t", "m1"));
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole("button", { name: "Marcar como lida" })).not.toBeInTheDocument();
  });

  it("mostra estado vazio", async () => {
    vi.spyOn(api, "fetchMensagens").mockResolvedValue({ mensagens: [], nao_lidas: 0 });
    render(<AdminMensagensPage />);
    expect(await screen.findByText("Nenhuma mensagem de agentes.")).toBeInTheDocument();
  });
});
