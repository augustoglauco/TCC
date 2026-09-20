# Technology Stack — Assistente Virtual Multimodal (TCC)

> Fonte: decisões arquiteturais de `docs/ARCHITECTURE.md`. Este documento
> descreve as escolhas tecnológicas específicas para cada componente do projeto.
> Atualize aqui quando mudar uma dependência ou ferramenta; não duplique
> decisões em CLAUDE.md ou `.agents/rules/project.md`.

## 1. Backend — Python + FastAPI

### Framework Web e API

| Componente | Tecnologia | Versão | Razão |
|---|---|---|---|
| **Linguagem** | Python | 3.11+ | Suporte a async nativo, ecossistema LLM maduro |
| **Framework** | FastAPI | latest | Async-first, suporte a SSE (streaming), validação automática com Pydantic |
| **Validação** | Pydantic | v2 | Schemas, type hints, serialização JSON |
| **Async DB Driver** | asyncpg | latest | PostgreSQL assíncrono, integra com SQLAlchemy |
| **ORM** | SQLAlchemy | 2.0+ | Async support, migrações com Alembic, queries complexas |
| **Migrações** | Alembic | latest | Versionamento de schema, reversibilidade |

### Modelo Local — Inferência de LLM

| Componente | Tecnologia | Versão | Razão |
|---|---|---|---|
| **Runtime de Inferência** | Ollama (decisão fechada) | latest | API HTTP simples, gestão de modelos trivial (`ollama pull`), e devolve `prompt_eval_count`/`eval_count` (tokens) e `load_duration`/`eval_duration` (breakdown de latência) prontos por requisição — reduz o código de instrumentação necessário para `docs/EVALUATION.md` |
| **Modelos candidatos** | Llama 3.1 8B; Qwen2.5 7B; Qwen3 14B (Q4_K_M, Q5_K_M); Qwen3 8B (Q5_K_M, Q8_0); Phi-4-mini/Phi-4; Gemma-4-12B (4-bit, 8-bit) | quantizado (GGUF) | 9 configurações na avaliação comparativa (ver `docs/ARCHITECTURE.md` tabela de escopo); Gemma-4-12B (4-bit, `gemma4:12b-it-q4_K_M`) já confirmado no Ollama local — é o `LOCAL_MODEL_NAME` em uso no `.env` de desenvolvimento; os demais 8 ainda precisam ser baixados |
| **Quantização** | GGUF | - | Reduz memory footprint, mantém qualidade aceitável |
| **Hardware-alvo** | GPU NVIDIA | 16GB VRAM mín. | Limite do MVP; candidatos >~12–14B mesmo quantizados arriscam OOM (sem margem para KV cache) |
| **Cliente de modelo externo** | OpenRouter | latest | API compatível com o formato OpenAI, uma única chave cobrindo múltiplos provedores/modelos — chave em `EXTERNAL_MODEL_API_KEY` e modelo em `EXTERNAL_MODEL_NAME` (`.env.example`; nomes propositalmente neutros de provedor) |

### Bancos de Dados

#### PostgreSQL

| Aspecto | Escolha | Justificativa |
|---|---|---|
| **Banco relacional** | PostgreSQL 13+ | Transações ACID (crítico para pedidos/reservas), integridade referencial, conector RAG estruturado |
| **Driver** | asyncpg (SQLAlchemy) | Integração nativa com FastAPI async |
| **Persistência** | Conversas, perfil de usuário, catálogo, estoque, preços, manuais | Backend único compartilhado entre RAG, MCP B2B e chat |
| **Sincronização** | Via API (sem replicação) | MVP: conector de leitura simples, sem sincronização incremental |

**Tabelas principais (Fase 6 em diante):**
- `conversations` — histórico de chat por ID
- `users` — perfil, classificação (Cliente/Lead/Esporádico)
- `products` — catálogo (especificações, dimensões, preços)
- `inventory` — estoque por centro de distribuição
- `orders` — pedidos, histórico, status
- `manuals` — documentação técnica (para RAG)
- `router_logs` — decisões do roteador (auditoria)

#### Qdrant (Vetorial)

| Aspecto | Escolha | Justificativa |
|---|---|---|
| **Banco vetorial** | Qdrant | Busca vetorial nativa, payload filtering, roda em container Docker |
| **Persistência** | Dois volumes Docker | Separação lógica e performance |
| **Collections** | `docs_texto`, `catalogo_imagens` | RAG textual e multimodal isoladas |
| **Embeddings (texto)** | sentence-transformers, default `paraphrase-multilingual-MiniLM-L12-v2` (384 dims) | Multilíngue (cobre português da empresa fictícia do TCC), leve, qualidade suficiente para MVP — configurável por perfil de collection (`RagCollection.embedding_model`, não mais uma única config fixa por processo, ver docs/superpowers/specs/2026-09-15-rag-collections-config-design.md) |
| **Embeddings (imagem)** | CLIP (ViT-B/32) | Multimodal, treinado em 400M pares imagem-texto, acesso via transformers |
| **Reranking** | BM25 + similarity score | Heurística simples, sem modelo dedicado (MVP) |

