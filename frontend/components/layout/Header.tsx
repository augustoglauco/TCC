"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { useChatStore } from "@/lib/hooks/useChatStore";
import AdminGearMenu from "./AdminGearMenu";

const STATIC_LINKS = [
  { href: "/", label: "Início", icon: "🏠" },
  { href: "/produtos", label: "Produtos", icon: "📦" },
  { href: "/pedidos", label: "Pedidos", icon: "🛒" },
  { href: "/agendamentos", label: "Agendamentos", icon: "📅" },
  { href: "/suporte", label: "Suporte", icon: "🔧" },
  { href: "/contato", label: "Contato", icon: "📞" },
];

export default function Header() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const user = useAuthStore((state) => state.user);

  const accountLink = user
    ? { href: "/conta/perfil", label: `Olá, ${user.nome.split(" ")[0]}`, icon: "👤" }
    : { href: "/conta/login", label: "Entrar", icon: "👤" };

  const navLinks = [...STATIC_LINKS, accountLink];

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-[#14161b]/90 backdrop-blur-[20px] text-white transition-all shadow-lg">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-3.5 sm:px-6 lg:px-8">
        {/* Logo / Marca estilo M3 Glass Industrial */}
        <Link href="/" className="flex items-center gap-3 group shrink-0 min-w-0">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#16c0dd] text-[#191919] font-extrabold text-lg shadow-md shadow-[#16c0dd]/25 group-hover:scale-105 transition-transform">
            ⚡
          </div>
          <div className="flex flex-col min-w-0">
            <span className="text-base sm:text-lg font-extrabold tracking-tight text-white group-hover:text-[#16c0dd] transition-colors truncate">
              Empresa Fictícia
            </span>
            <span className="text-[10px] sm:text-[11px] font-bold text-[#16c0dd] uppercase tracking-[0.18em] truncate">
              Controle de Acesso &amp; Segurança
            </span>
          </div>
        </Link>

        {/* Links desktop & Ações */}
        <div className="flex items-center gap-2 sm:gap-4 shrink-0">
          <nav aria-label="Navegação principal" className="hidden lg:block">
            <ul className="flex items-center gap-1 text-sm font-semibold text-white/85">
              {navLinks.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="rounded-full px-3.5 py-2 text-white/85 hover:bg-white/10 hover:text-[#16c0dd] transition-colors"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          {/* Atalho de Atendimento rápido inspirado no M3 Glass (.header-contact) */}
          <div className="hidden xl:flex items-center gap-2.5 border-l border-white/15 pl-4 text-xs text-white/75">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10 text-[#16c0dd]">
              📞
            </span>
            <div className="flex flex-col">
              <span className="text-[10px] uppercase tracking-wider text-white/50">
                Atendimento
              </span>
              <span className="font-bold text-white">0800 123 4567</span>
            </div>
          </div>

          {/* Menu de Administração (Engrenagem) */}
          <AdminGearMenu />

          {/* Botão de abrir Chat / Agente estilo M3 Glass */}
          <button
            type="button"
            onClick={() => useChatStore.getState().open()}
            className="inline-flex items-center gap-2 rounded-full bg-[#16c0dd] px-4 py-2 text-xs font-extrabold text-[#191919] shadow-md shadow-[#16c0dd]/25 hover:bg-white hover:text-[#191919] transition-all cursor-pointer shrink-0"
          >
            <span>💬</span>
            <span className="hidden sm:inline">Falar com Assistente IA</span>
            <span className="sm:hidden">Chat IA</span>
          </button>

          {/* Botão de Menu Mobile (Hambúrguer) */}
          <button
            type="button"
            onClick={() => setIsMobileMenuOpen((prev) => !prev)}
            aria-expanded={isMobileMenuOpen}
            aria-label={isMobileMenuOpen ? "Fechar menu principal" : "Abrir menu principal"}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/15 bg-white/5 text-white hover:bg-white/15 focus:outline-none focus:ring-2 focus:ring-[#16c0dd] lg:hidden"
          >
            <svg
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
              aria-hidden="true"
            >
              {isMobileMenuOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>
      </div>

      {/* Drawer do Menu Mobile / Tablet */}
      {isMobileMenuOpen && (
        <div className="border-b border-white/10 bg-[#14161b]/95 px-4 py-4 lg:hidden shadow-2xl backdrop-blur-xl">
          <nav aria-label="Navegação principal móvel">
            <ul className="flex flex-col space-y-2">
              <li>
                <button
                  type="button"
                  onClick={() => {
                    setIsMobileMenuOpen(false);
                    useChatStore.getState().open();
                  }}
                  className="flex w-full items-center gap-3 rounded-xl bg-[#16c0dd] px-4 py-3 text-sm font-extrabold text-[#191919] shadow-md hover:brightness-110 transition-all text-left"
                >
                  <span className="text-lg">💬</span>
                  <span>Abrir Chat / Assistente IA</span>
                </button>
              </li>
              {navLinks.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    onClick={() => setIsMobileMenuOpen(false)}
                    className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold text-white/85 hover:bg-white/10 hover:text-[#16c0dd] transition-colors"
                  >
                    <span className="text-lg">{link.icon}</span>
                    <span>{link.label}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      )}
    </header>
  );
}
