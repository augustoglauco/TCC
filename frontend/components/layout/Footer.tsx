import Link from "next/link";

export default function Footer() {
  return (
    <footer className="border-t border-slate-200/80 bg-slate-900 text-slate-400">
      <div className="mx-auto max-w-5xl px-4 py-8 sm:py-10">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
          <div className="space-y-1">
            <div className="flex items-center gap-2 font-bold text-white text-base">
              <span>⚡ Empresa Fictícia TCC</span>
            </div>
            <p className="text-xs text-slate-400 max-w-md leading-relaxed">
              Trabalho de Conclusão de Curso — Assistente Virtual Multimodal com Roteador Inteligente e Protocolo MCP.
            </p>
          </div>

          <div className="flex flex-wrap gap-4 text-xs font-medium text-slate-300">
            <Link href="/" className="hover:text-white transition-colors">Início</Link>
            <Link href="/produtos" className="hover:text-white transition-colors">Produtos</Link>
            <Link href="/pedidos" className="hover:text-white transition-colors">Pedidos</Link>
            <Link href="/agendamentos" className="hover:text-white transition-colors">Agendamentos</Link>
            <Link href="/suporte" className="hover:text-white transition-colors">Suporte</Link>
            <Link href="/contato" className="hover:text-white transition-colors">Contato</Link>
          </div>
        </div>

        <div className="mt-8 border-t border-slate-800 pt-6 flex flex-col sm:flex-row items-center justify-between gap-3 text-[11px] text-slate-500">
          <p>© 2026 Empresa Fictícia TCC. Todos os direitos reservados. Conteúdo demonstrativo.</p>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-slate-800 px-3 py-1 font-mono text-[10px] text-slate-400">
            <span>🎓 Protótipo TCC IA Generativa</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
