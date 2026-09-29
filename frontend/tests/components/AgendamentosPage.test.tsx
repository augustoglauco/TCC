import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AgendamentosPage from "@/app/agendamentos/page";
import * as agendamentosApi from "@/lib/api/agendamentos";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { useChatStore } from "@/lib/hooks/useChatStore";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => ({ get: () => null }),
}));

describe("AgendamentosPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({ user: null, token: null });
    useChatStore.setState({ isOpen: false });
  });

  it("renderiza mensagem de login necessário quando deslogado", async () => {
    render(<AgendamentosPage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Login Necessário/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Entrar na Conta/i })).toBeInTheDocument();
      expect(screen.getByText(/Para consultar e gerenciar seus agendamentos/i)).toBeInTheDocument();
    });
  });

  it("quando logado, renderiza lista de agendamentos e badges de status", async () => {
    useAuthStore.setState({
      user: { id: 1, email: "cliente@teste.com", nome: "Cliente Teste", perfil: "Cliente" },
      token: "fake-token",
    });

    const mockAgendamentos = [
      {
        id: "ag-1",
        user_email: "cliente@teste.com",
        nome_cliente: "Cliente Teste",
        telefone: "11999998888",
        data_hora_inicio: "2026-10-10T14:30:00Z",
        data_hora_fim: "2026-10-10T15:00:00Z",
        descricao: "Visita comercial técnica",
        status: "confirmado",
        origem: "chat",
        google_event_id: "evt-1",
        google_event_link: "https://calendar.google.com/evt-1",
        criado_em: "2026-09-29T10:00:00Z",
        atualizado_em: "2026-09-29T10:00:00Z",
      },
      {
        id: "ag-2",
        user_email: "cliente@teste.com",
        nome_cliente: "Cliente Teste",
        data_hora_inicio: "2026-09-20T10:00:00Z",
        data_hora_fim: "2026-09-20T10:30:00Z",
        status: "cancelado",
        origem: "chat",
        criado_em: "2026-09-15T10:00:00Z",
        atualizado_em: "2026-09-18T10:00:00Z",
      },
    ];

    vi.spyOn(agendamentosApi, "fetchMeusAgendamentos").mockResolvedValue(mockAgendamentos);

    render(<AgendamentosPage />);

    await waitFor(() => {
      expect(screen.getByText("Visita comercial técnica")).toBeInTheDocument();
      expect(screen.getByText(/Confirmado/i)).toBeInTheDocument();
      expect(screen.getByText(/Cancelado/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Desmarcar/i })).toBeInTheDocument();
    });
  });

  it("ao clicar em Desmarcar, exibe diálogo de confirmação e chama cancelarAgendamento ao confirmar", async () => {
    useAuthStore.setState({
      user: { id: 1, email: "cliente@teste.com", nome: "Cliente Teste", perfil: "Cliente" },
      token: "fake-token",
    });

    const mockAgendamentos = [
      {
        id: "ag-1",
        user_email: "cliente@teste.com",
        nome_cliente: "Cliente Teste",
        data_hora_inicio: "2026-10-10T14:30:00Z",
        data_hora_fim: "2026-10-10T15:00:00Z",
        descricao: "Visita comercial técnica",
        status: "confirmado",
        origem: "chat",
        criado_em: "2026-09-29T10:00:00Z",
        atualizado_em: "2026-09-29T10:00:00Z",
      },
    ];

    vi.spyOn(agendamentosApi, "fetchMeusAgendamentos").mockResolvedValue(mockAgendamentos);
    const cancelarSpy = vi.spyOn(agendamentosApi, "cancelarAgendamento").mockResolvedValue({
      ...mockAgendamentos[0],
      status: "cancelado",
    });

    render(<AgendamentosPage />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Desmarcar/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Desmarcar/i }));

    expect(screen.getByText(/Deseja realmente desmarcar esta visita\?/i)).toBeInTheDocument();

    const confirmarBtn = screen.getByRole("button", { name: /Sim, Desmarcar/i });
    fireEvent.click(confirmarBtn);

    await waitFor(() => {
      expect(cancelarSpy).toHaveBeenCalledWith("ag-1", "cliente@teste.com");
    });
  });

  it("ao clicar no CTA de novo agendamento, abre o widget de chat", async () => {
    useAuthStore.setState({
      user: { id: 1, email: "cliente@teste.com", nome: "Cliente Teste", perfil: "Cliente" },
      token: "fake-token",
    });

    vi.spyOn(agendamentosApi, "fetchMeusAgendamentos").mockResolvedValue([]);

    render(<AgendamentosPage />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Agendar Nova Visita pelo Chat/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Agendar Nova Visita pelo Chat/i }));

    expect(useChatStore.getState().isOpen).toBe(true);
  });
});
