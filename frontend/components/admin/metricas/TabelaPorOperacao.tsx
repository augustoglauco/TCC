import { MetricasPorOperacao } from "@/lib/api/metrics";
import { formatarCusto, formatarTokens, TITULO_NAO_MEDIDO } from "@/lib/format/metricas";

export function TabelaPorOperacao({ linhas }: { linhas: MetricasPorOperacao[] }) {
  return (
    <section className="space-y-3">
      <h2 className="text-base font-bold text-slate-900">
        Por Operação{" "}
        <span className="font-normal text-slate-500">
          — o nível que separa visão interna de visão externa
        </span>
      </h2>
      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-xs">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-3 py-2 text-left">Operação</th>
              <th className="px-3 py-2 text-left">Origem</th>
              <th className="px-3 py-2 text-left">Ambiente</th>
              <th className="px-3 py-2 text-right">Chamadas</th>
              <th className="px-3 py-2 text-right">Tokens entrada</th>
              <th className="px-3 py-2 text-right">Tokens saída</th>
              <th className="px-3 py-2 text-right">Custo</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {linhas.length === 0 ? (
              <tr>
                <td className="px-3 py-4 text-slate-500" colSpan={7}>
                  Nenhum uso de IA registrado no período.
                </td>
              </tr>
            ) : (
              linhas.map((linha) => {
                const id = `${linha.operacao}-${linha.origem}-${linha.ambiente}`;
                return (
                  <tr key={id}>
                    <td className="px-3 py-2 font-medium text-slate-900">{linha.operacao}</td>
                    <td className="px-3 py-2 text-slate-600">{linha.origem}</td>
                    <td className="px-3 py-2 text-slate-600">{linha.ambiente}</td>
                    <td className="px-3 py-2 text-right">
                      {linha.chamadas.toLocaleString("pt-BR")}
                    </td>
                    <td className="px-3 py-2 text-right">{formatarTokens(linha.tokens_entrada)}</td>
                    <td className="px-3 py-2 text-right">{formatarTokens(linha.tokens_saida)}</td>
                    <td
                      className="px-3 py-2 text-right font-semibold"
                      data-testid={`custo-operacao-${id}`}
                      title={linha.custo_usd === null ? TITULO_NAO_MEDIDO : undefined}
                    >
                      {formatarCusto(linha.custo_usd)}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
