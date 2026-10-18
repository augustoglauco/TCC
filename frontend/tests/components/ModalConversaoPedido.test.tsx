import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ModalConversaoPedido from "@/components/admin/ModalConversaoPedido";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import * as adminPedidosApi from "@/lib/api/adminPedidos";
import type { PedidoAdminItem } from "@/lib/api/adminPedidos";

vi.mock("@/lib/api/adminPedidos", () => ({
  converterManualSimples: vi.fn(),
  analisarComprovante: vi.fn(),
  confirmarConversaoManual: vi.fn(),
  converterAutoAdmin: vi.fn(),
}));

const makePedido = (overrides: Partial<PedidoAdminItem> = {}): PedidoAdminItem => ({
  id: "pedido-uuid-abc",
  status: "reservado",
  user_email: "cliente@teste.com",
  conversation_id: "conv-1",
  comprovante_url: null,
  tipo_conversao: null,
  convertido_em: null,
  convertido_por: null,
  llm_parecer: null,
  criado_em: new Date().toISOString(),
  valor_total: 1500.0,
  itens: [
    {
      id: "item-1",
      produto_id: 1,
      centro_distribuicao: "CD-SP",
      quantidade: 1,
      preco_unitario: 1500.0,
      subtotal: 1500.0,
    },
  ],
  ...overrides,
});

const defaultProps = {
  isOpen: true,
  onClose: vi.fn(),
  onSuccess: vi.fn(),
};

