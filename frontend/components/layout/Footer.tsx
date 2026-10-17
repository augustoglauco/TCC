"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function Footer() {
  const pathname = usePathname();

  // Esconde o footer em páginas do painel admin (ex. /admin/atendimento)
  // para permitir layout full-screen (100vh) sem barra de rolagem externa.
  if (pathname?.startsWith("/admin")) {
    return null;
  }

  return (
    <footer className="border-t border-slate-800 bg-slate-950 text-slate-400">
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        {/* Grade em 4 colunas industriais estilo M3 Glass */}
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {/* Coluna 1: Marca & Propósito */}
          <div className="space-y-4">
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-600 to-indigo-600 text-white font-bold text-base shadow-md shadow-blue-500/20 border border-blue-400/30">
                ⚡
              </div>
              <span className="font-extrabold text-white text-lg tracking-tight">
                Empresa Fictícia
              </span>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Distribuição e integração de tecnologia de ponta em hardware de acesso e segurança
              física. Equipamentos industriais de alta durabilidade com atendimento potencializado
              por IA.
            </p>
            <div className="pt-1">
              <span className="inline-flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900 px-3 py-1 text-[11px] font-medium text-slate-300">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Linha Oficial Control iD
              </span>
            </div>
          </div>

          {/* Coluna 2: Soluções de Hardware */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-widest text-slate-200">
              Soluções de Hardware
            </h4>
            <ul className="space-y-2 text-xs">
              <li>
                <Link
                  href="/produtos"
                  className="hover:text-blue-400 transition-colors flex items-center gap-1.5"
                >
                  <span>›</span>
                  <span>Reconhecimento Facial (iDFace)</span>
                </Link>
              </li>
              <li>
                <Link
                  href="/produtos"
                  className="hover:text-blue-400 transition-colors flex items-center gap-1.5"
                >
                  <span>›</span>
                  <span>Catracas &amp; Bloqueios (iDBlock)</span>
                </Link>
              </li>
              <li>
                <Link
                  href="/produtos"
                  className="hover:text-blue-400 transition-colors flex items-center gap-1.5"
                >
                  <span>›</span>
                  <span>Controle de Acesso Biométrico</span>
                </Link>
              </li>
              <li>
                <Link
                  href="/produtos"
                  className="hover:text-blue-400 transition-colors flex items-center gap-1.5"
                >
                  <span>›</span>
                  <span>Ponto Eletrônico (Portaria 671)</span>
                </Link>
              </li>
              <li>
                <Link
                  href="/produtos"
                  className="hover:text-blue-400 transition-colors flex items-center gap-1.5"
                >
                  <span>›</span>
                  <span>Fechaduras Digitais e Leitores UHF</span>
                </Link>
              </li>
            </ul>
          </div>

          {/* Coluna 3: Navegação & Serviços */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-widest text-slate-200">
              Navegação &amp; Serviços
            </h4>
            <ul className="space-y-2 text-xs">
              <li>
                <Link href="/" className="hover:text-white transition-colors">
                  Página Inicial
                </Link>
              </li>
              <li>
                <Link href="/produtos" className="hover:text-white transition-colors">
                  Catálogo Técnico Completo
                </Link>
              </li>
              <li>
                <Link href="/pedidos" className="hover:text-white transition-colors">
                  Carrinho &amp; Pedidos
                </Link>
              </li>
              <li>
                <Link href="/agendamentos" className="hover:text-white transition-colors">
                  Agendar Visita Técnica
                </Link>
              </li>
              <li>
                <Link href="/suporte" className="hover:text-white transition-colors">
                  Central de Suporte &amp; Manuais
                </Link>
              </li>
              <li>
                <Link href="/contato" className="hover:text-white transition-colors">
                  Fale Conosco
                </Link>
              </li>
            </ul>
          </div>

          {/* Coluna 4: Atendimento & B2B */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-widest text-slate-200">
              Atendimento &amp; Suporte
            </h4>
            <p className="text-xs text-slate-400">
              Atendimento 24/7 com Assistente Virtual integrado via RAG vetorial e protocolo MCP.
            </p>
            <div className="space-y-1.5 text-xs">
              <p className="flex items-center gap-2 text-slate-300">
                <span>📞</span>
                <span className="font-semibold">0800 123 4567</span>
              </p>
              <p className="flex items-center gap-2 text-slate-300">
                <span>✉️</span>
                <span>comercial@empresaficticia.com.br</span>
              </p>
              <p className="flex items-center gap-2 text-slate-400">
                <span>📍</span>
                <span>São Paulo, SP — Brasil</span>
              </p>
            </div>
          </div>
        </div>

        {/* Linha Inferior com Selo de TCC e Copyright */}
        <div className="mt-12 border-t border-slate-900 pt-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">
          <p>
            © 2026 Empresa Fictícia. Todos os direitos reservados. Catálogo baseado em Control iD.
          </p>
          <div className="inline-flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900/90 px-3.5 py-1 text-[11px] text-slate-400">
            <span>🎓</span>
            <span>Protótipo TCC IA Generativa — Assistente Virtual Multimodal</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
