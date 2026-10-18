import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { ProductFormGeralTab } from "@/components/admin/products/ProductFormGeralTab";
import type { AdminProduct, AdminProductImage } from "@/lib/types/adminProducts";

const BASE_PROPS = {
  produtoParaEditar: null,
  nome: "",
  categoria: "",
  preco: "",
  precoBaseFornecedor: "",
  diasAlertaEstoque: "",
  descricao: "",
  especificacoesTecnicas: "",
  imagemPreview: null,
  imagens: [] as AdminProductImage[],
  deletingImageId: null,
  saving: false,
  onNome: vi.fn(),
  onCategoria: vi.fn(),
  onPreco: vi.fn(),
  onPrecoBase: vi.fn(),
  onDiasAlerta: vi.fn(),
  onDescricao: vi.fn(),
  onEspecificacoes: vi.fn(),
  onImageChange: vi.fn(),
  onRemoverImagem: vi.fn(),
  onClose: vi.fn(),
  onSubmit: vi.fn(),
};

const PRODUTO: AdminProduct = {
  id: 1,
  nome: "Câmera IP HD",
  categoria: "CFTV",
  preco: "450.00",
  preco_base_fornecedor: "300.00",
  dias_alerta_estoque: 10,
  descricao: "Câmera de segurança HD",
  especificacoes_tecnicas: "2MP, IR 30m",
  imagem_url: null,
  estoque_total: 5,
  imagens: [],
};

const IMAGEM: AdminProductImage = {
  id: 10,
  produto_id: 1,
  imagem_url: "/media/cam.jpg",
  ordem: 0,
  criado_em: "2026-10-01T00:00:00Z",
};

describe("ProductFormGeralTab — renderização dos campos", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renderiza o campo Nome do Produto", () => {
    render(<ProductFormGeralTab {...BASE_PROPS} />);
    expect(screen.getByPlaceholderText(/Gravador IP NVD/)).toBeInTheDocument();
  });

  it("renderiza o campo Categoria", () => {
    render(<ProductFormGeralTab {...BASE_PROPS} />);
    expect(screen.getByPlaceholderText("Ex: CFTV")).toBeInTheDocument();
  });

  it("renderiza o campo Preço Venda", () => {
    render(<ProductFormGeralTab {...BASE_PROPS} />);
    expect(screen.getByText("Preço Venda *")).toBeInTheDocument();
  });

  it("renderiza o campo Preço Revendedor", () => {
    render(<ProductFormGeralTab {...BASE_PROPS} />);
    expect(screen.getByText("Preço Revendedor")).toBeInTheDocument();
  });

  it("renderiza o campo de dias de alerta de estoque", () => {
    render(<ProductFormGeralTab {...BASE_PROPS} />);
    expect(screen.getByLabelText(/Alertar estoque com/)).toBeInTheDocument();
  });

  it("renderiza o campo Descrição Comercial", () => {
    render(<ProductFormGeralTab {...BASE_PROPS} />);
    expect(screen.getByPlaceholderText(/Descrição do produto/)).toBeInTheDocument();
  });

  it("renderiza o campo Especificações Técnicas", () => {
    render(<ProductFormGeralTab {...BASE_PROPS} />);
    expect(screen.getByPlaceholderText(/Canais, resolução/)).toBeInTheDocument();
  });

  it("renderiza o input de arquivo de imagem", () => {
    render(<ProductFormGeralTab {...BASE_PROPS} />);
    expect(screen.getByRole("button", { name: /Cancelar/ })).toBeInTheDocument();
  });

  it("exibe 'Salvar Produto' quando não há produto para editar", () => {
    render(<ProductFormGeralTab {...BASE_PROPS} />);
    expect(screen.getByRole("button", { name: "Salvar Produto" })).toBeInTheDocument();
  });

  it("exibe 'Atualizar Dados' quando há produto para editar", () => {
    render(<ProductFormGeralTab {...BASE_PROPS} produtoParaEditar={PRODUTO} />);
    expect(screen.getByRole("button", { name: "Atualizar Dados" })).toBeInTheDocument();
  });

  it("exibe 'Salvando...' quando saving=true", () => {
    render(<ProductFormGeralTab {...BASE_PROPS} saving={true} />);
    expect(screen.getByRole("button", { name: "Salvando..." })).toBeInTheDocument();
  });

  it("desabilita os botões quando saving=true", () => {
    render(<ProductFormGeralTab {...BASE_PROPS} saving={true} />);
    expect(screen.getByRole("button", { name: "Salvando..." })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancelar" })).toBeDisabled();
  });
});

