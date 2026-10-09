import { DiaUsoIa } from "@/lib/api/metrics";
import { formatarCusto, TITULO_NAO_MEDIDO } from "@/lib/format/metricas";

function formatarDataPtBr(isoDate: string): string {
  const [ano, mes, dia] = isoDate.split("-");
  return ano && mes && dia ? `${dia}/${mes}/${ano}` : isoDate;
}

const ORIGENS = ["chat", "b2b", "admin"] as const;

export function TabelaDiaria({ dias }: { dias: DiaUsoIa[] }) {
  return (
    <section className="space-y-3">
      <h2 className="text-base font-bold text-slate-900">
        Detalhamento Diário{" "}
        <span className="font-normal text-slate-500">— no fuso local do administrador</span>
      </h2>
      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-xs">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-3 py-2 text-left">Data</th>
              <th className="px-3 py-2 text-right">Chats encerrados</th>
              <th className="px-3 py-2 text-right">Chamadas</th>
              {ORIGENS.map((origem) => (
                <th key={origem} className="px-3 py-2 text-right">
                  {origem}
                </th>
              ))}
              <th className="px-3 py-2 text-right">Custo total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {dias.length === 0 ? (
              <tr>
                <td className="px-3 py-4 text-slate-500" colSpan={7}>
                  Nenhum registro no período.
                </td>
              </tr>
            ) : (
              dias.map((dia) => {
                const porOrigem = new Map(dia.por_origem.map((b) => [b.origem, b]));
                return (
                  <tr key={dia.data}>
                    <td className="px-3 py-2 font-medium text-slate-900">
                      {formatarDataPtBr(dia.data)}
                    </td>
                    <td className="px-3 py-2 text-right">{dia.chats_encerrados}</td>
                    <td className="px-3 py-2 text-right">{dia.totais.chamadas}</td>
                    {ORIGENS.map((origem) => (
                      <td
                        key={origem}
                        className="px-3 py-2 text-right"
                        data-testid={`custo-dia-${dia.data}-${origem}`}
                      >
                        {porOrigem.has(origem)
                          ? formatarCusto(porOrigem.get(origem)!.custo_usd)
                          : "—"}
                      </td>
                    ))}
                    <td
                      className="px-3 py-2 text-right font-semibold"
                      data-testid={`custo-dia-${dia.data}-total`}
                      title={dia.totais.custo_usd === null ? TITULO_NAO_MEDIDO : undefined}
                    >
                      {formatarCusto(dia.totais.custo_usd)}
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
