import { BlocoMetricas, MetricasPorAmbiente } from "@/lib/api/metrics";
import { CardMetrica } from "./CardMetrica";

// Dimensões conhecidas do ledger (contrato: spec §2.3) — mesma regra de
// `SecaoPorOrigem`: um ambiente conhecido ausente da resposta é zero
// chamadas *conhecido* no período, não "não medido", então sempre
// renderiza os dois cards, preenchendo com `BLOCO_ZERADO` quando faltar.
const AMBIENTES_CONHECIDOS = ["interno", "externo"] as const;

const ROTULOS: Record<string, { titulo: string; subtitulo: string }> = {
  interno: { titulo: "Interno", subtitulo: "GPU local / CLIP — sem custo de API" },
  externo: { titulo: "Externo", subtitulo: "API paga (OpenRouter, visão externa)" },
};

const BLOCO_ZERADO: BlocoMetricas = {
  chamadas: 0,
  tokens_entrada: 0,
  tokens_saida: 0,
  custo_usd: 0,
  chamadas_sem_custo_medido: 0,
};

interface Props {
  linhas: MetricasPorAmbiente[];
  totais: BlocoMetricas;
}

export function SecaoPorAmbiente({ linhas, totais }: Props) {
  const porAmbiente = new Map(linhas.map((linha) => [linha.ambiente, linha]));
  const conhecidos: MetricasPorAmbiente[] = AMBIENTES_CONHECIDOS.map(
    (ambiente) => porAmbiente.get(ambiente) ?? { ambiente, ...BLOCO_ZERADO },
  );
  const desconhecidos = linhas.filter(
    (linha) => !(AMBIENTES_CONHECIDOS as readonly string[]).includes(linha.ambiente),
  );
  const todos = [...conhecidos, ...desconhecidos];

  return (
    <section className="space-y-3">
      <h2 className="text-base font-bold text-slate-900">
        Por Ambiente{" "}
        <span className="font-normal text-slate-500">— quanto foi grátis e quanto foi pago</span>
      </h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {todos.map((linha) => (
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
