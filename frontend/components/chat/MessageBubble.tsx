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

type Metrics = NonNullable<ChatUIMessage["metrics"]>;

// Largura real (borda a borda) da caixa de resposta — o painel de métricas
// abaixo dela usa esse valor para ter exatamente a mesma largura, em vez de
// um max-width fixo independente do tamanho da bolha.
function useElementWidth() {
  const ref = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState<number | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => setWidth(el.getBoundingClientRect().width));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return { ref, width };
}

function isVendasVisionByCost(message: ChatUIMessage, metrics: Metrics | undefined): boolean {
  return (
    message.domain === "vendas" &&
    metrics?.costPromptUsd !== undefined &&
    metrics.costPromptUsd > 0 &&
    Boolean(metrics?.modelName?.toLowerCase().includes("gemma"))
  );
}

function detectVision(message: ChatUIMessage, metrics: Metrics | undefined): boolean {
  return (
    Boolean(metrics?.visionUsed) ||
    message.backendUsed === "identificacao_imagem" ||
    isVendasVisionByCost(message, metrics)
  );
}

// Cálculo dinâmico de TPS caso o backend não tenha enviado explicitamente
function calculateTps(metrics: Metrics | undefined): number | null {
  if (metrics?.tps != null) return metrics.tps;
  if (!metrics?.completionTokens || !metrics?.latencyMs) return null;
  const seconds = Math.max((metrics.latencyMs - (metrics.ttftMs || 0)) / 1000, 0.001);
  return Math.round((metrics.completionTokens / seconds) * 10) / 10;
}

function bubbleClassName(isUser: boolean, isAtendente: boolean, isExternalLlm: boolean): string {
  const base = "max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm shadow-xs";
  if (isUser)
    return `${base} bg-gradient-to-br from-blue-600 to-indigo-600 text-white rounded-tr-xs`;
  if (isAtendente)
    return `${base} bg-emerald-50 text-emerald-950 border border-emerald-300 rounded-tl-xs`;
  if (isExternalLlm) return `${base} bg-red-50 text-red-950 border border-red-200/80 rounded-tl-xs`;
  return `${base} bg-slate-100 text-slate-900 border border-slate-200/60 rounded-tl-xs`;
}

function AtendenteHeader({ nome }: { nome?: string | null }) {
  return (
    <div className="mb-1 flex items-center gap-1.5 flex-wrap">
      <span
        data-testid="message-atendente-badge"
        className="inline-flex items-center gap-1 rounded bg-emerald-100 border border-emerald-300 px-1.5 py-0.5 text-[10px] font-bold text-emerald-800"
      >
        👤 Atendente Humano {nome ? `(${nome})` : ""}
      </span>
    </div>
  );
}

function VisionBadge() {
  return (
    <span
      data-testid="message-vision-badge"
      className="inline-flex items-center gap-1 rounded bg-purple-100/90 border border-purple-200/80 px-1.5 py-0.5 text-[9px] font-bold text-purple-800 shadow-2xs"
      title="Produto identificado via Visão Computacional (Multimodal)"
    >
      👁️ Visão Computacional
    </span>
  );
}

interface DomainHeaderProps {
  domainLabel: string;
  isExternalLlm: boolean;
  isVision: boolean;
  showDetails: boolean;
  onToggleDetails: () => void;
}

function DomainHeader({
  domainLabel,
  isExternalLlm,
  isVision,
  showDetails,
  onToggleDetails,
}: DomainHeaderProps) {
  return (
    <div className="mb-1 flex items-center gap-1.5 flex-wrap">
      <span
        data-testid="message-domain-label"
        className={`text-[10px] font-bold uppercase tracking-wider ${
          isExternalLlm ? "text-red-700" : "text-blue-600"
        }`}
      >
        {domainLabel}
      </span>
      {isVision && <VisionBadge />}
      <button
        type="button"
        onClick={onToggleDetails}
        aria-label={showDetails ? "Ocultar métricas da resposta" : "Mostrar métricas da resposta"}
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
  );
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const [showDetails, setShowDetails] = useState(false);
  const { ref: bubbleRef, width: bubbleWidth } = useElementWidth();

  const isUser = message.role === "user";
  const isAtendente = message.role === "atendente";
  const isBot = !isUser && !isAtendente;
  const isExternalLlm = isBot && message.backendUsed === "externo";
  const domainLabel = message.domain ? (DOMAIN_LABELS[message.domain] ?? message.domain) : null;
  const isVision = isBot && detectVision(message, message.metrics);
  const calculatedTps = calculateTps(message.metrics);

  return (
    <div className={`flex flex-col ${isUser ? "items-end" : "items-start"} space-y-1.5 w-full`}>
      <div
        ref={bubbleRef}
        data-testid="message-bubble"
        className={bubbleClassName(isUser, isAtendente, isExternalLlm)}
      >
        {isAtendente && <AtendenteHeader nome={message.atendenteNome} />}
        {isBot && domainLabel && (
          <DomainHeader
            domainLabel={domainLabel}
            isExternalLlm={isExternalLlm}
            isVision={isVision}
            showDetails={showDetails}
            onToggleDetails={() => setShowDetails((prev) => !prev)}
          />
        )}
        <p className="leading-relaxed whitespace-pre-wrap">{message.text}</p>
      </div>

      {isBot && message.card && <ChatCard card={message.card} />}

      {isBot && showDetails && (
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
