import type { ChatUIMessage } from "@/lib/types/chat";

export function exportMetricsToJson(messages: ChatUIMessage[]) {
  const data = messages
    .filter((m) => m.role === "assistant")
    .map((m, idx) => ({
      message_index: idx + 1,
      id: m.id,
      text_length: m.text.length,
      domain: m.domain ?? null,
      backend_used: m.backendUsed ?? null,
      model_name: m.metrics?.modelName ?? null,
      prompt_tokens: m.metrics?.promptTokens ?? null,
      completion_tokens: m.metrics?.completionTokens ?? null,
      total_tokens: (m.metrics?.promptTokens ?? 0) + (m.metrics?.completionTokens ?? 0),
      latency_ms: m.metrics?.latencyMs ?? null,
      ttft_ms: m.metrics?.ttftMs ?? null,
      tps: m.metrics?.tps ?? null,
      confidence: m.metrics?.confidence ?? null,
      complexity: m.metrics?.complexity ?? null,
      estimated_cost_usd: m.metrics?.estimatedCostUsd ?? null,
      rag_retrieval_ms: m.metrics?.ragRetrievalMs ?? null,
      rag_chunks_count: m.metrics?.ragChunksCount ?? null,
      rag_avg_score: m.metrics?.ragAvgScore ?? null,
      rag_chunks: m.metrics?.ragChunks ?? null,
      escalation_reason: m.metrics?.escalationReason ?? null,
    }));

  const jsonString = JSON.stringify(data, null, 2);
  const blob = new Blob([jsonString], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `telemetria_llm_${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

export function exportMetricsToCsv(messages: ChatUIMessage[]) {
  const assistantMessages = messages.filter((m) => m.role === "assistant");
  if (assistantMessages.length === 0) return;

  const headers = [
    "Index",
    "ID",
    "Domain",
    "Backend",
    "Model",
    "Prompt_Tokens",
    "Completion_Tokens",
    "Total_Tokens",
    "Latency_ms",
    "TTFT_ms",
    "TPS",
    "Confidence",
    "Complexity",
    "Cost_USD",
    "RAG_Latency_ms",
    "RAG_Chunks",
    "RAG_Avg_Score",
    "RAG_Sources",
    "Escalation_Reason",
  ];

  const rows = assistantMessages.map((m, idx) => [
    idx + 1,
    m.id,
    m.domain ?? "",
    m.backendUsed ?? "",
    m.metrics?.modelName ?? "",
    m.metrics?.promptTokens ?? "",
    m.metrics?.completionTokens ?? "",
    (m.metrics?.promptTokens ?? 0) + (m.metrics?.completionTokens ?? 0),
    m.metrics?.latencyMs ?? "",
    m.metrics?.ttftMs ?? "",
    m.metrics?.tps ?? "",
    m.metrics?.confidence ?? "",
    m.metrics?.complexity ?? "",
    m.metrics?.estimatedCostUsd ?? "",
    m.metrics?.ragRetrievalMs ?? "",
    m.metrics?.ragChunksCount ?? "",
    m.metrics?.ragAvgScore ?? "",
    m.metrics?.ragChunks
      ? `"${m.metrics.ragChunks.map((c) => `${c.source}(${c.score.toFixed(4)})`).join(" | ")}"`
      : "",
    m.metrics?.escalationReason ?? "",
  ]);

  const csvContent =
    "data:text/csv;charset=utf-8," +
    [headers.join(","), ...rows.map((e) => e.join(","))].join("\n");

  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", `telemetria_llm_${new Date().toISOString().slice(0, 10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
