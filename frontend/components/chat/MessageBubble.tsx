"use client";

import { useEffect, useRef, useState } from "react";
import ChatCard from "@/components/chat/cards/ChatCard";
import { MessageTelemetryPanel } from "@/components/chat/MessageTelemetryPanel";
import type { ChatUIMessage } from "@/lib/types/chat";

// MVP: rótulo de domínio é só um mapa fixo de texto — sem i18n nem vindo do
// backend (ver docs/FRONTEND.md §3, "Indicador de domínio").
const DOMAIN_LABELS: Record<string, string> = {
  vendas: "Vendas",
  suporte: "Suporte Técnico",
  atendimento: "Atendimento ao Usuário",
  agendamento: "Agendamento",
  fora_escopo: "Fora de escopo",
};

interface MessageBubbleProps {
  message: ChatUIMessage;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const [showDetails, setShowDetails] = useState(false);
  const bubbleRef = useRef<HTMLDivElement | null>(null);
  // Largura real (borda a borda) da caixa de resposta — o painel de
  // métricas abaixo dela usa esse valor para ter exatamente a mesma
  // largura, em vez de um max-width fixo independente do tamanho da bolha.
  const [bubbleWidth, setBubbleWidth] = useState<number | null>(null);

  useEffect(() => {
    const el = bubbleRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => setBubbleWidth(el.getBoundingClientRect().width));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const isUser = message.role === "user";
  const isAtendente = message.role === "atendente";
  const isExternalLlm = !isUser && !isAtendente && message.backendUsed === "externo";
  const domainLabel = message.domain ? (DOMAIN_LABELS[message.domain] ?? message.domain) : null;
  const metrics = message.metrics;
  const isVision = Boolean(
    !isUser &&
    !isAtendente &&
    (metrics?.visionUsed ||
      message.backendUsed === "identificacao_imagem" ||
      (message.domain === "vendas" &&
        metrics?.costPromptUsd !== undefined &&
        metrics.costPromptUsd > 0 &&
        metrics?.modelName?.toLowerCase().includes("gemma"))),
  );

  // Cálculo dinâmico de TPS caso o backend não tenha enviado explicitamente
  const calculatedTps =
    metrics?.tps ??
    (metrics?.completionTokens && metrics?.latencyMs
      ? Math.round(
          (metrics.completionTokens /
            Math.max((metrics.latencyMs - (metrics.ttftMs || 0)) / 1000, 0.001)) *
            10,
        ) / 10
      : null);

  return (
    <div className={`flex flex-col ${isUser ? "items-end" : "items-start"} space-y-1.5 w-full`}>
      <div
        ref={bubbleRef}
        data-testid="message-bubble"
        className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm shadow-xs ${
          isUser
            ? "bg-gradient-to-br from-blue-600 to-indigo-600 text-white rounded-tr-xs"
            : isAtendente
              ? "bg-emerald-50 text-emerald-950 border border-emerald-300 rounded-tl-xs"
              : isExternalLlm
                ? "bg-red-50 text-red-950 border border-red-200/80 rounded-tl-xs"
                : "bg-slate-100 text-slate-900 border border-slate-200/60 rounded-tl-xs"
        }`}
      >
        {isAtendente ? (
          <div className="mb-1 flex items-center gap-1.5 flex-wrap">
            <span
              data-testid="message-atendente-badge"
              className="inline-flex items-center gap-1 rounded bg-emerald-100 border border-emerald-300 px-1.5 py-0.5 text-[10px] font-bold text-emerald-800"
            >
              👤 Atendente Humano {message.atendenteNome ? `(${message.atendenteNome})` : ""}
            </span>
          </div>
        ) : (
          !isUser &&
          domainLabel && (
            <div className="mb-1 flex items-center gap-1.5 flex-wrap">
              <span
                data-testid="message-domain-label"
                className={`text-[10px] font-bold uppercase tracking-wider ${
                  isExternalLlm ? "text-red-700" : "text-blue-600"
                }`}
              >
                {domainLabel}
              </span>
              {isVision && (
                <span
                  data-testid="message-vision-badge"
                  className="inline-flex items-center gap-1 rounded bg-purple-100/90 border border-purple-200/80 px-1.5 py-0.5 text-[9px] font-bold text-purple-800 shadow-2xs"
                  title="Produto identificado via Visão Computacional (Multimodal)"
                >
                  👁️ Visão Computacional
                </span>
              )}
              <button
                type="button"
                onClick={() => setShowDetails((prev) => !prev)}
                aria-label={
                  showDetails ? "Ocultar métricas da resposta" : "Mostrar métricas da resposta"
                }
                aria-pressed={showDetails}
                title={showDetails ? "Ocultar métricas" : "Mostrar métricas"}
                className={`text-[10px] leading-none cursor-pointer ${
                  isExternalLlm
                    ? "text-red-700/70 hover:text-red-700"
                    : "text-blue-600/70 hover:text-blue-600"
                }`}
              >
                ⚙️
              </button>
            </div>
          )
        )}
        <p className="leading-relaxed whitespace-pre-wrap">{message.text}</p>
      </div>

      {!isUser && !isAtendente && message.card && <ChatCard card={message.card} />}

      {!isUser && !isAtendente && showDetails && (
        <MessageTelemetryPanel
          message={message}
          domainLabel={domainLabel}
          isExternalLlm={isExternalLlm}
          calculatedTps={calculatedTps}
          bubbleWidth={bubbleWidth}
        />
      )}
    </div>
  );
}
