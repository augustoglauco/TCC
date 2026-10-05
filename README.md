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

1. **🛍️ Vendas**: Consulta a catálogo de produtos, verificação de estoque em tempo real, cálculo de frete, cotação automática, reservas/pedidos e conversão de reserva em venda com comprovação multimodal (leitura de comprovante de pagamento por IA).
2. **🔧 Suporte Técnico**: Resolução de dúvidas técnicas com base em manuais, guias de instalação, esquemas e documentação.
3. **💬 Atendimento ao Usuário**: Informações institucionais, FAQ, políticas da empresa e procedimentos gerais.
4. **📅 Agendamento de Visita**: Marcação e confirmação automatizada de visitas/reuniões integradas ao Google Calendar.

### Principais Diferenciais Arquiteturais

- **Roteador/Orquestrador Inteligente**: Interpreta a intenção e a complexidade da mensagem (analisando o contexto de 1 a 3 mensagens recentes), decidindo entre processamento local em GPU, recuperação por RAG, acionamento de MCPs ou transbordo para modelo externo.
- **Inferência Local Sob Medida (GPU 16GB)**: Utiliza modelos *open-source* quantizados via **Ollama** em GPU dedicada (NVIDIA RTX 4080 16GB VRAM), com controle total de residência em VRAM (`keep_alive`, pré-aquecimento, carregar/liberar sob demanda) para eliminar o cold-start.
- **Escalonamento Transparente**: Recorre a modelos externos via **OpenRouter API** apenas quando a requisição foge ao escopo local, falta relevância no RAG ou exige alta complexidade de raciocínio.
- **Arquitetura Dual MCP (Model Context Protocol)**:
  - **Cliente MCP**: Consome o MCP do Google Calendar para criação automatizada de eventos de agendamento.
  - **Provedor MCP B2B**: Expõe servidor MCP próprio com dados de catálogo, estoque, preços e manuais, além de ferramentas transacionais (compatibilidade, frete, cotação, reserva/pedido e conversão de reserva em venda).
- **Entrada Multimodal**: Suporte nativo a Texto, Áudio (Speech-to-Text via Whisper) e Imagem (OCR para comprovantes/documentos e busca por similaridade visual via embeddings CLIP).
- **RAG com Isolamento por Finalidade**: Collections vetoriais segregadas por finalidade (`chat` pública, `mcp_b2b`, `admin`), com playground de comparação, reingestão entre collections e **card de download do documento-fonte diretamente no chat** quando a busca vetorial bate com alta confiança.
- **Monitoramento de Tom & Atendimento Humano ao Vivo**: Analisa continuamente o sentimento/urgência da conversa, escala para um atendente humano real (fila de transbordo, *claim* atômico, pausa automática da IA durante o atendimento) com interface dedicada de operador.
- **Painel Administrativo Completo**: gestão de usuários, ingestão e configuração do RAG, web crawler, gerenciador de modelos locais (Ollama), importação inteligente de catálogos (PDF/imagem via visão computacional), gestão de pedidos, dashboards e gráficos analíticos dinâmicos gerados sob demanda pelo próprio chat (Text-to-SQL), e métricas de custo/tokens.
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
            ├──► RAG Híbrido (PostgreSQL, PDFs, CLIP) └──► Atendimento Humano ao Vivo
            ├──► Modelo Local (Ollama - GPU 16GB)            (Fila de Transbordo + Operador)
            ├──► Modelo Externo (OpenRouter API)
            ├──► Cliente MCP (Google Calendar — Agendamento)
            └──► Servidor MCP B2B (Catálogo, Estoque, Pedidos)
            │
            ▼
       Resposta ao Usuário (Streaming SSE / Cards Ricos)
