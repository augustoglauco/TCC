import { useCallback, useEffect, useRef, useState } from "react";

import {
  ModelCatalogApiError,
  getModelCharacteristics,
  refreshModelCharacteristics,
} from "@/lib/api/modelCatalog";
import type { ModelCharacteristics, ModelSource } from "@/lib/types/modelCatalog";

// Cache em memória da aba (sobrevive entre cards diferentes que pedem a
// mesma tag, não entre reloads) — ver
// docs/superpowers/specs/2026-10-03-caracteristicas-modelo-hover-design.md §4.3.
const _cache = new Map<string, ModelCharacteristics | null>();

function chaveCache(source: ModelSource, tag: string): string {
  return `${source}:${tag}`;
}

export interface UseModelCharacteristicsResult {
  /** `null` com `loading=false` e `error=null` significa "fonte não tem
   * característica pra essa tag" (404), não um erro. */
  data: ModelCharacteristics | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useModelCharacteristics(
  source: ModelSource,
  tag: string,
): UseModelCharacteristicsResult {
  const chave = chaveCache(source, tag);
  const [data, setData] = useState<ModelCharacteristics | null>(() => _cache.get(chave) ?? null);
  const [loading, setLoading] = useState(!_cache.has(chave));
  const [error, setError] = useState<string | null>(null);
  const montadoRef = useRef(true);

  useEffect(() => {
    montadoRef.current = true;
    return () => {
      montadoRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (_cache.has(chave)) {
      setData(_cache.get(chave) ?? null);
      setLoading(false);
      return;
    }

    let cancelado = false;
    setLoading(true);
    setError(null);

    getModelCharacteristics(source, tag)
      .then((resultado) => {
        if (cancelado) return;
        _cache.set(chave, resultado);
        setData(resultado);
      })
      .catch((err) => {
        if (cancelado) return;
        setError(
          err instanceof ModelCatalogApiError ? err.message : "Erro ao buscar características.",
        );
      })
      .finally(() => {
        if (!cancelado) setLoading(false);
      });

    return () => {
      cancelado = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chave]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resultado = await refreshModelCharacteristics(source, tag);
      if (!montadoRef.current) return;
      _cache.set(chave, resultado);
      setData(resultado);
    } catch (err) {
      if (!montadoRef.current) return;
      setError(
        err instanceof ModelCatalogApiError ? err.message : "Erro ao atualizar características.",
      );
    } finally {
      if (montadoRef.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chave]);

  return { data, loading, error, refresh };
}
