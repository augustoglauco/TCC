export function AcessoRestrito() {
  return (
    <div className="mx-auto max-w-md px-4 py-16 text-center space-y-6">
      <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-rose-50 text-rose-600 text-3xl font-bold shadow-xs border border-rose-200">
        🔒
      </div>
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Acesso restrito</h1>
        <p className="mt-2 text-sm text-gray-600">Esta página é exclusiva de administradores.</p>
      </div>
    </div>
  );
}
