import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { CartTab } from "@/app/pedidos/CartTab";
import { useCartStore } from "@/lib/hooks/useCartStore";
import type { FreightQuoteResult } from "@/lib/api/orders";

const USER = { nome: "Ana Silva", email: "ana@empresa.com", perfil: "Cliente" };

const BASE_PROPS = {
  currentUser: USER,
  freightResult: null,
  isCalculatingFreight: false,
  isSubmittingOrder: false,
  checkoutError: null,
  cep: "",
  onCepChange: vi.fn(),
  onCalcFreight: vi.fn(),
  onCheckout: vi.fn(),
};

const ITEM_1 = {
  produtoId: 1,
  nome: "Câmera IP HD",
  preco: 450.0,
  imagemUrl: null,
  quantidade: 2,
  centroDistribuicao: "SP",
};

const ITEM_2 = {
  produtoId: 2,
  nome: "NVR 16 Canais",
  preco: 1200.0,
  imagemUrl: "http://localhost:8000/img/nvr.jpg",
  quantidade: 1,
  centroDistribuicao: "RJ",
};

const FRETE: FreightQuoteResult = {
  cep: "01000-000",
  peso_total_kg: 3.5,
  custo_estimado: 85.5,
  prazo_dias: 5,
};

describe("CartTab — carrinho vazio", () => {
  beforeEach(() => {
    useCartStore.setState({ items: [] });
  });

  it("exibe mensagem de carrinho vazio", () => {
    render(<CartTab {...BASE_PROPS} />);
    expect(screen.getByText("Seu carrinho está vazio")).toBeInTheDocument();
  });

  it("exibe link para o catálogo de produtos", () => {
    render(<CartTab {...BASE_PROPS} />);
    expect(screen.getByRole("link", { name: /Ver Catálogo de Produtos/ })).toBeInTheDocument();
  });

  it("não exibe o botão de finalizar pedido", () => {
    render(<CartTab {...BASE_PROPS} />);
    expect(
      screen.queryByRole("button", { name: /Finalizar Pedido/ }),
    ).not.toBeInTheDocument();
  });
});