### RAG — Retrieval-Augmented Generation

| Componente | Tecnologia | Versão | Razão |
|---|---|---|---|
| **Ingestão de PDF/texto** | pypdf (extração) + chunking próprio | latest | Extração de texto de PDF; chunking por tamanho fixo com overlap implementado diretamente em `app/rag/chunking.py` — decisão revista na Fase 2: dispensa `langchain` (dependência pesada para uma necessidade de chunking simples), mantendo o MVP mais enxuto (`# MVP: chunking ingênuo, sem respeitar limites semânticos`, ver `app/rag/chunking.py`) |
| **Busca vetorial** | Qdrant (conforme acima) | - | - |
| **Conector de BD** | SQLAlchemy (PostgreSQL) | - | Leitura estruturada, filtros por domínio/categoria; MVP: sem escrita, sem incremental |
| **Crawler Web** | httpx + beautifulsoup4 | latest | Parsing HTML assíncrono, navegação BFS de verdade a partir de uma URL semente (sem lista fixa de páginas), profundidade e teto parametrizáveis por execução, sem agendamento |
| **OCR** | Tesseract (pytesseract) | 4.x | Extração de texto em imagens dirigidas (ex.: comprovante) |
| **Processamento de imagem** | Pillow (PIL) | latest | Redimensionamento, validação, normalização para CLIP |

### Entrada Multimodal

| Componente | Tecnologia | Versão | Razão |
|---|---|---|---|
| **STT (Áudio → Texto)** | OpenAI Whisper (local) ou Google Cloud Speech-to-Text | local prefer | Whisper: open-source, rodável local em GPU; suporta wav, mp3, flac |
| **Formatos de áudio** | wav, mp3 | - | Dois formatos mínimos conforme R2 |
| **Processamento de áudio** | librosa | latest | Normalização, pré-processamento para STT |

### MCPs (Model Context Protocol)

#### Cliente MCP — Google Calendar

| Aspecto | Escolha | Justificativa |
|---|---|---|
| **SDK** | MCP SDK oficial (Python) | Padrão do protocolo, manutenção |
| **Autenticação** | OAuth 2.0 (var. de ambiente) | Google Calendar requer OAuth; credenciais em `.env.example` |
| **Integração** | Roteador (intenção de agendamento) | Fase 4: nova intenção que chama MCP |
| **Fallback de erro** | Sugerir nova tentativa ou transferir para atendente | Tratamento de erro claro (R11) |

#### Servidor MCP — B2B Próprio

| Aspecto | Escolha | Justificativa |
|---|---|---|
| **SDK** | MCP SDK oficial (Python) | Padrão do protocolo |
| **Recursos expostos** | Catálogo, estoque, preços, manuais (leitura) | Reutilizam backend único (PostgreSQL + RAG) |
| **Ferramentas** | Compatibilidade, frete, cotação, reserva/pedido | 4 operações transacionais sobre o backend |
| **Autenticação** | Nenhuma (MVP) | Uso interno apenas; autenticação por parceiro é evolução futura |
| **Rate limiting** | Nenhum (MVP) | Não implementado no protótipo |

### Monitoramento e Logging

| Componente | Tecnologia | Versão | Razão |
|---|---|---|---|
| **Logging estruturado** | Python `logging` + JSON | stdlib | ID de conversa em toda mensagem (R9 pré-requisito) |
| **Monitor de tom** | Heurística + LLM leve | - | Classificador de sentimento/urgência (Fase 4) |
| **Decisões do roteador** | Log de intenção escolhida, custo, latência | - | Auditoria e avaliação experimental (Fase 10) |

### Testes Backend

| Aspecto | Tecnologia | Versão | Razão |
|---|---|---|---|
| **Framework** | pytest | latest | Fixtures, parametrização, integração com CI |
| **Fixtures GPU** | pytest.mark.gpu | - | Testes com GPU pulável em ambientes sem (CI) |
| **Cobertura** | pytest-cov | latest | Rastreamento de cobertura |
| **Testes de integração** | pytest + FastAPI TestClient | - | Simular requisições HTTP |
| **Domínios testados** | Roteador, RAG, MCP B2B, schemas | - | Ver `docs/CONVENTIONS.md` para convenções |

### Lint e Format

| Componente | Tecnologia | Versão | Razão |
|---|---|---|---|
| **Linter + Formatter** | ruff | latest | Substitui black + flake8, muito mais rápido |
| **Pre-commit hook** | ruff check + ruff format | - | Rodar antes de cada commit (obrigatório) |