describe("ModalConversaoPedido", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    defaultProps.onClose = vi.fn();
    defaultProps.onSuccess = vi.fn();
    useAuthStore.setState({
      user: { id: 1, nome: "Admin Teste", email: "admin@empresa.com", perfil: "Admin" },
      token: "mock-token",
    });
  });

  it("não renderiza quando isOpen=false", () => {
    render(<ModalConversaoPedido {...defaultProps} isOpen={false} pedido={makePedido()} />);
    expect(screen.queryByText(/Modal de Conversão/i)).not.toBeInTheDocument();
  });

  it("não renderiza quando pedido=null", () => {
    render(<ModalConversaoPedido {...defaultProps} pedido={null} />);
    expect(screen.queryByText(/Modal de Conversão/i)).not.toBeInTheDocument();
  });

  it("exibe resumo do pedido (email, valor, status)", () => {
    render(<ModalConversaoPedido {...defaultProps} pedido={makePedido()} />);
    expect(screen.getByText("cliente@teste.com")).toBeInTheDocument();
    expect(screen.getByText(/1\.500,00/)).toBeInTheDocument();
    expect(screen.getByText("reservado")).toBeInTheDocument();
  });

  it("exibe link do comprovante quando comprovante_url está preenchido", () => {
    render(
      <ModalConversaoPedido
        {...defaultProps}
        pedido={makePedido({ comprovante_url: "https://cdn.example.com/comp.pdf" })}
      />,
    );
    expect(screen.getByText("Abrir Arquivo")).toBeInTheDocument();
  });

  it("exibe parecer da auditoria quando llm_parecer está preenchido", () => {
    render(
      <ModalConversaoPedido
        {...defaultProps}
        pedido={makePedido({ llm_parecer: '{"valido":true}' })}
      />,
    );
    expect(screen.getByText(/Parecer da Auditoria/i)).toBeInTheDocument();
  });

  it("chama onClose ao clicar no botão ✕", async () => {
    const user = userEvent.setup();
    render(<ModalConversaoPedido {...defaultProps} pedido={makePedido()} />);
    await user.click(screen.getByText("✕"));
    expect(defaultProps.onClose).toHaveBeenCalledOnce();
  });

  // --- Modo Simples ---
  describe("Modo 1 — Manual Simples", () => {
    it("converte com sucesso e chama onSuccess + onClose", async () => {
      vi.mocked(adminPedidosApi.converterManualSimples).mockResolvedValue(undefined as never);
      const user = userEvent.setup();
      render(<ModalConversaoPedido {...defaultProps} pedido={makePedido()} />);

      await user.click(screen.getByText("Confirmar Conversão Simples"));
      await waitFor(() => expect(defaultProps.onSuccess).toHaveBeenCalledOnce());
      expect(defaultProps.onClose).toHaveBeenCalledOnce();
    });

    it("exibe erro quando converterManualSimples rejeita", async () => {
      vi.mocked(adminPedidosApi.converterManualSimples).mockRejectedValue(
        new Error("Falha na conversão"),
      );
      const user = userEvent.setup();
      render(<ModalConversaoPedido {...defaultProps} pedido={makePedido()} />);

      await user.click(screen.getByText("Confirmar Conversão Simples"));
      await waitFor(() => expect(screen.getByText(/Falha na conversão/i)).toBeInTheDocument());
      expect(defaultProps.onSuccess).not.toHaveBeenCalled();
    });
  });

  // --- Modo Padrão (Manual com IA) ---
  describe("Modo 2 — Manual com IA", () => {
    it("botão Auditar fica desabilitado sem arquivo selecionado", async () => {
      const user = userEvent.setup();
      render(<ModalConversaoPedido {...defaultProps} pedido={makePedido()} />);
      await user.click(screen.getByText("2. Manual com IA"));
      expect(screen.getByText(/Auditar com IA/i)).toBeDisabled();
    });

    it("exibe resultado da auditoria após analisarComprovante", async () => {
      vi.mocked(adminPedidosApi.analisarComprovante).mockResolvedValue({
        comprovante_url: "https://cdn.example.com/comp.pdf",
        parecer: {
          valido: true,
          valor_pago: 1500.0,
          divergencia: 0,
          justificativa: "Pagamento integral confirmado",
          codigo_transacao: "TXN-123",
        },
      });
      const user = userEvent.setup();
      render(<ModalConversaoPedido {...defaultProps} pedido={makePedido()} />);
      await user.click(screen.getByText("2. Manual com IA"));

      const fileInput = screen.getByTestId("input-file-analise");
      const file = new File(["conteudo"], "comp.pdf", { type: "application/pdf" });
      await user.upload(fileInput, file);

      await user.click(screen.getByText(/Auditar com IA/i));
      await waitFor(() =>
        expect(screen.getByText(/Resultado da Auditoria/i)).toBeInTheDocument(),
      );
      expect(screen.getByText(/Pagamento integral confirmado/i)).toBeInTheDocument();
      expect(screen.getByText("Válido")).toBeInTheDocument();
    });

    it("exibe erro quando analisarComprovante rejeita", async () => {
      vi.mocked(adminPedidosApi.analisarComprovante).mockRejectedValue(
        new Error("Erro de visão"),
      );
      const user = userEvent.setup();
      render(<ModalConversaoPedido {...defaultProps} pedido={makePedido()} />);
      await user.click(screen.getByText("2. Manual com IA"));

      const fileInput = screen.getByTestId("input-file-analise");
      await user.upload(fileInput, new File(["x"], "c.pdf", { type: "application/pdf" }));
      await user.click(screen.getByText(/Auditar com IA/i));

      await waitFor(() => expect(screen.getByText(/Erro de visão/i)).toBeInTheDocument());
    });
  });

  // --- Modo Auto ---
  describe("Modo 3 — Automática (IA)", () => {
    it("botão converter fica desabilitado sem arquivo", async () => {
      const user = userEvent.setup();
      render(<ModalConversaoPedido {...defaultProps} pedido={makePedido()} />);
      await user.click(screen.getByText("3. Automática (IA)"));
      expect(screen.getByText(/Validar e Converter Automaticamente/i)).toBeDisabled();
    });

    it("converte automaticamente com sucesso", async () => {
      vi.mocked(adminPedidosApi.converterAutoAdmin).mockResolvedValue(undefined as never);
      const user = userEvent.setup();
      render(<ModalConversaoPedido {...defaultProps} pedido={makePedido()} />);
      await user.click(screen.getByText("3. Automática (IA)"));

      const fileInput = screen.getByTestId("input-file-auto");
      await user.upload(fileInput, new File(["x"], "comp.jpg", { type: "image/jpeg" }));
      await user.click(screen.getByText(/Validar e Converter Automaticamente/i));

      await waitFor(() => expect(defaultProps.onSuccess).toHaveBeenCalledOnce());
      expect(defaultProps.onClose).toHaveBeenCalledOnce();
    });

    it("exibe erro quando converterAutoAdmin rejeita", async () => {
      vi.mocked(adminPedidosApi.converterAutoAdmin).mockRejectedValue(
        new Error("Falha na conversão automática"),
      );
      const user = userEvent.setup();
      render(<ModalConversaoPedido {...defaultProps} pedido={makePedido()} />);
      await user.click(screen.getByText("3. Automática (IA)"));

      const fileInput = screen.getByTestId("input-file-auto");
      await user.upload(fileInput, new File(["x"], "comp.jpg", { type: "image/jpeg" }));
      await user.click(screen.getByText(/Validar e Converter Automaticamente/i));

      await waitFor(() =>
        expect(screen.getByText(/Falha na conversão automática/i)).toBeInTheDocument(),
      );
    });
  });
});
