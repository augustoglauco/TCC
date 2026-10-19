import Link from "next/link";

export function LoginRequired() {
  return (
    <div className="mx-auto max-w-md px-4 py-16 text-center space-y-6">
      <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-50 text-amber-600 text-3xl font-bold shadow-xs border border-amber-200">
        🔐
      </div>
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Autenticação Necessária</h1>
        <p className="mt-2 text-sm text-slate-600">
          Para entrar em pedidos, acessar seu carrinho e finalizar compras, é necessário estar
          logado na sua conta.
        </p>
      </div>
      <div className="flex flex-col gap-3 pt-2">
        <Link
          href="/conta/login?redirect=/pedidos"
          className="rounded-xl bg-blue-600 px-4 py-3 text-sm font-bold text-white shadow-xs hover:bg-blue-700 transition-colors"
        >
          Entrar na Conta &rarr;
        </Link>
        <Link
          href="/produtos"
          className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
        >
          Voltar para o Catálogo de Produtos
        </Link>
      </div>
    </div>
  );
}
