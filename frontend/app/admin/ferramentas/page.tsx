"use client";

import { useCallback, useEffect, useState } from "react";
import { atualizarFerramenta, fetchFerramentas, urlDeVisualizacao } from "@/lib/api/ferramentas";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { FerramentaCards } from "@/components/admin/ferramentas/FerramentaCards";
import { FerramentaViewer } from "@/components/admin/ferramentas/FerramentaViewer";
import type { FerramentaStatus } from "@/lib/api/ferramentas";

export default function AdminFerramentasPage() {
  const currentUser = useAuthStore((state) => state.user);
  const token = useAuthStore((state) => state.token);
  const isCurrentAdmin = currentUser?.perfil?.toLowerCase() === "admin";

  const [ferramentas, setFerramentas] = useState<FerramentaStatus[] | null>(null);
  const [selecionada, setSelecionada] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [atualizando, setAtualizando] = useState(false);
  const [resultadoAtualizacao, setResultadoAtualizacao] = useState<{
    id: string;
    sucesso: boolean;
    saida: string;
  } | null>(null);

  const carregar = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchFerramentas(token);
      setFerramentas(res.ferramentas);
      setSelecionada((atual) => atual ?? res.ferramentas.find((f) => f.online)?.id ?? null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao consultar as ferramentas.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  const atualizar = async (id: "graphify" | "gitnexus") => {
    if (!token) return;
    setAtualizando(true);
    setResultadoAtualizacao(null);
    try {
      setResultadoAtualizacao({ id, ...(await atualizarFerramenta(id, token)) });
      await carregar();
    } catch (err: unknown) {
      setResultadoAtualizacao({
        id,
        sucesso: false,
        saida: err instanceof Error ? err.message : "Erro ao atualizar a ferramenta.",
      });
    } finally {
      setAtualizando(false);
    }
  };

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

      {ferramentas && (
        <FerramentaCards
          ferramentas={ferramentas}
          selecionada={selecionada}
          onSelecionar={setSelecionada}
        />
      )}

      {ativa && (
        <FerramentaViewer
          ativa={ativa}
          urlAtiva={urlAtiva}
          atualizando={atualizando}
          resultadoAtualizacao={resultadoAtualizacao}
          onAtualizar={(id) => void atualizar(id)}
          onFecharResultado={() => setResultadoAtualizacao(null)}
        />
      )}
    </div>
  );
}
