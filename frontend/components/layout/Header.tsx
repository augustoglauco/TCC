"use client";

import { useState } from "react";
import Link from "next/link";
import AdminGearMenu from "./AdminGearMenu";

const NAV_LINKS = [
  { href: "/", label: "Início", icon: "🏠" },
  { href: "/produtos", label: "Produtos", icon: "📦" },
  { href: "/pedidos", label: "Pedidos", icon: "🛒" },
  { href: "/agendamentos", label: "Agendamentos", icon: "📅" },
  { href: "/suporte", label: "Suporte", icon: "🔧" },
  { href: "/contato", label: "Contato", icon: "📞" },
  { href: "/conta/login", label: "Entrar", icon: "👤" },
];

export default function Header() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/90 backdrop-blur-md transition-all shadow-xs">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3.5 sm:px-6">
        {/* Logo / Marca */}
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-600 text-white font-bold text-base shadow-sm group-hover:scale-105 transition-transform">
            ⚡
          </div>
          <div className="flex flex-col">
            <span className="text-base font-bold tracking-tight text-slate-900 group-hover:text-blue-600 transition-colors">
              Empresa Fictícia
            </span>
            <span className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">
              Assistente Multimodal
            </span>
          </div>
        </Link>

        {/* Links desktop & Ações */}
        <div className="flex items-center gap-2 sm:gap-3">
          <nav aria-label="Navegação principal" className="hidden md:block">
            <ul className="flex items-center gap-1 text-sm font-medium text-slate-700">
              {NAV_LINKS.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="rounded-lg px-3 py-2 text-slate-600 hover:bg-slate-100 hover:text-blue-600 transition-colors"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          {/* Menu de Administração (Engrenagem) */}
          <AdminGearMenu />

          {/* Botão de Menu Mobile (Hambúrguer) */}
          <button
            type="button"
            onClick={() => setIsMobileMenuOpen((prev) => !prev)}
            aria-expanded={isMobileMenuOpen}
            aria-label={isMobileMenuOpen ? "Fechar menu principal" : "Abrir menu principal"}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 md:hidden"
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

      {/* Drawer do Menu Mobile */}
      {isMobileMenuOpen && (
        <div className="border-b border-slate-200 bg-white px-4 py-3 md:hidden shadow-lg animate-in slide-in-from-top duration-200">
          <nav aria-label="Navegação principal móvel">
            <ul className="flex flex-col space-y-1">
              {NAV_LINKS.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    onClick={() => setIsMobileMenuOpen(false)}
                    className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-base font-medium text-slate-700 hover:bg-blue-50 hover:text-blue-700 transition-colors"
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
