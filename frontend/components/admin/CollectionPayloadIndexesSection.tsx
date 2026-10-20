"use client";

import { Tooltip } from "@/components/ui/Tooltip";
import type { PayloadIndex, PayloadSchemaType, TextIndexParams } from "@/lib/types/rag";

const SCHEMA_TYPES: PayloadSchemaType[] = [
  "keyword",
  "integer",
  "float",
  "bool",
  "geo",
  "datetime",
  "uuid",
  "text",
];

const TEXT_PARAMS_PADRAO: TextIndexParams = {
  tokenizer: "word",
  min_token_len: null,
  max_token_len: null,
  lowercase: true,
};

interface CollectionPayloadIndexesSectionProps {
  indexes: PayloadIndex[];
  onUpdate: (indice: number, campo: Partial<PayloadIndex>) => void;
  onRemove: (indice: number) => void;
  onAdd: () => void;
}

function ParamsTexto({
  item,
  indice,
  onUpdate,
}: {
  item: PayloadIndex;
  indice: number;
  onUpdate: (indice: number, campo: Partial<PayloadIndex>) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-2 pl-1">
      <div>
        <div className="flex items-center">
          <label htmlFor={`tokenizer-${indice}`} className="text-sm text-gray-700">
            Tokenizer
          </label>
          <Tooltip content="Estratégia de divisão do texto do campo: word (palavras), whitespace (espaços), prefix (prefixos) ou multilingual." />
        </div>
        <select
          id={`tokenizer-${indice}`}
          aria-label={`Tokenizer do índice ${indice + 1}`}
          value={item.text_params?.tokenizer ?? TEXT_PARAMS_PADRAO.tokenizer}
          onChange={(e) =>
            onUpdate(indice, {
              text_params: {
                ...(item.text_params ?? TEXT_PARAMS_PADRAO),
                tokenizer: e.target.value as TextIndexParams["tokenizer"],
              },
            })
          }
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
        >
          <option value="prefix">prefix</option>
          <option value="whitespace">whitespace</option>
          <option value="word">word</option>
          <option value="multilingual">multilingual</option>
        </select>
      </div>
      <div>
        <div className="flex items-center">
          <label htmlFor={`min-token-${indice}`} className="text-sm text-gray-700">
            min_token_len (vazio = padrão)
          </label>
          <Tooltip content="Comprimento mínimo que um token precisa ter para ser incluído no índice." />
        </div>
        <input
          id={`min-token-${indice}`}
          type="number"
          aria-label={`min_token_len do índice ${indice + 1}`}
          value={item.text_params?.min_token_len ?? ""}
          onChange={(e) =>
            onUpdate(indice, {
              text_params: {
                ...(item.text_params ?? TEXT_PARAMS_PADRAO),
                min_token_len: e.target.value === "" ? null : Number(e.target.value),
              },
            })
          }
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
        />
      </div>
      <div>
        <div className="flex items-center">
          <label htmlFor={`max-token-${indice}`} className="text-sm text-gray-700">
            max_token_len (vazio = padrão)
          </label>
          <Tooltip content="Comprimento máximo que um token pode ter para ser incluído no índice." />
        </div>
        <input
          id={`max-token-${indice}`}
          type="number"
          aria-label={`max_token_len do índice ${indice + 1}`}
          value={item.text_params?.max_token_len ?? ""}
          onChange={(e) =>
            onUpdate(indice, {
              text_params: {
                ...(item.text_params ?? TEXT_PARAMS_PADRAO),
                max_token_len: e.target.value === "" ? null : Number(e.target.value),
              },
            })
          }
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
        />
      </div>
      <div className="flex items-center gap-2">
        <input
          id={`lowercase-${indice}`}
          type="checkbox"
          aria-label={`lowercase do índice ${indice + 1}`}
          checked={item.text_params?.lowercase ?? TEXT_PARAMS_PADRAO.lowercase}
          onChange={(e) =>
            onUpdate(indice, {
              text_params: {
                ...(item.text_params ?? TEXT_PARAMS_PADRAO),
                lowercase: e.target.checked,
              },
            })
          }
        />
        <label htmlFor={`lowercase-${indice}`} className="text-sm text-gray-700">
          lowercase
        </label>
        <Tooltip content="Converte todo o texto do campo para letras minúsculas antes de indexar." />
      </div>
    </div>
  );
}

export function CollectionPayloadIndexesSection({
  indexes,
  onUpdate,
  onRemove,
  onAdd,
}: CollectionPayloadIndexesSectionProps) {
  return (
    <fieldset className="space-y-2">
      <legend className="flex items-center text-sm font-medium text-gray-900">
        Payload indexes
        <Tooltip content="Índices em campos de metadados dos documentos para permitir buscas filtradas extremamente rápidas (ex.: por domínio ou documento ID)." />
      </legend>

      {indexes.map((item, indice) => (
        <div key={indice} className="space-y-2 rounded-md border border-gray-100 p-2">
          <div className="flex items-center gap-2">
            <input
              aria-label={`Campo do índice ${indice + 1}`}
              value={item.field}
              onChange={(e) => onUpdate(indice, { field: e.target.value })}
              placeholder="campo"
              className="w-1/2 rounded-md border border-gray-300 px-3 py-2 text-gray-900"
            />
            <select
              aria-label={`Tipo do índice ${indice + 1}`}
              value={item.schema_type}
              onChange={(e) => {
                const schema_type = e.target.value as PayloadSchemaType;
                onUpdate(indice, {
                  schema_type,
                  text_params:
                    schema_type === "text" ? (item.text_params ?? TEXT_PARAMS_PADRAO) : undefined,
                });
              }}
              className="w-1/3 rounded-md border border-gray-300 px-3 py-2 text-gray-900"
            >
              {SCHEMA_TYPES.map((tipo) => (
                <option key={tipo} value={tipo}>
                  {tipo}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => onRemove(indice)}
              className="inline-flex items-center gap-1 rounded-lg border border-red-200 bg-red-50/60 px-2.5 py-1.5 text-xs font-semibold text-red-600 shadow-2xs hover:bg-red-100 hover:text-red-700 transition-colors"
            >
              Remover
            </button>
          </div>

          {item.schema_type === "text" && (
            <ParamsTexto item={item} indice={indice} onUpdate={onUpdate} />
          )}
        </div>
      ))}

      <button
        type="button"
        onClick={onAdd}
        className="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-slate-300 bg-slate-50 px-3.5 py-2 text-xs font-semibold text-slate-700 hover:border-blue-400 hover:bg-blue-50 hover:text-blue-700 transition-all"
      >
        + Adicionar índice
      </button>
    </fieldset>
  );
}
