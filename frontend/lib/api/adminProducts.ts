import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";
import type {
  AdminProduct,
  AdminProductImage,
  AdminProductsListResponse,
  AdminProductsQueryParams,
  CatalogConfirmPayload,
  CatalogConfirmResponse,
  CatalogExtractionProgress,
  CatalogPageResult,
} from "@/lib/types/adminProducts";

function parseSseBlock(block: string): { event: string; data: string } | null {
  let event = "message";
  let data = "";
  for (const linha of block.split("\n")) {
    if (linha.startsWith("event:")) {
      event = linha.slice("event:".length).trim();
    } else if (linha.startsWith("data:")) {
      data += linha.slice("data:".length).trim();
    }
  }
  return data ? { event, data } : null;
}

export async function fetchAdminProducts(
  params?: AdminProductsQueryParams
): Promise<AdminProductsListResponse> {
  const baseUrl = getApiBaseUrl();
  const query = new URLSearchParams();
  if (params?.termo) query.set("termo", params.termo);
  if (params?.categoria) query.set("categoria", params.categoria);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));

  const url = `${baseUrl}/api/admin/produtos${query.toString() ? `?${query.toString()}` : ""}`;
  const res = await fetch(url, { method: "GET" });
  if (!res.ok) {
    throw new Error(`Erro ao listar produtos (${res.status})`);
  }
  return res.json();
}

export async function fetchAdminCategories(): Promise<string[]> {
  const baseUrl = getApiBaseUrl();
  const res = await fetch(`${baseUrl}/api/admin/produtos/categorias`);
  if (!res.ok) {
    throw new Error(`Erro ao listar categorias (${res.status})`);
  }
  return res.json();
}

export async function fetchAdminProduct(id: number): Promise<AdminProduct> {
  const baseUrl = getApiBaseUrl();
  const res = await fetch(`${baseUrl}/api/admin/produtos/${id}`);
  if (!res.ok) {
    throw new Error(`Erro ao obter produto ${id} (${res.status})`);
  }
  return res.json();
}

export async function createAdminProduct(
  data: Partial<AdminProduct>
): Promise<AdminProduct> {
  const baseUrl = getApiBaseUrl();
  const res = await fetch(`${baseUrl}/api/admin/produtos`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    throw new Error(`Erro ao criar produto (${res.status})`);
  }
  return res.json();
}

export async function updateAdminProduct(
  id: number,
  data: Partial<AdminProduct>
): Promise<AdminProduct> {
  const baseUrl = getApiBaseUrl();
  const res = await fetch(`${baseUrl}/api/admin/produtos/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    throw new Error(`Erro ao atualizar produto ${id} (${res.status})`);
  }
  return res.json();
}

export async function deleteAdminProduct(id: number): Promise<void> {
  const baseUrl = getApiBaseUrl();
  const res = await fetch(`${baseUrl}/api/admin/produtos/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error(`Erro ao excluir produto ${id} (${res.status})`);
  }
}

export async function uploadAdminProductImage(
  produtoId: number,
  file: File
): Promise<AdminProductImage> {
  const baseUrl = getApiBaseUrl();
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${baseUrl}/api/admin/produtos/${produtoId}/imagens`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    throw new Error(`Erro ao enviar imagem (${res.status})`);
  }
  return res.json();
}

export async function deleteAdminProductImage(
  produtoId: number,
  imgId: number
): Promise<void> {
  const baseUrl = getApiBaseUrl();
  const res = await fetch(
    `${baseUrl}/api/admin/produtos/${produtoId}/imagens/${imgId}`,
    {
      method: "DELETE",
    }
  );
  if (!res.ok) {
    throw new Error(`Erro ao excluir imagem (${res.status})`);
  }
}

export async function confirmCatalogExtraction(
  payload: CatalogConfirmPayload
): Promise<CatalogConfirmResponse> {
  const baseUrl = getApiBaseUrl();
  const res = await fetch(`${baseUrl}/api/admin/produtos/catalogo/confirmar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`Erro ao confirmar produtos (${res.status})`);
  }
  return res.json();
}

export async function uploadTempImage(file: File): Promise<string> {
  const baseUrl = getApiBaseUrl();
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${baseUrl}/api/admin/produtos/upload-temp`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    throw new Error(`Erro ao enviar foto (${res.status})`);
  }
  const data = await res.json();
  return data.imagem_temp_url;
}

export interface ExtractCatalogStreamOptions {
  provider?: "local" | "external";
  fallbackExternal?: boolean;
}

export interface ExtractCatalogCallbacks {
  onProgress?: (progress: CatalogExtractionProgress) => void;
  onPageComplete?: (pageResult: CatalogPageResult) => void;
  onDone?: (data: { total_produtos: number; total_paginas: number }) => void;
  onError?: (error: string) => void;
}

export async function extractCatalogStream(
  files: File[],
  options: ExtractCatalogStreamOptions,
  callbacks: ExtractCatalogCallbacks
): Promise<void> {
  const baseUrl = getApiBaseUrl();
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  formData.append("provider", options.provider ?? "local");
  formData.append("fallback_external", String(options.fallbackExternal ?? true));

  let res: Response;
  try {
    res = await fetch(`${baseUrl}/api/admin/produtos/catalogo/extrair/stream`, {
      method: "POST",
      body: formData,
    });
  } catch (err: any) {
    callbacks.onError?.(err?.message ?? "Falha de conexão com o servidor");
    return;
  }

  if (!res.ok || !res.body) {
    callbacks.onError?.(`Erro ao iniciar extração (${res.status})`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      if (!part.trim()) continue;
      const sse = parseSseBlock(part);
      if (!sse) continue;

      try {
        const parsed = JSON.parse(sse.data);
        if (sse.event === "progresso") {
          callbacks.onProgress?.(parsed);
        } else if (sse.event === "pagina_concluida") {
          callbacks.onPageComplete?.(parsed);
        } else if (sse.event === "done") {
          callbacks.onDone?.(parsed);
        }
      } catch (err) {
        console.warn("Erro ao fazer parse de evento SSE:", err);
      }
    }
  }
}