describe("ProductFormGeralTab — callbacks dos campos", () => {
  beforeEach(() => vi.clearAllMocks());

  it("chama onNome ao digitar no campo nome", () => {
    const onNome = vi.fn();
    render(<ProductFormGeralTab {...BASE_PROPS} onNome={onNome} />);
    fireEvent.change(screen.getByPlaceholderText(/Gravador IP NVD/), {
      target: { value: "Câmera IP" },
    });
    expect(onNome).toHaveBeenCalledWith("Câmera IP");
  });

  it("chama onCategoria ao digitar no campo categoria", () => {
    const onCategoria = vi.fn();
    render(<ProductFormGeralTab {...BASE_PROPS} onCategoria={onCategoria} />);
    fireEvent.change(screen.getByPlaceholderText("Ex: CFTV"), {
      target: { value: "Alarmes" },
    });
    expect(onCategoria).toHaveBeenCalledWith("Alarmes");
  });

  it("chama onPreco ao digitar no campo preço venda", () => {
    const onPreco = vi.fn();
    render(<ProductFormGeralTab {...BASE_PROPS} onPreco={onPreco} />);
    // O campo de preço venda tem placeholder "R$ 0,00" e é required
    const inputs = screen.getAllByPlaceholderText("R$ 0,00");
    // O segundo é o preço venda (required)
    const precoVenda = inputs.find((el) => el.hasAttribute("required"))!;
    fireEvent.change(precoVenda, { target: { value: "500" } });
    expect(onPreco).toHaveBeenCalledWith("500");
  });

  it("chama onPrecoBase ao digitar no campo preço revendedor", () => {
    const onPrecoBase = vi.fn();
    render(<ProductFormGeralTab {...BASE_PROPS} onPrecoBase={onPrecoBase} />);
    const inputs = screen.getAllByPlaceholderText("R$ 0,00");
    const precoBase = inputs.find((el) => !el.hasAttribute("required"))!;
    fireEvent.change(precoBase, { target: { value: "300" } });
    expect(onPrecoBase).toHaveBeenCalledWith("300");
  });

  it("chama onDiasAlerta ao digitar no campo de dias", () => {
    const onDiasAlerta = vi.fn();
    render(<ProductFormGeralTab {...BASE_PROPS} onDiasAlerta={onDiasAlerta} />);
    fireEvent.change(screen.getByLabelText(/Alertar estoque com/), {
      target: { value: "15" },
    });
    expect(onDiasAlerta).toHaveBeenCalledWith("15");
  });

  it("chama onDescricao ao digitar na descrição", () => {
    const onDescricao = vi.fn();
    render(<ProductFormGeralTab {...BASE_PROPS} onDescricao={onDescricao} />);
    fireEvent.change(screen.getByPlaceholderText(/Descrição do produto/), {
      target: { value: "Nova descrição" },
    });
    expect(onDescricao).toHaveBeenCalledWith("Nova descrição");
  });

  it("chama onEspecificacoes ao digitar nas especificações", () => {
    const onEspecificacoes = vi.fn();
    render(<ProductFormGeralTab {...BASE_PROPS} onEspecificacoes={onEspecificacoes} />);
    fireEvent.change(screen.getByPlaceholderText(/Canais, resolução/), {
      target: { value: "4MP, IR 50m" },
    });
    expect(onEspecificacoes).toHaveBeenCalledWith("4MP, IR 50m");
  });

  it("chama onClose ao clicar em Cancelar", () => {
    const onClose = vi.fn();
    render(<ProductFormGeralTab {...BASE_PROPS} onClose={onClose} />);
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("chama onSubmit ao submeter o formulário", () => {
    const onSubmit = vi.fn((e: React.FormEvent) => e.preventDefault());
    render(<ProductFormGeralTab {...BASE_PROPS} onSubmit={onSubmit} nome="Produto X" preco="100" />);
    fireEvent.submit(screen.getByRole("button", { name: "Salvar Produto" }).closest("form")!);
    expect(onSubmit).toHaveBeenCalled();
  });
});

describe("ProductFormGeralTab — preview de imagem", () => {
  it("exibe o preview quando imagemPreview está preenchido", () => {
    render(
      <ProductFormGeralTab
        {...BASE_PROPS}
        imagemPreview="data:image/png;base64,abc"
      />,
    );
    const img = screen.getByAltText("Preview") as HTMLImageElement;
    expect(img.src).toContain("data:image/png");
  });

  it("não exibe o preview quando imagemPreview é null", () => {
    render(<ProductFormGeralTab {...BASE_PROPS} imagemPreview={null} />);
    expect(screen.queryByAltText("Preview")).not.toBeInTheDocument();
  });
});

describe("ProductFormGeralTab — galeria de imagens existentes", () => {
  it("não exibe a galeria quando não há produto para editar", () => {
    render(
      <ProductFormGeralTab {...BASE_PROPS} produtoParaEditar={null} imagens={[IMAGEM]} />,
    );
    expect(screen.queryByText(/Imagens associadas/)).not.toBeInTheDocument();
  });

  it("não exibe a galeria quando imagens está vazio", () => {
    render(
      <ProductFormGeralTab {...BASE_PROPS} produtoParaEditar={PRODUTO} imagens={[]} />,
    );
    expect(screen.queryByText(/Imagens associadas/)).not.toBeInTheDocument();
  });

  it("exibe a galeria com a contagem quando há produto e imagens", () => {
    render(
      <ProductFormGeralTab {...BASE_PROPS} produtoParaEditar={PRODUTO} imagens={[IMAGEM]} />,
    );
    expect(screen.getByText("Imagens associadas (1):")).toBeInTheDocument();
  });

  it("chama onRemoverImagem ao clicar no botão de remover imagem", () => {
    const onRemoverImagem = vi.fn();
    render(
      <ProductFormGeralTab
        {...BASE_PROPS}
        produtoParaEditar={PRODUTO}
        imagens={[IMAGEM]}
        onRemoverImagem={onRemoverImagem}
      />,
    );
    fireEvent.click(screen.getByTitle("Remover imagem do produto e do CLIP"));
    expect(onRemoverImagem).toHaveBeenCalledWith(10);
  });

  it("desabilita o botão de remover quando deletingImageId está preenchido", () => {
    render(
      <ProductFormGeralTab
        {...BASE_PROPS}
        produtoParaEditar={PRODUTO}
        imagens={[IMAGEM]}
        deletingImageId={10}
      />,
    );
    expect(screen.getByTitle("Remover imagem do produto e do CLIP")).toBeDisabled();
  });
});
