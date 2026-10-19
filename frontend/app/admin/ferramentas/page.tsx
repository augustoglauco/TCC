"use client";

import { urlDeVisualizacao } from "@/lib/api/ferramentas";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { useFerramentas } from "@/lib/hooks/useFerramentas";
import { AcessoRestrito } from "@/components/admin/ferramentas/AcessoRestrito";
import { FerramentaCards } from "@/components/admin/ferramentas/FerramentaCards";
import { FerramentaViewer } from "@/components/admin/ferramentas/FerramentaViewer";

export default function AdminFerramentasPage() {
  const currentUser = useAuthStore((state) => state.user);
  const token = useAuthStore((state) => state.token);
  const isCurrentAdmin = currentUser?.perfil?.toLowerCase() === "admin";

  const f = useFerramentas(token, isCurrentAdmin);

  if (!currentUser || !isCurrentAdmin) return <AcessoRestrito />;

  const ativa = f.ferramentas?.find((x) => x.id === f.selecionada) ?? null;
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
          onClick={() => void f.carregar()}
          disabled={f.loading}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          {f.loading ? "Verificando..." : "Verificar novamente"}
        </button>
      </header>

      {f.error && (
        <div
          role="alert"
          className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"
        >
          {f.error}
        </div>
      )}

      {f.ferramentas && (
        <FerramentaCards
          ferramentas={f.ferramentas}
          selecionada={f.selecionada}
          onSelecionar={f.setSelecionada}
        />
      )}

      {ativa && (
        <FerramentaViewer
          ativa={ativa}
          urlAtiva={urlAtiva}
          atualizando={f.atualizando}
          resultadoAtualizacao={f.resultadoAtualizacao}
          onAtualizar={(id) => void f.atualizar(id)}
          onFecharResultado={() => f.setResultadoAtualizacao(null)}
        />
      )}
    </div>
  );
}
