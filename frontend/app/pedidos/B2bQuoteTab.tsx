"use client";

import { Produto } from "@/lib/api/products";
import { QuoteSimulationResult } from "@/lib/api/orders";

interface B2bQuoteTabProps {
  catalogProducts: Produto[];
  selectedProdId: number | null;
  simQuantity: number;
  simCd: string;
  simResult: QuoteSimulationResult | null;
  isSimulating: boolean;
  simError: string | null;
  onProdChange: (id: number) => void;
  onQuantityChange: (q: number) => void;
  onCdChange: (cd: string) => void;
  onSimulate: (e: React.FormEvent) => void;
  onAddToCart: () => void;
}

function ResultadoCotacao({
  simResult,
  onAddToCart,
}: {
  simResult: QuoteSimulationResult;
  onAddToCart: () => void;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-6 shadow-xs">
      <div className="flex justify-between items-center border-b border-slate-100 pb-4">
        <div>
          <h4 className="font-bold text-slate-900 text-base">Resultado da Cotação B2B</h4>
          <p className="text-xs text-slate-500">
            Calculado via motor de precificação e desconto por volume.
          </p>
        </div>
        <span className="rounded-full bg-blue-100 text-blue-800 px-3 py-1 text-xs font-bold">
          {simResult.itens[0].percentual_desconto_aplicado}% de Desconto Aplicado
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-center">
        <div className="rounded-xl border border-slate-100 bg-slate-50 p-4">
          <span className="text-xs text-slate-500 block">Preço Unitário Base</span>
          <span className="text-base font-bold text-slate-800">
            R${" "}
            {Number(simResult.itens[0].preco_unitario_base).toLocaleString("pt-BR", {
              minimumFractionDigits: 2,
            })}
          </span>
        </div>

        <div className="rounded-xl border border-blue-100 bg-blue-50/50 p-4">
          <span className="text-xs text-blue-700 font-medium block">
            Preço com Desconto de Volume
          </span>
          <span className="text-base font-bold text-blue-900">
            R${" "}
            {(
              Number(simResult.itens[0].preco_unitario_base) *
              (1 - Number(simResult.itens[0].percentual_desconto_aplicado) / 100)
            ).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
          </span>
        </div>

        <div className="rounded-xl border border-emerald-100 bg-emerald-50/50 p-4">
          <span className="text-xs text-emerald-700 font-medium block">Valor Total Cotado</span>
          <span className="text-lg font-bold text-emerald-900">
            R${" "}
            {Number(simResult.valor_total).toLocaleString("pt-BR", {
              minimumFractionDigits: 2,
            })}
          </span>
        </div>
      </div>

      <div className="flex justify-end pt-2">
        <button
          type="button"
          onClick={onAddToCart}
          className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2.5 text-xs font-bold text-white hover:bg-emerald-700 transition-colors cursor-pointer"
        >
          <span>Adicionar Cotação ao Carrinho</span> &rarr;
        </button>
      </div>
    </div>
  );
}

export function B2bQuoteTab({
  catalogProducts,
  selectedProdId,
  simQuantity,
  simCd,
  simResult,
  isSimulating,
  simError,
  onProdChange,
  onQuantityChange,
  onCdChange,
  onSimulate,
  onAddToCart,
}: B2bQuoteTabProps) {
  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-blue-100 bg-blue-50/40 p-6 space-y-4">
        <h3 className="text-lg font-bold text-slate-900">🏢 Cotador B2B de Preços Diferenciados</h3>
        <p className="text-xs text-slate-600">
          Simule a aplicação de políticas comerciais com faixas de desconto por quantidade mínima e
          precificação diferenciada B2B via API/MCP.
        </p>

        <form
          onSubmit={onSimulate}
          className="grid grid-cols-1 sm:grid-cols-4 gap-4 items-end pt-2"
        >
          <div className="sm:col-span-2 space-y-1">
            <label className="text-xs font-bold text-slate-700">Produto:</label>
            <select
              value={selectedProdId || ""}
              onChange={(e) => onProdChange(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 focus:ring-2 focus:ring-blue-500 focus:outline-hidden"
            >
              {catalogProducts.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nome} (R${" "}
                  {Number(p.preco).toLocaleString("pt-BR", { minimumFractionDigits: 2 })})
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-bold text-slate-700">Quantidade:</label>
            <input
              type="number"
              min="1"
              value={simQuantity}
              onChange={(e) => onQuantityChange(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 focus:ring-2 focus:ring-blue-500 focus:outline-hidden"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs font-bold text-slate-700">Centro de Distribuição:</label>
            <select
              value={simCd}
              onChange={(e) => onCdChange(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 focus:ring-2 focus:ring-blue-500 focus:outline-hidden"
            >
              <option value="CD-SP">CD-SP (São Paulo)</option>
              <option value="CD-RJ">CD-RJ (Rio de Janeiro)</option>
              <option value="CD-MG">CD-MG (Minas Gerais)</option>
            </select>
          </div>

          <div className="sm:col-span-4 flex justify-end">
            <button
              type="submit"
              disabled={isSimulating}
              className="rounded-lg bg-blue-600 px-5 py-2.5 text-xs font-bold text-white hover:bg-blue-700 disabled:opacity-50 transition-colors cursor-pointer"
            >
              {isSimulating ? "Calculando..." : "Simular Cotação B2B"}
            </button>
          </div>
        </form>
      </div>

      {simError && (
        <div className="rounded-lg bg-rose-50 border border-rose-200 p-4 text-xs text-rose-700">
          {simError}
        </div>
      )}

      {simResult && simResult.itens.length > 0 && (
        <ResultadoCotacao simResult={simResult} onAddToCart={onAddToCart} />
      )}
    </div>
  );
}
