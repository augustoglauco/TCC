"use client";

import type { ChatBackendUsed, ChatPerfilUsuario, ChatUIMessage } from "@/lib/types/chat";

const BACKEND_LABELS: Record<ChatBackendUsed, string> = {
  local: "Local (Ollama)",
  externo: "Cloud (OpenRouter)",
  resposta_fixa: "Resposta fixa (sem LLM)",
  identificacao_imagem: "Identificação por imagem",
};

const PERFIL_LABELS: Record<ChatPerfilUsuario, string> = {
  cliente: "Cliente",
  esporadico: "Cliente esporádico",
  lead: "Lead",
  nao_classificado: "Não classificado",
};

const REASON_LABELS: Record<string, string> = {
  nenhum: "Execução Direta (Sem Escalonamento)",
  fora_escopo: "Fora do Escopo Conhecido",
  rag_vazio: "Base RAG Sem Documentos Relevantes",
  complexidade_alta: "Alta Complexidade Detectada",
};

type Metrics = NonNullable<ChatUIMessage["metrics"]>;

function SecaoRoteador({
  metrics,
  domainLabel,
  message,
}: {
  metrics: Metrics | undefined;
  domainLabel: string | null;
  message: ChatUIMessage;
}) {
  return (
    <div className="rounded-lg bg-slate-800/60 p-2 space-y-1">
      <div className="font-sans font-semibold text-blue-400 text-[10px] uppercase tracking-wider">
        🤖 Roteador &amp; Modelo
      </div>
      <div>
        <span className="text-slate-400">Backend:</span>{" "}
        {BACKEND_LABELS[message.backendUsed ?? "local"]}
      </div>
      {metrics?.routerProvider && (
        <div>
          <span className="text-slate-400">Provedor:</span>{" "}
          {metrics.routerProvider === "jev_openrouter"
            ? "TypeSafe Jev (OpenRouter)"
            : metrics.routerProvider === "heuristica"
              ? "Heurística (Palavras-chave)"
              : "Heurística + LLM Local"}
        </div>
      )}
      <div>
        <span className="text-slate-400">Modelo:</span> {metrics?.modelName || "-"}
      </div>
      <div>
        <span className="text-slate-400">Domínio:</span> {domainLabel || "-"}
      </div>
      {metrics?.perfilUsuario && (
        <div>
          <span className="text-slate-400">Perfil:</span> {PERFIL_LABELS[metrics.perfilUsuario]}
          {metrics.perfilMotivo && (
            <span className="text-[10px] text-slate-400"> ({metrics.perfilMotivo})</span>
          )}
        </div>
      )}
      <div>
        <span className="text-slate-400">Complexidade:</span> {metrics?.complexity || "baixa"}
      </div>
      {metrics?.confidence !== undefined && metrics.confidence !== null && (
        <div>
          <span className="text-slate-400">Confiança Rota:</span>{" "}
          {(metrics.confidence * 100).toFixed(1)}%
        </div>
      )}
      {metrics?.escalationReason && (
        <div
          className="text-[10px] text-slate-400 truncate"
          title={REASON_LABELS[metrics.escalationReason] ?? metrics.escalationReason}
        >
          Motivo: {metrics.escalationReason}
        </div>
      )}
    </div>
  );
}

function SecaoDesempenho({
  metrics,
  calculatedTps,
}: {
  metrics: Metrics | undefined;
  calculatedTps: number | null;
}) {
  return (
    <div className="rounded-lg bg-slate-800/60 p-2 space-y-1">
      <div className="font-sans font-semibold text-amber-400 text-[10px] uppercase tracking-wider">
        ⏱️ Desempenho
      </div>
      <div>
        <span className="text-slate-400">Latência Total:</span>{" "}
        {metrics?.latencyMs ? `${Math.round(metrics.latencyMs)} ms` : "-"}
      </div>
      <div>
        <span className="text-slate-400">1º Token (TTFT):</span>{" "}
        {metrics?.ttftMs ? `${Math.round(metrics.ttftMs)} ms` : "-"}
      </div>
      <div>
        <span className="text-slate-400">Tempo Geração:</span>{" "}
        {metrics?.latencyMs && metrics?.ttftMs
          ? `${Math.max(Math.round(metrics.latencyMs - metrics.ttftMs), 0)} ms`
          : "-"}
      </div>
      <div>
        <span className="text-slate-400">Velocidade (TPS):</span>{" "}
        {calculatedTps !== null ? `${calculatedTps} tokens/s` : "-"}
      </div>
    </div>
  );
}

function SecaoTokens({ metrics }: { metrics: Metrics | undefined }) {
  return (
    <div className="rounded-lg bg-slate-800/60 p-2 space-y-1">
      <div className="font-sans font-semibold text-emerald-400 text-[10px] uppercase tracking-wider">
        🔤 Tokens &amp; Custo
      </div>
      <div>
        <span className="text-slate-400">Prompt (IN):</span> {metrics?.promptTokens ?? 0} tokens
      </div>
      <div>
        <span className="text-slate-400">Resposta (OUT):</span> {metrics?.completionTokens ?? 0}{" "}
        tokens
      </div>
      <div>
        <span className="text-slate-400">Total Tokens:</span>{" "}
        {(metrics?.promptTokens ?? 0) + (metrics?.completionTokens ?? 0)} tokens
      </div>
      <div>
        <span className="text-slate-400">Custo Estimado:</span>{" "}
        {metrics?.estimatedCostUsd !== undefined && metrics.estimatedCostUsd !== null
          ? `$${metrics.estimatedCostUsd.toFixed(6)}`
          : "$0.000000 (Local)"}
      </div>
      {metrics?.costPromptUsd !== undefined && metrics.costPromptUsd !== null && (
        <div>
          <span className="text-slate-400">Custo Entrada (IN):</span> $
          {metrics.costPromptUsd.toFixed(6)}
        </div>
      )}
      {metrics?.costCompletionUsd !== undefined && metrics.costCompletionUsd !== null && (
        <div>
          <span className="text-slate-400">Custo Saída (OUT):</span> $
          {metrics.costCompletionUsd.toFixed(6)}
        </div>
      )}
    </div>
  );
}

