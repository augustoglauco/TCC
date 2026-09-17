/**
 * Tipos do contrato de `GET`/`PUT /api/admin/runtime-settings` (ver
 * `backend/src/app/models/runtime_settings.py`) — parâmetros de execução
 * ajustáveis em runtime (temperatura do Ollama, timeouts, fallback de
 * domínio do RAG), só em memória, resetam a cada restart do backend.
 */

export interface RuntimeSettings {
  local_llm_temperature: number | null;
  local_llm_timeout_s: number;
  external_llm_timeout_s: number;
  rag_search_domain_fallback: boolean;
}

/** Corpo de `PUT /api/admin/runtime-settings` — atualização parcial, só os
 * campos presentes são alterados (`local_llm_temperature: null` reseta
 * explicitamente para o default do próprio modelo). */
export type RuntimeSettingsUpdate = Partial<RuntimeSettings>;
