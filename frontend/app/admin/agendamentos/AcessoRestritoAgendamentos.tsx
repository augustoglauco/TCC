import Link from "next/link";

export function AcessoRestritoAgendamentos() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-16 text-center space-y-4">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-red-50 text-2xl">
        🚫
      </div>
      <h1 className="text-2xl font-bold text-red-600">Acesso Restrito</h1>
      <p className="text-sm text-slate-600">
        Apenas administradores podem acessar esta página de gestão de agendamentos.
      </p>
      <Link
        href="/"
        className="inline-flex items-center rounded-lg bg-slate-800 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700"
      >
        Voltar para Início
      </Link>
    </div>
  );
}