```

### Assimetria Intencional dos Domínios no MVP
- **Vendas** e **Agendamento de Visita** contam com camadas de ação dedicadas via MCP (MCP B2B próprio e MCP Google Calendar, respectivamente).
- **Suporte Técnico** e **Atendimento ao Usuário** são resolvidos no protótipo pela combinação de LLM + RAG (PDFs, manuais, crawler web), sem integração a sistemas externos de *ticketing* — a transferência para humano, quando necessária, usa a Central de Atendimento interna do próprio sistema (não um ticketing externo).

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
| **R12** | **Servidor MCP B2B** | Exposição de catálogo/estoque e ferramentas transacionais (compatibilidade, frete, cotação, pedido, conversão de reserva em venda). |

---

## 🛠️ Stack Tecnológica

### Backend (Python + FastAPI)
- **Linguagem & Framework**: Python 3.14, [FastAPI](https://fastapi.tiangolo.com/) (Async-first, suporte a Server-Sent Events), Uvicorn, Pydantic v2.
- **Inferência Local**: [Ollama](https://ollama.com/) servindo modelos quantizados GGUF (ex.: `gemma4:12b-it-q4_K_M`, Llama 3.1 8B, Qwen2.5/3, Phi-4 — ver avaliação comparativa em `docs/EVALUATION.md`).
- **Inferência Externa**: [OpenRouter API](https://openrouter.ai/) via `httpx` (texto, visão e classificador estruturado Jev).
- **Banco Relacional & ORM**: PostgreSQL 15 via [SQLAlchemy 2.0](https://www.sqlalchemy.org/) (`asyncpg`) e Alembic para migrações.
- **Banco Vetorial**: [Qdrant](https://qdrant.tech/) rodando em container Docker, com collections segregadas por finalidade (`chat`, `mcp_b2b`, `admin`) e por domínio de imagem.
- **Embeddings & Visão**: `sentence-transformers` (texto, `paraphrase-multilingual-MiniLM-L12-v2`), `CLIP ViT-B/32` (imagens) e `pytesseract` / Tesseract (OCR).
- **Processamento de Áudio**: `faster-whisper` (local, STT).
- **Protocolo MCP**: SDK oficial MCP em Python ([modelcontextprotocol](https://github.com/modelcontextprotocol)).
- **Qualidade & Linters**: `ruff` (linter/formatter) e `pytest`/`pytest-asyncio` (testes unitários e de integração).

### Frontend (Next.js + TypeScript)
- **Framework Web**: Next.js 16 (App Router), React 19, TypeScript 5 em modo `strict`.
- **Estilização & UI**: Tailwind CSS 4, Radix UI (dialog, tabs).
- **Gestão de Estado**: `Zustand` 5 (estado do widget de chat e autenticação).
- **Comunicação em Tempo Real**: `fetch` + `ReadableStream` (Server-Sent Events) para streaming de respostas.
- **Cards Ricos**: Componentes para produto, cotação B2B, confirmação de agendamento, gráfico analítico dinâmico (Admin) e download do documento-fonte do RAG.
- **Qualidade & Testes**: Vitest 4 + Testing Library, Playwright (E2E), ESLint 9, Prettier 3.

### Infraestrutura & DevOps
- **Containerização**: Docker & Docker Compose (PostgreSQL, Qdrant).
- **Hardware de Desenvolvimento**: GPU NVIDIA com 16GB VRAM e driver com suporte a CUDA.
- **Acesso Público**: Caddy + DuckDNS para o endpoint HTTPS do MCP B2B (ver `goup.md`).

---

## 📂 Estrutura do Repositório (Monorepo)

O projeto adota a estrutura de monorepo, mantendo backend, frontend, testes e documentação no mesmo repositório:

```text
.
├── CLAUDE.md                   # Instruções de desenvolvimento para Claude Code CLI
├── .agents/                    # Regras do workspace para Antigravity IDE
├── .kiro/                      # Regras e agentes para o Kiro CLI
├── docs/                       # Documentação técnica e fonte de verdade
│   ├── ARCHITECTURE.md         # Arquitetura, requisitos e escopo do MVP
│   ├── FRONTEND.md             # Especificação da UI, rotas Next.js e contratos de API
│   ├── CONVENTIONS.md          # Padrões de código, estrutura e regras do Git
│   ├── EVALUATION.md           # Detalhamento operacional das avaliações experimentais
│   ├── TESTE_LOCAL.md          # Teste na máquina do desenvolvedor (./testar.sh) e roteiros manuais
│   ├── Manuais/                # Manuais do usuário, administrador e mapa de prompts/instruções LLM
│   ├── AGENTIC_WORKFLOW.md     # Guia de colaboração com agentes de IA (Antigravity/Kiro/Claude)
│   └── ROADMAP.md              # Checklist de desenvolvimento por fases (Fase 0 a 11 + extras)
├── backend/                    # Código-fonte da aplicação Backend (FastAPI)
│   ├── src/app/
│   │   ├── api/                 # Rotas HTTP/SSE: chat, rag, admin_* (ingestão, produtos, pedidos,
│   │   │                        # atendimento, charts, métricas, runtime-settings), crawler, auth
│   │   ├── router/               # Roteador/Orquestrador, clientes LLM (Ollama/OpenRouter), playbooks
│   │   ├── rag/                   # Pipeline de ingestão, embeddings, busca Qdrant e crawler
│   │   ├── services/               # Dashboards/Text-to-SQL, atendimento humano, avaliação de
│   │   │                           # comprovantes, métricas de ingestão, fechamento de conversas
│   │   ├── catalog_extractor/       # Extração estruturada de catálogos (PDF/Imagem/Texto)
│   │   ├── model_catalog/            # Catálogo de características dos modelos locais/externos
│   │   ├── stt/                       # Transcrição de áudio em texto (Whisper)
│   │   ├── ocr/                        # Extração de texto e leitura de imagens
│   │   ├── tone_monitor/                # Análise de sentimento, urgência e alerta
│   │   ├── mcp_client/                   # Cliente MCP (Google Calendar)
│   │   ├── mcp_server/                    # Servidor MCP B2B (catálogo, estoque, ferramentas)
│   │   ├── memory/                         # Persistência de sessões e sumarização automática
│   │   ├── user_profile/                    # Classificação de usuários (Cliente/Lead/Esporádico)
│   │   ├── db/                               # Modelos SQLAlchemy, engine e sessão PostgreSQL
│   │   ├── models/                            # Schemas de validação Pydantic v2
│   │   └── config.py                           # Configurações globais (`pydantic-settings`)
│   ├── migrations/              # Versionamento do schema PostgreSQL (Alembic)
│   ├── eval/                    # Artefatos e scripts das avaliações experimentais
│   │   ├── router_intents/      # Benchmark de acurácia e matriz de confusão 4x4
│   │   ├── rag_quality/         # Avaliação de qualidade (Ground Truth + LLM-as-Judge)
│   │   └── latency/             # Benchmark de latência (GPU Local vs API Externa)
│   ├── tests/                   # Suíte de testes automatizados (pytest)
│   ├── pyproject.toml           # Dependências Python, ruff e configurações do pytest
│   └── .env.example             # Modelo de variáveis de ambiente
└── frontend/                    # Interface Web e Widget de Chat (Next.js)
    ├── app/                      # Rotas App Router: `/`, `/produtos`, `/pedidos`, `/agendamentos`,
    │                             # `/conta`, `/suporte`, `/admin/*` (usuarios, ingestao, modelos,
    │                             # produtos, pedidos, atendimento, dashboards, metricas, agendamentos)
    ├── components/                # ChatWidget e cards ricos, componentes admin, gráficos, UI
    ├── lib/                        # Clientes API HTTP, hooks e estado Zustand
    ├── tests/                      # Testes de componentes (Vitest) e E2E (Playwright)
    └── package.json                # Dependências do Node.js
