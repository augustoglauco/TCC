"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/hooks/useAuthStore";

export default function CadastroPage() {
  const router = useRouter();
  const { user, register: registerUser } = useAuthStore();

  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("12345");
  const [perfil, setPerfil] = useState<"Cliente" | "Admin">("Cliente");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nome.trim() || !email.trim()) return;

    setIsLoading(true);
    setError(null);

    try {
      if (perfil === "Admin" && user?.perfil?.toLowerCase() !== "admin" && email !== "admin@example.com") {
        setError("Apenas um administrador logado pode criar contas com perfil Administrador.");
        setIsLoading(false);
        return;
      }

      await registerUser({
        nome: nome.trim(),
        email: email.trim(),
        password,
        perfil,
        requesterEmail: user?.email,
      });

      if (perfil === "Admin") {
        router.push("/admin/produtos");
      } else {
        router.push("/conta/perfil");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao realizar cadastro.");
    } finally {
      setIsLoading(false);
    }
  };

  const isCurrentAdmin = user?.perfil?.toLowerCase() === "admin";

  if (user && !isCurrentAdmin) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center space-y-6">
        <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600 text-3xl font-bold shadow-xs">
          ✓
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Sessão Ativa</h1>
          <p className="mt-2 text-sm text-slate-600">
            Você está logado como <strong className="text-slate-900">{user.nome}</strong> ({user.email}) - Perfil{" "}
            <span className="rounded bg-blue-100 text-blue-800 px-2 py-0.5 font-bold text-xs">
              {user.perfil}
            </span>.
          </p>
          <p className="mt-2 text-xs text-slate-500">
            Apenas um Administrador autenticado pode cadastrar novos Administradores.
          </p>
        </div>

        <div className="flex flex-col gap-3">
          <Link
            href="/conta/perfil"
            className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-xs hover:bg-blue-700 transition-colors"
          >
            Ver Meu Perfil
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg px-4 py-10 sm:py-16 space-y-8">
      {/* Banner de permissão Admin caso o admin esteja cadastrando */}
      {isCurrentAdmin && (
        <div className="rounded-xl border border-purple-200 bg-purple-50/80 p-4 flex items-center gap-3">
          <span className="text-xl">⚙️</span>
          <div className="text-xs text-purple-900">
            <span className="font-bold block">Sessão Administrativa Ativa ({user.nome})</span>
            Você possui autorização para criar contas com perfil <strong>Administrador (Admin)</strong> ou <strong>Cliente</strong>.
          </div>
        </div>
      )}

      {/* Cabeçalho */}
      <div className="text-center space-y-2">
        <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-blue-50 text-blue-600 text-xl font-bold mb-1 shadow-2xs">
          👤
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
          Novo Cadastro de Usuário
        </h1>
        <p className="text-xs sm:text-sm text-slate-600 max-w-sm mx-auto">
          Crie sua conta para acessar pedidos, frete por CEP, simulações B2B ou permissões administrativas.
        </p>
      </div>

      {/* Formulário Principal */}
      <div className="rounded-2xl border border-slate-200/80 bg-white p-6 sm:p-8 shadow-xs space-y-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="register-nome"
              className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5"
            >
              Nome Completo
            </label>
            <input
              id="register-nome"
              type="text"
              required
              placeholder="ex: João Silva"
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-blue-600 focus:outline-hidden focus:ring-2 focus:ring-blue-600/20"
            />
          </div>

          <div>
            <label
              htmlFor="register-email"
              className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5"
            >
              Endereço de E-mail
            </label>
            <input
              id="register-email"
              type="email"
              required
              placeholder="ex: joao.silva@empresa.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-blue-600 focus:outline-hidden focus:ring-2 focus:ring-blue-600/20"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label
                htmlFor="register-password"
                className="block text-xs font-semibold text-slate-700 uppercase tracking-wider"
              >
                Senha de Acesso
              </label>
              <span className="text-[11px] font-medium text-blue-600 bg-blue-50 px-2 py-0.5 rounded-md">
                Senha mock: 12345
              </span>
            </div>
            <input
              id="register-password"
              type="password"
              required
              placeholder="12345"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 focus:border-blue-600 focus:outline-hidden focus:ring-2 focus:ring-blue-600/20"
            />
          </div>

          {/* Seleção do Perfil de Usuário */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
              Tipo de Perfil de Usuário
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setPerfil("Cliente")}
                className={`rounded-xl border p-3 text-left transition-all cursor-pointer ${
                  perfil === "Cliente"
                    ? "border-blue-600 bg-blue-50/60 ring-2 ring-blue-600/20"
                    : "border-slate-200 bg-white hover:border-slate-300"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-900">👤 Simples (Cliente)</span>
                  {perfil === "Cliente" && <span className="text-blue-600 text-xs">✓</span>}
                </div>
                <p className="text-[11px] text-slate-500 mt-1">
                  Perfil padrão para realizar compras, frete e histórico de pedidos.
                </p>
              </button>

              <button
                type="button"
                onClick={() => setPerfil("Admin")}
                className={`rounded-xl border p-3 text-left transition-all cursor-pointer ${
                  perfil === "Admin"
                    ? "border-purple-600 bg-purple-50/60 ring-2 ring-purple-600/20"
                    : "border-slate-200 bg-white hover:border-slate-300"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-900">⚙️ Administrador</span>
                  {perfil === "Admin" && <span className="text-purple-600 text-xs">✓</span>}
                </div>
                <p className="text-[11px] text-slate-500 mt-1">
                  Acesso total ao Menu Admin, Catálogo de Produtos e Ingestão.
                </p>
              </button>
            </div>
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
            {isLoading ? "Cadastrando..." : "Criar Minha Conta"}
          </button>
        </form>

        <div className="text-center pt-2 border-t border-slate-100">
          <p className="text-xs text-slate-600">
            Já possui uma conta criada?{" "}
            <Link href="/conta/login" className="font-bold text-blue-600 hover:underline">
              Fazer Login &rarr;
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
