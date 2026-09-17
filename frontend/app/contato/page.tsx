export default function ContatoPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:py-12 space-y-8">
      {/* Cabeçalho */}
      <div className="border-b border-slate-200 pb-6">
        <div className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
          <span>📞</span> Atendimento & Contato
        </div>
        <h1 className="mt-3 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
          Fale Conosco
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          Canais institucionais de comunicação para dúvidas, parcerias e suporte corporativo.
        </p>
      </div>

      {/* Cards de Contato */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-xs text-center space-y-2">
          <span className="text-3xl">📧</span>
          <h3 className="font-bold text-slate-900 text-base">E-mail</h3>
          <p className="text-xs text-slate-600 font-mono">contato@empresaficticia-tcc.example</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-xs text-center space-y-2">
          <span className="text-3xl">📞</span>
          <h3 className="font-bold text-slate-900 text-base">Telefone</h3>
          <p className="text-xs text-slate-600 font-mono">(11) 4004-9000</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-xs text-center space-y-2">
          <span className="text-3xl">🏢</span>
          <h3 className="font-bold text-slate-900 text-base">Endereço</h3>
          <p className="text-xs text-slate-600">Av. Paulista, 1000 — São Paulo/SP</p>
        </div>
      </div>
    </div>
  );
}
