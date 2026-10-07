"use client";

import React, { useEffect, useRef, useState } from "react";
import type { AtendimentoDetalhes, AtendimentoFilaItem } from "@/lib/api/adminAtendimento";

interface MeusChatsTabsProps {
  chats: AtendimentoFilaItem[];
  activeChatId: string | null;
  onSelectChat: (conversationId: string) => void;
  detalhes: AtendimentoDetalhes | null;
  onSendMessage: (texto: string) => Promise<void>;
  onFinalizar: (motivo?: string) => Promise<void>;
  onDevolverIA: () => Promise<void>;
  sendingMessage: boolean;
  closing: boolean;
}

export default function MeusChatsTabs({
  chats,
  activeChatId,
  onSelectChat,
  detalhes,
  onSendMessage,
  onFinalizar,
  onDevolverIA,
  sendingMessage,
  closing,
}: MeusChatsTabsProps) {
  const [inputText, setInputText] = useState("");
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Achado de 2026-10-07: `detalhes` é repollado a cada 3s (ver
  // `app/admin/atendimento/page.tsx`) e cada busca traz um array de
  // `mensagens` novo (nova referência) mesmo sem nenhuma mensagem nova —
  // usar o array inteiro como dependência disparava o scroll a cada poll,
  // prendendo a tela sempre no fundo e impedindo o atendente de rolar para
  // cima para reler o histórico. `.length` só muda quando chega mensagem
  // nova de fato.
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [detalhes?.mensagens.length]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = inputText.trim();
    if (!trimmed || sendingMessage) return;
    setInputText("");
    await onSendMessage(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSubmit(e);
    }
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
      {/* Abas dos Meus Chats */}
      <div className="flex items-center gap-1 px-3 pt-2 border-b border-slate-200 bg-slate-50/90 overflow-x-auto">
        <span className="text-xs font-semibold text-slate-500 mr-2 shrink-0">
          Meus Chats ({chats.length}):
        </span>

        {chats.length === 0 ? (
          <span className="text-xs text-slate-400 italic py-1.5">Nenhum chat assumido</span>
        ) : (
          chats.map((c) => {
            const isActive = c.id === activeChatId;
            return (
              <button
                key={c.id}
                type="button"
                onClick={() => onSelectChat(c.id)}
                className={`px-3 py-1.5 text-xs font-medium rounded-t-lg transition-all border-t border-x shrink-0 flex items-center gap-1.5 ${
                  isActive
                    ? "bg-white text-blue-700 border-slate-200 font-semibold shadow-2xs"
                    : "bg-slate-100 text-slate-600 border-transparent hover:bg-slate-200/70"
                }`}
              >
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                <span className="truncate max-w-[130px]">{c.cliente?.nome || c.id.slice(0, 8)}</span>
              </button>
            );
          })
        )}
      </div>

      {/* Conteúdo Principal do Chat */}
      {!activeChatId || !detalhes ? (
        <div className="flex-1 flex flex-col items-center justify-center p-6 text-center text-slate-400">
          <span className="text-3xl mb-2">💬</span>
          <p className="text-sm font-medium text-slate-700">Central de Conversas em Andamento</p>
          <p className="text-xs text-slate-500 max-w-sm mt-1">
            Selecione uma aba acima ou assuma uma conversa da fila de espera para interagir diretamente com o cliente.
          </p>
        </div>
      ) : (
        <div className="flex-1 flex flex-col min-h-0">
          {/* Header do Chat Ativo */}
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-100 bg-slate-50/50">
            <div>
              <div className="text-xs font-semibold text-slate-900">
                {detalhes.cliente?.nome || "Cliente Visitante"}
              </div>
              <div className="text-[11px] text-slate-500 font-mono">
                Conversa ID: {detalhes.id}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  if (
                    typeof window !== "undefined" &&
                    window.confirm("Deseja devolver esta conversa para o assistente de IA?")
                  ) {
                    void onDevolverIA();
                  }
                }}
                disabled={closing}
                title="Devolver controle para o bot de IA responder"
                className="px-2.5 py-1 text-xs font-medium rounded-md border border-purple-200 bg-purple-50 text-purple-700 hover:bg-purple-100 transition-colors disabled:opacity-50"
              >
                🤖 Devolver para IA
              </button>

              <button
                type="button"
                onClick={() => {
                  if (
                    typeof window !== "undefined" &&
                    window.confirm("Deseja encerrar o atendimento desta conversa?")
                  ) {
                    void onFinalizar("atendimento_concluido");
                  }
                }}
                disabled={closing}
                title="Finalizar e fechar a sessão de atendimento"
                className="px-2.5 py-1 text-xs font-medium rounded-md border border-slate-200 bg-white text-slate-700 hover:bg-slate-100 transition-colors disabled:opacity-50"
              >
                🏁 Encerrar Chat
              </button>
            </div>
          </div>

          {/* Histórico de Mensagens */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-50/30">
            {detalhes.mensagens.map((m) => {
              const isCliente = m.papel === "cliente" || m.papel === "user";
              const isIA = m.papel === "assistant";
              const isOperador = m.papel === "atendente";

              return (
                <div
                  key={m.id}
                  className={`flex flex-col ${
                    isOperador ? "items-end" : "items-start"
                  }`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-xs shadow-2xs ${
                      isCliente
                        ? "bg-slate-200 text-slate-900 rounded-tl-xs"
                        : isIA
                          ? "bg-purple-50 border border-purple-200 text-purple-950 rounded-tl-xs"
                          : "bg-emerald-600 text-white rounded-tr-xs"
                    }`}
                  >
                    <div className="mb-1 flex items-center gap-1.5 flex-wrap font-bold text-[10px]">
                      {isCliente && <span className="text-slate-600">👤 Cliente</span>}
                      {isIA && <span className="text-purple-700">🤖 IA Assistente</span>}
                      {isOperador && (
                        <span className="text-emerald-100">
                          🧑‍💼 Atendente ({m.atendente_nome || "Você"})
                        </span>
                      )}
                    </div>
                    <p className="leading-relaxed whitespace-pre-wrap">{m.texto}</p>
                  </div>
                </div>
              );
            })}
            <div ref={messagesEndRef} />
          </div>

          {/* Campo de Envio de Mensagem */}
          <form
            onSubmit={handleSubmit}
            className="p-3 border-t border-slate-200 bg-white flex items-center gap-2"
          >
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={sendingMessage}
              placeholder="Digite sua resposta para o cliente..."
              className="flex-1 px-3.5 py-2 rounded-lg border border-slate-300 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={!inputText.trim() || sendingMessage}
              className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-xs transition-colors disabled:opacity-50 cursor-pointer"
            >
              {sendingMessage ? "Enviando..." : "Enviar"}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