```

---

## 📊 Avaliação Experimental (`eval/`)

Como requisito metodológico do TCC, o protótipo é submetido a três baterias de avaliações quantitativas e qualitativas (Fase 10, em andamento — conjuntos de teste já montados, execuções finais pendentes):

1. **🎯 Acurácia do Roteador de Intenções (`eval/router_intents/`)**:
   - Avaliação com mensagens rotuladas cobrindo os 4 domínios + casos ambíguos.
   - Geração da **Matriz de Confusão 4x4** e cálculo da acurácia global de classificação.
2. **📚 Qualidade das Respostas do RAG (`eval/rag_quality/`)**:
   - Bateria de perguntas com respostas esperadas conhecidas (*ground truth*).
   - Avaliação dupla: nota manual (1 a 5) e avaliação automatizada via *LLM-as-Judge* (relevância, correção e uso da fonte).
3. **⚡ Latência e Custo: Modelo Local vs. Modelo Externo (`eval/latency/`)**:
   - Medição do tempo de resposta ponta a ponta (média e percentil $p_{95}$) e consumo de tokens.
   - Comparação empírica entre inferência local em GPU (Ollama) e chamada externa (OpenRouter).
4. **🔬 Benchmark Comparativo entre 9 Modelos Locais**:
   - Avaliação comparativa de 9 configurações de modelos em GPU de 16GB (Llama 3.1 8B, Qwen2.5 7B, Qwen3 14B Q4/Q5, Qwen3 8B Q5/Q8, Phi-4-mini/Phi-4, Gemma-4-12B 4-bit/8-bit) contra o sistema completo (com RAG e playbooks reais).

---

## 🗺️ Status e Roadmap de Desenvolvimento

O progresso é estruturado em fases sequenciais conforme documentado em [`docs/ROADMAP.md`](docs/ROADMAP.md). **As Fases 0 a 9 do MVP original estão concluídas**:

- [x] **Fase 0 — Fundamentos e Infraestrutura**
- [x] **Fase 1 — Modelo Local e Roteador Básico** (R1, R3)
- [x] **Fase 2 — Entrada Multimodal e RAG Textual** (R2, R4, R5)
- [x] **Fase 3 — RAG Multimodal, Tratamento de Imagem e Domínios** (R4, R6, R7)
- [x] **Fase 4 — Agendamento via MCP e Monitor de Tom** (R8, R11) — inclui a Central de Atendimento Humano ao Vivo (fila de transbordo, pausa automática da IA, interface de operador)
- [x] **Fase 5 — MCP B2B Provido pela Empresa** (R12)
- [x] **Fase 6 — Memória e Classificação do Usuário** (R9, R10)
- [x] **Fase 7 — Frontend: Site Institucional, Produtos e Pedidos**
- [x] **Fase 8 — Frontend: Widget de Chat Multimodal**
- [x] **Fase 9 — Integração Ponta a Ponta e Robustez**
- [~] **Fase 10 — Avaliação Experimental**: conjuntos de teste (roteador e RAG) já montados; execução dos benchmarks comparativos de modelo local, medição de latência e consolidação do relatório final ainda pendentes.
- [~] **Fase 11 — Preparação da Entrega**: revisão final dos 12 requisitos funcionais, atualização de documentação e demonstração ponta a ponta ainda pendentes.

> Além das 12 fases do MVP original, diversos recursos extras foram entregues
> a pedido explícito ao longo do projeto (ver `docs/ARCHITECTURE.md` §5 e
> `docs/ROADMAP.md`): configuração avançada de ingestão do RAG com isolamento
> por finalidade (`/admin/ingestao`), gerenciador de modelos locais do Ollama
> com controle de VRAM (`/admin/modelos`), gestão e importação inteligente de
> catálogos com visão computacional (`/admin/produtos`), gestão de pedidos e
> conversão de reserva em venda com comprovação multimodal
> (`/admin/pedidos`), dashboards e gráficos analíticos dinâmicos gerados via
> chat por um agente Text-to-SQL (`/admin/dashboards`), métricas de custo e
> tokens (`/admin/metricas`), e download do documento-fonte do RAG via card
> rico diretamente no chat público.
>
> Um único item segue fora do MVP por decisão consciente, pendente de uma
> nova decisão de arquitetura antes de ser implementado: avaliar se vale a
> pena adicionar suporte a visão multimodal ao modelo local (hoje só texto),
> para identificação de produtos por imagem sem depender de um modelo
> externo pago.

---

## 🚀 Como Executar o Projeto

### 1. Pré-requisitos
- **Docker** e **Docker Compose** instalados.
- **Python 3.14+** — recomendamos [`uv`](https://docs.astral.sh/uv/)
  para criar o ambiente virtual: ele baixa/gerencia o próprio interpretador
  isoladamente, sem depender de pacotes extras do sistema operacional (ex.:
  `python3.14-venv` do apt, que costuma exigir `sudo` e nem sempre está
  instalado). Sem `uv`, `pip`/`venv` do sistema também funcionam, desde que
  o pacote `venv` da sua versão de Python esteja instalado.
- **Node.js 20+** e `npm`.
- **Ollama** instalado e rodando localmente com GPU NVIDIA (`ollama serve`).

### 2. Configuração do Backend
```bash
# Navegar até a pasta do backend
cd backend

