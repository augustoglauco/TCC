export interface AdminProductImage {
  id: number;
  produto_id: number;
  imagem_url: string;
  clip_image_id: string | null;
  criado_em: string;
}

export interface AdminProduct {
  id: number;
  nome: string;
  descricao: string;
  preco: number;
  categoria: string;
  especificacoes_tecnicas: string | null;
  dimensoes_cm: string | null;
  peso_kg: number | null;
  preco_promocional: number | null;
  promocao_valida_ate: string | null;
  preco_base_fornecedor: number | null;
  imagem_url: string | null;
  imagens: AdminProductImage[];
  ativo: boolean;
  criado_em?: string;
  atualizado_em?: string;
}

export interface AdminProductsListResponse {
  items: AdminProduct[];
  total: number;
}

export interface AdminProductsQueryParams {
  termo?: string;
  categoria?: string;
  limit?: number;
  offset?: number;
}

export interface ExtractedProductItem {
  id_temporario?: string;
  nome: string;
  descricao?: string;
  categoria?: string;
  preco_base_fornecedor?: number | null;
  preco?: number | null;
  especificacoes_tecnicas?: string | null;
  imagem_temp_url?: string | null;
  pagina_origem?: number;
  confianca?: number;
  provider_usado?: string;
  selecionado?: boolean;
}

export interface CatalogPageResult {
  pagina: number;
  total_paginas: number;
  produtos: ExtractedProductItem[];
  provider_usado: string;
  imagem_preview_url?: string | null;
}

export interface CatalogExtractionProgress {
  pagina: number;
  total: number;
  status: string;
}

export interface CatalogConfirmPayload {
  produtos: {
    nome: string;
    descricao?: string;
    categoria?: string;
    preco_base_fornecedor?: number | null;
    preco?: number | null;
    especificacoes_tecnicas?: string | null;
    imagem_temp_url?: string | null;
  }[];
}

export interface CatalogConfirmResponse {
  criados: number;
  produtos: AdminProduct[];
}
