import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";

/**
 * Resolve uma URL de imagem relativa do backend (ex.: `/api/uploads/...`)
 * para uma URL completa, apontando para o host do backend em vez do
 * frontend — mesma lógica já usada em `components/products/ProductCard.tsx`,
 * extraída aqui para o card de produto do chat (Fase 8) reaproveitar.
 */
export function resolveImageUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  if (url.startsWith("http://") || url.startsWith("https://") || url.startsWith("data:")) {
    return url;
  }
  const baseUrl = getApiBaseUrl();
  const cleanPath = url.startsWith("/") ? url : `/${url}`;
  return `${baseUrl}${cleanPath}`;
}
