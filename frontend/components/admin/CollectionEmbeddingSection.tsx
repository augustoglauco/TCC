"use client";

import { Tooltip } from "@/components/ui/Tooltip";

const CURATED_MODELS = [
  { value: "paraphrase-multilingual-MiniLM-L12-v2", label: "MiniLM multilíngue (384 dim)" },
  { value: "paraphrase-multilingual-mpnet-base-v2", label: "MPNet multilíngue (768 dim)" },
  { value: "intfloat/multilingual-e5-base", label: "E5 base multilíngue (768 dim)" },
  { value: "intfloat/multilingual-e5-large", label: "E5 large multilíngue (1024 dim)" },
  { value: "BAAI/bge-m3", label: "BGE-M3 multilíngue (1024 dim)" },
  { value: "google/embeddinggemma-300m", label: "EmbeddingGemma 300M (768 dim)" },
  { value: "__custom__", label: "Outro (digitar nome)" },
] as const;

export { CURATED_MODELS };

interface CollectionEmbeddingSectionProps {
  modelSelecionado: string;
  modeloCustom: string;
  onModelSelecionado: (v: string) => void;
  onModeloCustom: (v: string) => void;
}

export function CollectionEmbeddingSection({
  modelSelecionado,
  modeloCustom,
  onModelSelecionado,
  onModeloCustom,
}: CollectionEmbeddingSectionProps) {
  return (
    <fieldset className="space-y-2">
      <legend className="flex items-center text-sm font-medium text-gray-900">
        Modelo de embedding
        <Tooltip content="Modelo de IA responsável por gerar os vetores densos a partir dos textos dos documentos." />
      </legend>
      <select
        aria-label="Modelo de embedding"
        value={modelSelecionado}
        onChange={(e) => onModelSelecionado(e.target.value)}
        className="block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
      >
        {CURATED_MODELS.map((modelo) => (
          <option key={modelo.value} value={modelo.value}>
            {modelo.label}
          </option>
        ))}
      </select>
      {modelSelecionado === "__custom__" && (
        <input
          aria-label="Nome do modelo"
          value={modeloCustom}
          onChange={(e) => onModeloCustom(e.target.value)}
          placeholder="ex.: intfloat/multilingual-e5-small"
          required
          className="block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
        />
      )}
    </fieldset>
  );
}