---

## 2. Frontend — Next.js + TypeScript

### Framework Web

| Componente | Tecnologia | Versão | Razão |
|---|---|---|---|
| **Framework** | Next.js | 14+ (App Router) | App Router (não Pages), SSR/SSG, otimização automática |
| **Linguagem** | TypeScript | strict mode | Type safety, DX melhorada |
| **Estilo** | Tailwind CSS | latest | Utility-first, configurável, leve |
| **Componentes** | React | 18+ | Hooks, Suspense, async components |

### State Management

| Componente | Tecnologia | Versão | Razão |
|---|---|---|---|
| **Data do servidor** | React Query ou SWR | latest | Caching, invalidação, retry automático |
| **Estado local** | Zustand ou Context API | Zustand prefer | Simples, TypeScript-friendly, sem boilerplate |
| **Persistência local** | localStorage (conversaID) | browser | Retomar chat entre sessões (R9) |

### Comunicação com Backend

| Componente | Tecnologia | Versão | Razão |
|---|---|---|---|
| **HTTP Client** | fetch ou axios | fetch prefer | Moderno, nativo, SSE suporta bem |
| **Streaming (SSE)** | EventSource (browser native) | - | Simples que WebSocket, suficiente para chat streaming |
| **Upload de arquivos** | FormData (fetch) | - | Imagem/áudio multipart |

### Componentes Principais

| Seção | Componentes | Tecnologia |
|---|---|---|
| **Catálogo** | ProductList, ProductDetail | React + Tailwind |
| **Pedidos** | CartWidget, CheckoutFlow, OrderHistory | Zustand (state) + React Query |
| **Autenticação** | LoginForm, SignupForm, ProfilePage | Zustand + localStorage (token) |
| **Chat** | ChatWidget, ChatModal, MessageList, InputArea, AudioRecorder, ImageUploader | React + Zustand + SSE |
| **Cards ricos** | ProductCard, OrderConfirmation, QuotationCard, AppointmentCard | React components |

### Testes Frontend

| Aspecto | Tecnologia | Versão | Razão |
|---|---|---|---|
| **Unit/Component** | Vitest + React Testing Library | latest | Rápido, API familiar, snapshot opcional |
| **E2E** | Playwright | latest | Browsers reais, testes de fluxo completo |
| **Fluxos testados** | Chat (texto/imagem/áudio), pedido, login, agendamento | - | Ver `docs/FRONTEND.md` §6 |

### Lint e Format

| Componente | Tecnologia | Versão | Razão |
|---|---|---|---|
| **Linter** | ESLint | latest | Regras React/Next.js |
| **Formatter** | Prettier | latest | Consistência de código |

---

## 3. Infraestrutura e DevOps

### Bancos de Dados (Docker)

| Serviço | Imagem | Porta | Volume | Razão |
|---|---|---|---|---|
| **PostgreSQL** | postgres:15-alpine | 5432 | `/var/lib/postgresql/data` | BD relacional principal |
| **Qdrant** | qdrant/qdrant:latest | 6333 | `/qdrant/storage` | Vetorial para RAG |

### Orquestração Local

| Ferramenta | Uso | Razão |
|---|---|---|
| **Docker Compose** | Subir PostgreSQL + Qdrant + Ollama/vLLM | Desenvolvimento local; facilita reprodução |
| **Variáveis de ambiente** | `.env.example` (versionado) + `.env.local` (git-ignored) | Não versionam credenciais reais |

### VPS/EC2 (Produção/Deploy)

| Aspecto | Configuração | Justificativa |
|---|---|---|
| **Instância** | EC2 ou VPS com GPU NVIDIA 16GB+ | Inferência local do modelo |
| **Runtime LLM** | Ollama ou vLLM (systemd service) | HTTP API exposta para FastAPI |
| **Banco de dados** | PostgreSQL (managed ou self-hosted) | Persistência durável |
| **Cache vetorial** | Qdrant (managed ou container) | Vetores persistidos entre requisições |
| **Reverse Proxy** | nginx | SSL/TLS, rate limiting, compressão |
| **CI/CD** | GitHub Actions ou similar | Testes, lint, deploy automático |

---

## 4. Resumo de Dependências (Arquivos de Definição)

### Backend (`backend/pyproject.toml`)

