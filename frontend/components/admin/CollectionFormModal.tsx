"use client";

import { useState } from "react";

import { Modal } from "@/components/ui/Modal";
import { Tooltip } from "@/components/ui/Tooltip";
import { RagApiError, createCollection } from "@/lib/api/rag";
import type {
  CollectionCreatePayload,
  CollectionPurpose,
  PayloadIndex,
  PayloadSchemaType,
  QuantizationType,
  RagCollection,
  TextIndexParams,
} from "@/lib/types/rag";

const CURATED_MODELS = [
  { value: "paraphrase-multilingual-MiniLM-L12-v2", label: "MiniLM multilíngue (384 dim)" },
  { value: "paraphrase-multilingual-mpnet-base-v2", label: "MPNet multilíngue (768 dim)" },
  { value: "intfloat/multilingual-e5-base", label: "E5 base multilíngue (768 dim)" },
  { value: "intfloat/multilingual-e5-large", label: "E5 large multilíngue (1024 dim)" },
  { value: "__custom__", label: "Outro (digitar nome)" },
] as const;

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

const PAYLOAD_INDEXES_PADRAO: PayloadIndex[] = [
  { field: "domain", schema_type: "keyword" },
  { field: "document_id", schema_type: "keyword" },
];

const TEXT_PARAMS_PADRAO: TextIndexParams = {
  tokenizer: "word",
  min_token_len: null,
  max_token_len: null,
  lowercase: true,
};

export interface CollectionFormModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (collection: RagCollection) => void;
}

