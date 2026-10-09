import { BlocoMetricas, MetricasPorAmbiente } from "@/lib/api/metrics";
import { CardMetrica } from "./CardMetrica";

const ROTULOS: Record<string, { titulo: string; subtitulo: string }> = {
  interno: { titulo: "Interno", subtitulo: "GPU local / CLIP — sem custo de API" },
  externo: { titulo: "Externo", subtitulo: "API paga (OpenRouter, visão externa)" },
};

interface Props {
  linhas: MetricasPorAmbiente[];
  totais: BlocoMetricas;
}

export function SecaoPorAmbiente({ linhas, totais }: Props) {
  return (
    <section className="space-y-3">
      <h2 className="text-base font-bold text-slate-900">
        Por Ambiente{" "}
        <span className="font-normal text-slate-500">— quanto foi grátis e quanto foi pago</span>
      </h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {linhas.map((linha) => (
          <CardMetrica
            key={linha.ambiente}
            titulo={ROTULOS[linha.ambiente]?.titulo ?? linha.ambiente}
            subtitulo={ROTULOS[linha.ambiente]?.subtitulo}
            bloco={linha}
            testIdPrefixo={`ambiente-${linha.ambiente}`}
          />
        ))}
        <CardMetrica
          titulo="Consolidado"
          subtitulo="Todas as origens e ambientes"
          bloco={totais}
          testIdPrefixo="total"
          destaque
        />
      </div>
    </section>
  );
}
