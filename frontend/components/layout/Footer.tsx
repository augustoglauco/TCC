"use client";
/* eslint-disable @next/next/no-img-element */

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
    <footer className="footer-section relative overflow-hidden border-t border-white/10 bg-[#100d0b] text-white/75">
      {/* Background Product Image + M3 Glass .footer-shade (backdrop-blur-29px) */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
        <img
          src="/images/produtos/idblock-facial-preta.jpg"
          alt=""
          className="h-full w-full object-cover object-center opacity-15"
        />
        <div className="footer-shade absolute inset-0 bg-[#100d0b]/85 backdrop-blur-[29px]" />
      </div>

      <div className="relative z-10 mx-auto max-w-7xl px-4 pt-14 pb-10 sm:px-6 lg:px-8">
        {/* Grade em 4 colunas industriais estilo M3 Glass */}
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {/* Coluna 1: Marca & Propósito */}
          <div className="space-y-4">
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#16c0dd] text-[#191919] font-extrabold text-base shadow-md shadow-[#16c0dd]/20">
                ⚡
              </div>
              <span className="font-extrabold text-white text-lg tracking-tight">
                Empresa Fictícia
              </span>
            </div>
            <p className="text-xs text-white/65 leading-relaxed">
              Distribuição e integração de tecnologia de ponta em hardware de acesso e segurança
              física. Equipamentos industriais de alta durabilidade com atendimento potencializado
              por IA.
            </p>
            <div className="pt-1">
              <span className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-[11px] font-bold text-[#16c0dd]">
                <span className="h-1.5 w-1.5 rounded-full bg-[#16c0dd] animate-pulse" />
                Linha Oficial Fictícia
              </span>
            </div>
          </div>

          {/* Coluna 2: Soluções de Hardware */}
          <div className="space-y-3">
            <h4 className="text-xs font-extrabold uppercase tracking-[0.18em] text-white">
              Soluções de Hardware
            </h4>
            <ul className="space-y-2 text-xs">
              <li>
                <Link
                  href="/produtos"
                  className="hover:text-[#16c0dd] transition-colors flex items-center gap-1.5"
                >
                  <span className="text-[#16c0dd]">›</span>
                  <span>Reconhecimento Facial (iDFace)</span>
                </Link>
              </li>
              <li>
                <Link
                  href="/produtos"
                  className="hover:text-[#16c0dd] transition-colors flex items-center gap-1.5"
                >
                  <span className="text-[#16c0dd]">›</span>
                  <span>Catracas &amp; Bloqueios (iDBlock)</span>
                </Link>
              </li>
              <li>
                <Link
                  href="/produtos"
                  className="hover:text-[#16c0dd] transition-colors flex items-center gap-1.5"
                >
                  <span className="text-[#16c0dd]">›</span>
                  <span>Controle de Acesso Biométrico</span>
                </Link>
              </li>
              <li>
                <Link
                  href="/produtos"
                  className="hover:text-[#16c0dd] transition-colors flex items-center gap-1.5"
                >
                  <span className="text-[#16c0dd]">›</span>
                  <span>Ponto Eletrônico (Portaria 671)</span>
                </Link>
              </li>
              <li>
                <Link
                  href="/produtos"
                  className="hover:text-[#16c0dd] transition-colors flex items-center gap-1.5"
                >
                  <span className="text-[#16c0dd]">›</span>
                  <span>Fechaduras Digitais e Leitores UHF</span>
                </Link>
              </li>
            </ul>
          </div>

          {/* Coluna 3: Navegação & Serviços */}
          <div className="space-y-3">
            <h4 className="text-xs font-extrabold uppercase tracking-[0.18em] text-white">
              Navegação &amp; Serviços
            </h4>
            <ul className="space-y-2 text-xs">
              <li>
                <Link href="/" className="hover:text-[#16c0dd] transition-colors">
                  Página Inicial
                </Link>
              </li>
              <li>
                <Link href="/produtos" className="hover:text-[#16c0dd] transition-colors">
                  Catálogo Técnico Completo
                </Link>
              </li>
              <li>
                <Link href="/pedidos" className="hover:text-[#16c0dd] transition-colors">
                  Carrinho &amp; Pedidos
                </Link>
              </li>
              <li>
                <Link href="/agendamentos" className="hover:text-[#16c0dd] transition-colors">
                  Agendar Visita Técnica
                </Link>
              </li>
              <li>
                <Link href="/suporte" className="hover:text-[#16c0dd] transition-colors">
                  Central de Suporte &amp; Manuais
                </Link>
              </li>
              <li>
                <Link href="/contato" className="hover:text-[#16c0dd] transition-colors">
                  Fale Conosco
                </Link>
              </li>
            </ul>
          </div>

          {/* Coluna 4: Atendimento & B2B */}
          <div className="space-y-3">
            <h4 className="text-xs font-extrabold uppercase tracking-[0.18em] text-white">
              Atendimento &amp; Suporte
            </h4>
            <p className="text-xs text-white/65">
              Atendimento 24/7 com Assistente Virtual integrado via RAG vetorial e protocolo MCP.
            </p>
            <div className="space-y-1.5 text-xs">
              <p className="flex items-center gap-2 text-white">
                <span>📞</span>
                <span className="font-semibold">0800 123 4567</span>
              </p>
              <p className="flex items-center gap-2 text-white/85">
                <span>✉️</span>
                <span>comercial@empresaficticia.com.br</span>
              </p>
              <p className="flex items-center gap-2 text-white/65">
                <span>📍</span>
                <span>São Paulo, SP — Brasil</span>
              </p>
            </div>
          </div>
        </div>

        {/* Linha Inferior com Selo de TCC e Copyright */}
        <div className="mt-12 border-t border-white/10 pt-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-white/55">
          <p>
            © 2026 Empresa Fictícia. Todos os direitos reservados. Catálogo Oficial Fictícia.
          </p>
          <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3.5 py-1 text-[11px] text-white/75">
            <span>🎓</span>
            <span>Protótipo TCC IA Generativa — Assistente Virtual Multimodal</span>
          </div>
        </div>

        {/* Giant Watermark at the bottom */}
        <div
          aria-hidden="true"
          className="mt-8 text-center select-none pointer-events-none overflow-hidden"
        >
          <span className="block text-[44px] sm:text-[84px] lg:text-[128px] font-black uppercase tracking-tight leading-none bg-gradient-to-b from-white/15 to-transparent bg-clip-text text-transparent">
            EMPRESA FICTÍCIA
          </span>
        </div>
      </div>
    </footer>
  );
}
