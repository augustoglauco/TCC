# Modelos de IA Previstos para Teste no Projeto (TCC)

Este arquivo consolida a relação de todos os modelos de Inteligência Artificial previstos para teste, experimentação e benchmark no projeto de Assistente Virtual Multimodal.

---

## 1. Modelos Locais Candidatos a SLM Principal (`LOCAL_MODEL_NAME`)
*Avaliação comparativa no benchmark da Fase 10 contra o sistema completo (Roteador, RAG, Injeção de Prompt e Visão). Servidos via Ollama em GPU RTX 4080 16GB.*
*Fonte: `backend/eval/model_benchmark/modelos.json` e `docs/ARCHITECTURE.md`.*

| ID | Nome / Rótulo | Tag Ollama | Família | Parâmetros | Quantização | Visão Local (`vision`) | Papel / Critério no Teste |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| `llama31-8b` | Llama 3.1 8B | `llama3.1:8b` | llama3.1 | 8B | Q4_0 | Não | Baseline de mercado / eficiência geral |
| `qwen25-vl-7b` | Qwen2.5-VL 7B Instruct | `qwen2.5-vl:7b` | qwen2.5-vl | 7B | Q4_K_M | **Sim** | Multimodal nativo (visão local) e alta qualidade lógica |
| `qwen3-14b-q4` | Qwen3 14B Q4_K_M | `qwen3:14b-q4_K_M` | qwen3 | 14B | Q4_K_M | Não | Teste de teto de capacidade em 16GB VRAM |
| `qwen3-14b-q5` | Qwen3 14B Q5_K_M | `qwen3:14b-q5_K_M` | qwen3 | 14B | Q5_K_M | Não | Teste de precisão x risco de contenção de VRAM |
| `qwen3-8b-q5` | Qwen3 8B Q5_K_M | `qwen3:8b-q5_K_M` | qwen3 | 8B | Q5_K_M | Não | Equilíbrio entre latência e fidelidade |
| `qwen3-8b-q8` | Qwen3 8B Q8_0 | `qwen3:8b-q8_0` | qwen3 | 8B | Q8_0 | Não | Teste de alta precisão de quantização (8-bit) |
| `phi4-mini` | Phi-4-mini | `phi4-mini` | phi4 | 3.8B | Q4_K_M | Não | Candidato ultra-rápido de baixa latência |
| `phi4` | Phi-4 | `phi4` | phi4 | 14B | Q4_K_M | Não | Modelo compacto com forte capacidade lógica |
| `gemma4-12b-q4` | Gemma-4-12B 4-bit | `gemma4:12b-it-q4_K_M` | gemma4 | 12B | Q4_K_M | **Sim** | Multimodal nativo (visão local sem custo de API) |
| `gemma4-e4b-q8` | Gemma-4-E4B-it UD-Q8_K_XL | `gemma-4-E4B-it-GGUF:UD-Q8_K_XL` | gemma4 | 26B (E4B) | UD-Q8_K_XL | **Sim** | Multimodal nativo MoE em alta precisão quantizada |

---

## 2. Modelos de Embedding de Texto para o RAG
*Avaliação comparativa da Etapa 2 de Ingestão de RAG (MTEB-BR, nDCG@10, separação positiva/negativa e respeito à janela de contexto).*
*Fonte: `docs/EVALUATION.md` §2.1 e `backend/eval/rag_ingestion/run_etapa2.py`.*

| Modelo | Parâmetros | Dimensões | Janela Contexto | MTEB-BR (Mean22) | Papel / Observação no Teste |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `paraphrase-multilingual-MiniLM-L12-v2` | 118M | 384 | 128 tokens | 0,248 (93º) | Baseline atual do projeto (janela curta de ~550 chars) |
| `google/embeddinggemma-300m` | 308M | 768 (MRL) | 2048 tokens | 0,649 (13º) | **Candidato preferido**; exige prefixos assimétricos de tarefa |
| `intfloat/multilingual-e5-large-instruct` | 560M | 1024 | 512 tokens | 0,641 | Candidato avaliado; exige prefixos `query:` e `passage:` |
| `BAAI/bge-m3` | 568M | 1024 | 8192 tokens | — | Dense + sparse + multi-vector (prepara busca híbrida) |

---

## 3. Modelos de Visão Multimodal e Embeddings de Imagem
*Identificação de produtos do portfólio, OCR e busca vetorial multimodal no catálogo.*
*Fonte: `docs/ARCHITECTURE.md` §4 e `docs/EVALUATION.md`.*

| Tecnologia / Modelo | Provedor / Runtime | Tipo / Função | Papel no Projeto |
| :--- | :--- | :--- | :--- |
| `gemma4:12b-it` (Q4 / Q8) | Local (Ollama) | Visão Multimodal | Descrição e classificação de imagens no próprio hardware |
| `qwen2.5-vl:7b` (Instruct) | Local (Ollama) | Visão Multimodal | Descrição e classificação de imagens no próprio hardware |
| `google/gemma-4-31b-it:free` | Externo (OpenRouter) | Visão Multimodal | Fallback externo (`EXTERNAL_VISION_MODEL_NAME`) para imagens |
| `CLIP` (Sentence Transformers) | Local (Qdrant) | Embedding de Imagem | Busca vetorial direta de similaridade visual no catálogo de produtos |

---

## 4. Modelos Externos (APIs / OpenRouter) e Avaliação
*Roteamento por complexidade, testes de latência local x externo e LLM-as-judge.*
*Fonte: `docs/EVALUATION.md` e `.env.example`.*

| Modelo | Provedor | Função Principal | Papel no Teste / Avaliação |
| :--- | :--- | :--- | :--- |
| `liquid/lfm-2.5-2.6b:free` | OpenRouter | LLM-as-Judge Neutro | Juiz externo nas baterias de RAG e Prompt Injection |
| `anthropic/claude-3.5-haiku` | OpenRouter | Modelo Externo de Chat | Comparação de latência (local x externo) e escalonamento |
| `~typesafe/jev-latest` | OpenRouter (System One) | Classificador de Intenção / Tom | Teste de classificação ultrarrápida (<10s) sem chat completion |

---

## 5. Modelo de Áudio / Transcrição (STT)
*Transcrição de mensagens de voz na GPU local.*
*Fonte: `docs/ARCHITECTURE.md` §escopo e `.env.example`.*

| Modelo | Runtime | Tamanho / Config | Papel no Projeto |
| :--- | :--- | :--- | :--- |
| `faster-whisper` | Local (GPU CUDA) | `small` (`STT_MODEL_SIZE`) | Transcrição local de áudios (wav/mp3) dividindo VRAM com o SLM |
