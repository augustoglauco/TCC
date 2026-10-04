/**
 * Tipos do contrato dos endpoints de características de modelo (ver
 * `backend/src/app/models/model_catalog.py` e
 * docs/superpowers/specs/2026-10-03-caracteristicas-modelo-hover-design.md).
 */

export type ModelSource = "openrouter" | "ollama" | "huggingface";

/** Resposta de `GET/POST .../model-catalog/characteristics`. */
export interface ModelCharacteristics {
  source: ModelSource;
  tag: string;
  is_multimodal: boolean;
  input_modalities: string[];
  output_modalities: string[];
  context_length: number | null;
  parameter_size: string | null;
  quantization: string | null;
  pricing_prompt_per_1k: number | null;
  pricing_completion_per_1k: number | null;
  knowledge_cutoff: string | null;
  fetched_at: string;
}
