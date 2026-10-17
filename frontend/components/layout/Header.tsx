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
    <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-slate-950/85 backdrop-blur-md text-slate-100 transition-all shadow-lg">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-3 sm:px-6 lg:px-8">
        {/* Logo / Marca estilo Industrial */}
        <Link href="/" className="flex items-center gap-2.5 group shrink-0 min-w-0">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-blue-600 via-indigo-600 to-sky-500 text-white font-bold text-lg shadow-md shadow-blue-500/20 group-hover:scale-105 transition-transform border border-blue-400/30">
            ⚡
          </div>
          <div className="flex flex-col min-w-0">
            <span className="text-base sm:text-lg font-extrabold tracking-tight text-white group-hover:text-blue-400 transition-colors truncate">
              Empresa Fictícia
            </span>
            <span className="text-[10px] sm:text-[11px] font-semibold text-slate-400 uppercase tracking-widest truncate">
              Controle de Acesso &amp; Segurança
            </span>
          </div>
        </Link>

        {/* Links desktop & Ações */}
        <div className="flex items-center gap-2 sm:gap-4 shrink-0">
          <nav aria-label="Navegação principal" className="hidden lg:block">
            <ul className="flex items-center gap-1 text-sm font-medium text-slate-300">
              {navLinks.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="rounded-lg px-3 py-2 text-slate-300 hover:bg-slate-900/80 hover:text-white transition-colors"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          {/* Atalho de Atendimento rápido inspirado no M3 Glass */}
          <div className="hidden xl:flex items-center gap-2 border-l border-slate-800 pl-4 text-xs text-slate-400">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-900 text-blue-400">
              📞
            </span>
            <div className="flex flex-col">
              <span className="text-[10px] uppercase tracking-wider text-slate-500">
                Atendimento
              </span>
              <span className="font-semibold text-slate-200">0800 123 4567</span>
            </div>
          </div>

          {/* Menu de Administração (Engrenagem) */}
          <AdminGearMenu />

          {/* Botão de abrir Chat / Agente estilo M3 Glass */}
          <button
            type="button"
            onClick={() => useChatStore.getState().open()}
            aria-label="Falar com Assistente IA"
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-3.5 py-2 text-xs font-bold text-white shadow-md shadow-blue-500/25 hover:from-blue-500 hover:to-indigo-500 hover:shadow-lg hover:shadow-blue-500/35 transition-all cursor-pointer shrink-0 border border-blue-400/30"
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
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-slate-800 bg-slate-900 text-slate-300 hover:bg-slate-800 hover:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 lg:hidden"
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
        <div className="border-b border-slate-800 bg-slate-950/95 px-4 py-4 lg:hidden shadow-2xl backdrop-blur-xl">
          <nav aria-label="Navegação principal móvel">
            <ul className="flex flex-col space-y-2">
              <li>
                <button
                  type="button"
                  onClick={() => {
                    setIsMobileMenuOpen(false);
                    useChatStore.getState().open();
                  }}
                  className="flex w-full items-center gap-3 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-4 py-3 text-sm font-bold text-white shadow-md hover:brightness-110 transition-all text-left"
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
                    className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-slate-300 hover:bg-slate-900 hover:text-white transition-colors"
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
