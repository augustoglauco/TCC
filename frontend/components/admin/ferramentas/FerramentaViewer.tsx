import type { FerramentaStatus } from "@/lib/api/ferramentas";

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

interface ResultadoAtualizacao {
  id: string;
  sucesso: boolean;
  saida: string;
}

interface FerramentaViewerProps {
  ativa: FerramentaStatus;
  urlAtiva: string | null;
  atualizando: boolean;
  resultadoAtualizacao: ResultadoAtualizacao | null;
  onAtualizar: (id: "graphify" | "gitnexus") => void;
  onFecharResultado: () => void;
}

function BotaoAtualizar({
  id,
  online,
  atualizando,
  onAtualizar,
}: {
  id: "graphify" | "gitnexus";
  online: boolean;
  atualizando: boolean;
  onAtualizar: (id: "graphify" | "gitnexus") => void;
}) {
  const semServidor = id === "gitnexus" && !online;
  return (
    <button
      type="button"
      onClick={() => onAtualizar(id)}
      disabled={atualizando || semServidor}
      title={semServidor ? "Suba o servidor do GitNexus para atualizar" : undefined}
      className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {atualizando
        ? "Atualizando..."
        : id === "graphify"
          ? "Atualizar grafo (graphify update)"
          : "Atualizar índice (gitnexus analyze)"}
    </button>
  );
}

function ResultadoBanner({
  resultado,
  onFechar,
}: {
  resultado: ResultadoAtualizacao;
  onFechar: () => void;
}) {
  return (
    <div
      role="status"
      className={
        resultado.sucesso
          ? "relative border-b border-emerald-200 bg-emerald-50 text-emerald-800"
          : "relative border-b border-rose-200 bg-rose-50 text-rose-800"
      }
    >
      <button
        type="button"
        onClick={onFechar}
        aria-label="Fechar mensagem"
        title="Fechar"
        className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded border border-current text-sm font-bold leading-none hover:bg-black/10"
      >
        ✕
      </button>
      <pre className="max-h-48 overflow-auto px-4 py-3 pr-10 text-xs">
        {resultado.sucesso ? "Atualizado.\n" : "Falha na atualização.\n"}
        {resultado.saida}
      </pre>
    </div>
  );
}

export function FerramentaViewer({
  ativa,
  urlAtiva,
  atualizando,
  resultadoAtualizacao,
  onAtualizar,
  onFecharResultado,
}: FerramentaViewerProps) {
  return (
    <section className="rounded-xl border border-gray-200 bg-white shadow-xs">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-200 px-4 py-3">
        <h2 className="flex items-center gap-2 font-medium text-gray-900">
          {ativa.nome}
          <Led online={ativa.online} />
        </h2>
        {(ativa.id === "graphify" || ativa.id === "gitnexus") && (
          <BotaoAtualizar
            id={ativa.id}
            online={ativa.online}
            atualizando={atualizando}
            onAtualizar={onAtualizar}
          />
        )}
        {urlAtiva && (
          <a
            href={urlAtiva}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium text-blue-600 hover:text-blue-700"
          >
            Abrir em nova aba ↗
          </a>
        )}
      </div>

      {resultadoAtualizacao && resultadoAtualizacao.id === ativa.id && (
        <ResultadoBanner resultado={resultadoAtualizacao} onFechar={onFecharResultado} />
      )}

      {ativa.online && urlAtiva ? (
        <>
          <iframe
            src={urlAtiva}
            title={`Visualização do ${ativa.nome}`}
            allow="local-network-access *; local-network *; loopback-network *"
            className="h-[70vh] w-full rounded-b-xl"
          />
          {/* MVP: se a ferramenta mandar X-Frame-Options/CSP frame-ancestors,
              o iframe fica em branco — por isso o link "Abrir em nova aba"
              está sempre visível, e não só no estado de erro. */}
        </>
      ) : (
        <div className="px-4 py-10 text-center text-sm text-gray-600">
          <p>
            {ativa.tipo === "artefato"
              ? "O artefato ainda não foi gerado."
              : "O servidor desta ferramenta não está no ar."}
          </p>
          <code className="mt-3 inline-block rounded bg-gray-100 px-2 py-1 font-mono text-xs text-gray-800">
            {ativa.comando}
          </code>
        </div>
      )}
    </section>
  );
}
