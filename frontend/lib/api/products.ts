import { getApiBaseUrl } from "./apiBaseUrl";

export interface ProdutoEstoque {
  id: string;
  centro_distribuicao: string;
  quantidade: number;
  atualizado_em: string;
}

export interface ProdutoImagem {
  id: number;
  imagem_url: string;
  clip_image_id?: string | null;
  is_principal: boolean;
  criado_em: string;
}

export interface ProdutoDescontoVolume {
  id: string;
  quantidade_minima: number;
  percentual_desconto: number;
}

export interface Produto {
  id: number;
  nome: string;
  descricao: string;
  preco: number;
  categoria: string;
  especificacoes_tecnicas?: string | null;
  dimensoes_cm?: string | null;
  peso_kg?: number | null;
  preco_promocional?: number | null;
  promocao_valida_ate?: string | null;
  preco_base_fornecedor?: number | null;
  imagem_url?: string | null;
  estoques: ProdutoEstoque[];
  imagens: ProdutoImagem[];
  descontos_volume?: ProdutoDescontoVolume[];
}

export interface PaginatedProdutosResponse {
  items: Produto[];
  total: number;
  limit: number;
  offset: number;
}

export interface FetchProductsParams {
  termo?: string;
  categoria?: string;
  limit?: number;
  offset?: number;
}

export async function fetchProducts(
  params: FetchProductsParams = {},
): Promise<PaginatedProdutosResponse> {
  const baseUrl = getApiBaseUrl();
  const urlParams = new URLSearchParams();

  if (params.termo && params.termo.trim()) {
    urlParams.set("termo", params.termo.trim());
  }
  if (params.categoria && params.categoria.trim() && params.categoria !== "Todas") {
    urlParams.set("categoria", params.categoria.trim());
  }
  if (params.limit) {
    urlParams.set("limit", params.limit.toString());
  }
  if (params.offset !== undefined) {
    urlParams.set("offset", params.offset.toString());
  }

  const response = await fetch(`${baseUrl}/api/products?${urlParams.toString()}`);
  if (!response.ok) {
    throw new Error(`Erro ao buscar produtos: ${response.statusText}`);
  }
  return response.json();
}

export async function fetchProductCategories(): Promise<string[]> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/api/products/categorias`);
  if (!response.ok) {
    throw new Error(`Erro ao buscar categorias: ${response.statusText}`);
  }
  return response.json();
}

export async function fetchProductById(id: number | string): Promise<Produto> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/api/products/${id}`);
  if (response.status === 404) {
    throw new Error("Produto não encontrado.");
  }
  if (!response.ok) {
    throw new Error(`Erro ao buscar produto: ${response.statusText}`);
  }
  return response.json();
}