```toml
[project]
dependencies = [
    "fastapi",
    "uvicorn[standard]",
    "pydantic[email]",
    "sqlalchemy[asyncio]",
    "asyncpg",
    "alembic",
    "qdrant-client",
    "pypdf",
    "sentence-transformers",
    "pillow",
    "pytesseract",
    "openai-whisper",  # ou google-cloud-speech-to-text
    "librosa",
    "requests",
    "beautifulsoup4",
    "pydantic-settings",
    "python-multipart",
    "httpx",  # client HTTP async
    "pytest",
    "pytest-cov",
    "pytest-asyncio",
    "ruff",
]

[project.optional-dependencies]
llm = ["ollama"]  # cliente Python oficial do Ollama; OpenRouter via httpx (já listado)
```

### Frontend (`frontend/package.json`)

```json
{
  "dependencies": {
    "next": "14+",
    "react": "18+",
    "typescript": "latest",
    "tailwindcss": "latest",
    "zustand": "latest",
    "@tanstack/react-query": "latest",
    "axios": "latest"
  },
  "devDependencies": {
    "vitest": "latest",
    "@testing-library/react": "latest",
    "@playwright/test": "latest",
    "eslint": "latest",
    "prettier": "latest"
  }
}
```

---

## 5. Matriz de Mapeamento: Requisitos ↔ Tecnologias

| Req. | Requisito | Tecnologias-chave |
|---|---|---|
| R1 | Modelo local GPU | Ollama/vLLM + Llama 3.1 8B (quantizado) |
| R2 | Entrada multimodal | FastAPI (text/image/audio upload), Whisper (STT) |
| R3 | Roteador/Orquestrador | FastAPI + LLM local/externo |
| R4 | RAG multimodal | Qdrant + sentence-transformers + CLIP + PostgreSQL |
| R5 | STT | Whisper (local) |
| R6 | Tratamento de imagem | Pillow + Tesseract (OCR) + CLIP (busca) |
| R7 | Domínios (4) | Schemas Pydantic + prompts do roteador |
| R8 | Monitor de tom | LLM leve + heurística |
| R9 | Memória de conversa | PostgreSQL + logging estruturado |
| R10 | Classificação de usuário | Heurística + PostgreSQL |
| R11 | Agendamento (MCP) | MCP SDK (Python) + Google Calendar OAuth |
| R12 | MCP B2B | MCP SDK (Python) + FastAPI |

---

## 6. Decisões Críticas e Alternativas Consideradas

### Por que PostgreSQL e não MongoDB?

**Decisão:** PostgreSQL é backend único.

**Razão:**
- Dados altamente relacionais (produtos ↔ estoque ↔ pedidos)
- Transações ACID essenciais para reservas/pedidos
- Integridade referencial crítica
- Conector RAG estruturado requer SQL
- MongoDB seria útil só se conversas fossem não-estruturadas (mas não são)

### Por que Qdrant e não Pinecone/Weaviate?

**Decisão:** Qdrant (self-hosted em Docker).

**Razão:**
- Open-source, roda local (sem custo cloud)
- Payload filtering nativo (filtro por domínio/categoria)
- Performance aceitável para MVP
- Alternativa: Pinecone (cloud, pagas) se escala crescer

### Por que Ollama e não vLLM ou API externa como padrão?

**Decisão:** Modelo local via Ollama; modelo externo via OpenRouter (não como padrão, só quando o roteador decide escalar).

**Razão:**
- R1 requer modelo local (GPU 16GB)
- Reduz latência e custo quando resolve localmente (sem chamadas externas)
- Ollama devolve tokens e breakdown de latência (load x eval) prontos na resposta — menos código de instrumentação para `docs/EVALUATION.md` do que vLLM ou llama.cpp puro
- vLLM traria mais throughput sob concorrência, mas é overkill para um protótipo de TCC sem carga concorrente real — considerado, descartado por ora
- OpenRouter: uma única chave cobrindo múltiplos provedores/modelos, API compatível com OpenAI — evita amarrar o cliente externo a um provedor específico

### Por que Next.js e não FastAPI full-stack?

**Decisão:** Separação backend (FastAPI) + frontend (Next.js).

**Razão:**
- Chat de alta interatividade requer frontend dedicado
- SSE e SSR beneficiam Next.js
- Documentação completa em `docs/FRONTEND.md`

---

## 7. Compatibilidade e Versões Mínimas

| Componente | Versão Mínima | Razão |
|---|---|---|
| Python | 3.11 | async/await estável, type hints modernos |
| PostgreSQL | 13 | JSON nativo, async drivers maduros |
| Node.js | 18+ | ESM, TypeScript suporte |
| Docker | 20+ | buildkit, compose v2 |
| CUDA (NVIDIA) | 11.8+ | suporte a Ollama/vLLM, quantização |

---

## 8. Referências

- `docs/ARCHITECTURE.md` — decisões arquiteturais (por quê cada escolha)
- `docs/CONVENTIONS.md` — estrutura de pastas, testes, git
- `docs/FRONTEND.md` — contrato de API backend ↔ frontend
- `CLAUDE.md` — stack resumido
