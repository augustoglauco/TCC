/**
 * Tipos do contrato de `GET`/`PUT /api/admin/runtime-settings` (ver
 * `backend/src/app/models/runtime_settings.py`) — parâmetros de execução
 * ajustáveis em runtime (parâmetros de amostragem do Ollama, timeouts,
 * fallback de domínio do RAG, teto default do crawler). Aplicados na hora e
 * gravados no banco; todos sempre têm valor (sem "vazio = padrão").
 */

export interface RuntimeSettings {
  local_llm_temperature: number;
  local_llm_num_ctx: number;
  local_llm_top_p: number;
  local_llm_top_k: number;
  local_llm_repeat_penalty: number;
  local_llm_seed: number;
  local_llm_timeout_s: number;
  external_llm_timeout_s: number;
  rag_top_k?: number;
  rag_score_threshold?: number;
  rag_search_domain_fallback: boolean;
  crawler_max_pages_default: number;
  external_model_name?: string;
  external_vision_model_name?: string;
  image_internal_confidence?: number;
  image_external_confidence?: number;
  intent_router_provider?: "heuristica" | "heuristica_llm" | "jev_openrouter";
  tone_monitor_enabled?: boolean;
  tone_monitor_provider?: "heuristica_llm" | "jev_openrouter";
  estoque_agent_mode?: "desativado" | "deterministico" | "ia";
  estoque_agent_llm?: "local" | "externo";
  local_llm_keep_alive?: string;
  local_llm_warmup_on_startup?: boolean;
  local_model_loaded?: boolean;
  local_model_vram_bytes?: number | null;
}

/** Corpo de `PUT /api/admin/runtime-settings` — atualização parcial, só os
 * campos presentes são alterados; `null` não é aceito (HTTP 422). */
export type RuntimeSettingsUpdate = Partial<RuntimeSettings>;