describe("CartTab — carrinho com itens", () => {
  beforeEach(() => {
    useCartStore.setState({ items: [ITEM_1, ITEM_2] });
  });

  it("exibe os nomes dos produtos", () => {
    render(<CartTab {...BASE_PROPS} />);
    expect(screen.getByText("Câmera IP HD")).toBeInTheDocument();
    expect(screen.getByText("NVR 16 Canais")).toBeInTheDocument();
  });

  it("exibe a contagem de itens no cabeçalho", () => {
    render(<CartTab {...BASE_PROPS} />);
    expect(screen.getByText("Itens Selecionados (2)")).toBeInTheDocument();
  });

  it("exibe o preço unitário de cada item", () => {
    render(<CartTab {...BASE_PROPS} />);
    expect(screen.getByText(/R\$ 450,00 \/ un/)).toBeInTheDocument();
    expect(screen.getByText(/R\$ 1\.200,00 \/ un/)).toBeInTheDocument();
  });

  it("exibe o subtotal de cada item (preco × quantidade)", () => {
    render(<CartTab {...BASE_PROPS} />);
    // ITEM_1: 450 × 2 = 900
    expect(screen.getByText(/R\$\s*900,00/)).toBeInTheDocument();
    // ITEM_2: 1200 × 1 = 1200
    expect(screen.getAllByText(/R\$\s*1\.200,00/).length).toBeGreaterThan(0);
  });

  it("exibe o subtotal total no resumo", () => {
    render(<CartTab {...BASE_PROPS} />);
    // total = 900 + 1200 = 2100 — aparece no resumo lateral
    expect(screen.getAllByText(/R\$\s*2\.100,00/).length).toBeGreaterThan(0);
  });

  it("exibe o centro de distribuição de cada item", () => {
    render(<CartTab {...BASE_PROPS} />);
    expect(screen.getByText("SP")).toBeInTheDocument();
    expect(screen.getByText("RJ")).toBeInTheDocument();
  });

  it("exibe a quantidade de cada item", () => {
    render(<CartTab {...BASE_PROPS} />);
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("exibe o nome e e-mail do usuário autenticado no resumo", () => {
    render(<CartTab {...BASE_PROPS} />);
    expect(screen.getByText("Ana Silva")).toBeInTheDocument();
    expect(screen.getByText("ana@empresa.com")).toBeInTheDocument();
  });

  it("exibe o perfil do usuário no badge", () => {
    render(<CartTab {...BASE_PROPS} />);
    expect(screen.getByText("Cliente")).toBeInTheDocument();
  });

  it("exibe 'Calcular acima' quando não há resultado de frete", () => {
    render(<CartTab {...BASE_PROPS} />);
    expect(screen.getByText("Calcular acima")).toBeInTheDocument();
  });

  it("chama onCepChange ao digitar no campo de CEP", () => {
    const onCepChange = vi.fn();
    render(<CartTab {...BASE_PROPS} onCepChange={onCepChange} />);
    fireEvent.change(screen.getByPlaceholderText(/CEP/), { target: { value: "01000-000" } });
    expect(onCepChange).toHaveBeenCalledWith("01000-000");
  });

  it("chama onCalcFreight ao submeter o formulário de frete", () => {
    const onCalcFreight = vi.fn((e: React.FormEvent) => e.preventDefault());
    render(<CartTab {...BASE_PROPS} cep="01000-000" onCalcFreight={onCalcFreight} />);
    fireEvent.submit(screen.getByRole("button", { name: "Calcular Frete" }).closest("form")!);
    expect(onCalcFreight).toHaveBeenCalled();
  });

  it("desabilita o botão de calcular frete quando cep está vazio", () => {
    render(<CartTab {...BASE_PROPS} cep="" />);
    expect(screen.getByRole("button", { name: "Calcular Frete" })).toBeDisabled();
  });

  it("habilita o botão de calcular frete quando cep está preenchido", () => {
    render(<CartTab {...BASE_PROPS} cep="01000-000" />);
    expect(screen.getByRole("button", { name: "Calcular Frete" })).not.toBeDisabled();
  });

  it("chama onCheckout ao clicar em Finalizar Pedido", () => {
    const onCheckout = vi.fn();
    render(<CartTab {...BASE_PROPS} onCheckout={onCheckout} />);
    fireEvent.click(screen.getByRole("button", { name: /Finalizar Pedido/ }));
    expect(onCheckout).toHaveBeenCalledOnce();
  });

  it("desabilita o botão de checkout enquanto isSubmittingOrder=true", () => {
    render(<CartTab {...BASE_PROPS} isSubmittingOrder={true} />);
    expect(screen.getByRole("button", { name: /Processando Reserva/ })).toBeDisabled();
  });

  it("exibe 'Calculando...' no botão de frete enquanto isCalculatingFreight=true", () => {
    render(<CartTab {...BASE_PROPS} cep="01000-000" isCalculatingFreight={true} />);
    expect(screen.getByRole("button", { name: "Calculando..." })).toBeDisabled();
  });

  it("exibe o erro de checkout quando checkoutError está preenchido", () => {
    render(<CartTab {...BASE_PROPS} checkoutError="Estoque insuficiente para o item." />);
    expect(screen.getByText("Estoque insuficiente para o item.")).toBeInTheDocument();
  });
});

describe("CartTab — com resultado de frete", () => {
  beforeEach(() => {
    useCartStore.setState({ items: [ITEM_1] });
  });

  it("exibe prazo e peso do frete", () => {
    render(<CartTab {...BASE_PROPS} freightResult={FRETE} />);
    expect(screen.getByText(/5 dias úteis/)).toBeInTheDocument();
    expect(screen.getByText(/3\.5 kg total/)).toBeInTheDocument();
  });

  it("exibe o custo do frete formatado", () => {
    render(<CartTab {...BASE_PROPS} freightResult={FRETE} />);
    expect(screen.getAllByText(/R\$\s*85,50/).length).toBeGreaterThan(0);
  });

  it("exibe o total geral somando subtotal + frete", () => {
    render(<CartTab {...BASE_PROPS} freightResult={FRETE} />);
    // ITEM_1: 450 × 2 = 900 + 85.50 = 985.50
    expect(screen.getByText(/R\$\s*985,50/)).toBeInTheDocument();
  });
});

describe("CartTab — ações de quantidade e remoção", () => {
  beforeEach(() => {
    useCartStore.setState({ items: [ITEM_1] });
  });

  it("chama updateQuantity ao clicar em '+'", () => {
    const updateQuantity = vi.fn();
    useCartStore.setState({ items: [ITEM_1], updateQuantity });
    render(<CartTab {...BASE_PROPS} />);
    fireEvent.click(screen.getByRole("button", { name: "+" }));
    expect(updateQuantity).toHaveBeenCalledWith(1, "SP", 3);
  });

  it("chama updateQuantity ao clicar em '-'", () => {
    const updateQuantity = vi.fn();
    useCartStore.setState({ items: [ITEM_1], updateQuantity });
    render(<CartTab {...BASE_PROPS} />);
    fireEvent.click(screen.getByRole("button", { name: "-" }));
    expect(updateQuantity).toHaveBeenCalledWith(1, "SP", 1);
  });

  it("chama removeItem ao clicar em ✕", () => {
    const removeItem = vi.fn();
    useCartStore.setState({ items: [ITEM_1], removeItem });
    render(<CartTab {...BASE_PROPS} />);
    fireEvent.click(screen.getByTitle("Remover item"));
    expect(removeItem).toHaveBeenCalledWith(1, "SP");
  });

  it("chama clearCart ao clicar em 'Esvaziar carrinho'", () => {
    const clearCart = vi.fn();
    useCartStore.setState({ items: [ITEM_1], clearCart });
    render(<CartTab {...BASE_PROPS} />);
    fireEvent.click(screen.getByText("Esvaziar carrinho"));
    expect(clearCart).toHaveBeenCalledOnce();
  });
});

describe("CartTab — imagem do item", () => {
  it("exibe a imagem quando imagemUrl está preenchida", () => {
    useCartStore.setState({ items: [ITEM_2] });
    render(<CartTab {...BASE_PROPS} />);
    const img = screen.getByAltText("NVR 16 Canais") as HTMLImageElement;
    expect(img.src).toContain("nvr.jpg");
  });

  it("exibe placeholder 'Foto' quando imagemUrl é null", () => {
    useCartStore.setState({ items: [ITEM_1] });
    render(<CartTab {...BASE_PROPS} />);
    expect(screen.getByText("Foto")).toBeInTheDocument();
  });
});
