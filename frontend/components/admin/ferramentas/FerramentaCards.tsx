import type { FerramentaStatus } from "@/lib/api/ferramentas";

const ICONES: Record<string, string> = {
  graphify: "🕸️",
  repowise: "📚",
  gitnexus: "🧭",
};

function Led({ online }: { online: boolean }) {
  return (
    <span
      role="img"
      aria-label={online ? "Online" : "Offline"}
      title={online ? "Online" : "Offline"}
      className={
        online
          ? "inline-block h-2.5 w-2.5 shrink-0 animate-pulse rounded-full bg-emerald-500 shadow-[0_0_6px_1px_rgba(16,185,129,0.6)]"
          : "inline-block h-2.5 w-2.5 shrink-0 rounded-full bg-red-500 shadow-[0_0_6px_1px_rgba(239,68,68,0.5)]"
      }
    />
  );
}

function Selo({ online, tipo }: { online: boolean; tipo: string }) {
  const rotulo = online
    ? tipo === "artefato"
      ? "Gerado"
      : "No ar"
    : tipo === "artefato"
      ? "Não gerado"
      : "Fora do ar";
  return (
    <span
      className={
        online
          ? "rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700 border border-emerald-200"
          : "rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600 border border-gray-200"
      }
    >
      {rotulo}
    </span>
  );
}

interface FerramentaCardsProps {
  ferramentas: FerramentaStatus[];
  selecionada: string | null;
  onSelecionar: (id: string) => void;
}

export function FerramentaCards({ ferramentas, selecionada, onSelecionar }: FerramentaCardsProps) {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {ferramentas.map((f) => (
        <button
          key={f.id}
          type="button"
          onClick={() => onSelecionar(f.id)}
          aria-pressed={selecionada === f.id}
          className={
            selecionada === f.id
              ? "rounded-xl border-2 border-blue-500 bg-white p-4 text-left shadow-xs"
              : "rounded-xl border border-gray-200 bg-white p-4 text-left shadow-xs hover:border-gray-300"
          }
        >
          <div className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-2 font-semibold text-gray-900">
              <span className="text-lg">{ICONES[f.id] ?? "🔧"}</span>
              {f.nome}
              <Led online={f.online} />
            </span>
            <Selo online={f.online} tipo={f.tipo} />
          </div>
          <p className="mt-2 text-sm text-gray-600">{f.descricao}</p>
          {!f.online && (
            <p className="mt-3 text-xs text-gray-500">
              Para usar, rode:{" "}
              <code className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-gray-800">
                {f.comando}
              </code>
            </p>
          )}
          {f.detalhe && <p className="mt-2 break-all text-xs text-gray-400">{f.detalhe}</p>}
        </button>
      ))}
    </div>
  );
}
