import { BlocoMetricas } from "@/lib/api/metrics";
import { formatarCusto, formatarTokens, TITULO_NAO_MEDIDO } from "@/lib/format/metricas";

interface CardMetricaProps {
  titulo: string;
  subtitulo?: string;
  bloco: BlocoMetricas;
  /** Prefixo dos `data-testid` das células (ex.: "origem-chat"). */
  testIdPrefixo: string;
  destaque?: boolean;
}

export function CardMetrica({
  titulo,
  subtitulo,
  bloco,
  testIdPrefixo,
  destaque = false,
}: CardMetricaProps) {
  const custoNaoMedido = bloco.custo_usd === null;
  return (
    <div
      className={`rounded-2xl border p-4 shadow-xs ${
        destaque ? "border-blue-200 bg-blue-50/60" : "border-slate-200 bg-white"
      }`}
    >
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{titulo}</div>
      {subtitulo ? <div className="text-[11px] text-slate-400">{subtitulo}</div> : null}
      <div
        className="mt-2 text-2xl font-bold text-slate-900"
        data-testid={`custo-${testIdPrefixo}`}
        title={custoNaoMedido ? TITULO_NAO_MEDIDO : undefined}
      >
        {formatarCusto(bloco.custo_usd)}
      </div>
      <dl className="mt-3 space-y-1 text-xs text-slate-600">
        <div className="flex justify-between gap-2">
          <dt>Chamadas</dt>
          <dd data-testid={`chamadas-${testIdPrefixo}`} className="font-semibold">
            {bloco.chamadas.toLocaleString("pt-BR")}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Tokens entrada</dt>
          <dd data-testid={`tokens-entrada-${testIdPrefixo}`} className="font-semibold">
            {formatarTokens(bloco.tokens_entrada)}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Tokens saída</dt>
          <dd data-testid={`tokens-saida-${testIdPrefixo}`} className="font-semibold">
            {formatarTokens(bloco.tokens_saida)}
          </dd>
        </div>
        {bloco.chamadas_sem_custo_medido > 0 ? (
          <div className="flex justify-between gap-2 text-amber-700">
            <dt title={TITULO_NAO_MEDIDO}>Sem custo medido</dt>
            <dd data-testid={`sem-custo-${testIdPrefixo}`} className="font-semibold">
              {bloco.chamadas_sem_custo_medido}
            </dd>
          </div>
        ) : null}
      </dl>
    </div>
  );
}
