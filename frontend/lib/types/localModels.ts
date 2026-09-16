/**
 * Tipos do contrato dos endpoints do gerenciador de modelos locais (ver
 * `backend/src/app/models/local_models.py` e
 * docs/superpowers/specs/2026-09-16-local-model-manager-design.md).
 */

export interface LocalModel {
  name: string;
  size_bytes: number;
  modified_at: string;
  is_active: boolean;
}

/** Resposta de `GET /api/admin/local-models`. */
export interface LocalModelsListResponse {
  models: LocalModel[];
  active_model: string;
}

export type PullStatus = "pulling" | "done" | "error";

/** Resposta de `GET /api/admin/local-models/pull-status?name=...`. */
export interface PullStatusResponse {
  status: PullStatus;
  percent: number | null;
  detail: string | null;
}
