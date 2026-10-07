import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, screen, fireEvent, waitFor } from "@testing-library/react";
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

  it("não força scroll a cada poll de 3s do painel de chat ativo sem mensagem nova (achado de 2026-10-07)", async () => {
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
      mensagens_count: 1,
      ultima_mensagem: "Preciso de ajuda urgente",
      cliente: null,
    };

    // `fetchDetalhesConversa` real devolve um array novo (JSON recém-
    // parseado) a cada chamada, mesmo com o mesmo conteúdo — a função aqui
    // reproduz isso de propósito (`[...]` a cada chamada), em vez de
    // `mockResolvedValue` (que devolveria sempre a MESMA referência e não
    // pegaria a regressão).
    const mensagemFixa = {
      id: 1,
      conversa_id: "conv-101",
      papel: "cliente" as const,
      texto: "Preciso de ajuda urgente",
      atendente_nome: null,
      dominio: "suporte",
      criada_em: new Date().toISOString(),
    };
    vi.mocked(adminApi.fetchDetalhesConversa).mockImplementation(async () => ({
      id: "conv-101",
      status: "em_atendimento_humano",
      atendente_id: "1",
      atendente_nome: "Carlos Atendente",
      prioridade: 5,
      motivo_escalonamento: "tom_frustrado",
      escalado_em: new Date().toISOString(),
      criada_em: new Date().toISOString(),
      atualizada_em: new Date().toISOString(),
      cliente: null,
      mensagens: [{ ...mensagemFixa }],
    }));

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

    const scrollIntoViewMock = vi.fn();
    window.HTMLElement.prototype.scrollIntoView = scrollIntoViewMock;

    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      render(<AdminAtendimentoPage />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /Assumir/i })).toBeInTheDocument();
      });
      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: /Assumir/i }));
      });
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/Digite sua resposta/i)).toBeInTheDocument();
      });

      const chamadasAposAssumir = scrollIntoViewMock.mock.calls.length;
      expect(chamadasAposAssumir).toBeGreaterThan(0);

      // Três polls de 3s sem nenhuma mensagem nova — o scroll não deve se
      // repetir a cada um deles.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(9000);
      });

      expect(scrollIntoViewMock.mock.calls.length).toBe(chamadasAposAssumir);
    } finally {
      vi.useRealTimers();
    }
  });

  it("fecha o painel do chat ativo quando o cliente encerra a conversa (achado de 2026-10-07)", async () => {
    // Antes: quando a conversa sumia de `meusChats` (porque o cliente
    // encerrou, outro atendente a devolveu para a IA, etc.), o bloco que
    // deveria limpar `activeChatId`/`detalhes` só tinha o comentário da
    // intenção — o corpo do `if` estava vazio. O painel continuava
    // mostrando a conversa como ativa (histórico, campo de envio,
    // botões) mesmo já encerrada no servidor; o atendente via o chat
    // como se nunca tivesse fechado.
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
      mensagens_count: 1,
      ultima_mensagem: "Preciso de ajuda urgente",
      cliente: null,
    };

    vi.mocked(adminApi.fetchFilaEspera).mockResolvedValue([mockFilaItem]);
    // Flag em vez de `mockResolvedValueOnce` encadeado: com fake timers
    // (`shouldAdvanceTime: true`) o `setInterval` de 5s de
    // `carregarFilaEMeusChats` pode disparar uma chamada extra enquanto os
    // `waitFor` abaixo ainda resolvem, o que consumiria os mocks
    // encadeados fora de ordem. O flag é robusto a qualquer número de
    // chamadas antes do ponto em que o teste efetivamente o vira.
    let clienteAindaAtivo = true;
    vi.mocked(adminApi.fetchMeusChats).mockImplementation(async () =>
      clienteAindaAtivo ? [mockFilaItem] : [],
    );
    vi.mocked(adminApi.claimConversa).mockResolvedValue({
      status: "em_atendimento_humano",
      conversation_id: "conv-101",
      atendente_id: "1",
      atendente_nome: "Carlos Atendente",
    });
    vi.mocked(adminApi.fetchDetalhesConversa).mockResolvedValue({
      id: "conv-101",
      status: "em_atendimento_humano",
      atendente_id: "1",
      atendente_nome: "Carlos Atendente",
      prioridade: 5,
      motivo_escalonamento: "tom_frustrado",
      escalado_em: new Date().toISOString(),
      criada_em: new Date().toISOString(),
      atualizada_em: new Date().toISOString(),
      cliente: null,
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
    });

    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      render(<AdminAtendimentoPage />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /Assumir/i })).toBeInTheDocument();
      });
      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: /Assumir/i }));
      });
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/Digite sua resposta/i)).toBeInTheDocument();
      });

      // Cliente encerra a conversa do outro lado — no próximo poll de 5s
      // da fila/meus-chats, `fetchMeusChats` passa a devolver [].
      clienteAindaAtivo = false;
      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000);
      });

      expect(screen.queryByPlaceholderText(/Digite sua resposta/i)).not.toBeInTheDocument();
      expect(screen.getByText(/Central de Conversas em Andamento/i)).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});
