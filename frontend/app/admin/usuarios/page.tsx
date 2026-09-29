"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { fetchUsers } from "@/lib/api/auth";
import { User } from "@/lib/types/auth";

export default function AdminUsuariosPage() {
  const currentUser = useAuthStore((state) => state.user);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [termo, setTermo] = useState("");
  const [perfilFiltro, setPerfilFiltro] = useState<string>("todos");

  const isCurrentAdmin = currentUser?.perfil?.toLowerCase() === "admin";

  const carregarUsuarios = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchUsers();
      setUsers(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao carregar usuários.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isCurrentAdmin) {
      carregarUsuarios();
    }
  }, [isCurrentAdmin]);

  if (!currentUser || !isCurrentAdmin) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center space-y-6">
        <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-rose-50 text-rose-600 text-3xl font-bold shadow-xs border border-rose-200">
          🔒
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Acesso Restrito ao Administrador</h1>
          <p className="mt-2 text-sm text-slate-600">
            Apenas usuários com perfil <strong>Administrador (Admin)</strong> têm permissão para acessar a gestão de contas e usuários.
          </p>
        </div>

        <div className="flex flex-col gap-3 pt-2">
          <Link
            href="/conta/login"
            className="rounded-xl bg-purple-600 px-4 py-3 text-sm font-bold text-white shadow-xs hover:bg-purple-700 transition-colors"
          >
            Entrar como Administrador &rarr;
          </Link>
          <Link
            href="/"
            className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
          >
            Voltar ao Início
          </Link>
        </div>
      </div>
    );
  }

  // Filtragem local
  const usuariosFiltrados = users.filter((u) => {
    const matchTermo =
      u.nome.toLowerCase().includes(termo.toLowerCase()) ||
      u.email.toLowerCase().includes(termo.toLowerCase());
    const matchPerfil =
      perfilFiltro === "todos" || u.perfil.toLowerCase() === perfilFiltro.toLowerCase();
    return matchTermo && matchPerfil;
  });

  const totalUsuarios = users.length;
  const totalAdmins = users.filter((u) => u.perfil.toLowerCase() === "admin").length;
  const totalClientes = users.filter((u) => u.perfil.toLowerCase() !== "admin").length;

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:py-10 space-y-6">
      {/* Cabeçalho */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-purple-50 border border-purple-200 px-3 py-1 text-xs font-semibold text-purple-800 mb-2">
            <span>👥</span> Gestão Administrativa de Contas
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Gerenciamento de Usuários
          </h1>
          <p className="text-xs sm:text-sm text-slate-600 mt-1">
            Consulte usuários cadastrados, atribua perfis comerciais e crie novos administradores ou clientes.
          </p>
        </div>

        {/* Botão de Ação */}
        <div className="flex items-center gap-3">
          <Link
            href="/conta/cadastro"
            className="inline-flex items-center gap-2 rounded-xl bg-purple-600 px-4 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-purple-700 transition-colors cursor-pointer"
          >
            <span>+</span>
            <span>Novo Usuário / Admin</span>
          </Link>
        </div>
      </div>

      {/* Cards de Métricas */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 block">
            Total de Usuários
          </span>
          <span className="mt-1 text-2xl font-bold text-slate-900 block">{totalUsuarios}</span>
        </div>

        <div className="rounded-xl border border-purple-100 bg-purple-50/50 p-4 shadow-2xs">
          <span className="text-xs font-semibold uppercase tracking-wider text-purple-700 block">
            Administradores (Admin)
          </span>
          <span className="mt-1 text-2xl font-bold text-purple-900 block">{totalAdmins}</span>
        </div>

        <div className="rounded-xl border border-blue-100 bg-blue-50/50 p-4 shadow-2xs">
          <span className="text-xs font-semibold uppercase tracking-wider text-blue-700 block">
            Clientes / Leads
          </span>
          <span className="mt-1 text-2xl font-bold text-blue-900 block">{totalClientes}</span>
        </div>
      </div>

      {/* Barra de Busca e Filtros */}
      <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
        <div className="relative flex-1">
          <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
            🔍
          </span>
          <input
            type="text"
            value={termo}
            onChange={(e) => setTermo(e.target.value)}
            placeholder="Buscar por nome ou e-mail..."
            className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-4 text-xs text-slate-900 placeholder:text-slate-400 focus:border-purple-600 focus:outline-hidden"
          />
        </div>

        <select
          value={perfilFiltro}
          onChange={(e) => setPerfilFiltro(e.target.value)}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 focus:border-purple-600 focus:outline-hidden"
        >
          <option value="todos">Todos os Perfis</option>
          <option value="admin">Administrador (Admin)</option>
          <option value="cliente">Cliente (Recorrente)</option>
          <option value="esporadico">Esporádico</option>
          <option value="lead">Lead</option>
        </select>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-700">
          {error}
        </div>
      )}

      {/* Tabela de Usuários */}
      {loading ? (
        <div className="py-12 text-center text-xs text-slate-500">Carregando usuários...</div>
      ) : usuariosFiltrados.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 p-12 text-center space-y-2">
          <div className="text-3xl">👥</div>
          <h3 className="text-sm font-bold text-slate-800">Nenhum usuário encontrado</h3>
          <p className="text-xs text-slate-500">Tente ajustar os termos de busca ou filtro de perfil.</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-2xs">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="bg-slate-50/80 border-b border-slate-200 text-[11px] font-bold uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-3">ID</th>
                <th className="px-4 py-3">Nome do Usuário</th>
                <th className="px-4 py-3">E-mail</th>
                <th className="px-4 py-3">Perfil Comercial</th>
                <th className="px-4 py-3">Origem / Motivo</th>
                <th className="px-4 py-3 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {usuariosFiltrados.map((u) => {
                const isUserAdmin = u.perfil.toLowerCase() === "admin";
                return (
                  <tr key={u.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="px-4 py-3.5 font-mono text-slate-400">#{u.id}</td>
                    <td className="px-4 py-3.5 font-bold text-slate-900">{u.nome}</td>
                    <td className="px-4 py-3.5 font-mono text-slate-600">{u.email}</td>
                    <td className="px-4 py-3.5">
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-bold border ${
                          isUserAdmin
                            ? "bg-purple-50 text-purple-700 border-purple-200"
                            : u.perfil.toLowerCase() === "cliente"
                              ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                              : u.perfil.toLowerCase() === "esporadico"
                                ? "bg-blue-50 text-blue-700 border-blue-200"
                                : "bg-amber-50 text-amber-700 border-amber-200"
                        }`}
                      >
                        {isUserAdmin ? "⚙️ Admin" : `👤 ${u.perfil}`}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 text-slate-500 text-[11px]">
                      {u.perfil_motivo || "Cadastro direto no sistema"}
                    </td>
                    <td className="px-4 py-3.5 text-right">
                      <Link
                        href={`/pedidos/historico`}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-800 underline"
                      >
                        <span>Ver Pedidos</span>
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
