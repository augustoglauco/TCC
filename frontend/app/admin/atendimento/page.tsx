"use client";

import React from "react";
import Link from "next/link";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import ContextoClientePanel from "@/components/admin/atendimento/ContextoClientePanel";
import FilaEsperaPanel from "@/components/admin/atendimento/FilaEsperaPanel";
import MeusChatsTabs from "@/components/admin/atendimento/MeusChatsTabs";
import { useEstaNoCliente } from "@/lib/hooks/useEstaNoCliente";
import { useAtendimentoAcoes } from "@/lib/hooks/useAtendimentoAcoes";
import { useAtendimentoDados } from "@/lib/hooks/useAtendimentoDados";
import { AtendimentoHeader } from "./AtendimentoHeader";

function CarregandoAtendimento() {
  return (
    <div className="flex h-[calc(100vh-4rem)] items-center justify-center">
      <span className="animate-spin text-2xl">⏳</span>
    </div>
  );
}

function AcessoRestrito() {
  return (
    <div className="mx-auto max-w-lg p-6 my-12 bg-white rounded-xl border border-red-200 shadow-sm text-center">
      <span className="text-4xl">🚫</span>
      <h1 className="mt-3 text-lg font-bold text-red-700">Acesso Restrito</h1>
      <p className="mt-2 text-xs text-slate-600 leading-relaxed">
        Esta central de suporte humano é restrita a operadores e administradores autenticados.
      </p>
      <Link
        href="/"
        className="mt-4 inline-block px-4 py-2 bg-slate-900 text-white text-xs font-semibold rounded-lg hover:bg-slate-800 transition-colors"
      >
        Voltar ao Início
      </Link>
    </div>
  );
}

export default function AdminAtendimentoPage() {
  const user = useAuthStore((s) => s.user);
  const token = useAuthStore((s) => s.token);
  const hasHydrated = useEstaNoCliente();

  const isAdmin = user?.perfil?.toLowerCase() === "admin";
  const atendenteId = user?.id ? String(user.id) : "admin_1";
  const atendenteNome = user?.nome || "Atendente Humano";

  const dados = useAtendimentoDados({ token, isAdmin, hasHydrated, atendenteId });
  const acoes = useAtendimentoAcoes({
    token,
    activeChatId: dados.activeChatId,
    atendenteId,
    atendenteNome,
    setActiveChatId: dados.setActiveChatId,
    limparChatAtivo: dados.limparChatAtivo,
    carregarFilaEMeusChats: dados.carregarFilaEMeusChats,
    carregarDetalhes: dados.carregarDetalhes,
  });

  if (!hasHydrated) return <CarregandoAtendimento />;
  if (!isAdmin) return <AcessoRestrito />;

  return (
    <div className="flex flex-col h-[calc(100vh-3.75rem)] sm:h-[calc(100vh-4rem)] p-2.5 sm:p-3 bg-slate-100 overflow-hidden space-y-2.5">
      {/* Top Banner / Header */}
      <AtendimentoHeader
        atendenteNome={atendenteNome}
        atendenteId={atendenteId}
        errorMessage={acoes.errorMessage}
        onDismissError={() => acoes.setErrorMessage(null)}
      />

      {/* Grid 3 Colunas */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-3 min-h-0">
        {/* Coluna 1: Fila de Espera (3/12 cols) */}
        <div className="lg:col-span-3 h-full min-h-0">
          <FilaEsperaPanel
            fila={dados.fila}
            loading={dados.loadingFila && isAdmin && !!token}
            claimingId={acoes.claimingId}
            onClaim={acoes.handleClaim}
            onRefresh={dados.recarregarFila}
          />
        </div>

        {/* Coluna 2: Meus Chats Ativos (6/12 cols) */}
        <div className="lg:col-span-6 h-full min-h-0">
          <MeusChatsTabs
            chats={dados.meusChats}
            activeChatId={dados.activeChatId}
            onSelectChat={(id) => dados.setActiveChatId(id)}
            detalhes={dados.detalhes}
            onSendMessage={acoes.handleSendMessage}
            onFinalizar={acoes.handleFinalizar}
            onDevolverIA={acoes.handleDevolverIA}
            sendingMessage={acoes.sendingMessage}
            closing={acoes.closing}
          />
        </div>

        {/* Coluna 3: Contexto do Cliente (3/12 cols) */}
        <div className="lg:col-span-3 h-full min-h-0">
          <ContextoClientePanel detalhes={dados.detalhes} />
        </div>
      </div>
    </div>
  );
}
