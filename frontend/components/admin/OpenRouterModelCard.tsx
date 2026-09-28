"use client";

import { useEffect, useState } from "react";
import { getRuntimeSettings, updateRuntimeSettings } from "@/lib/api/runtimeSettings";

interface PresetModel {
  tag: string;
  name: string;
  provider: string;
  description: string;
  isFree?: boolean;
}

const POPULAR_MODELS: PresetModel[] = [
  {
    tag: "openai/gpt-4o-mini",
    name: "GPT-4o Mini",
    provider: "OpenAI",
    description: "Excelente equilíbrio entre velocidade, inteligência e custo reduzido.",
  },
  {
    tag: "openai/gpt-4o",
    name: "GPT-4o",
    provider: "OpenAI",
    description: "Modelo flagship multimodal de alta capacidade de raciocínio.",
  },
  {
    tag: "anthropic/claude-3.5-sonnet",
    name: "Claude 3.5 Sonnet",
    provider: "Anthropic",
    description: "Líder de mercado em qualidade de código, redação e análise profunda.",
  },
  {
    tag: "meta-llama/llama-3.1-70b-instruct",
    name: "Llama 3.1 70B",
    provider: "Meta AI",
    description: "Modelo open-source de alta performance e suporte a múltiplos idiomas.",
  },
  {
    tag: "google/gemini-flash-1.5",
    name: "Gemini Flash 1.5",
    provider: "Google",
    description: "Resposta ultra-rápida com grande janela de contexto.",
  },
  {
    tag: "qwen/qwen-2.5-72b-instruct",
    name: "Qwen 2.5 72B",
    provider: "Alibaba Cloud",
    description: "Alta precisão em instruções complexas e raciocínio lógico.",
  },
];

const FREE_MODELS: PresetModel[] = [
  {
    tag: "meta-llama/llama-3.1-8b-instruct:free",
    name: "Llama 3.1 8B Free",
    provider: "Meta AI",
    description: "Modelo leve de código aberto totalmente gratuito no OpenRouter.",
    isFree: true,
  },
  {
    tag: "google/gemma-2-9b-it:free",
    name: "Gemma 2 9B Free",
    provider: "Google",
    description: "Excelente para tarefas gerais e respostas rápidas sem custos.",
    isFree: true,
  },
  {
    tag: "qwen/qwen-2.5-7b-instruct:free",
    name: "Qwen 2.5 7B Free",
    provider: "Alibaba Cloud",
    description: "Modelo ágil e gratuito para conversas e estruturação de dados.",
    isFree: true,
  },
  {
    tag: "mistralai/mistral-7b-instruct:free",
    name: "Mistral 7B Free",
    provider: "Mistral AI",
    description: "Compacto e eficiente para tarefas de conversação e RAG.",
    isFree: true,
  },
  {
    tag: "deepseek/deepseek-r1:free",
    name: "DeepSeek R1 Free",
    provider: "DeepSeek",
    description: "Raciocínio lógico avançado gratuito no OpenRouter.",
    isFree: true,
  },
];

const STORAGE_KEY = "openrouter_model_history";

interface OpenRouterModelCardProps {
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}

