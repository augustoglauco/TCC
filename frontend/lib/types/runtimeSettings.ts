/**
 * Tipos do contrato de `GET`/`PUT /api/admin/runtime-settings` (ver
 * `backend/src/app/models/runtime_settings.py`) — parâmetros de execução
 * ajustáveis em runtime (temperatura do Ollama, timeouts, fallback de
 * domínio do RAG, teto default/limiar de confiança do crawler), só em
 * memória, resetam a cada restart do backend.
 */

export interface RuntimeSettings {
  local_llm_temperature: number | null;
  local_llm_timeout_s: number;
  external_llm_timeout_s: number;
  rag_search_domain_fallback: boolean;
  crawler_max_pages_default: number;
  crawler_confidence_threshold: number;
  intent_router_provider?: "heuristica_llm" | "jev_openrouter";
  tone_monitor_enabled?: boolean;
  tone_monitor_provider?: "heuristica_llm" | "jev_openrouter";
}

/** Corpo de `PUT /api/admin/runtime-settings` — atualização parcial, só os
 * campos presentes são alterados (`local_llm_temperature: null` reseta
 * explicitamente para o default do próprio modelo). */
export type RuntimeSettingsUpdate = Partial<RuntimeSettings>;
