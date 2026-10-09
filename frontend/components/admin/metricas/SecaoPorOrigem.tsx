import { MetricasPorOrigem } from "@/lib/api/metrics";
import { CardMetrica } from "./CardMetrica";

const ROTULOS: Record<string, { titulo: string; subtitulo: string }> = {
  chat: { titulo: "Chat", subtitulo: "Atendimento ao cliente no site" },
  b2b: { titulo: "B2B", subtitulo: "MCP provido a parceiros" },
  admin: { titulo: "Admin", subtitulo: "Ingestão, catálogo e gráficos" },
};

export function SecaoPorOrigem({ linhas }: { linhas: MetricasPorOrigem[] }) {
  return (
    <section className="space-y-3">
      <h2 className="text-base font-bold text-slate-900">
        Por Origem{" "}
        <span className="font-normal text-slate-500">— de onde partiu a chamada de IA</span>
      </h2>
      {linhas.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum uso de IA registrado no período.</p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {linhas.map((linha) => (
            <CardMetrica
              key={linha.origem}
              titulo={ROTULOS[linha.origem]?.titulo ?? linha.origem}
              subtitulo={ROTULOS[linha.origem]?.subtitulo}
              bloco={linha}
              testIdPrefixo={`origem-${linha.origem}`}
            />
          ))}
        </div>
      )}
    </section>
  );
}
