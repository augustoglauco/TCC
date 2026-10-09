import { BlocoMetricas, MetricasPorOrigem } from "@/lib/api/metrics";
import { CardMetrica } from "./CardMetrica";

// Dimensões conhecidas do ledger (contrato: spec §2.3) — o backend só manda
// linhas com evento; uma origem conhecida ausente da resposta é uma origem
// com zero chamadas no período (zero *conhecido*, não "não medido"), então
// o frontend sempre renderiza as três, preenchendo com `BLOCO_ZERADO` quando
// faltar. Uma origem nova que o backend venha a mandar (ledger é extensível
// por design) também é renderizada — só não tem rótulo em `ROTULOS`.
export const ORIGENS_CONHECIDAS = ["chat", "b2b", "admin"] as const;

export const ROTULOS_ORIGEM: Record<string, { titulo: string; subtitulo: string }> = {
  chat: { titulo: "Chat", subtitulo: "Atendimento ao cliente no site" },
  b2b: { titulo: "B2B", subtitulo: "MCP provido a parceiros" },
  admin: { titulo: "Admin", subtitulo: "Ingestão, catálogo e gráficos" },
};

const BLOCO_ZERADO: BlocoMetricas = {
  chamadas: 0,
  tokens_entrada: 0,
  tokens_saida: 0,
  custo_usd: 0,
  chamadas_sem_custo_medido: 0,
};

export function SecaoPorOrigem({ linhas }: { linhas: MetricasPorOrigem[] }) {
  const porOrigem = new Map(linhas.map((linha) => [linha.origem, linha]));
  const conhecidas: MetricasPorOrigem[] = ORIGENS_CONHECIDAS.map(
    (origem) => porOrigem.get(origem) ?? { origem, ...BLOCO_ZERADO },
  );
  const desconhecidas = linhas.filter(
    (linha) => !(ORIGENS_CONHECIDAS as readonly string[]).includes(linha.origem),
  );
  const todas = [...conhecidas, ...desconhecidas];

  return (
    <section className="space-y-3">
      <h2 className="text-base font-bold text-slate-900">
        Por Origem{" "}
        <span className="font-normal text-slate-500">— de onde partiu a chamada de IA</span>
      </h2>
      {/* Mensagem é informativa, não substitui os cards: um período sem uso
          ainda mostra as três origens conhecidas zeradas (ver cabeçalho do
          módulo) — ela só avisa que não houve nenhum evento no período. */}
      {linhas.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum uso de IA registrado no período.</p>
      ) : null}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {todas.map((linha) => (
          <CardMetrica
            key={linha.origem}
            titulo={ROTULOS_ORIGEM[linha.origem]?.titulo ?? linha.origem}
            subtitulo={ROTULOS_ORIGEM[linha.origem]?.subtitulo}
            bloco={linha}
            testIdPrefixo={`origem-${linha.origem}`}
          />
        ))}
      </div>
    </section>
  );
}
