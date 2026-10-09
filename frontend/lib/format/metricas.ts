/**
 * Formatação do painel de uso de IA (`/admin/metricas`).
 *
 * A distinção que importa: no ledger `null` significa "não medido" e `0`
 * significa "zero conhecido" (CLIP e modelo local são genuinamente
 * grátis). Um `—` e um `$0.0000` querem dizer coisas diferentes, e o
 * painel não os confunde — é a razão de existir do ledger chegando aos
 * olhos do administrador.
 */

export const NAO_MEDIDO = "—";
export const TITULO_NAO_MEDIDO = "Não medido — a chamada aconteceu, mas o custo/tokens não foram capturados";

export function formatarCusto(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return NAO_MEDIDO;
  return `$${valor.toFixed(4)}`;
}

export function formatarTokens(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return NAO_MEDIDO;
  return valor.toLocaleString("pt-BR");
}