function SecaoRag({ metrics }: { metrics: Metrics | undefined }) {
  return (
    <div className="rounded-lg bg-slate-800/60 p-2 space-y-1">
      <div className="font-sans font-semibold text-cyan-400 text-[10px] uppercase tracking-wider">
        📚 RAG &amp; Recuperação
      </div>
      <div>
        <span className="text-slate-400">Tempo Busca RAG:</span>{" "}
        {metrics?.ragRetrievalMs !== undefined && metrics.ragRetrievalMs !== null
          ? `${metrics.ragRetrievalMs} ms`
          : "N/A"}
      </div>
      <div>
        <span className="text-slate-400">Chunks Usados:</span> {metrics?.ragChunksCount ?? 0}{" "}
        trechos
      </div>
      <div>
        <span className="text-slate-400">Score Médio:</span>{" "}
        {metrics?.ragAvgScore !== undefined && metrics.ragAvgScore !== null
          ? metrics.ragAvgScore.toFixed(4)
          : "N/A"}
      </div>
      {metrics?.ragChunks && metrics.ragChunks.length > 0 && (
        <div className="pt-1 space-y-0.5">
          <div className="text-slate-400">Fontes:</div>
          {metrics.ragChunks.map((chunk, idx) => (
            <div key={`${chunk.source}-${idx}`} className="truncate pl-2" title={chunk.source}>
              {chunk.source} <span className="text-slate-500">({chunk.score.toFixed(4)})</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

interface MessageTelemetryPanelProps {
  message: ChatUIMessage;
  domainLabel: string | null;
  isExternalLlm: boolean;
  calculatedTps: number | null;
  bubbleWidth: number | null;
}

export function MessageTelemetryPanel({
  message,
  domainLabel,
  isExternalLlm,
  calculatedTps,
  bubbleWidth,
}: MessageTelemetryPanelProps) {
  const metrics = message.metrics;

  return (
    <div
      className="flex flex-col max-w-full items-start space-y-1"
      style={bubbleWidth ? { width: bubbleWidth, minWidth: "16rem" } : undefined}
    >
      {/* Barra de métricas dinâmicas */}
      <div
        data-testid="message-metrics"
        className="flex w-full flex-wrap items-center gap-x-2.5 gap-y-1 rounded-xl border border-slate-800 bg-slate-900/90 px-3 py-1.5 font-mono text-[11px] text-slate-300 shadow-md backdrop-blur-xs"
      >
        <span className="flex items-center gap-1 font-semibold text-slate-100">
          🤖{" "}
          <span className="text-blue-400">
            {metrics?.modelName || (isExternalLlm ? "OpenRouter" : "Ollama (local)")}
          </span>
        </span>

        <span className="text-slate-700">|</span>

        <span className="flex items-center gap-1">
          🔤 <span className="text-emerald-400">IN:</span> {metrics?.promptTokens ?? "-"}{" "}
          <span className="text-emerald-400">OUT:</span> {metrics?.completionTokens ?? "-"}
        </span>

        <span className="text-slate-700">|</span>

        <span className="flex items-center gap-1">
          ⏱️ <span className="text-amber-400">Latência:</span>{" "}
          {metrics?.latencyMs ? `${(metrics.latencyMs / 1000).toFixed(2)}s` : "-"}
        </span>

        <span className="text-slate-700">|</span>

        <span className="flex items-center gap-1">
          ⚡ <span className="text-cyan-400">1º Token:</span>{" "}
          {metrics?.ttftMs ? `${Math.round(metrics.ttftMs)}ms` : "-"}
        </span>

        {calculatedTps !== null && (
          <>
            <span className="text-slate-700">|</span>
            <span className="flex items-center gap-1">
              🚀 <span className="text-purple-400">TPS:</span> {calculatedTps} tok/s
            </span>
          </>
        )}
      </div>

      {/* Painel de telemetria expandido */}
      <div className="w-full rounded-xl border border-slate-700/60 bg-slate-900/95 p-3 text-xs text-slate-200 shadow-xl space-y-2.5 font-mono animate-in fade-in slide-in-from-top-1 duration-200">
        <div className="flex items-center justify-between border-b border-slate-800 pb-1.5">
          <span className="font-semibold text-slate-100 flex items-center gap-1.5">
            🔍 Telemetria &amp; Diagnóstico LLM
          </span>
          <span className="text-[10px] text-slate-400">TCC Performance Analytics</span>
        </div>

        <div className="grid grid-cols-2 gap-2 text-[11px]">
          <SecaoRoteador metrics={metrics} domainLabel={domainLabel} message={message} />
          <SecaoDesempenho metrics={metrics} calculatedTps={calculatedTps} />
          <SecaoTokens metrics={metrics} />
          <SecaoRag metrics={metrics} />
        </div>
      </div>
    </div>
  );
}
