import Link from "next/link";

export function DashboardsAcessoRestrito() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-16 text-center">
      <div className="rounded-2xl border border-red-200 bg-red-50 p-8">
        <span className="text-4xl">🔒</span>
        <h1 className="mt-3 text-xl font-bold text-red-800">Acesso Restrito</h1>
        <p className="mt-2 text-sm text-red-600">
          Você precisa estar logado como Administrador para visualizar e gerenciar Dashboards.
        </p>
        <div className="mt-6">
          <Link
            href="/conta/login"
            className="rounded-xl bg-red-600 px-5 py-2.5 text-sm font-semibold text-white shadow-xs hover:bg-red-700 transition-colors"
          >
            Fazer Login como Administrador
          </Link>
        </div>
      </div>
    </main>
  );
}
