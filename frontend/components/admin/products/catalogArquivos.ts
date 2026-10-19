import type { CatalogPageResult, ExtractedProductItem } from "@/lib/types/adminProducts";

const EXTENSOES_ACEITAS = /\.(pdf|png|jpe?g|webp|txt|md|csv)$/i;
const TIPOS_IMAGEM_ACEITOS = ["image/png", "image/jpeg", "image/webp"];
const TIPOS_TEXTO_ACEITOS = ["text/plain", "text/markdown", "text/csv"];

export function arquivoAceito(file: File): boolean {
  return (
    file.type === "application/pdf" ||
    TIPOS_IMAGEM_ACEITOS.includes(file.type) ||
    TIPOS_TEXTO_ACEITOS.includes(file.type) ||
    EXTENSOES_ACEITAS.test(file.name)
  );
}

export function chaveArquivo(file: File): string {
  return `${file.name}|${file.size}|${file.lastModified}`;
}

export function nomearArquivoColado(file: File, indice: number): File {
  if (!/^image\.\w+$/i.test(file.name)) return file;
  const extensao = file.name.split(".").pop();
  return new File([file], `imagem-colada-${Date.now()}-${indice}.${extensao}`, {
    type: file.type,
    lastModified: file.lastModified,
  });
}

/** Arquivos colados: da lista `files` ou, na falta, dos `items` do clipboard. */
export function arquivosDoClipboard(data: DataTransfer): File[] {
  const colados = Array.from(data.files);
  if (colados.length > 0) return colados;
  return Array.from(data.items)
    .filter((item) => item.kind === "file")
    .map((item) => item.getAsFile())
    .filter((f): f is File => f !== null);
}

export function produtosDaPagina(pageRes: CatalogPageResult): ExtractedProductItem[] {
  return (pageRes.produtos ?? []).map((p, idx) => ({
    ...p,
    id_temporario: `${pageRes.pagina}_${idx}_${Date.now()}`,
    selecionado: true,
    preco:
      p.preco ||
      (p.preco_base_fornecedor ? Number((p.preco_base_fornecedor * 1.35).toFixed(2)) : null),
  }));
}

export function payloadConfirmacao(selecionados: ExtractedProductItem[]) {
  return {
    produtos: selecionados.map((p) => ({
      nome: p.nome,
      descricao: p.descricao || "",
      categoria: p.categoria || "Geral",
      preco_base_fornecedor: p.preco_base_fornecedor,
      preco: p.preco || p.preco_base_fornecedor || 0,
      especificacoes_tecnicas: p.especificacoes_tecnicas || null,
      imagem_temp_url: p.imagem_temp_url || null,
    })),
  };
}
