"use client";

import React from "react";
import { Tooltip } from "@/components/ui/Tooltip";

interface CollectionHnswSectionProps {
  m: number;
  efConstruct: number;
  fullScanThreshold: number;
  maxIndexingThreads: number;
  payloadM: string;
  onDisk: boolean;
  onM: (v: number) => void;
  onEfConstruct: (v: number) => void;
  onFullScanThreshold: (v: number) => void;
  onMaxIndexingThreads: (v: number) => void;
  onPayloadM: (v: string) => void;
  onOnDisk: (v: boolean) => void;
}

export function CollectionHnswSection({
  m,
  efConstruct,
  fullScanThreshold,
  maxIndexingThreads,
  payloadM,
  onDisk,
  onM,
  onEfConstruct,
  onFullScanThreshold,
  onMaxIndexingThreads,
  onPayloadM,
  onOnDisk,
}: CollectionHnswSectionProps) {
  return (
    <fieldset className="grid grid-cols-2 gap-4">
      <legend className="col-span-2 flex items-center text-sm font-medium text-gray-900">
        HNSW
        <Tooltip content="Grafo de busca aproximada de vizinhos mais próximos (Hierarchical Navigable Small World)." />
      </legend>

      <div>
        <div className="flex items-center">
          <label htmlFor="hnsw-m" className="text-sm text-gray-700">
            m
          </label>
          <Tooltip content="Número de conexões direcionadas por elemento no grafo HNSW. Maior valor melhora a precisão mas aumenta o uso de RAM." />
        </div>
        <input
          id="hnsw-m"
          type="number"
          value={m}
          onChange={(e) => onM(Number(e.target.value))}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
        />
      </div>

      <div>
        <div className="flex items-center">
          <label htmlFor="hnsw-ef-construct" className="text-sm text-gray-700">
            ef_construct
          </label>
          <Tooltip content="Tamanho da lista de candidatos durante a construção do índice HNSW. Valores maiores melhoram a qualidade do índice ao custo de maior tempo de criação." />
        </div>
        <input
          id="hnsw-ef-construct"
          type="number"
          value={efConstruct}
          onChange={(e) => onEfConstruct(Number(e.target.value))}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
        />
      </div>

      <div>
        <div className="flex items-center">
          <label htmlFor="hnsw-full-scan" className="text-sm text-gray-700">
            full_scan_threshold
          </label>
          <Tooltip content="Quantidade mínima de vetores na coleção para ativar o índice HNSW. Coleções menores usam busca exaustiva (brute-force)." />
        </div>
        <input
          id="hnsw-full-scan"
          type="number"
          value={fullScanThreshold}
          onChange={(e) => onFullScanThreshold(Number(e.target.value))}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
        />
      </div>

      <div>
        <div className="flex items-center">
          <label htmlFor="hnsw-threads" className="text-sm text-gray-700">
            max_indexing_threads
          </label>
          <Tooltip content="Número de threads em paralelo para construção do índice HNSW. 0 usa a quantidade automática do servidor." />
        </div>
        <input
          id="hnsw-threads"
          type="number"
          value={maxIndexingThreads}
          onChange={(e) => onMaxIndexingThreads(Number(e.target.value))}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
        />
      </div>

      <div>
        <div className="flex items-center">
          <label htmlFor="hnsw-payload-m" className="text-sm text-gray-700">
            payload_m (vazio = padrão)
          </label>
          <Tooltip content="Número de conexões adicionais no grafo dedicadas para navegação rápida em buscas com filtros de payload." />
        </div>
        <input
          id="hnsw-payload-m"
          type="number"
          value={payloadM}
          onChange={(e) => onPayloadM(e.target.value)}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
        />
      </div>

      <div className="flex items-center gap-2">
        <input
          id="hnsw-on-disk"
          type="checkbox"
          checked={onDisk}
          onChange={(e) => onOnDisk(e.target.checked)}
        />
        <label htmlFor="hnsw-on-disk" className="flex items-center text-sm text-gray-700">
          on_disk
        </label>
        <Tooltip content="Armazena os vetores e o índice HNSW no disco rígido para economizar memória RAM." />
      </div>
    </fieldset>
  );
}
