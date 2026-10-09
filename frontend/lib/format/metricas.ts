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
export const TITULO_NAO_MEDIDO =
  "Não medido — a chamada aconteceu, mas o custo/tokens não foram capturados";

export function formatarCusto(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return NAO_MEDIDO;
  // Um custo medido e genuinamente zero ($0.0000) e um custo medido mas tão
  // pequeno que 4 casas decimais o arredondariam para $0.0000 (ex.: 0.00004)
  // são coisas diferentes — a segunda ainda é um gasto real, só pequeno
  // demais para a precisão de exibição. Colapsá-los é exatamente a
  // confusão que este ledger existe para evitar (ver cabeçalho do módulo),
  // então um valor não-zero abaixo do limiar de exibição ganha seu próprio
  // rótulo em vez de aparentar ser o zero conhecido.
  if (valor !== 0 && Math.abs(valor) < 0.0001) return "<$0.0001";
  return `$${valor.toFixed(4)}`;
}

export function formatarTokens(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return NAO_MEDIDO;
  return valor.toLocaleString("pt-BR");
}

export function formatarDataPtBr(isoDate: string): string {
  if (!isoDate) return "";
  const [ano, mes, dia] = isoDate.split("-");
  return ano && mes && dia ? `${dia}/${mes}/${ano}` : isoDate;
}
