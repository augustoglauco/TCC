"use client";

import { Tooltip } from "@/components/ui/Tooltip";
import type { QuantizationType } from "@/lib/types/rag";

interface CollectionQuantizationSectionProps {
  quantizationType: QuantizationType;
  scalarQuantile: number;
  scalarAlwaysRam: boolean;
  productCompression: "x4" | "x8" | "x16" | "x32" | "x64";
  productAlwaysRam: boolean;
  binaryAlwaysRam: boolean;
  onType: (v: QuantizationType) => void;
  onScalarQuantile: (v: number) => void;
  onScalarAlwaysRam: (v: boolean) => void;
  onProductCompression: (v: "x4" | "x8" | "x16" | "x32" | "x64") => void;
  onProductAlwaysRam: (v: boolean) => void;
  onBinaryAlwaysRam: (v: boolean) => void;
}

export function CollectionQuantizationSection({
  quantizationType,
  scalarQuantile,
  scalarAlwaysRam,
  productCompression,
  productAlwaysRam,
  binaryAlwaysRam,
  onType,
  onScalarQuantile,
  onScalarAlwaysRam,
  onProductCompression,
  onProductAlwaysRam,
  onBinaryAlwaysRam,
}: CollectionQuantizationSectionProps) {
  return (
    <fieldset className="space-y-2">
      <legend className="flex items-center text-sm font-medium text-gray-900">
        Quantização
        <Tooltip content="Técnica de compressão vetorial para reduzir o uso de RAM e acelerar as buscas no banco de vetores." />
      </legend>
      <select
        value={quantizationType}
        onChange={(e) => onType(e.target.value as QuantizationType)}
        className="block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
      >
        <option value="none">Nenhuma</option>
        <option value="scalar">Scalar (int8)</option>
        <option value="product">Product</option>
        <option value="binary">Binary</option>
      </select>

      {quantizationType === "scalar" && (
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="flex items-center">
              <label htmlFor="scalar-quantile" className="text-sm text-gray-700">
                quantile
              </label>
              <Tooltip content="Percentil limite para descarte de valores extremos na quantização escalar (int8), padrão 0.99." />
            </div>
            <input
              id="scalar-quantile"
              type="number"
              step="0.01"
              value={scalarQuantile}
              onChange={(e) => onScalarQuantile(Number(e.target.value))}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              id="scalar-ram"
              type="checkbox"
              checked={scalarAlwaysRam}
              onChange={(e) => onScalarAlwaysRam(e.target.checked)}
            />
            <label htmlFor="scalar-ram" className="flex items-center text-sm text-gray-700">
              always_ram
            </label>
            <Tooltip content="Mantém os vetores quantizados carregados na memória RAM mesmo que a coleção principal esteja configurada em disco." />
          </div>
        </div>
      )}

      {quantizationType === "product" && (
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="flex items-center">
              <label htmlFor="product-compression" className="text-sm text-gray-700">
                compression
              </label>
              <Tooltip content="Fator de compressão do Product Quantization (ex.: x16 reduz o tamanho dos vetores em 16 vezes)." />
            </div>
            <select
              id="product-compression"
              value={productCompression}
              onChange={(e) => onProductCompression(e.target.value as typeof productCompression)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
            >
              {(["x4", "x8", "x16", "x32", "x64"] as const).map((valor) => (
                <option key={valor} value={valor}>
                  {valor}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <input
              id="product-ram"
              type="checkbox"
              checked={productAlwaysRam}
              onChange={(e) => onProductAlwaysRam(e.target.checked)}
            />
            <label htmlFor="product-ram" className="flex items-center text-sm text-gray-700">
              always_ram
            </label>
            <Tooltip content="Mantém os vetores quantizados carregados na memória RAM mesmo que a coleção esteja em disco." />
          </div>
        </div>
      )}

      {quantizationType === "binary" && (
        <div className="flex items-center gap-2">
          <input
            id="binary-ram"
            type="checkbox"
            checked={binaryAlwaysRam}
            onChange={(e) => onBinaryAlwaysRam(e.target.checked)}
          />
          <label htmlFor="binary-ram" className="flex items-center text-sm text-gray-700">
            always_ram
          </label>
          <Tooltip content="Mantém os vetores quantizados carregados na memória RAM." />
        </div>
      )}
    </fieldset>
  );
}
