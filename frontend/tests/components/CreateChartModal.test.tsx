import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import CreateChartModal from "@/components/admin/CreateChartModal";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import * as chartsApi from "@/lib/api/charts";

vi.mock("@/lib/api/charts", () => ({
  createAdminChart: vi.fn(),
}));

describe("CreateChartModal", () => {
  const onClose = vi.fn();
  const onCreated = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({
      user: { id: 1, nome: "Admin", email: "admin@empresa.com", perfil: "Admin" },
      token: "mock-token",
    });
  });

  it("não renderiza nada se isOpen for false", () => {
    render(<CreateChartModal isOpen={false} onClose={onClose} onCreated={onCreated} />);
    expect(screen.queryByText(/Criar Gráfico/i)).not.toBeInTheDocument();
  });

  it("renderiza campos e permite preencher dados manuais e submeter", async () => {
    const mockCreated = {
      id: "new-chart-1",
      titulo: "Metas por Região",
      descricao: "Vendas Q3",
      tipo_grafico: "bar",
      config_json: { x_key: "categoria", y_keys: ["valor"], format: "currency" },
      dados_json: [
        { categoria: "Sudeste", valor: 100 },
        { categoria: "Sul", valor: 50 },
      ],
      sql_query: "dynamic_user_data",
      fixado: true,
      ordem: 0,
      criado_em: "2026-10-04T00:00:00Z",
      atualizado_em: "2026-10-04T00:00:00Z",
    };

    vi.mocked(chartsApi.createAdminChart).mockResolvedValueOnce(mockCreated);

    render(<CreateChartModal isOpen={true} onClose={onClose} onCreated={onCreated} />);

    expect(screen.getByText("Criar Gráfico Personalizado")).toBeInTheDocument();

    // Fill title
    const inputTitulo = screen.getByLabelText(/Título do Gráfico/i);
    fireEvent.change(inputTitulo, { target: { value: "Metas por Região" } });

    // Fill description
    const inputDesc = screen.getByLabelText(/Descrição/i);
    fireEvent.change(inputDesc, { target: { value: "Vendas Q3" } });

    // Select format
    const selectFormat = screen.getByLabelText(/Formato dos Valores/i);
    fireEvent.change(selectFormat, { target: { value: "currency" } });

    // Add row button
    const btnAddRow = screen.getByRole("button", { name: /\+ Adicionar Linha/i });
    fireEvent.click(btnAddRow);

    // Inputs for rows
    const catInputs = screen.getAllByPlaceholderText(/Ex: Categoria/i);
    const valInputs = screen.getAllByPlaceholderText(/Ex: 100/i);

    expect(catInputs.length).toBeGreaterThanOrEqual(2);

    fireEvent.change(catInputs[0], { target: { value: "Sudeste" } });
    fireEvent.change(valInputs[0], { target: { value: "100" } });

    fireEvent.change(catInputs[1], { target: { value: "Sul" } });
    fireEvent.change(valInputs[1], { target: { value: "50" } });

    // Submit form
    const btnSubmit = screen.getByRole("button", { name: /Salvar Gráfico/i });
    fireEvent.click(btnSubmit);

    await waitFor(() => {
      expect(chartsApi.createAdminChart).toHaveBeenCalledTimes(1);
    });

    expect(chartsApi.createAdminChart).toHaveBeenCalledWith(
      expect.objectContaining({
        titulo: "Metas por Região",
        descricao: "Vendas Q3",
        tipo_grafico: "bar",
        config_json: expect.objectContaining({
          x_key: "categoria",
          y_keys: ["valor"],
          format: "currency",
        }),
        dados_json: [
          { categoria: "Sudeste", valor: 100 },
          { categoria: "Sul", valor: 50 },
        ],
        sql_query: "dynamic_user_data",
        fixado: true,
      }),
      "mock-token",
    );

    expect(onCreated).toHaveBeenCalledWith(mockCreated);
    expect(onClose).toHaveBeenCalled();
  });

  it("exibe mensagem de erro se a criação falhar", async () => {
    vi.mocked(chartsApi.createAdminChart).mockRejectedValueOnce(
      new Error("Erro de validação do servidor"),
    );

    render(<CreateChartModal isOpen={true} onClose={onClose} onCreated={onCreated} />);

    const inputTitulo = screen.getByLabelText(/Título do Gráfico/i);
    fireEvent.change(inputTitulo, { target: { value: "Gráfico Teste" } });

    const catInputs = screen.getAllByPlaceholderText(/Ex: Categoria/i);
    const valInputs = screen.getAllByPlaceholderText(/Ex: 100/i);
    fireEvent.change(catInputs[0], { target: { value: "Item 1" } });
    fireEvent.change(valInputs[0], { target: { value: "10" } });

    const btnSubmit = screen.getByRole("button", { name: /Salvar Gráfico/i });
    fireEvent.click(btnSubmit);

    await waitFor(() => {
      expect(screen.getByText("Erro de validação do servidor")).toBeInTheDocument();
    });

    expect(onCreated).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });
});
