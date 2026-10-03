import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ProductListTable from "@/components/admin/products/ProductListTable";
import type { AdminProduct } from "@/lib/types/adminProducts";

const MOCK_PRODUTO_COM_ESTOQUES: AdminProduct = {
  id: 1,
  nome: "Sensor Infravermelho Passivo",
  descricao: "Sensor com fio para ambientes internos",
  categoria: "Alarmes",
  preco: 120.0,
  preco_base_fornecedor: 75.0,
  especificacoes_tecnicas: "Alcance 12m",
  imagem_url: null,
  imagens: [],
  estoques: [
    {
      id: "est-1",
      centro_distribuicao: "CD-SP",
      quantidade: 15,
      atualizado_em: "2026-10-01T10:00:00Z",
    },
    {
      id: "est-2",
      centro_distribuicao: "CD-PR",
      quantidade: 10,
      atualizado_em: "2026-10-01T10:00:00Z",
    },
  ],
};

const MOCK_PRODUTO_SEM_ESTOQUE: AdminProduct = {
  id: 2,
  nome: "Sirene Eletrônica 120dB",
  descricao: "Sirene de alta potência",
  categoria: "Alarmes",
  preco: 45.0,
  preco_base_fornecedor: 25.0,
  especificacoes_tecnicas: null,
  imagem_url: null,
  imagens: [],
  estoques: [],
};

describe("ProductListTable", () => {
  it("renderiza coluna de estoque total com ícone e somatório correto dos CDs", () => {
    render(
      <ProductListTable
        produtos={[MOCK_PRODUTO_COM_ESTOQUES, MOCK_PRODUTO_SEM_ESTOQUE]}
        loading={false}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    // Deve ter cabeçalho de Estoque
    expect(screen.getByText(/Estoque/i)).toBeInTheDocument();

    // Produto 1 tem 15 + 10 = 25 un
    expect(screen.getByText("25 un")).toBeInTheDocument();

    // Produto 2 tem 0 un
    expect(screen.getByText("0 un")).toBeInTheDocument();
  });

  it("renderiza coluna unificada de preços com duas linhas (revendedor e venda)", () => {
    render(
      <ProductListTable
        produtos={[MOCK_PRODUTO_COM_ESTOQUES]}
        loading={false}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    // Não deve existir a coluna separada 'Preço Fornecedor'
    expect(screen.queryByText("Preço Fornecedor")).not.toBeInTheDocument();

    // Deve exibir rótulo ou indicação de Revendedor e Venda
    expect(screen.getByText("Preço (Rev. / Venda)")).toBeInTheDocument();
    expect(screen.getByText("Rev.:")).toBeInTheDocument();
    expect(screen.getByText("Venda:")).toBeInTheDocument();

    // Valores formatados em BRL
    expect(screen.getByText(/75,00/)).toBeInTheDocument();
    expect(screen.getByText(/120,00/)).toBeInTheDocument();
  });

  it("exibe bubble com estoques individualizados por CD ao passar o mouse sobre o totalizador", async () => {
    const { fireEvent } = await import("@testing-library/react");

    render(
      <ProductListTable
        produtos={[MOCK_PRODUTO_COM_ESTOQUES]}
        loading={false}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    const badgeEstoque = screen.getByText("25 un").closest("span")!;
    expect(badgeEstoque).toBeInTheDocument();

    // Antes do hover não deve mostrar o popup
    expect(screen.queryByText(/Detalhamento por CD/i)).not.toBeInTheDocument();

    // Dispara mouseEnter
    fireEvent.mouseEnter(badgeEstoque);

    // Deve exibir o cabeçalho e cada CD individualizado
    expect(screen.getByText(/Detalhamento por CD/i)).toBeInTheDocument();
    expect(screen.getByText("CD-SP")).toBeInTheDocument();
    expect(screen.getByText("15 un")).toBeInTheDocument();
    expect(screen.getByText("CD-PR")).toBeInTheDocument();
    expect(screen.getByText("10 un")).toBeInTheDocument();

    // Dispara mouseLeave
    fireEvent.mouseLeave(badgeEstoque);
    expect(screen.queryByText(/Detalhamento por CD/i)).not.toBeInTheDocument();
  });

  it("exibe mensagem adequada na bubble quando o produto não tem estoque nos CDs", async () => {
    const { fireEvent } = await import("@testing-library/react");

    render(
      <ProductListTable
        produtos={[MOCK_PRODUTO_SEM_ESTOQUE]}
        loading={false}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    const badgeEstoque = screen.getByText("0 un").closest("span")!;
    fireEvent.mouseEnter(badgeEstoque);

    expect(screen.getByText(/Detalhamento por CD/i)).toBeInTheDocument();
    expect(screen.getByText(/Nenhum CD com estoque registrado/i)).toBeInTheDocument();

    fireEvent.mouseLeave(badgeEstoque);
    expect(screen.queryByText(/Detalhamento por CD/i)).not.toBeInTheDocument();
  });
});
