"use client";

import { useCallback, useEffect, useState } from "react";

import { DatasetsConjuntoCards } from "@/components/admin/DatasetsConjuntoCards";
import { DatasetsFilaRevisao } from "@/components/admin/DatasetsFilaRevisao";
import { DatasetsTarefas } from "@/components/admin/DatasetsTarefas";
import { fetchConjuntos, type ConjuntoStatus } from "@/lib/api/datasets";
import { useAuthStore } from "@/lib/hooks/useAuthStore";

/**
 * Painel de Preparação da Avaliação (Fase 10) — pedido pelo dono em
 * 2026-10-16 e servido por `/api/admin/datasets`.
 *
 * # MVP: tela de apoio à condução do experimento, fora do escopo do MVP do
 * assistente (ver docs/ROADMAP.md, "Extra fora do MVP — Painel de
 * Preparação da Avaliação").
 */
export default function AdminDatasetsPage() {
  const currentUser = useAuthStore((state) => state.user);
  const token = useAuthStore((state) => state.token);
  const isCurrentAdmin = currentUser?.perfil?.toLowerCase() === "admin";

  const [conjuntos, setConjuntos] = useState<ConjuntoStatus[] | null>(null);
  const [selecionado, setSelecionado] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    if (!token) return;
    setErro(null);
    try {
      const res = await fetchConjuntos(token);
      setConjuntos(res.conjuntos);
      // Abre direto no primeiro conjunto com fila: o caso comum é querer
      // revisar, não olhar o painel.
      setSelecionado(
        (atual) =>
          atual ??
          res.conjuntos.find((c) => !c.revisao_automatica && c.pendentes > 0)?.id ??
          res.conjuntos[0]?.id ??
          null,
      );
    } catch (err: unknown) {
      setErro(err instanceof Error ? err.message : "Erro ao consultar os conjuntos.");
    }
  }, [token]);

  useEffect(() => {
    // Mesmo padrão de AdminFerramentasPage: a carga inicial é um efeito que
    // chama setState, que é o que esta regra proíbe.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void carregar();
  }, [carregar]);

  if (!isCurrentAdmin) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10">
        <p className="text-sm text-gray-600">Esta área é restrita a administradores.</p>
      </main>
    );
  }

  const conjuntoAtual = conjuntos?.find((c) => c.id === selecionado) ?? null;

  return (
    <main className="mx-auto max-w-7xl px-4 py-8">
      <header className="mb-5">
        <h1 className="text-xl font-semibold text-gray-900">Preparação da Avaliação</h1>
        <p className="mt-1 text-sm text-gray-600">
          Progresso dos cinco conjuntos da Estratégia A, fila de revisão item a item e disparo das
          tarefas longas (ingestão e benchmark).
        </p>
      </header>

      {erro ? (
        <p className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {erro}
        </p>
      ) : null}

      {conjuntos === null ? (
        <p className="text-sm text-gray-500">Carregando…</p>
      ) : (
        <div className="space-y-5">
          <DatasetsConjuntoCards
            conjuntos={conjuntos}
            selecionado={selecionado}
            onSelecionar={setSelecionado}
          />

          {conjuntoAtual && token ? (
            <DatasetsFilaRevisao
              conjunto={conjuntoAtual}
              token={token}
              onRevisado={() => void carregar()}
            />
          ) : null}

          {token ? <DatasetsTarefas token={token} /> : null}
        </div>
      )}
    </main>
  );
}
