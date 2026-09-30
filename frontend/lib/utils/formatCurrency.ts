/** Formata um valor em Real (R$ 1.234,56) — mesmo padrão já usado em
 * `components/products/ProductCard.tsx`, extraído para os cards do chat
 * (Fase 8) reaproveitarem. */
export function formatarPrecoBRL(valor: number | string): string {
  const numero = typeof valor === "string" ? Number(valor) : valor;
  if (Number.isNaN(numero)) return `R$ ${valor}`;
  const numStr = numero.toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `R$ ${numStr}`;
}