# Criar o ambiente virtual com uv (usa um Python 3.14+ já disponível na
# máquina, ou baixa um isolado se preciso — sem precisar de sudo/apt)
uv venv .venv
source .venv/bin/activate

# Copiar modelo de variáveis de ambiente e ajustar credenciais
cp .env.example .env

# Instalar dependências em modo editável (inclui pytest/ruff)
uv pip install -e ".[dev]"

# Garantir que os containers de banco (PostgreSQL e Qdrant) estejam ativos
docker compose up -d postgres qdrant

# Aplicar as migrações do banco
alembic upgrade head

# Iniciar o servidor backend (FastAPI)
uvicorn app.main:app --reload --port 8000
```
> Alternativa sem `uv`: `python3.14 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"` — só funciona se o Python 3.14 e seu pacote `venv` já estiverem instalados no sistema. Se quiser fixar uma versão específica com `uv` (ex.: para bater exatamente com CI), use `uv venv --python 3.14 .venv`.
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
> O frontend estará disponível em `http://localhost:3001`.

### 4. Testes e Qualidade de Código
```bash
cd backend

# Rodar a suíte de testes unitários e de integração
pytest

# Rodar verificação de lint e formatação
ruff check . && ruff format --check .
```

```bash
cd frontend

# Rodar a suíte de testes de componentes
npm test

# Rodar verificação de tipos e lint
npx tsc --noEmit && npx eslint .
```

