"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchFerramentas, urlDeVisualizacao, FerramentaStatus } from "@/lib/api/ferramentas";
import { useAuthStore } from "@/lib/hooks/useAuthStore";

const ICONES: Record<string, string> = {
  graphify: "🕸️",
  repowise: "📚",
  gitnexus: "🧭",
};

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

export default function AdminFerramentasPage() {
  const currentUser = useAuthStore((state) => state.user);
  const token = useAuthStore((state) => state.token);
  const isCurrentAdmin = currentUser?.perfil?.toLowerCase() === "admin";

  const [ferramentas, setFerramentas] = useState<FerramentaStatus[] | null>(null);
  const [selecionada, setSelecionada] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchFerramentas(token);
      setFerramentas(res.ferramentas);
      // Abre direto a primeira que estiver disponível: o caso comum é só o
      // Graphify estar pronto (artefato versionado), com os dois servidores
      // locais desligados.
      setSelecionada((atual) => atual ?? res.ferramentas.find((f) => f.online)?.id ?? null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao consultar as ferramentas.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (isCurrentAdmin && token) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      void carregar();
    }
  }, [isCurrentAdmin, token, carregar]);

  if (!currentUser || !isCurrentAdmin) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center space-y-6">
        <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-rose-50 text-rose-600 text-3xl font-bold shadow-xs border border-rose-200">
          🔒
        </div>
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Acesso restrito</h1>
          <p className="mt-2 text-sm text-gray-600">Esta página é exclusiva de administradores.</p>
        </div>
      </div>
    );
  }

  const ativa = ferramentas?.find((f) => f.id === selecionada) ?? null;
  const urlAtiva = ativa && token ? urlDeVisualizacao(ativa, token) : null;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Ferramentas de Código</h1>
          <p className="mt-1 text-sm text-gray-600">
            Graphify, Repowise e GitNexus num lugar só — as três mapeiam este repositório por
            caminhos diferentes.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void carregar()}
          disabled={loading}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          {loading ? "Verificando..." : "Verificar novamente"}
        </button>
      </header>

      {error && (
        <div
          role="alert"
          className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"
        >
          {error}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        {(ferramentas ?? []).map((f) => (
          <button
            key={f.id}
            type="button"
            onClick={() => setSelecionada(f.id)}
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

      {ativa && (
        <section className="rounded-xl border border-gray-200 bg-white shadow-xs">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-200 px-4 py-3">
            <h2 className="font-medium text-gray-900">{ativa.nome}</h2>
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
          {ativa.online && urlAtiva ? (
            <>
              <iframe
                src={urlAtiva}
                title={`Visualização do ${ativa.nome}`}
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
      )}
    </div>
  );
}
