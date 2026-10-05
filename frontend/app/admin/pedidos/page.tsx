"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { fetchPedidos, type PedidoAdminItem } from "@/lib/api/adminPedidos";
import ModalConversaoPedido from "@/components/admin/ModalConversaoPedido";

export default function AdminPedidosPage() {
  const user = useAuthStore((s) => s.user);
  const token = useAuthStore((s) => s.token);

  const [hasHydrated, setHasHydrated] = useState(false);
  const [pedidos, setPedidos] = useState<PedidoAdminItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [filtroStatus, setFiltroStatus] = useState<string>("todos");
  const [termoBusca, setTermoBusca] = useState<string>("");
  const [pedidoSelecionado, setPedidoSelecionado] = useState<PedidoAdminItem | null>(null);
  const [modalAberto, setModalAberto] = useState(false);
  const [erroMsg, setErroMsg] = useState<string | null>(null);

  const isAdmin = user?.perfil?.toLowerCase() === "admin";

  useEffect(() => {
    setHasHydrated(true);
  }, []);

  const carregarPedidos = useCallback(async () => {
    if (!token || !isAdmin) return;
    setLoading(true);
    setErroMsg(null);
    try {
      const data = await fetchPedidos(
        { status: filtroStatus === "todos" ? undefined : filtroStatus },
        token
      );
      setPedidos(data);
    } catch (err: unknown) {
      setErroMsg(err instanceof Error ? err.message : "Erro ao carregar pedidos");
    } finally {
      setLoading(false);
    }
  }, [token, isAdmin, filtroStatus]);

  useEffect(() => {
    if (!hasHydrated || !isAdmin || !token) return;
    carregarPedidos();
  }, [hasHydrated, isAdmin, token, carregarPedidos]);

  if (!hasHydrated) {
    return null;
  }

  if (!isAdmin) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center p-4">
        <div className="w-full max-w-md rounded-xl border border-red-200 bg-red-50 p-6 text-center">
          <span className="text-3xl">🚫</span>
          <h2 className="mt-2 text-lg font-bold text-red-900">Acesso Restrito</h2>
          <p className="mt-1 text-sm text-red-700">
            Esta área é restrita a administradores do sistema.
          </p>
          <Link
            href="/"
            className="mt-4 inline-block rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
          >
            Voltar ao Início
          </Link>
        </div>
      </div>
    );
  }

  // Filtragem local por termo de busca
  const pedidosFiltrados = pedidos.filter((p) => {
    if (!termoBusca.trim()) return true;
    const busca = termoBusca.toLowerCase();
    return (
      p.id.toLowerCase().includes(busca) ||
      (p.user_email && p.user_email.toLowerCase().includes(busca)) ||
      (p.conversation_id && p.conversation_id.toLowerCase().includes(busca))
    );
  });

  // KPIs
  const totalReservados = pedidos.filter((p) => p.status === "reservado").length;
  const totalConcluidos = pedidos.filter((p) => p.status === "venda_concluida").length;
  const totalDivergentes = pedidos.filter((p) => p.status === "pagamento_divergente").length;
  const valorTotalVendas = pedidos
    .filter((p) => p.status === "venda_concluida")
    .reduce((acc, p) => acc + p.valor_total, 0);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">
            Gestão de Pedidos & Conversão
          </h1>
          <p className="text-sm text-gray-500">
            Acompanhe reservas, audite comprovantes financeiros com IA Multimodal e realize a conversão em vendas concluídas.
          </p>
        </div>
        <button
          onClick={carregarPedidos}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 disabled:opacity-50"
        >
          🔄 {loading ? "Atualizando..." : "Atualizar"}
        </button>
      </div>

      {erroMsg && (
        <div className="mt-4 rounded-lg bg-red-50 p-4 text-sm text-red-700 border border-red-200">
          ⚠️ {erroMsg}
        </div>
      )}

      {/* KPI Cards */}
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-amber-200 bg-amber-50/50 p-4 shadow-sm">
          <span className="text-xs font-semibold uppercase text-amber-700">Reservas Ativas</span>
          <p className="mt-1 text-2xl font-bold text-amber-900">{totalReservados}</p>
        </div>
        <div className="rounded-xl border border-green-200 bg-green-50/50 p-4 shadow-sm">
          <span className="text-xs font-semibold uppercase text-green-700">Vendas Concluídas</span>
          <p className="mt-1 text-2xl font-bold text-green-900">{totalConcluidos}</p>
        </div>
        <div className="rounded-xl border border-red-200 bg-red-50/50 p-4 shadow-sm">
          <span className="text-xs font-semibold uppercase text-red-700">Pagamentos Divergentes</span>
          <p className="mt-1 text-2xl font-bold text-red-900">{totalDivergentes}</p>
        </div>
        <div className="rounded-xl border border-blue-200 bg-blue-50/50 p-4 shadow-sm">
          <span className="text-xs font-semibold uppercase text-blue-700">Total Faturado (Vendas)</span>
          <p className="mt-1 text-2xl font-bold text-blue-900">
            R$ {valorTotalVendas.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
          </p>
        </div>
      </div>

      {/* Filtros e Busca */}
      <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setFiltroStatus("todos")}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              filtroStatus === "todos"
                ? "bg-gray-900 text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            Todos
          </button>
          <button
            type="button"
            onClick={() => setFiltroStatus("reservado")}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              filtroStatus === "reservado"
                ? "bg-amber-600 text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            Reservados ({totalReservados})
          </button>
          <button
            type="button"
            onClick={() => setFiltroStatus("venda_concluida")}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              filtroStatus === "venda_concluida"
                ? "bg-green-600 text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            Venda Concluída ({totalConcluidos})
          </button>
          <button
            type="button"
            onClick={() => setFiltroStatus("pagamento_divergente")}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              filtroStatus === "pagamento_divergente"
                ? "bg-red-600 text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            Divergentes ({totalDivergentes})
          </button>
        </div>

        <div className="w-full sm:w-72">
          <input
            type="text"
            placeholder="Buscar por ID ou e-mail..."
            value={termoBusca}
            onChange={(e) => setTermoBusca(e.target.value)}
            className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>
      </div>

      {/* Tabela de Pedidos */}
      <div className="mt-4 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-left text-sm">
            <thead className="bg-gray-50 text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3 font-semibold">ID / Criação</th>
                <th className="px-4 py-3 font-semibold">Cliente</th>
                <th className="px-4 py-3 font-semibold">Itens</th>
                <th className="px-4 py-3 font-semibold">Valor Total</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">Conversão</th>
                <th className="px-4 py-3 font-semibold text-right">Ação</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {pedidosFiltrados.length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-sm text-gray-500">
                    {loading ? "Carregando pedidos..." : "Nenhum pedido encontrado para os filtros selecionados."}
                  </td>
                </tr>
              ) : (
                pedidosFiltrados.map((pedido) => (
                  <tr key={pedido.id} className="hover:bg-gray-50/50">
                    <td className="px-4 py-3 font-mono text-xs">
                      <span className="font-semibold text-gray-900 block" title={pedido.id}>
                        {pedido.id.substring(0, 8)}...
                      </span>
                      <span className="text-[11px] text-gray-400">
                        {pedido.criado_em ? new Date(pedido.criado_em).toLocaleDateString("pt-BR") : "-"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-700">
                      {pedido.user_email || "Anônimo / Visitante"}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">
                      {pedido.itens.length} {pedido.itens.length === 1 ? "item" : "itens"}
                    </td>
                    <td className="px-4 py-3 font-semibold text-gray-900 text-xs">
                      R$ {pedido.valor_total.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${
                          pedido.status === "venda_concluida"
                            ? "bg-green-100 text-green-800"
                            : pedido.status === "pagamento_divergente"
                            ? "bg-red-100 text-red-800"
                            : "bg-amber-100 text-amber-800"
                        }`}
                      >
                        {pedido.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">
                      {pedido.tipo_conversao ? (
                        <div>
                          <span className="font-medium text-gray-800 block">
                            {pedido.tipo_conversao}
                          </span>
                          <span className="text-[10px] text-gray-400">
                            por {pedido.convertido_por || "sistema"}
                          </span>
                        </div>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => {
                          setPedidoSelecionado(pedido);
                          setModalAberto(true);
                        }}
                        className={`rounded px-3 py-1 text-xs font-semibold transition-colors ${
                          pedido.status === "venda_concluida"
                            ? "border border-gray-200 bg-gray-50 text-gray-600 hover:bg-gray-100"
                            : "bg-blue-600 text-white hover:bg-blue-700"
                        }`}
                      >
                        {pedido.status === "venda_concluida" ? "Ver Detalhes" : "Converter / Tratar"}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal de Conversão */}
      <ModalConversaoPedido
        pedido={pedidoSelecionado}
        isOpen={modalAberto}
        onClose={() => {
          setModalAberto(false);
          setPedidoSelecionado(null);
        }}
        onSuccess={carregarPedidos}
      />
    </div>
  );
}