> Para subir todo o ambiente de uma vez (containers, backend e frontend), veja `./g.sh` e o guia completo em [`goup.md`](goup.md).

---

## 📚 Documentação do Projeto

Para detalhes aprofundados sobre cada componente da solução, consulte a documentação técnica na pasta [`docs/`](docs/):

### 📖 Manuais Operacionais (How-To)
- 🛠️ [goup.md](goup.md) — Instalação inicial, subida do ambiente a cada sessão, acesso externo, MCP B2B público (com o manual do parceiro) e solução de problemas.
- ⚙️ [HOWTO_ADMINISTRADOR.md](docs/Manuais/HOWTO_ADMINISTRADOR.md) — Manual do Administrador do Sistema (Gestão RAG/PDFs, Web Crawler, Parametrização da IA em runtime, Catálogo, Pedidos, Dashboards, Métricas, Atendimento Humano).
- 👤 [HOWTO_USUARIO.md](docs/Manuais/HOWTO_USUARIO.md) — Manual do Usuário e Cliente (Recursos do Website + Guia do Chat Multimodal com Texto, Áudio, Imagem e Cards).
- 🧭 [PROMPTS_E_INSTRUCOES_LLM.md](docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md) — Mapeamento de todos os prompts e instruções enviados a um LLM no código.

### 📐 Especificações Técnicas e Arquitetura
- 📘 [ARCHITECTURE.md](docs/ARCHITECTURE.md) — Visão geral da arquitetura, requisitos funcionais (R1–R12), fluxos de decisão e limitações.
- 💻 [FRONTEND.md](docs/FRONTEND.md) — Especificação da interface Next.js, componentes do widget, rotas e contratos da API REST.
- 🧪 [TESTE_LOCAL.md](docs/TESTE_LOCAL.md) — Teste na máquina do desenvolvedor (`./testar.sh`) e roteiros manuais.
- 📏 [CONVENTIONS.md](docs/CONVENTIONS.md) — Stack (bibliotecas e versões), estrutura do monorepo, convenções de código Python/TypeScript, Git e testes.
- 📊 [EVALUATION.md](docs/EVALUATION.md) — Procedimentos operacionais para as avaliações experimentais (Acurácia, RAG, Latência, Comparativo de Modelos).
- 🔄 [AGENTIC_WORKFLOW.md](docs/AGENTIC_WORKFLOW.md) — Guia do fluxo de trabalho com agentes de IA (Antigravity IDE, Kiro CLI e Claude Code CLI).
- 🗺️ [ROADMAP.md](docs/ROADMAP.md) — Lista detalhada de tarefas dividida por fases do MVP e entregas além do MVP.

---

## 📝 Licença e Autoria

- **Autor**: Augusto Quintino ([augustoglauco@gmail.com](mailto:augustoglauco@gmail.com))
- **Projeto**: Trabalho de Conclusão de Curso (TCC)
- **Repositório**: [augustoglauco/TCC](https://github.com/augustoglauco/TCC)
