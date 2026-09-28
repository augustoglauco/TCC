"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/hooks/useAuthStore";

// MVP: contas fictícias semeadas no banco pela migração 0011 (Fase 6/7)
const DEMO_ACCOUNTS = [
  {
    nome: "Ana Recorrente",
    email: "ana.recorrente@example.com",
    perfil: "Cliente",
    descricao: "3 compras recentes no histórico",
    badgeColor: "bg-emerald-50 text-emerald-700 border-emerald-200",
  },
  {
    nome: "Bruno Único",
    email: "bruno.unico@example.com",
    perfil: "Esporádico",
    descricao: "1 compra recente no histórico",
    badgeColor: "bg-blue-50 text-blue-700 border-blue-200",
  },
  {
    nome: "Carla Antiga",
    email: "carla.antiga@example.com",
    perfil: "Esporádico",
    descricao: "2 compras há mais de 12 meses",
    badgeColor: "bg-amber-50 text-amber-700 border-amber-200",
  },
];

export default function LoginPage() {
  const router = useRouter();
  const { user, login, logout } = useAuthStore();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("12345");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;

    setIsLoading(true);
    setError(null);

    try {
      await login(email.trim(), password);
      router.push("/conta/perfil");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao efetuar login.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuickLogin = async (demoEmail: string) => {
    setEmail(demoEmail);
    setPassword("12345");
    setIsLoading(true);
    setError(null);

    try {
      await login(demoEmail, "12345");
      router.push("/conta/perfil");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao efetuar login.");
    } finally {
      setIsLoading(false);
    }
  };

  // Se já estiver autenticado
  if (user) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center space-y-6">
        <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600 text-3xl font-bold shadow-xs">
          👤
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Sessão Ativa</h1>
          <p className="mt-2 text-sm text-slate-600">
            Você está autenticado como <strong className="text-slate-900">{user.nome}</strong> (
            <span className="font-mono text-xs">{user.email}</span>).
          </p>
        </div>

        <div className="flex flex-col gap-3">
          <Link
            href="/conta/perfil"
            className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-xs hover:bg-blue-700 transition-colors"
          >
            Ver Meu Perfil e Pedidos
          </Link>
          <button
            type="button"
            onClick={logout}
            className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer"
          >
            Sair da Conta
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg px-4 py-10 sm:py-16 space-y-8">
      {/* Cabeçalho */}
      <div className="text-center space-y-2">
        <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-blue-50 text-blue-600 text-xl font-bold mb-1 shadow-2xs">
          🔐
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
          Entrar na Conta
        </h1>
        <p className="text-xs sm:text-sm text-slate-600 max-w-sm mx-auto">
          Ambiente simulado para teste de perfil de cliente, diferenciação de pedidos e contexto no
          Chat.
        </p>
      </div>

      {/* Formulário Principal */}
      <div className="rounded-2xl border border-slate-200/80 bg-white p-6 sm:p-8 shadow-xs space-y-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="login-email"
              className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5"
            >
              Endereço de E-mail
            </label>
            <input
              id="login-email"
              type="email"
              required
              placeholder="ex: seu.email@empresa.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-blue-600 focus:outline-hidden focus:ring-2 focus:ring-blue-600/20"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label
                htmlFor="login-password"
                className="block text-xs font-semibold text-slate-700 uppercase tracking-wider"
              >
                Senha de Acesso
              </label>
              <span className="text-[11px] font-medium text-blue-600 bg-blue-50 px-2 py-0.5 rounded-md">
                Senha mock: 12345
              </span>
            </div>
            <input
              id="login-password"
              type="password"
              required
              placeholder="12345"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 focus:border-blue-600 focus:outline-hidden focus:ring-2 focus:ring-blue-600/20"
            />
          </div>

          {error && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full rounded-xl bg-blue-600 py-3 px-4 text-sm font-bold text-white shadow-xs hover:bg-blue-700 transition-all disabled:opacity-50 cursor-pointer"
          >
            {isLoading ? "Entrando..." : "Entrar"}
          </button>
        </form>

        {/* Divisor */}
        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-slate-200" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-white px-3 font-semibold text-slate-400">
              Ou escolha um perfil de teste
            </span>
          </div>
        </div>

        {/* Contas de Demonstração Rápidas */}
        <div className="space-y-2.5">
          {DEMO_ACCOUNTS.map((acc) => (
            <button
              key={acc.email}
              type="button"
              onClick={() => handleQuickLogin(acc.email)}
              disabled={isLoading}
              className="w-full flex items-center justify-between rounded-xl border border-slate-200 p-3 text-left hover:border-blue-300 hover:bg-blue-50/50 transition-all cursor-pointer group"
            >
              <div>
                <span className="block text-sm font-bold text-slate-900 group-hover:text-blue-700">
                  {acc.nome}
                </span>
                <span className="block text-xs text-slate-500 font-mono">{acc.email}</span>
                <span className="block text-[11px] text-slate-400 mt-0.5">{acc.descricao}</span>
              </div>
              <span
                className={`rounded-lg px-2.5 py-1 text-[11px] font-bold border ${acc.badgeColor}`}
              >
                {acc.perfil}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
