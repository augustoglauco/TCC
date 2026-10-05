import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import AdminPedidosPage from "@/app/admin/pedidos/page";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import * as adminPedidosApi from "@/lib/api/adminPedidos";

vi.mock("@/lib/api/adminPedidos", () => ({
  fetchPedidos: vi.fn(),
  fetchPedido: vi.fn(),
  converterManualSimples: vi.fn(),
  analisarComprovante: vi.fn(),
  confirmarConversaoManual: vi.fn(),
  converterAutoAdmin: vi.fn(),
}));

describe("Painel de Gestão de Pedidos e Conversão de Reserva (/admin/pedidos)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("bloqueia acesso para usuários não administradores", () => {
    useAuthStore.setState({
      user: { id: 2, nome: "Cliente", email: "cliente@teste.com", perfil: "Cliente" },
      token: "token-cliente",
    });

    render(<AdminPedidosPage />);
    expect(screen.getByText(/Acesso Restrito/i)).toBeInTheDocument();
  });

  it("renderiza lista de pedidos e filtra por status", async () => {
    useAuthStore.setState({
      user: { id: 1, nome: "Admin Operador", email: "admin@empresa.com", perfil: "Admin" },
      token: "mock-token-admin",
    });

    const mockPedidos: adminPedidosApi.PedidoAdminItem[] = [
      {
        id: "pedido-uuid-1",
        status: "reservado",
        user_email: "cliente1@teste.com",
        conversation_id: "conv-1",
        comprovante_url: null,
        tipo_conversao: null,
        convertido_em: null,
        convertido_por: null,
        llm_parecer: null,
        criado_em: new Date().toISOString(),
        valor_total: 1250.0,
        itens: [
          {
            id: "item-1",
            produto_id: 1,
            centro_distribuicao: "CD-SP",
            quantidade: 2,
            preco_unitario: 625.0,
            subtotal: 1250.0,
          },
        ],
      },
      {
        id: "pedido-uuid-2",
        status: "venda_concluida",
        user_email: "b2b@parceiro.com",
        conversation_id: null,
        comprovante_url: "/uploads/comprovantes/recibo.pdf",
        tipo_conversao: "auto_mcp_b2b",
        convertido_em: new Date().toISOString(),
        convertido_por: "parceiro_alpha",
        llm_parecer: JSON.stringify({ valido: true, valor_pago: 2000.0, divergencia: 0.0 }),
        criado_em: new Date().toISOString(),
        valor_total: 2000.0,
        itens: [],
      },
      {
        id: "pedido-uuid-3",
        status: "pagamento_divergente",
        user_email: "cliente2@teste.com",
        conversation_id: null,
        comprovante_url: "/uploads/comprovantes/divergente.png",
        tipo_conversao: null,
        convertido_em: null,
        convertido_por: null,
        llm_parecer: JSON.stringify({ valido: false, valor_pago: 300.0, divergencia: 200.0, justificativa: "Valor inferior" }),
        criado_em: new Date().toISOString(),
        valor_total: 500.0,
        itens: [],
      },
    ];

    vi.mocked(adminPedidosApi.fetchPedidos).mockResolvedValue(mockPedidos);

    render(<AdminPedidosPage />);

    await waitFor(() => {
      expect(screen.getByText("Gestão de Pedidos & Conversão")).toBeInTheDocument();
      expect(screen.getByText("cliente1@teste.com")).toBeInTheDocument();
      expect(screen.getByText("b2b@parceiro.com")).toBeInTheDocument();
      expect(screen.getByText("cliente2@teste.com")).toBeInTheDocument();
    });

    // Testar filtro por status
    const botaoFiltroReservado = screen.getByRole("button", { name: /Reservados/i });
    fireEvent.click(botaoFiltroReservado);

    expect(adminPedidosApi.fetchPedidos).toHaveBeenCalledWith(
      expect.objectContaining({ status: "reservado" }),
      "mock-token-admin"
    );
  });

  it("abre modal e executa Modo 1: Manual Simples", async () => {
    useAuthStore.setState({
      user: { id: 1, nome: "Admin Operador", email: "admin@empresa.com", perfil: "Admin" },
      token: "mock-token-admin",
    });

    const mockPedido: adminPedidosApi.PedidoAdminItem = {
      id: "pedido-uuid-1",
      status: "reservado",
      user_email: "cliente1@teste.com",
      conversation_id: "conv-1",
      comprovante_url: null,
      tipo_conversao: null,
      convertido_em: null,
      convertido_por: null,
      llm_parecer: null,
      criado_em: new Date().toISOString(),
      valor_total: 1250.0,
      itens: [],
    };

    vi.mocked(adminPedidosApi.fetchPedidos).mockResolvedValue([mockPedido]);
    vi.mocked(adminPedidosApi.converterManualSimples).mockResolvedValue({
      ...mockPedido,
      status: "venda_concluida",
      tipo_conversao: "manual_simples",
    });

    render(<AdminPedidosPage />);

    await waitFor(() => {
      expect(screen.getByText("cliente1@teste.com")).toBeInTheDocument();
    });

    // Clica no botão para abrir modal
    const btnConverter = screen.getByRole("button", { name: /Converter /i });
    fireEvent.click(btnConverter);

    expect(screen.getByText("Modal de Conversão de Reserva")).toBeInTheDocument();

    // Seleciona modalidade Manual Simples e clica em confirmar
    const btnConfirmarSimples = screen.getByRole("button", { name: /Confirmar Conversão Simples/i });
    fireEvent.click(btnConfirmarSimples);

    await waitFor(() => {
      expect(adminPedidosApi.converterManualSimples).toHaveBeenCalledWith(
        "pedido-uuid-1",
        expect.any(Object),
        "mock-token-admin"
      );
    });
  });

  it("executa Modo 2: Auditoria com IA e Confirmação com Parecer", async () => {
    useAuthStore.setState({
      user: { id: 1, nome: "Admin Operador", email: "admin@empresa.com", perfil: "Admin" },
      token: "mock-token-admin",
    });

    const mockPedido: adminPedidosApi.PedidoAdminItem = {
      id: "pedido-uuid-2",
      status: "reservado",
      user_email: "cliente2@teste.com",
      conversation_id: null,
      comprovante_url: null,
      tipo_conversao: null,
      convertido_em: null,
      convertido_por: null,
      llm_parecer: null,
      criado_em: new Date().toISOString(),
      valor_total: 800.0,
      itens: [],
    };

    vi.mocked(adminPedidosApi.fetchPedidos).mockResolvedValue([mockPedido]);
    vi.mocked(adminPedidosApi.analisarComprovante).mockResolvedValue({
      pedido_id: "pedido-uuid-2",
      valor_devido: 800.0,
      comprovante_url: "/uploads/comprovantes/recibo.png",
      parecer: {
        valido: true,
        valor_pago: 800.0,
        divergencia: 0.0,
        justificativa: "Comprovante PIX conferido com valor integral.",
        codigo_transacao: "E12345678",
      },
    });
    vi.mocked(adminPedidosApi.confirmarConversaoManual).mockResolvedValue({
      ...mockPedido,
      status: "venda_concluida",
      tipo_conversao: "manual_padrao",
    });

    render(<AdminPedidosPage />);

    await waitFor(() => {
      expect(screen.getByText("cliente2@teste.com")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Converter /i }));

    // Troca para a aba de Auditoria com IA (Modo 2)
    const tabModo2 = screen.getByRole("button", { name: /Manual com IA/i });
    fireEvent.click(tabModo2);

    // Mock do arquivo
    const file = new File(["dummy content"], "comprovante.png", { type: "image/png" });
    const input = screen.getByTestId("input-file-analise");
    fireEvent.change(input, { target: { files: [file] } });

    // Clica no botão de auditar
    const btnAuditar = screen.getByRole("button", { name: /Auditar com IA/i });
    fireEvent.click(btnAuditar);

    await waitFor(() => {
      expect(adminPedidosApi.analisarComprovante).toHaveBeenCalled();
      expect(screen.getByText(/Comprovante PIX conferido/i)).toBeInTheDocument();
    });

    // Clica em confirmar com IA
    const btnAprovar = screen.getByRole("button", { name: /Aprovar e Concluir Venda/i });
    fireEvent.click(btnAprovar);

    await waitFor(() => {
      expect(adminPedidosApi.confirmarConversaoManual).toHaveBeenCalledWith(
        "pedido-uuid-2",
        expect.any(Object),
        "mock-token-admin"
      );
    });
  });

  it("executa Modo 3: Conversão Automática via IA no Upload", async () => {
    useAuthStore.setState({
      user: { id: 1, nome: "Admin Operador", email: "admin@empresa.com", perfil: "Admin" },
      token: "mock-token-admin",
    });

    const mockPedido: adminPedidosApi.PedidoAdminItem = {
      id: "pedido-uuid-3",
      status: "reservado",
      user_email: "cliente3@teste.com",
      conversation_id: null,
      comprovante_url: null,
      tipo_conversao: null,
      convertido_em: null,
      convertido_por: null,
      llm_parecer: null,
      criado_em: new Date().toISOString(),
      valor_total: 450.0,
      itens: [],
    };

    vi.mocked(adminPedidosApi.fetchPedidos).mockResolvedValue([mockPedido]);
    vi.mocked(adminPedidosApi.converterAutoAdmin).mockResolvedValue({
      ...mockPedido,
      status: "venda_concluida",
      tipo_conversao: "auto_admin",
    });

    render(<AdminPedidosPage />);

    await waitFor(() => {
      expect(screen.getByText("cliente3@teste.com")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Converter /i }));

    // Troca para a aba Automática (Modo 3)
    const tabModo3 = screen.getByRole("button", { name: /Automática \(IA\)/i });
    fireEvent.click(tabModo3);

    // Mock do arquivo
    const file = new File(["dummy auto content"], "comprovante_pix.pdf", { type: "application/pdf" });
    const input = screen.getByTestId("input-file-auto");
    fireEvent.change(input, { target: { files: [file] } });

    // Clica no botão de conversão automática
    const btnConverterAuto = screen.getByRole("button", { name: /Validar e Converter Automaticamente via IA/i });
    fireEvent.click(btnConverterAuto);

    await waitFor(() => {
      expect(adminPedidosApi.converterAutoAdmin).toHaveBeenCalledWith(
        "pedido-uuid-3",
        file,
        "mock-token-admin"
      );
    });
  });
});

