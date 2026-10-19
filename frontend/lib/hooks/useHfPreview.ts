"use client";

import { useEffect, useState } from "react";

import { getModelCharacteristics, refreshModelCharacteristics } from "@/lib/api/modelCatalog";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import type { ModelCharacteristics } from "@/lib/types/modelCatalog";

export function ehTagHuggingFace(nome: string): boolean {
  return /^hf\.co\//i.test(nome.trim());
}

// Preview ao vivo das características de uma tag `hf.co/...` ainda não
// baixada — debounce de 500ms após o usuário parar de digitar, pra não
// disparar uma requisição a cada tecla.
export function useHfPreview(nome: string) {
  const token = useAuthStore((s) => s.token);
  const [previewHf, setPreviewHf] = useState<ModelCharacteristics | null>(null);
  const [previewHfLoading, setPreviewHfLoading] = useState(false);
  const [previewHfError, setPreviewHfError] = useState<string | null>(null);

  useEffect(() => {
    if (!ehTagHuggingFace(nome)) {
      // Limpa o preview ao sair de uma tag hf.co/... (sincronização com `nome`)
      // — padrão aceito no projeto para `react-hooks/set-state-in-effect`.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setPreviewHf(null);
      setPreviewHfError(null);
      // Uma busca de preview pode estar em voo quando o usuário edita a tag
      // para algo que não bate mais com `hf.co/...` — sem isso, o loading
      // ficava preso em `true` incoerentemente (achado #5 da revisão final).
      setPreviewHfLoading(false);
      return;
    }
    if (!token) return;

    const tagAtual = nome.trim();
    setPreviewHfLoading(true);
    const timeoutId = setTimeout(() => {
      getModelCharacteristics(token, "huggingface", tagAtual)
        .then((resultado) => {
          setPreviewHf(resultado);
          setPreviewHfError(null);
        })
        .catch(() => {
          setPreviewHfError("Não foi possível obter características deste repositório.");
        })
        .finally(() => setPreviewHfLoading(false));
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [nome, token]);

  const refreshPreview = () => {
    if (!token) return;
    // refresh manual do preview antes de baixar — reaproveita o mesmo
    // endpoint usado pelo painel pós-download (ver ModelCharacteristicsPanel)
    setPreviewHfLoading(true);
    setPreviewHfError(null);
    refreshModelCharacteristics(token, "huggingface", nome.trim())
      .then((resultado) => setPreviewHf(resultado))
      .catch(() => {
        setPreviewHfError("Erro ao atualizar características.");
      })
      .finally(() => setPreviewHfLoading(false));
  };

  return { previewHf, previewHfLoading, previewHfError, refreshPreview };
}
