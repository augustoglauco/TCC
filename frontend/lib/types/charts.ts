/**
 * Tipos dos gráficos dinâmicos do painel admin (R11, Fase 9).
 *
 * `dados_json` é sempre o resultado de um SELECT agregado, então cada célula
 * é um escalar JSON — o backend nunca devolve objeto ou lista aninhada aqui.
 */

/** Valor de uma célula de dados de gráfico. */
export type ChartCellValue = string | number | boolean | null;

/** Formatação aplicada aos valores do eixo Y e do tooltip. */
export type ChartFormat = "currency" | "number" | "percent";

/** Uma linha de `dados_json` (uma linha do resultado da query agregada). */
export type ChartRow = Record<string, ChartCellValue>;

/** Configuração de renderização gravada em `config_json`. */
export interface ChartConfig {
  x_key?: string;
  y_keys?: string[];
  labels?: Record<string, string>;
  format?: ChartFormat;
  palette?: string[];
  [key: string]: unknown;
}
