"use client";

import { Tooltip } from "@/components/ui/Tooltip";

interface CollectionChunkingSectionProps {
  chunkSize: number;
  chunkOverlap: number;
  onChunkSize: (v: number) => void;
  onChunkOverlap: (v: number) => void;
}

export function CollectionChunkingSection({
  chunkSize,
  chunkOverlap,
  onChunkSize,
  onChunkOverlap,
}: CollectionChunkingSectionProps) {
  const invalido = chunkSize <= chunkOverlap;
  return (
    <fieldset className="grid grid-cols-2 gap-4">
      <legend className="col-span-2 flex items-center text-sm font-medium text-gray-900">
        Chunking
        <Tooltip content="Configuração de divisão e fatiamento de documentos longos em blocos menores (chunks) para vetorização." />
      </legend>
      <div>
        <div className="flex items-center">
          <label htmlFor="chunk-size" className="text-sm text-gray-700">
            Chunk size
          </label>
          <Tooltip content="Tamanho máximo (em caracteres/tokens) de cada bloco de texto extraído do documento." />
        </div>
        <input
          id="chunk-size"
          type="number"
          value={chunkSize}
          onChange={(e) => onChunkSize(Number(e.target.value))}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
        />
      </div>
      <div>
        <div className="flex items-center">
          <label htmlFor="chunk-overlap" className="text-sm text-gray-700">
            Overlap
          </label>
          <Tooltip content="Quantidade de caracteres/tokens compartilhados entre chunks consecutivos para preservar o contexto." />
        </div>
        <input
          id="chunk-overlap"
          type="number"
          value={chunkOverlap}
          onChange={(e) => onChunkOverlap(Number(e.target.value))}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
        />
      </div>
      {invalido && (
        <p className="col-span-2 text-sm text-red-600">Chunk size deve ser maior que o overlap.</p>
      )}
    </fieldset>
  );
}
