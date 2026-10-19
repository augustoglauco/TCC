export interface PresetModel {
  tag: string;
  name: string;
  provider: string;
  description: string;
  isFree?: boolean;
}

// MVP: sugestões fixas no código (sem consultar o catálogo do OpenRouter) e
// histórico só no localStorage do navegador; o modelo escolhido vale até o
// restart do backend (ver docs/ARCHITECTURE.md §5, card "Modelo externo").
export const POPULAR_MODELS: PresetModel[] = [
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

export const FREE_MODELS: PresetModel[] = [
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
