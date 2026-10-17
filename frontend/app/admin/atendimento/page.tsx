"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import {
  claimConversa,
  enviarMensagemAtendente,
  fecharAtendimento,
  fetchDetalhesConversa,
  fetchFilaEspera,
  fetchMeusChats,
  type AtendimentoDetalhes,
  type AtendimentoFilaItem,
} from "@/lib/api/adminAtendimento";
import ContextoClientePanel from "@/components/admin/atendimento/ContextoClientePanel";
import FilaEsperaPanel from "@/components/admin/atendimento/FilaEsperaPanel";
import MeusChatsTabs from "@/components/admin/atendimento/MeusChatsTabs";
import { useEstaNoCliente } from "@/lib/hooks/useEstaNoCliente";
import { AtendimentoHeader } from "./AtendimentoHeader";

export default function AdminAtendimentoPage() {
  const user = useAuthStore((s) => s.user);
  const token = useAuthStore((s) => s.token);

  const hasHydrated = useEstaNoCliente();
  const [fila, setFila] = useState<AtendimentoFilaItem[]>([]);
  const [meusChats, setMeusChats] = useState<AtendimentoFilaItem[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [detalhesCarregados, setDetalhesCarregados] = useState<AtendimentoDetalhes | null>(null);

  const [loadingFila, setLoadingFila] = useState(true);
  const [claimingId, setClaimingId] = useState<string | null>(null);
  const [sendingMessage, setSendingMessage] = useState(false);
  const [closing, setClosing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const isAdmin = user?.perfil?.toLowerCase() === "admin";

  // Derivados em vez de estado: sem chat ativo nao ha detalhes, e sem
  // admin/token o efeito da fila nem roda (ficaria preso em "carregando").
  // Derivar evita o setState sincrono dentro de efeito que a regra
  // react-hooks/set-state-in-effect proibe.
  const detalhes = activeChatId ? detalhesCarregados : null;

  const atendenteId = user?.id ? String(user.id) : "admin_1";
  const atendenteNome = user?.nome || "Atendente Humano";

  const carregarFilaEMeusChats = useCallback(async () => {
    if (!token || !isAdmin) return;
    try {
      const [filaRes, meusChatsRes] = await Promise.all([
        fetchFilaEspera(token),
        fetchMeusChats(atendenteId, token),
      ]);
      setFila(filaRes);
      setMeusChats(meusChatsRes);

      // Achado de 2026-10-07: este bloco só tinha o comentário da intenção,
      // nunca a limpeza em si — quando o cliente encerrava a conversa (ou
      // outro atendente/a devolvia para a IA), ela sumia da lista de abas
      // (`meusChats`), mas `activeChatId`/`detalhes` continuavam apontando
      // para ela. O painel de chat ativo (`MeusChatsTabs`) não olha o
      // status da conversa para decidir o que mostrar — então o atendente
      // via o chat como se o cliente ainda estivesse ali, podendo mandar
      // mensagem sem efeito, achando que a conversa "não encerra".
      if (activeChatId && !meusChatsRes.some((c) => c.id === activeChatId)) {
        setActiveChatId(null);
        setDetalhesCarregados(null);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Erro ao atualizar fila";
      console.error("Erro ao atualizar fila:", message);
    }
  }, [token, isAdmin, atendenteId, activeChatId]);

  // Carrega fila ao montar e estabelece polling a cada 5s
  useEffect(() => {
    if (!hasHydrated || !isAdmin || !token) return;

    // Falso positivo: `carregarFilaEMeusChats` so toca estado depois de
    // `await Promise.all([...])` sobre funcoes `async` importadas, logo nao
    // ha setState sincrono. A regra nao resolve a assincronia de funcoes
    // importadas e assume o pior caso.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    carregarFilaEMeusChats().finally(() => setLoadingFila(false));

    const interval = setInterval(() => {
      void carregarFilaEMeusChats();
    }, 5000);

    return () => clearInterval(interval);
  }, [hasHydrated, isAdmin, token, carregarFilaEMeusChats]);

  // Carrega detalhes do chat ativo e atualiza a cada 3s se ativo
  const carregarDetalhes = useCallback(async () => {
    if (!activeChatId || !token) return;
    try {
      const data = await fetchDetalhesConversa(activeChatId, token);
      setDetalhesCarregados(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Erro ao carregar detalhes";
      console.error("Erro ao carregar detalhes:", message);
    }
  }, [activeChatId, token]);

  useEffect(() => {
    if (!activeChatId) return;
    // Falso positivo: `carregarDetalhes` so toca estado depois de
    // `await fetchDetalhesConversa` (funcao `async` importada).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void carregarDetalhes();
    const interval = setInterval(() => {
      void carregarDetalhes();
    }, 3000);
    return () => clearInterval(interval);
  }, [activeChatId, carregarDetalhes]);

  // Ação de Claim (Assumir Chat)
  const handleClaim = async (conversationId: string) => {
    if (!token) return;
    setClaimingId(conversationId);
    setErrorMessage(null);
    try {
      await claimConversa(conversationId, atendenteId, atendenteNome, token);
      setActiveChatId(conversationId);
      await carregarFilaEMeusChats();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erro ao assumir atendimento.";
      setErrorMessage(msg);
      await carregarFilaEMeusChats();
    } finally {
      setClaimingId(null);
    }
  };

  // Enviar Mensagem do Atendente
  const handleSendMessage = async (texto: string) => {
    if (!activeChatId || !token) return;
    setSendingMessage(true);
    try {
      await enviarMensagemAtendente(activeChatId, atendenteNome, texto, token);
      await carregarDetalhes();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erro ao enviar mensagem.";
      setErrorMessage(msg);
    } finally {
      setSendingMessage(false);
    }
  };

  // Finalizar Atendimento
  const handleFinalizar = async (motivo?: string) => {
    if (!activeChatId || !token) return;
    setClosing(true);
    try {
      await fecharAtendimento(activeChatId, "finalizar", motivo, token);
      setActiveChatId(null);
      setDetalhesCarregados(null);
      await carregarFilaEMeusChats();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erro ao encerrar atendimento.";
      setErrorMessage(msg);
    } finally {
      setClosing(false);
    }
  };

  // Devolver para IA
  const handleDevolverIA = async () => {
    if (!activeChatId || !token) return;
    setClosing(true);
    try {
      await fecharAtendimento(activeChatId, "devolver_ia", undefined, token);
      setActiveChatId(null);
      setDetalhesCarregados(null);
      await carregarFilaEMeusChats();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erro ao devolver para IA.";
      setErrorMessage(msg);
    } finally {
      setClosing(false);
    }
  };

  if (!hasHydrated) {
    return (
      <div className="flex h-[calc(100vh-4rem)] items-center justify-center">
        <span className="animate-spin text-2xl">⏳</span>
      </div>
    );
  }

  if (!isAdmin) {
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

  return (
    <div className="flex flex-col h-[calc(100vh-3.75rem)] sm:h-[calc(100vh-4rem)] p-2.5 sm:p-3 bg-slate-100 overflow-hidden space-y-2.5">
      {/* Top Banner / Header */}
      <AtendimentoHeader
        atendenteNome={atendenteNome}
        atendenteId={atendenteId}
        errorMessage={errorMessage}
        onDismissError={() => setErrorMessage(null)}
      />

      {/* Grid 3 Colunas */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-3 min-h-0">
        {/* Coluna 1: Fila de Espera (3/12 cols) */}
        <div className="lg:col-span-3 h-full min-h-0">
          <FilaEsperaPanel
            fila={fila}
            loading={loadingFila && isAdmin && !!token}
            claimingId={claimingId}
            onClaim={handleClaim}
            onRefresh={() => {
              setLoadingFila(true);
              void carregarFilaEMeusChats().finally(() => setLoadingFila(false));
            }}
          />
        </div>

        {/* Coluna 2: Meus Chats Ativos (6/12 cols) */}
        <div className="lg:col-span-6 h-full min-h-0">
          <MeusChatsTabs
            chats={meusChats}
            activeChatId={activeChatId}
            onSelectChat={(id) => setActiveChatId(id)}
            detalhes={detalhes}
            onSendMessage={handleSendMessage}
            onFinalizar={handleFinalizar}
            onDevolverIA={handleDevolverIA}
            sendingMessage={sendingMessage}
            closing={closing}
          />
        </div>

        {/* Coluna 3: Contexto do Cliente (3/12 cols) */}
        <div className="lg:col-span-3 h-full min-h-0">
          <ContextoClientePanel detalhes={detalhes} />
        </div>
      </div>
    </div>
  );
}