export function CollectionFormModal({ open, onOpenChange, onCreated }: CollectionFormModalProps) {
  const [name, setName] = useState("");
  const [purpose, setPurpose] = useState<CollectionPurpose>("chat");
  const [modelSelecionado, setModelSelecionado] = useState<string>(CURATED_MODELS[0].value);
  const [modeloCustom, setModeloCustom] = useState("");
  const [distanceMetric, setDistanceMetric] = useState<CollectionCreatePayload["distance_metric"]>("cosine");
  const [chunkSize, setChunkSize] = useState(800);
  const [chunkOverlap, setChunkOverlap] = useState(100);
  const [hnswM, setHnswM] = useState(16);
  const [hnswEfConstruct, setHnswEfConstruct] = useState(100);
  const [hnswFullScanThreshold, setHnswFullScanThreshold] = useState(10000);
  const [hnswMaxIndexingThreads, setHnswMaxIndexingThreads] = useState(0);
  const [hnswOnDisk, setHnswOnDisk] = useState(false);
  const [hnswPayloadM, setHnswPayloadM] = useState("");
  const [quantizationType, setQuantizationType] = useState<QuantizationType>("none");
  const [scalarQuantile, setScalarQuantile] = useState(0.99);
  const [scalarAlwaysRam, setScalarAlwaysRam] = useState(false);
  const [productCompression, setProductCompression] = useState<"x4" | "x8" | "x16" | "x32" | "x64">("x16");
  const [productAlwaysRam, setProductAlwaysRam] = useState(false);
  const [binaryAlwaysRam, setBinaryAlwaysRam] = useState(false);
  const [payloadIndexes, setPayloadIndexes] = useState<PayloadIndex[]>(PAYLOAD_INDEXES_PADRAO);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const embeddingModel = modelSelecionado === "__custom__" ? modeloCustom : modelSelecionado;
  const chunkingInvalido = chunkSize <= chunkOverlap;

  function resetar() {
    setName("");
    setPurpose("chat");
    setModelSelecionado(CURATED_MODELS[0].value);
    setModeloCustom("");
    setDistanceMetric("cosine");
    setChunkSize(800);
    setChunkOverlap(100);
    setHnswM(16);
    setHnswEfConstruct(100);
    setHnswFullScanThreshold(10000);
    setHnswMaxIndexingThreads(0);
    setHnswOnDisk(false);
    setHnswPayloadM("");
    setQuantizationType("none");
    setScalarQuantile(0.99);
    setScalarAlwaysRam(false);
    setProductCompression("x16");
    setProductAlwaysRam(false);
    setBinaryAlwaysRam(false);
    setPayloadIndexes(PAYLOAD_INDEXES_PADRAO);
    setError(null);
  }

  function atualizarPayloadIndex(indice: number, campo: Partial<PayloadIndex>) {
    setPayloadIndexes((atual) => atual.map((item, i) => (i === indice ? { ...item, ...campo } : item)));
  }

  function removerPayloadIndex(indice: number) {
    setPayloadIndexes((atual) => atual.filter((_, i) => i !== indice));
  }

  function adicionarPayloadIndex() {
    setPayloadIndexes((atual) => [...atual, { field: "", schema_type: "keyword" }]);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting || chunkingInvalido || !embeddingModel) return;

    setIsSubmitting(true);
    setError(null);

    const payload: CollectionCreatePayload = {
      name,
      embedding_model: embeddingModel,
      distance_metric: distanceMetric,
      chunk_size: chunkSize,
      chunk_overlap: chunkOverlap,
      hnsw: {
        m: hnswM,
        ef_construct: hnswEfConstruct,
        full_scan_threshold: hnswFullScanThreshold,
        max_indexing_threads: hnswMaxIndexingThreads,
        on_disk: hnswOnDisk,
        payload_m: hnswPayloadM === "" ? null : Number(hnswPayloadM),
      },
      quantization: {
        type: quantizationType,
        scalar: quantizationType === "scalar" ? { quantile: scalarQuantile, always_ram: scalarAlwaysRam } : null,
        product:
          quantizationType === "product"
            ? { compression: productCompression, always_ram: productAlwaysRam }
            : null,
        binary: quantizationType === "binary" ? { always_ram: binaryAlwaysRam } : null,
      },
      payload_indexes: payloadIndexes
        .filter((item) => item.field.trim() !== "")
        .map((item) =>
          item.schema_type === "text"
            ? { field: item.field, schema_type: item.schema_type, text_params: item.text_params ?? TEXT_PARAMS_PADRAO }
            : { field: item.field, schema_type: item.schema_type },
        ),
      purpose,
    };

    try {
      const collection = await createCollection(payload);
      onCreated(collection);
      resetar();
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof RagApiError ? err.message : "Erro inesperado ao criar a collection.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onOpenChange={(novoOpen) => {
        if (!novoOpen) resetar();
        onOpenChange(novoOpen);
      }}
      title="Nova collection"
      size="3xl"
    >
      <form onSubmit={handleSubmit} className="max-h-[70vh] space-y-6 overflow-y-auto pr-2">
        <div>
          <div className="flex items-center">
            <label htmlFor="collection-name" className="text-sm font-medium text-gray-900">
              Nome
            </label>
            <Tooltip content="Nome único identificador da collection no Qdrant (ex.: vendas_docs, suporte_manuais)." />
          </div>
          <input
            id="collection-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
          />
        </div>

        <div>
          <div className="flex items-center">
            <label htmlFor="collection-purpose" className="text-sm font-medium text-gray-900">
              Finalidade
            </label>
            <Tooltip content="Chat (pública): conteúdo usado pelo chat. Restrita ao MCP B2B: conteúdo não aparece no chat; será consultado pelo canal MCP B2B (Fase 5)." />
          </div>
          <select
            id="collection-purpose"
            value={purpose}
            onChange={(e) => setPurpose(e.target.value as CollectionPurpose)}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
          >
            <option value="chat">Chat (pública)</option>
            <option value="mcp_b2b">Restrita ao MCP B2B</option>
          </select>
          {purpose === "mcp_b2b" && (
            <p className="mt-1 text-xs text-amber-700">
              Conteúdo não aparece no chat; será consultado pelo canal MCP B2B (Fase 5). Esta
              collection não pode ser ativada para o chat.
            </p>
          )}
        </div>

        <fieldset className="space-y-2">
          <legend className="flex items-center text-sm font-medium text-gray-900">
            Modelo de embedding
            <Tooltip content="Modelo de IA responsável por gerar os vetores densos a partir dos textos dos documentos." />
          </legend>
          <select
            aria-label="Modelo de embedding"
            value={modelSelecionado}
            onChange={(e) => setModelSelecionado(e.target.value)}
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
              onChange={(e) => setModeloCustom(e.target.value)}
              placeholder="ex.: intfloat/multilingual-e5-small"
              required
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
            />
          )}
        </fieldset>

        <div>
          <div className="flex items-center">
            <label htmlFor="distance-metric" className="text-sm font-medium text-gray-900">
              Métrica de distância
            </label>
            <Tooltip content="Métrica matemática para calcular a similaridade entre vetores. Cosine (cosseno) é ideal para busca semântica em texto." />
          </div>
          <select
            id="distance-metric"
            value={distanceMetric}
            onChange={(e) => setDistanceMetric(e.target.value as CollectionCreatePayload["distance_metric"])}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
          >
            <option value="cosine">Cosine</option>
            <option value="euclid">Euclid</option>
            <option value="dot">Dot</option>
            <option value="manhattan">Manhattan</option>
          </select>
        </div>

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
              onChange={(e) => setChunkSize(Number(e.target.value))}
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
              onChange={(e) => setChunkOverlap(Number(e.target.value))}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
            />
          </div>
          {chunkingInvalido && (
            <p className="col-span-2 text-sm text-red-600">Chunk size deve ser maior que o overlap.</p>
          )}
        </fieldset>

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
              value={hnswM}
              onChange={(e) => setHnswM(Number(e.target.value))}
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
              value={hnswEfConstruct}
              onChange={(e) => setHnswEfConstruct(Number(e.target.value))}
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
              value={hnswFullScanThreshold}
              onChange={(e) => setHnswFullScanThreshold(Number(e.target.value))}
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
              value={hnswMaxIndexingThreads}
              onChange={(e) => setHnswMaxIndexingThreads(Number(e.target.value))}
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
              value={hnswPayloadM}
              onChange={(e) => setHnswPayloadM(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
            />
          </div>
          <div className="flex items-center gap-2">
            <input id="hnsw-on-disk" type="checkbox" checked={hnswOnDisk} onChange={(e) => setHnswOnDisk(e.target.checked)} />
            <label htmlFor="hnsw-on-disk" className="flex items-center text-sm text-gray-700">
              on_disk
            </label>
            <Tooltip content="Armazena os vetores e o índice HNSW no disco rígido para economizar memória RAM." />
          </div>
        </fieldset>

        <fieldset className="space-y-2">
          <legend className="flex items-center text-sm font-medium text-gray-900">
            Quantização
            <Tooltip content="Técnica de compressão vetorial para reduzir o uso de RAM e acelerar as buscas no banco de vetores." />
          </legend>
          <select
            value={quantizationType}
            onChange={(e) => setQuantizationType(e.target.value as QuantizationType)}
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
                  onChange={(e) => setScalarQuantile(Number(e.target.value))}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
                />
              </div>
              <div className="flex items-center gap-2">
                <input id="scalar-ram" type="checkbox" checked={scalarAlwaysRam} onChange={(e) => setScalarAlwaysRam(e.target.checked)} />
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
                  onChange={(e) => setProductCompression(e.target.value as typeof productCompression)}
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
                <input id="product-ram" type="checkbox" checked={productAlwaysRam} onChange={(e) => setProductAlwaysRam(e.target.checked)} />
                <label htmlFor="product-ram" className="flex items-center text-sm text-gray-700">
                  always_ram
                </label>
                <Tooltip content="Mantém os vetores quantizados carregados na memória RAM mesmo que a coleção esteja em disco." />
              </div>
            </div>
          )}
          {quantizationType === "binary" && (
            <div className="flex items-center gap-2">
              <input id="binary-ram" type="checkbox" checked={binaryAlwaysRam} onChange={(e) => setBinaryAlwaysRam(e.target.checked)} />
              <label htmlFor="binary-ram" className="flex items-center text-sm text-gray-700">
                always_ram
              </label>
              <Tooltip content="Mantém os vetores quantizados carregados na memória RAM." />
            </div>
          )}
        </fieldset>

        <fieldset className="space-y-2">
          <legend className="flex items-center text-sm font-medium text-gray-900">
            Payload indexes
            <Tooltip content="Índices em campos de metadados dos documentos para permitir buscas filtradas extremamente rápidas (ex.: por domínio ou documento ID)." />
          </legend>
          {payloadIndexes.map((item, indice) => (
            <div key={indice} className="space-y-2 rounded-md border border-gray-100 p-2">
              <div className="flex items-center gap-2">
                <input
                  aria-label={`Campo do índice ${indice + 1}`}
                  value={item.field}
                  onChange={(e) => atualizarPayloadIndex(indice, { field: e.target.value })}
                  placeholder="campo"
                  className="w-1/2 rounded-md border border-gray-300 px-3 py-2 text-gray-900"
                />
                <select
                  aria-label={`Tipo do índice ${indice + 1}`}
                  value={item.schema_type}
                  onChange={(e) => {
                    const schema_type = e.target.value as PayloadSchemaType;
                    atualizarPayloadIndex(indice, {
                      schema_type,
                      text_params: schema_type === "text" ? (item.text_params ?? TEXT_PARAMS_PADRAO) : undefined,
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
                  onClick={() => removerPayloadIndex(indice)}
                  className="inline-flex items-center gap-1 rounded-lg border border-red-200 bg-red-50/60 px-2.5 py-1.5 text-xs font-semibold text-red-600 shadow-2xs hover:bg-red-100 hover:text-red-700 transition-colors"
                >
                  Remover
                </button>
              </div>
              {item.schema_type === "text" && (
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
                        atualizarPayloadIndex(indice, {
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
                        atualizarPayloadIndex(indice, {
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
                        atualizarPayloadIndex(indice, {
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
                        atualizarPayloadIndex(indice, {
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
              )}
            </div>
          ))}
          <button
            type="button"
            onClick={adicionarPayloadIndex}
            className="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-slate-300 bg-slate-50 px-3.5 py-2 text-xs font-semibold text-slate-700 hover:border-blue-400 hover:bg-blue-50 hover:text-blue-700 transition-all"
          >
            + Adicionar índice
          </button>
        </fieldset>

        {error && <p className="rounded-md bg-red-50 px-4 py-3 text-red-800">{error}</p>}

        <div className="flex justify-end gap-3 border-t border-gray-200 pt-4">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="rounded-md px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={isSubmitting || chunkingInvalido || !name || !embeddingModel}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            {isSubmitting ? "Criando..." : "Criar collection"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
