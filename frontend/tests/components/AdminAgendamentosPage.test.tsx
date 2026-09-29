import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminAgendamentosPage from "@/app/admin/agendamentos/page";
import * as agendamentosApi from "@/lib/api/agendamentos";
import { useAuthStore } from "@/lib/hooks/useAuthStore";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => ({ get: () => null }),
}));

describe("AdminAgendamentosPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({ user: null, token: null });
  });

  it("bloqueia acesso para usuários que não são admin", async () => {
    useAuthStore.setState({
      user: { id: 2, email: "cliente@teste.com", nome: "Cliente", perfil: "Cliente" },
      token: "tok",
    });

    render(<AdminAgendamentosPage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Acesso Restrito/i })).toBeInTheDocument();
      expect(screen.getByText(/Apenas administradores podem acessar esta página/i)).toBeInTheDocument();
    });
  });

  it("para admin, renderiza métricas e agendamentos do sistema na Aba 1", async () => {
    useAuthStore.setState({
      user: { id: 1, email: "admin@teste.com", nome: "Admin", perfil: "Admin" },
      token: "tok",
    });

    const mockAgendamentos = [
      {
        id: "ag-1",
        user_email: "cliente1@teste.com",
        nome_cliente: "Cliente 1",
        telefone: "11988887777",
        data_hora_inicio: "2026-10-15T10:00:00Z",
        data_hora_fim: "2026-10-15T10:30:00Z",
        descricao: "Visita CFTV",
        status: "confirmado",
        origem: "chat",
        criado_em: "2026-09-29T10:00:00Z",
        atualizado_em: "2026-09-29T10:00:00Z",
      },
      {
        id: "ag-2",
        user_email: "cliente2@teste.com",
        nome_cliente: "Cliente 2",
        telefone: "11977776666",
        data_hora_inicio: "2026-10-16T14:00:00Z",
        data_hora_fim: "2026-10-16T14:30:00Z",
        descricao: "Visita Solar",
        status: "cancelado",
        origem: "manual_admin",
        criado_em: "2026-09-29T11:00:00Z",
        atualizado_em: "2026-09-29T11:00:00Z",
      },
    ];

    vi.spyOn(agendamentosApi, "fetchAdminAgendamentos").mockResolvedValue(mockAgendamentos);

    render(<AdminAgendamentosPage />);

    await waitFor(() => {
      expect(screen.getByText("Painel de Agendamentos")).toBeInTheDocument();
      expect(screen.getByText("Cliente 1")).toBeInTheDocument();
      expect(screen.getByText("Cliente 2")).toBeInTheDocument();
      expect(screen.getByText("Visita CFTV")).toBeInTheDocument();
      expect(screen.getByText("Visita Solar")).toBeInTheDocument();
    });
  });

  it("permite alternar para a Aba 2 e exibe eventos do Google Calendar", async () => {
    useAuthStore.setState({
      user: { id: 1, email: "admin@teste.com", nome: "Admin", perfil: "Admin" },
      token: "tok",
    });

    vi.spyOn(agendamentosApi, "fetchAdminAgendamentos").mockResolvedValue([]);
    const mockEvents = [
      {
        id: "evt-g-1",
        summary: "Reunião de Alinhamento Google",
        start: "2026-10-20T14:00:00Z",
        end: "2026-10-20T15:00:00Z",
      },
    ];
    vi.spyOn(agendamentosApi, "fetchGoogleCalendarEvents").mockResolvedValue(mockEvents);

    render(<AdminAgendamentosPage />);

    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /Google Calendar/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("tab", { name: /Google Calendar/i }));

    await waitFor(() => {
      expect(screen.getByText("Reunião de Alinhamento Google")).toBeInTheDocument();
    });
  });

  it("abre modal de agendamento manual, preenche e submete com sucesso", async () => {
    useAuthStore.setState({
      user: { id: 1, email: "admin@teste.com", nome: "Admin", perfil: "Admin" },
      token: "tok",
    });

    vi.spyOn(agendamentosApi, "fetchAdminAgendamentos").mockResolvedValue([]);
    const criarSpy = vi.spyOn(agendamentosApi, "criarAgendamentoManual").mockResolvedValue({
      id: "ag-novo",
      user_email: "novo@cliente.com",
      nome_cliente: "Novo Cliente",
      data_hora_inicio: "2026-10-25T10:00",
      data_hora_fim: "2026-10-25T11:30",
      status: "confirmado",
      origem: "manual_admin",
      criado_em: "2026-09-29T12:00:00Z",
      atualizado_em: "2026-09-29T12:00:00Z",
    });

    render(<AdminAgendamentosPage />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /\+ Agendar Manualmente/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /\+ Agendar Manualmente/i }));

    expect(screen.getByText("Novo Agendamento Manual")).toBeInTheDocument();

    const duracaoInput = screen.getByLabelText(/Duração \(minutos\)/i);
    expect(duracaoInput).toHaveValue(60);

    fireEvent.change(screen.getByLabelText(/E-mail do Cliente/i), {
      target: { value: "novo@cliente.com" },
    });
    fireEvent.change(screen.getByLabelText(/Nome do Cliente/i), {
      target: { value: "Novo Cliente" },
    });
    fireEvent.change(screen.getByLabelText(/Data e Hora de Início/i), {
      target: { value: "2026-10-25T10:00" },
    });
    fireEvent.change(duracaoInput, {
      target: { value: "90" },
    });

    fireEvent.click(screen.getByRole("button", { name: /Confirmar Agendamento/i }));

    await waitFor(() => {
      expect(criarSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          user_email: "novo@cliente.com",
          nome_cliente: "Novo Cliente",
          duracao_minutos: 90,
        })
      );
    });
  });
});

