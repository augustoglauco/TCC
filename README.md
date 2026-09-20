# Assistente Virtual Multimodal com Roteador Inteligente

> **Trabalho de Conclusão de Curso (TCC)** — Sistema de atendimento virtual multimodal (texto, áudio e imagem) baseado em arquitetura agêntica com inferência local de IA em GPU (16GB), RAG híbrido, roteamento inteligente e integração bidirecional via Protocolo MCP (*Model Context Protocol*).

---

## 📋 Sumário

- [📌 Visão Geral do Projeto](#-visão-geral-do-projeto)
- [🏗️ Arquitetura do Sistema](#️-arquitetura-do-sistema)
- [🎯 Requisitos Funcionais (R1 – R12)](#-requisitos-funcionais-r1--r12)
- [🛠️ Stack Tecnológica](#️-stack-tecnológica)
- [📂 Estrutura do Repositório (Monorepo)](#-estrutura-do-repositório-monorepo)
- [📊 Avaliação Experimental (`eval/`)](#-avaliação-experimental-eval)
- [🗺️ Status e Roadmap de Desenvolvimento](#️-status-e-roadmap-de-desenvolvimento)
- [🚀 Como Executar o Projeto](#-como-executar-o-projeto)
- [📚 Documentação do Projeto](#-documentação-do-projeto)
- [📝 Licença e Autoria](#-licença-e-autoria)

---

## 📌 Visão Geral do Projeto

Este projeto consiste em um **Assistente Virtual Multimodal** projetado para automatizar o atendimento ao cliente em quatro domínios empresariais estratégicos:

1. **🛍️ Vendas**: Consulta a catálogo de produtos, verificação de estoque em tempo real, cálculo de frete, cotação automática e reservas/pedidos.
2. **🔧 Suporte Técnico**: Resolução de dúvidas técnicas com base em manuais, guias de instalação, esquemas e documentação.
3. **💬 Atendimento ao Usuário**: Informações institucionais, FAQ, políticas da empresa e procedimentos gerais.
4. **📅 Agendamento de Visita**: Marcação e confirmação automatizada de visitas/reuniões integradas ao Google Calendar.

### Principais Diferenciais Arquiteturais

- **Roteador/Orquestrador Inteligente**: Interpreta a intenção e a complexidade da mensagem (analisando o contexto de 1 a 3 mensagens recentes), decidindo entre processamento local em GPU, recuperação por RAG, acionamento de MCPs ou transbordo para modelo externo.
- **Inferência Local Sob Medida (GPU 16GB)**: Utiliza modelos *open-source* quantizados via **Ollama** em GPU dedicada (NVIDIA RTX 4080 16GB VRAM), garantindo privacidade de dados, resposta rápida e menor custo.
- **Escalonamento Transparente**: Recorre a modelos externos via **OpenRouter API** apenas quando a requisição foge ao escopo local, falta relevância no RAG ou exige alta complexidade de raciocínio.
- **Arquitetura Dual MCP (Model Context Protocol)**:
  - **Cliente MCP**: Consome o MCP do Google Calendar para criação automatizada de eventos de agendamento.
  - **Provedor MCP B2B**: Expõe servidor MCP próprio com dados de catálogo, estoque, preços e manuais, além de 4 ferramentas transacionais (compatibilidade, frete, cotação e reserva/pedido).
- **Entrada Multimodal**: Suporte nativo a Texto, Áudio (Speech-to-Text via Whisper) e Imagem (OCR para comprovantes/documentos e busca por similaridade visual via embeddings CLIP).
- **Monitoramento de Tom & Escalada Humana**: Analisa continuamente o sentimento/urgência da conversa e simula a transferência para atendente humano quando detecta insatisfação ou urgência elevada.
- **Memória de Sessão & Perfilamento**: Persistência de conversas com resumos periódicos automatizados (R9) e classificação dinâmica do usuário como *Cliente*, *Lead* ou *Contato Esporádico* (R10).

---

## 🏗️ Arquitetura do Sistema

```text
               Entrada Multimodal (Texto / Áudio / Imagem)
                                   │
                                   ▼
                      Pré-processamento (STT / OCR)
                                   │
                                   ▼
    Roteador / Orquestrador  ──── (paralelo) ──── Monitor de Tom
            │                                          │
            ├──► RAG Híbrido (PostgreSQL, PDFs, CLIP) └──► Atendente Humano
            ├──► Modelo Local (Ollama - GPU 16GB)            (Transferência)
            ├──► Modelo Externo (OpenRouter API)
            ├──► Cliente MCP (Google Calendar — Agendamento)
            └──► Servidor MCP B2B (Catálogo, Estoque, Pedidos)
            │
            ▼
       Resposta ao Usuário (Streaming SSE / Cards Ricos)
```

### Assimetria Intencional dos Domínios no MVP
- **Vendas** e **Agendamento de Visita** contam com camadas de ação dedicadas via MCP (MCP B2B próprio e MCP Google Calendar, respectivamente).
- **Suporte Técnico** e **Atendimento ao Usuário** são resolvidos no protótipo pela combinação de LLM + RAG (PDFs, manuais, crawler web), sem integração a sistemas externos de *ticketing*.

---

## 🎯 Requisitos Funcionais (R1 – R12)

| # | Requisito | Descrição |
|---|---|---|
| **R1** | **Modelo Local GPU** | Inferência de LLM executada localmente em GPU com 16GB VRAM via Ollama. |
| **R2** | **Entrada Multimodal** | Aceite de mensagens em texto, áudio (WAV/MP3) e imagem (PNG/JPG). |
| **R3** | **Roteador Inteligente** | Classificação de intenção e decisão entre modelo local, externo e RAG. |
| **R4** | **RAG Multimodal** | Busca vetorial híbrida em PostgreSQL, PDFs, sites (crawler) e banco de imagens. |
| **R5** | **Transcrição de Áudio (STT)** | Conversão de áudio em texto via Whisper antes da contextualização. |
| **R6** | **Tratamento de Imagem** | OCR para uso dirigido (comprovantes) e embeddings CLIP para busca no catálogo. |
| **R7** | **Domínios de Atendimento** | Suporte especializado a Vendas, Suporte, Atendimento e Agendamento. |
| **R8** | **Monitor de Tom** | Avaliação de sentimento e urgência com alerta e escalada para humano. |
| **R9** | **Memória da Conversa** | Persistência por ID único no PostgreSQL e geração de resumos periódicos. |
| **R10** | **Classificação de Usuário** | Rotulagem dinâmica do perfil como *Cliente*, *Lead* ou *Esporádico*. |
| **R11** | **Agendamento via MCP** | Consumo do protocolo MCP para criar reuniões no Google Calendar + confirmação por e-mail. |
| **R12** | **Servidor MCP B2B** | Exposição de catálogo/estoque e 4 ferramentas (compatibilidade, frete, cotação, pedido). |

---

## 🛠️ Stack Tecnológica

### Backend (Python + FastAPI)
- **Linguagem & Framework**: Python 3.11+, [FastAPI](https://fastapi.tiangolo.com/) (Async-first, suporte a Server-Sent Events).
- **Inferência Local**: [Ollama](https://ollama.com/) servindo modelos quantizados GGUF (Llama 3.1 8B, Qwen2.5/3, Phi-4, Gemma 4 12B).
- **Inferência Externa**: [OpenRouter API](https://openrouter.ai/) (cliente HTTP async para múltiplos provedores).
- **Banco Relacional & ORM**: PostgreSQL 15+ via [SQLAlchemy 2.0](https://www.sqlalchemy.org/) (`asyncpg`) e Alembic para migrações.
- **Banco Vetorial**: [Qdrant](https://qdrant.tech/) rodando em container Docker (collections `docs_texto` e `catalogo_imagens`).
- **Embeddings & Visão**: `sentence-transformers` (texto), `CLIP ViT-B/32` (imagens) e `pytesseract` / Tesseract 4.x (OCR).
- **Processamento de Áudio**: OpenAI Whisper (local) e `librosa` para pré-processamento.
- **Protocolo MCP**: SDK oficial MCP em Python ([modelcontextprotocol](https://github.com/modelcontextprotocol)).
- **Qualidade & Linters**: `ruff` (linter/formatter de alta velocidade) e `pytest` (testes unitários e de integração).

### Frontend (Next.js + TypeScript)
- **Framework Web**: Next.js 14+ (App Router), React 18+, TypeScript em modo `strict`.
- **Estilização & UI**: Tailwind CSS (design moderno, responsivo e adaptável).
- **Gestão de Estado & Cache**: `@tanstack/react-query` / `SWR` (dados de servidor) e `Zustand` (estado local do widget).
- **Comunicação em Tempo Real**: `EventSource` (Server-Sent Events - SSE) para streaming de respostas.
- **Cards Ricos**: Componentes para exibição de produtos, confirmações de agendamento e cotações B2B.

### Infraestrutura & DevOps
- **Containerização**: Docker & Docker Compose (PostgreSQL, Qdrant e ambiente Ollama).
- **Hardware de Desenvolvimento**: GPU NVIDIA RTX 4080 (16GB VRAM), CUDA 11.8+.

---

## 📂 Estrutura do Repositório (Monorepo)

O projeto adota a estrutura de monorepo, mantendo backend, frontend, testes e documentação no mesmo repositório:

```text
.
├── CLAUDE.md                   # Instruções de desenvolvimento para Claude Code CLI
├── .agents/                    # Regras do workspace para Antigravity IDE
├── docs/                       # Documentação técnica e fonte de verdade
│   ├── ARCHITECTURE.md         # Arquitetura, requisitos e escopo do MVP
│   ├── FRONTEND.md             # Especificação da UI, rotas Next.js e contratos de API
│   ├── CONVENTIONS.md          # Padrões de código, estrutura e regras do Git
│   ├── EVALUATION.md           # Detalhamento operacional das avaliações experimentais
│   ├── TECHNOLOGY_STACK.md     # Especificação das tecnologias, bibliotecas e justificativas
│   ├── AGENTIC_WORKFLOW.md     # Guia de colaboração com agentes de IA (Antigravity/Claude)
│   └── ROADMAP.md              # Checklist de desenvolvimento por fases (Fase 0 a 11)
├── backend/                    # Código-fonte da aplicação Backend (FastAPI)
│   ├── src/app/
│   │   ├── api/                # Rotas HTTP e endpoints SSE (`/api/chat`, `/api/products`, etc.)
│   │   ├── router/             # Roteador/Orquestrador e clientes LLM (Ollama / OpenRouter)
│   │   ├── rag/                # Pipeline de ingestão, embeddings e busca Qdrant
│   │   ├── stt/                # Transcrição de áudio em texto (Whisper)
│   │   ├── ocr/                # Extração de texto e leitura de imagens
│   │   ├── tone_monitor/       # Análise de sentimento, urgência e alerta
│   │   ├── mcp_client/         # Cliente MCP (Google Calendar)
│   │   ├── mcp_server/         # Servidor MCP B2B (catálogo, estoque, ferramentas)
│   │   ├── memory/             # Persistência de sessões e sumarização automática
│   │   ├── user_profile/       # Classificação de usuários (Cliente/Lead/Esporádico)
│   │   ├── db/                 # Modelos SQLAlchemy e sessão PostgreSQL
│   │   ├── models/             # Schemas de validação Pydantic v2
│   │   └── config.py           # Configurações globais (`pydantic-settings`)
│   ├── migrations/             # Versionamento do schema PostgreSQL (Alembic)
│   ├── eval/                   # Artefatos e scripts das avaliações experimentais
│   │   ├── router_intents/     # Benchmark de acurácia e matriz de confusão 4x4
│   │   ├── rag_quality/        # Avaliação de qualidade (Ground Truth + LLM-as-Judge)
│   │   └── latency/            # Benchmark de latência (GPU Local vs API Externa)
│   ├── tests/                  # Suíte de testes automatizados (pytest)
│   ├── pyproject.toml          # Dependências Python, ruff e configurações do pytest
│   └── .env.example            # Modelo de variáveis de ambiente
└── frontend/                   # Interface Web e Widget de Chat (Next.js)
    ├── app/                    # Páginas e rotas App Router (`/`, `/produtos`, `/pedidos`, etc.)
    ├── components/             # Componentes React, ChatWidget, AudioRecorder, ImageUploader
    ├── lib/                    # Clientes API HTTP, hooks e gerenciamento de estado Zustand
    ├── tests/                  # Testes de componentes (Vitest) e E2E (Playwright)
    └── package.json            # Dependências do Node.js
```

---

## 📊 Avaliação Experimental (`eval/`)

Como requisito metodológico do TCC, o protótipo é submetido a três baterias de avaliações quantitativas e qualitativas:

1. **🎯 Acurácia do Roteador de Intenções (`eval/router_intents/`)**:
   - Avaliação com 30 a 50 mensagens rotuladas cobrindo os 4 domínios + casos ambíguos.
   - Geração da **Matriz de Confusão 4x4** e cálculo da acurácia global de classificação.
2. **📚 Qualidade das Respostas do RAG (`eval/rag_quality/`)**:
   - Bateria de 15 a 20 perguntas com respostas esperadas conhecidas (*ground truth*).
   - Avaliação dupla: nota manual (1 a 5) e avaliação automatizada via *LLM-as-Judge* (relevância, correção e uso da fonte).
3. **⚡ Latência e Custo: Modelo Local vs. Modelo Externo (`eval/latency/`)**:
   - Medição do tempo de resposta ponta a ponta (média e percentil $p_{95}$) e consumo de tokens.
   - Comparação empírica entre inferência local em GPU (Ollama) e chamada externa (OpenRouter).
4. **🔬 Benchmark Comparativo entre 9 Modelos Locais (Fase 10)**:
   - Avaliação comparativa de 9 configurações de modelos em GPU de 16GB (Llama 3.1 8B, Qwen2.5 7B, Qwen3 14B Q4/Q5, Qwen3 8B Q5/Q8, Phi-4, Gemma 4 12B) contra o sistema completo (com RAG e playbooks reais).

---

## 🗺️ Status e Roadmap de Desenvolvimento

O progresso é estruturado em 12 fases sequenciais conforme documentado em [`docs/ROADMAP.md`](docs/ROADMAP.md):

- [x] **Fase 0 — Fundamentos e Infraestrutura**: Ambiente GPU (NVIDIA RTX 4080 16GB), Ollama 0.30.6 rodando localmente, estrutura do monorepo, logging estruturado com ID de conversa, ruff e pytest configurados.
- [~] **Fase 1 — Modelo Local e Roteador Básico**: Cliente Ollama verificado contra `gemma4:12b-it-q4_K_M`, cliente OpenRouter implementado, classificador de intenção (regras + LLM) considerando histórico de 1–3 mensagens; falta revisitar a resolução de ambiguidade entre domínios, que depende do conjunto de teste rotulado da Fase 10.
- [x] **Fase 2 — Entrada Multimodal e RAG Textual**: Entrada de texto/áudio, STT (Whisper), ingestão de PDFs/textos com busca vetorial (Qdrant), conector de leitura a PostgreSQL, endpoint de upload e crawler de páginas (navegação BFS de verdade a partir de uma URL semente, sem lista fixa) — todos concluídos.
- [ ] **Fase 3 — RAG Multimodal, Imagens e Domínios**: Upload de imagens, OCR, busca por embeddings CLIP, playbooks de Vendas, Suporte e Atendimento.
- [ ] **Fase 4 — Agendamento MCP e Monitor de Tom**: Cliente MCP Google Calendar, confirmação por e-mail, classificador de sentimento/urgência e transbordo simulado.
- [ ] **Fase 5 — Provedor MCP B2B**: Servidor MCP interno com catálogo, estoque, preços e 4 ferramentas transacionais (compatibilidade, frete, cotação, pedido).
- [ ] **Fase 6 — Memória e Classificação de Usuário**: Persistência de conversas, sumarização automática e classificação Cliente/Lead/Esporádico.
- [~] **Fase 7 — Frontend: Site Institucional e Catálogo**: Scaffold Next.js pronto, `/suporte` e `/admin/ingestao` completos; `/`, `/contato`, `/produtos`, `/pedidos`, `/conta` e `/agendamentos` existem como stubs de rota, aguardando as APIs de backend correspondentes (Fases 5–6).
- [~] **Fase 8 — Frontend: Widget de Chat Multimodal**: Botão flutuante, painel, envio de texto/áudio, persistência de conversa e indicadores de domínio/origem do modelo prontos; faltam streaming (SSE), upload de imagem, cards ricos e banner de transferência humana — dependem de R6/R8/R11/R12 no backend.
- [~] **Fase 9 — Integração Ponta a Ponta**: Testes E2E de chat (texto/áudio) prontos com mocks; faltam testes de integração multi-domínio no backend e os fluxos E2E de imagem/pedido/login.
- [ ] **Fase 10 — Avaliação Experimental**: Execução dos benchmarks de acurácia, qualidade RAG, latência local vs externo e comparação dos 9 modelos locais.
- [ ] **Fase 11 — Preparação da Entrega**: Checklist final de requisitos R1–R12 e consolidação da demonstração do TCC.

> Fora das 12 fases do MVP original, dois extras foram entregues a pedido
> explícito (ver `docs/ARCHITECTURE.md` §5 e `docs/ROADMAP.md`): configuração
> de ingestão do RAG (`/admin/ingestao` — perfis de collection, playground de
> busca comparativa) e um gerenciador de modelos locais do Ollama
> (`/admin/modelos`).

---

## 🚀 Como Executar o Projeto

### 1. Pré-requisitos
- **Docker** e **Docker Compose** instalados.
- **Python 3.11+** (testado até 3.14) — recomendamos [`uv`](https://docs.astral.sh/uv/)
  para criar o ambiente virtual: ele baixa/gerencia o próprio interpretador
  isoladamente, sem depender de pacotes extras do sistema operacional (ex.:
  `python3.11-venv`/`python3.14-venv` do apt, que costumam exigir `sudo` e
  nem sempre estão instalados). Sem `uv`, `pip`/`venv` do sistema também
  funcionam, desde que o pacote `venv` da sua versão de Python esteja
  instalado.
- **Node.js 18+** e `npm`.
- **Ollama** instalado e rodando localmente com GPU NVIDIA (`ollama serve`).

### 2. Configuração do Backend
```bash
# Navegar até a pasta do backend
cd backend

# Criar o ambiente virtual com uv (usa um Python 3.11+ já disponível na
# máquina, ou baixa um isolado se preciso — sem precisar de sudo/apt)
uv venv .venv
source .venv/bin/activate

# Copiar modelo de variáveis de ambiente e ajustar credenciais
cp .env.example .env

# Instalar dependências em modo editável (inclui pytest/ruff)
uv pip install -e ".[dev]"

# Garantir que os containers de banco (PostgreSQL e Qdrant) estejam ativos
docker compose up -d postgres qdrant

# Aplicar as migrações do banco (cria a tabela rag_documents, entre outras)
alembic upgrade head

# Iniciar o servidor backend (FastAPI)
uvicorn app.main:app --reload --port 8000
```
> Alternativa sem `uv`: `python3.11 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"` — só funciona se o Python 3.11 e seu pacote `venv` já estiverem instalados no sistema. Se quiser fixar uma versão específica com `uv` (ex.: para bater exatamente com CI), use `uv venv --python 3.11 .venv`.
> O backend estará disponível em `http://localhost:8000` (Documentação Swagger em `http://localhost:8000/docs`).

### 3. Executar o Frontend
```bash
# Em outro terminal, navegar até a pasta do frontend
cd frontend

# Instalar dependências Node.js
npm install

# Iniciar o servidor de desenvolvimento Next.js
npm run dev
```
> O frontend estará disponível em `http://localhost:3000`.

### 4. Testes e Qualidade de Código
```bash
cd backend

# Rodar a suíte de testes unitários e de integração
pytest

# Rodar verificação de lint e formatação
ruff check . && ruff format --check .
```

---

## 📚 Documentação do Projeto

Para detalhes aprofundados sobre cada componente da solução, consulte a documentação técnica na pasta [`docs/`](docs/):

### 📖 Manuais Operacionais (How-To)
- 🛠️ [HOWTO_IMPLANTACAO_INFRA.md](docs/HOWTO_IMPLANTACAO_INFRA.md) — Manual de Implantação e Infraestrutura (GPU, Docker, Ollama, Backend, Frontend e Troubleshooting).
- ⚙️ [HOWTO_ADMINISTRADOR.md](docs/HOWTO_ADMINISTRADOR.md) — Manual do Administrador do Sistema (Gestão RAG/PDFs, Web Crawler, Parametrização da IA em runtime, Catálogo e Tom).
- 👤 [HOWTO_USUARIO.md](docs/HOWTO_USUARIO.md) — Manual do Usuário e Cliente (Recursos do Website + Guia do Chat Multimodal com Texto, Áudio, Imagem e Cards).

### 📐 Especificações Técnicas e Arquitetura
- 📘 [ARCHITECTURE.md](docs/ARCHITECTURE.md) — Visão geral da arquitetura, requisitos funcionais (R1–R12), fluxos de decisão e limitações.
- 💻 [FRONTEND.md](docs/FRONTEND.md) — Especificação da interface Next.js, componentes do widget, rotas e contratos da API REST.
- 🛠️ [TECHNOLOGY_STACK.md](docs/TECHNOLOGY_STACK.md) — Justificativa técnica, versões de bibliotecas e matriz de requisitos.
- 📏 [CONVENTIONS.md](docs/CONVENTIONS.md) — Estrutura do monorepo, convenções de código Python/TypeScript, Git e testes.
- 📊 [EVALUATION.md](docs/EVALUATION.md) — Procedimentos operacionais para as 3 avaliações experimentais (Acurácia, RAG, Latência).
- 🔄 [AGENTIC_WORKFLOW.md](docs/AGENTIC_WORKFLOW.md) — Guia do fluxo de trabalho com agentes de IA (Antigravity IDE e Claude Code CLI).
- 🗺️ [ROADMAP.md](docs/ROADMAP.md) — Lista detalhada de tarefas dividida por 12 fases do MVP.

---

## 📝 Licença e Autoria

- **Autor**: Augusto Quintino ([augustoglauco@gmail.com](mailto:augustoglauco@gmail.com))
- **Projeto**: Trabalho de Conclusão de Curso (TCC)
- **Repositório**: [augustoglauco/TCC](https://github.com/augustoglauco/TCC)