export function OpenRouterModelCard({ onError, onSuccess }: OpenRouterModelCardProps) {
  const [activeModel, setActiveModel] = useState<string>("");
  const [historyModels, setHistoryModels] = useState<string[]>([]);
  const [customInput, setCustomInput] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [activatingTag, setActivatingTag] = useState<string | null>(null);

  // Carrega modelo ativo do backend e histórico do localStorage
  useEffect(() => {
    let cancelado = false;

    async function init() {
      try {
        const settings = await getRuntimeSettings();
        if (cancelado) return;
        const currentModel = settings.external_model_name || "openai/gpt-4o-mini";
        setActiveModel(currentModel);

        // Carrega histórico do localStorage
        const savedHistory = localStorage.getItem(STORAGE_KEY);
        let list: string[] = [];
        if (savedHistory) {
          try {
            list = JSON.parse(savedHistory);
          } catch {
            list = [];
          }
        }
        if (!list.includes(currentModel)) {
          list = [currentModel, ...list];
        }
        setHistoryModels(list);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
      } catch (err) {
        if (!cancelado) {
          onError(err instanceof Error ? err.message : "Erro ao carregar modelo externo.");
        }
      } finally {
        if (!cancelado) setLoading(false);
      }
    }

    init();
    return () => {
      cancelado = true;
    };
  }, [onError]);

  // Função central para ativar modelo e guardar no histórico
  const handleActivateModel = async (modelTag: string) => {
    const tag = modelTag.trim();
    if (!tag || activatingTag) return;

    setActivatingTag(tag);
    try {
      await updateRuntimeSettings({ external_model_name: tag });
      setActiveModel(tag);

      // Salva e atualiza o histórico no localStorage
      setHistoryModels((prev) => {
        const updated = [tag, ...prev.filter((m) => m !== tag)];
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
        return updated;
      });

      onSuccess(`Modelo externo ativado com sucesso: ${tag}`);
      setCustomInput("");
    } catch (err) {
      onError(err instanceof Error ? err.message : "Falha ao ativar modelo no OpenRouter.");
    } finally {
      setActivatingTag(null);
    }
  };

  const handleRemoveFromHistory = (tag: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setHistoryModels((prev) => {
      const updated = prev.filter((m) => m !== tag);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      return updated;
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-slate-500">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
        <span className="ml-2.5 text-xs font-medium">Carregando configurações do OpenRouter...</span>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Banner de Modelo Ativo */}
      <div className="rounded-2xl border border-blue-200/80 bg-gradient-to-r from-blue-50/80 to-indigo-50/80 p-5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-blue-600 text-white text-2xl shadow-sm">
            🌐
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-blue-700">
                Modelo Externo Ativo (OpenRouter)
              </span>
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            </div>
            <h2 className="text-lg font-bold text-slate-900 font-mono mt-0.5">{activeModel}</h2>
          </div>
        </div>

        <div className="inline-flex items-center gap-1.5 rounded-xl bg-white px-3.5 py-1.5 text-xs font-semibold text-emerald-700 border border-emerald-200 shadow-2xs">
          <span>✓ Em Execução em Runtime</span>
        </div>
      </div>

      {/* Seção 1: Modelos Populares */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <span>⭐</span> Modelos Populares no OpenRouter
          </h3>
          <span className="text-xs text-slate-500">Modelos comerciais de alta performance</span>
        </div>

        <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
          {POPULAR_MODELS.map((model) => {
            const isSelected = activeModel === model.tag;
            const isActivating = activatingTag === model.tag;

            return (
              <div
                key={model.tag}
                className={`flex flex-col justify-between rounded-xl border p-4 transition-all ${
                  isSelected
                    ? "border-blue-500 bg-blue-50/40 ring-1 ring-blue-500 shadow-xs"
                    : "border-slate-200 bg-white hover:border-slate-300 hover:shadow-2xs"
                }`}
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-600">
                      {model.provider}
                    </span>
                    {isSelected && (
                      <span className="rounded bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                        Ativo
                      </span>
                    )}
                  </div>

                  <h4 className="mt-2 font-bold text-slate-900 text-sm">{model.name}</h4>
                  <p className="mt-1 text-[11px] text-slate-500 leading-relaxed">{model.description}</p>
                  <code className="mt-2 block text-[10px] font-mono text-slate-400 truncate">{model.tag}</code>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100">
                  <button
                    type="button"
                    disabled={isSelected || isActivating}
                    onClick={() => handleActivateModel(model.tag)}
                    className={`w-full rounded-lg py-2 text-xs font-bold transition-colors cursor-pointer ${
                      isSelected
                        ? "bg-slate-100 text-slate-400 cursor-default"
                        : "bg-blue-600 text-white hover:bg-blue-700 shadow-2xs"
                    }`}
                  >
                    {isActivating ? "Ativando..." : isSelected ? "Modelo Ativo" : "Ativar Modelo"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Seção 2: Modelos Gratuitos (Free) */}
      <div className="space-y-3 pt-2 border-t border-slate-200/80">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <span>🎁</span> Modelos Gratuitos (Free Tier)
          </h3>
          <span className="text-xs text-emerald-700 font-semibold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
            Sem Custo de Tokens (0$/1M)
          </span>
        </div>

        <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
          {FREE_MODELS.map((model) => {
            const isSelected = activeModel === model.tag;
            const isActivating = activatingTag === model.tag;

            return (
              <div
                key={model.tag}
                className={`flex flex-col justify-between rounded-xl border p-4 transition-all ${
                  isSelected
                    ? "border-emerald-500 bg-emerald-50/40 ring-1 ring-emerald-500 shadow-xs"
                    : "border-slate-200 bg-white hover:border-slate-300 hover:shadow-2xs"
                }`}
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="rounded bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                      GRATUITO
                    </span>
                    {isSelected && (
                      <span className="rounded bg-emerald-600 text-white px-2 py-0.5 text-[10px] font-bold">
                        Ativo
                      </span>
                    )}
                  </div>

                  <h4 className="mt-2 font-bold text-slate-900 text-sm">{model.name}</h4>
                  <p className="mt-1 text-[11px] text-slate-500 leading-relaxed">{model.description}</p>
                  <code className="mt-2 block text-[10px] font-mono text-slate-400 truncate">{model.tag}</code>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100">
                  <button
                    type="button"
                    disabled={isSelected || isActivating}
                    onClick={() => handleActivateModel(model.tag)}
                    className={`w-full rounded-lg py-2 text-xs font-bold transition-colors cursor-pointer ${
                      isSelected
                        ? "bg-slate-100 text-slate-400 cursor-default"
                        : "bg-emerald-600 text-white hover:bg-emerald-700 shadow-2xs"
                    }`}
                  >
                    {isActivating ? "Ativando..." : isSelected ? "Modelo Ativo" : "Ativar Grátis"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Seção 3: Histórico de Modelos Selecionados */}
      {historyModels.length > 0 && (
        <div className="space-y-3 pt-2 border-t border-slate-200/80">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <span>🕒</span> Histórico de Selecionados / Salvos
            </h3>
            <span className="text-xs text-slate-500">Modelos ativados recentemente e salvos localmente</span>
          </div>

          <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
            {historyModels.map((tag) => {
              const isSelected = activeModel === tag;
              const isActivating = activatingTag === tag;

              return (
                <div
                  key={tag}
                  className="flex items-center justify-between gap-3 p-3 sm:px-4 hover:bg-slate-50 transition-colors"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className={`h-2 w-2 rounded-full shrink-0 ${isSelected ? "bg-emerald-500" : "bg-slate-300"}`} />
                    <span className="font-mono text-xs font-semibold text-slate-900 truncate" title={tag}>
                      {tag}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {isSelected ? (
                      <span className="rounded bg-emerald-100 px-2.5 py-1 text-[11px] font-bold text-emerald-800">
                        Ativo
                      </span>
                    ) : (
                      <button
                        type="button"
                        disabled={isActivating}
                        onClick={() => handleActivateModel(tag)}
                        className="rounded-lg bg-slate-900 px-3 py-1 text-xs font-semibold text-white hover:bg-slate-800 transition-colors cursor-pointer"
                      >
                        {isActivating ? "Ativando..." : "Ativar"}
                      </button>
                    )}

                    {!isSelected && (
                      <button
                        type="button"
                        onClick={(e) => handleRemoveFromHistory(tag, e)}
                        className="rounded p-1 text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors cursor-pointer"
                        title="Remover do histórico"
                        aria-label="Remover do histórico"
                      >
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Seção 4: Adicionar Outro Modelo Personalizado */}
      <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4 sm:p-5 space-y-3 pt-2">
        <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
          <span>➕</span> Adicionar / Ativar Outro Modelo do OpenRouter
        </h3>
        <p className="text-xs text-slate-500">
          Insira a tag identificadora de qualquer modelo suportado pelo OpenRouter (ex.: <code className="rounded bg-slate-200 px-1 py-0.5 font-mono text-slate-800">deepseek/deepseek-chat</code>).
        </p>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleActivateModel(customInput);
          }}
          className="flex flex-col sm:flex-row gap-2"
        >
          <input
            type="text"
            value={customInput}
            onChange={(e) => setCustomInput(e.target.value)}
            placeholder="provedor/nome-do-modelo"
            className="flex-1 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs sm:text-sm font-mono text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          />
          <button
            type="submit"
            disabled={!customInput.trim() || activatingTag !== null}
            className="rounded-lg bg-slate-900 px-5 py-2 text-xs font-bold text-white hover:bg-slate-800 disabled:opacity-40 transition-colors cursor-pointer"
          >
            Ativar Modelo
          </button>
        </form>
      </div>
    </div>
  );
}
