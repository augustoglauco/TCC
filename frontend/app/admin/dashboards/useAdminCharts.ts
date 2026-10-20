"use client";

import { useCallback, useEffect, useState, type Dispatch, type SetStateAction } from "react";
import type { AdminChartData } from "@/components/admin/DynamicChartCard";
import {
  deleteAdminChart,
  fetchAdminCharts,
  refreshAdminChart,
  updateAdminChart,
} from "@/lib/api/charts";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { useEstaNoCliente } from "@/lib/hooks/useEstaNoCliente";

function mensagemDe(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback;
}

/** Recarrega os gráficos por evento customizado, foco da janela e volta da aba. */
function useRecarregarGraficos(
  token: string | null,
  loadData: () => Promise<void>,
  setLoading: (v: boolean) => void,
  setError: (v: string | null) => void,
) {
  useEffect(() => {
    const handleRefresh = () => {
      if (token) {
        setLoading(true);
        setError(null);
        void loadData();
      }
    };
    const handleVisibility = () => {
      if (document.visibilityState === "visible" && token) {
        setLoading(true);
        void loadData();
      }
    };

    window.addEventListener("refresh_admin_charts", handleRefresh);
    window.addEventListener("focus", handleRefresh);
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      window.removeEventListener("refresh_admin_charts", handleRefresh);
      window.removeEventListener("focus", handleRefresh);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [token, loadData, setLoading, setError]);
}

function useAcoesGraficos(
  token: string | null,
  charts: AdminChartData[],
  setCharts: Dispatch<SetStateAction<AdminChartData[]>>,
  setIsRefreshingAll: (v: boolean) => void,
) {
  const substituir = (id: string, updated: AdminChartData) =>
    setCharts((prev) => prev.map((c) => (c.id === id ? updated : c)));

  // Executa a ação e avisa o usuário se falhar.
  const comAviso = async (acao: () => Promise<void>, fallback: string) => {
    try {
      await acao();
    } catch (err) {
      alert(mensagemDe(err, fallback));
    }
  };

  const handleRefresh = async (id: string) => {
    if (!token) return;
    await comAviso(
      async () => substituir(id, await refreshAdminChart(id, token)),
      "Erro ao atualizar gráfico.",
    );
  };

  const handleRefreshAll = async () => {
    if (!token || charts.length === 0) return;
    setIsRefreshingAll(true);
    try {
      await Promise.all(
        charts.map(async (c) => {
          try {
            substituir(c.id, await refreshAdminChart(c.id, token));
          } catch {
            // MVP: falha individual e ignorada de proposito — os demais
            // graficos continuam sendo atualizados, sem alerta por grafico.
          }
        }),
      );
    } finally {
      setIsRefreshingAll(false);
    }
  };

  const handleTogglePin = async (id: string, fixado: boolean) => {
    if (!token) return;
    await comAviso(
      async () => substituir(id, await updateAdminChart(id, { fixado }, token)),
      "Erro ao alternar fixação.",
    );
  };

  const handleEditTitle = async (id: string, novoTitulo: string) => {
    if (!token) return;
    await comAviso(
      async () => substituir(id, await updateAdminChart(id, { titulo: novoTitulo }, token)),
      "Erro ao renomear gráfico.",
    );
  };

  const handleDelete = async (id: string) => {
    if (!token) return;
    if (!window.confirm("Deseja realmente remover este gráfico do painel?")) return;
    await comAviso(async () => {
      await deleteAdminChart(id, token);
      setCharts((prev) => prev.filter((c) => c.id !== id));
    }, "Erro ao excluir gráfico.");
  };

  return { handleRefresh, handleRefreshAll, handleTogglePin, handleEditTitle, handleDelete };
}

/** Estado, carga e ações (CRUD) dos gráficos do painel admin. */
export function useAdminCharts() {
  const user = useAuthStore((s) => s.user);
  const token = useAuthStore((s) => s.token);

  const hasHydrated = useEstaNoCliente();
  const [charts, setCharts] = useState<AdminChartData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshingAll, setIsRefreshingAll] = useState(false);

  const isAdmin = user?.perfil?.toLowerCase() === "admin";

  // `carregando` deriva de quem realmente carrega: antes do hydrate sempre
  // mostra esqueleto; depois, so enquanto um admin com token esta buscando.
  // Era isso que o `else { setLoading(false) }` dentro do efeito fazia — e
  // derivar remove de vez o caso do visitante nao-admin preso no esqueleto
  // quando o efeito nao re-roda (ver comentario do efeito abaixo).
  const carregando = loading && (!hasHydrated || (isAdmin && !!token));

  // Nao toca estado antes do primeiro `await`: este loader e chamado de
  // dentro de um efeito, onde setState sincrono dispara render em cascata
  // (react-hooks/set-state-in-effect). Quem chama por evento liga o spinner
  // no proprio handler.
  const loadData = useCallback(async () => {
    if (!token) return;
    try {
      const data = await fetchAdminCharts(token);
      setCharts(data);
      setError(null);
    } catch (err) {
      setError(mensagemDe(err, "Não foi possível carregar os gráficos."));
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    // Antes do hydrate do zustand persist, `user`/`token` ainda são os
    // valores iniciais (null) independente de haver sessão salva — decidir
    // aqui destravaria a tela cedo demais para um admin de verdade. Mas uma
    // vez hidratado, se o visitante não é admin (ou não está logado),
    // `isAdmin`/`token` nunca mais mudam sozinhos — sem `hasHydrated` na
    // lista de dependências, este efeito nunca rodava de novo pra aplicar
    // esse caso, e a página ficava presa no esqueleto de carregamento pra
    // sempre (achado ao vivo: "fica rendering" pra qualquer visitante
    // não-admin).
    if (!hasHydrated) return;
    if (isAdmin && token) {
      // Falso positivo: `loadData` so toca estado depois de
      // `await fetchAdminCharts` (funcao `async` importada), logo nao ha
      // setState sincrono. A regra nao resolve a assincronia de funcoes
      // importadas e assume o pior caso.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      void loadData();
    }
  }, [hasHydrated, isAdmin, token, loadData]);

  useRecarregarGraficos(token, loadData, setLoading, setError);

  const { handleRefresh, handleRefreshAll, handleTogglePin, handleEditTitle, handleDelete } =
    useAcoesGraficos(token, charts, setCharts, setIsRefreshingAll);

  const handleChartCreated = (newChart: AdminChartData) => {
    setCharts((prev) => [newChart, ...prev]);
  };

  return {
    charts,
    error,
    isRefreshingAll,
    isAdmin,
    hasHydrated,
    carregando,
    handleRefresh,
    handleRefreshAll,
    handleTogglePin,
    handleEditTitle,
    handleDelete,
    handleChartCreated,
  };
}
