import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import AdminAtendimentoPage from "@/app/admin/atendimento/page";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import * as adminApi from "@/lib/api/adminAtendimento";

vi.mock("@/lib/api/adminAtendimento", () => ({
  fetchFilaEspera: vi.fn(),
  fetchMeusChats: vi.fn(),
  fetchDetalhesConversa: vi.fn(),
  claimConversa: vi.fn(),
  enviarMensagemAtendente: vi.fn(),
  fecharAtendimento: vi.fn(),
}));

describe("Central de Atendimento Humano (/admin/atendimento)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("bloqueia acesso para usuários não administradores", () => {
    useAuthStore.setState({
      user: { id: 2, nome: "Cliente", email: "cliente@teste.com", perfil: "Cliente" },
      token: "token-cliente",
    });

    render(<AdminAtendimentoPage />);
    expect(screen.getByText(/Acesso Restrito/i)).toBeInTheDocument();
  });

  it("renderiza os três painéis e lista itens da fila para administrador", async () => {
    useAuthStore.setState({
      user: { id: 1, nome: "Carlos Atendente", email: "admin@empresa.com", perfil: "Admin" },
      token: "mock-token-1",
    });

    const mockFilaItem: adminApi.AtendimentoFilaItem = {
      id: "conv-101",
      status: "aguardando_humano",
      prioridade: 5,
      motivo_escalonamento: "tom_frustrado",
      escalado_em: new Date().toISOString(),
      criada_em: new Date().toISOString(),
      atualizada_em: new Date().toISOString(),
      tempo_espera_segundos: 120,
      mensagens_count: 3,
      ultima_mensagem: "Preciso falar com um humano agora!",
      cliente: {
        id: 10,
        nome: "João Cliente",
        email: "joao@cliente.com",
        perfil: "Cliente",
        perfil_motivo: "Comprador frequente",
      },
    };

    vi.mocked(adminApi.fetchFilaEspera).mockResolvedValue([mockFilaItem]);
    vi.mocked(adminApi.fetchMeusChats).mockResolvedValue([]);

    render(<AdminAtendimentoPage />);

    expect(screen.getByText(/Central de Atendimento/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/Preciso falar com um humano agora!/)).toBeInTheDocument();
      expect(screen.getByText(/Tom Frustrado/i)).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: /Assumir/i })).toBeInTheDocument();
  });

  it("permite assumir chat e interagir no painel de atendimento ativo", async () => {
    useAuthStore.setState({
      user: { id: 1, nome: "Carlos Atendente", email: "admin@empresa.com", perfil: "Admin" },
      token: "mock-token-1",
    });

    const mockFilaItem: adminApi.AtendimentoFilaItem = {
      id: "conv-101",
      status: "aguardando_humano",
      prioridade: 5,
      motivo_escalonamento: "tom_frustrado",
      escalado_em: new Date().toISOString(),
      criada_em: new Date().toISOString(),
      atualizada_em: new Date().toISOString(),
      tempo_espera_segundos: 120,
      mensagens_count: 3,
      ultima_mensagem: "Preciso de ajuda urgente",
      cliente: {
        id: 10,
        nome: "João Cliente",
        email: "joao@cliente.com",
        perfil: "Cliente",
        perfil_motivo: "Comprador frequente",
      },
    };

    const mockDetalhes: adminApi.AtendimentoDetalhes = {
      id: "conv-101",
      status: "em_atendimento_humano",
      atendente_id: "1",
      atendente_nome: "Carlos Atendente",
      prioridade: 5,
      motivo_escalonamento: "tom_frustrado",
      escalado_em: new Date().toISOString(),
      criada_em: new Date().toISOString(),
      atualizada_em: new Date().toISOString(),
      cliente: {
        id: 10,
        nome: "João Cliente",
        email: "joao@cliente.com",
        perfil: "Cliente",
        perfil_motivo: "Comprador recorrente",
        compras_count: 5,
        total_gasto: 1540.5,
      },
      mensagens: [
        {
          id: 1,
          conversa_id: "conv-101",
          papel: "cliente",
          texto: "Preciso de ajuda urgente",
          atendente_nome: null,
          dominio: "suporte",
          criada_em: new Date().toISOString(),
        },
      ],
    };

    vi.mocked(adminApi.fetchFilaEspera).mockResolvedValue([mockFilaItem]);
    vi.mocked(adminApi.fetchMeusChats)
      .mockResolvedValueOnce([])
      .mockResolvedValue([mockFilaItem]);
    vi.mocked(adminApi.claimConversa).mockResolvedValue({
      status: "em_atendimento_humano",
      conversation_id: "conv-101",
      atendente_id: "1",
      atendente_nome: "Carlos Atendente",
    });
    vi.mocked(adminApi.fetchDetalhesConversa).mockResolvedValue(mockDetalhes);
    vi.mocked(adminApi.enviarMensagemAtendente).mockResolvedValue({
      id: 2,
      conversa_id: "conv-101",
      papel: "atendente",
      texto: "Olá João! Estou aqui para te ajudar.",
      atendente_nome: "Carlos Atendente",
      criado_em: new Date().toISOString(),
    });

    render(<AdminAtendimentoPage />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Assumir/i })).toBeInTheDocument();
    });

    // Clica em assumir
    fireEvent.click(screen.getByRole("button", { name: /Assumir/i }));

    await waitFor(() => {
      expect(adminApi.claimConversa).toHaveBeenCalledWith("conv-101", "1", "Carlos Atendente", "mock-token-1");
      expect(screen.getAllByText("João Cliente").length).toBeGreaterThan(0);
    });

    // Aguarda o input carregar
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Digite sua resposta/i)).toBeInTheDocument();
    });

    // Envia mensagem
    const input = screen.getByPlaceholderText(/Digite sua resposta/i);
    fireEvent.change(input, { target: { value: "Olá João! Estou aqui para te ajudar." } });
    fireEvent.click(screen.getByRole("button", { name: /Enviar/i }));

    await waitFor(() => {
      expect(adminApi.enviarMensagemAtendente).toHaveBeenCalled();
    });
  });
});
