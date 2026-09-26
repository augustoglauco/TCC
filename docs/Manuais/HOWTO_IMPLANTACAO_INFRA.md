# 🛠️ Manual de Implantação e Infraestrutura (How-To)

> **Público-Alvo**: Equipes de Infraestrutura, DevOps e Administradores de Sistemas (Sysadmins).  
> **Objetivo**: Orientar o provisionamento de ambiente, instalação de dependências, configuração de infraestrutura containerizada (PostgreSQL, Qdrant), servidor de inferência GPU (Ollama), serviços FastAPI (Backend), Next.js (Frontend), barramento de comunicação MCP e rotinas de manutenção/troubleshooting.

---

## 📋 Sumário

1. [📌 Pré-requisitos de Hardware e Software](#-pré-requisitos-de-hardware-e-software)
2. [🐳 Passo 1: Infraestrutura Containerizada (Docker)](#-passo-1-infraestrutura-containerizada-docker)
3. [🤖 Passo 2: Configuração da Inferência GPU Local (Ollama)](#-passo-2-configuração-da-inferência-gpu-local-ollama)
4. [🐍 Passo 3: Configuração do Backend (FastAPI & Python)](#-passo-3-configuração-do-backend-fastapi--python)
5. [📚 Passo 4: Inicialização da Base RAG e Vetores](#-passo-4-inicialização-da-base-rag-e-vetores)
6. [🔌 Passo 5: Configuração dos Provedores e Clientes MCP](#-passo-5-configuração-dos-provedores-e-clientes-mcp)
7. [💻 Passo 6: Configuração e Build do Frontend (Next.js)](#-passo-6-configuração-e-build-do-frontend-nextjs)
8. [📊 Passo 7: Logs, Monitoramento e Troubleshooting](#-passo-7-logs-monitoramento-e-troubleshooting)

---

## 📌 Pré-requisitos de Hardware e Software

### Hardware Mínimo Recomendado
* **GPU**: NVIDIA dedicada com **16GB de VRAM** (ex.: RTX 4080, RTX 3090 ou A4000) com suporte a CUDA 11.8+.
* **Processador**: 8 núcleos / 16 threads (Intel i7/i9 ou AMD Ryzen 7/9).
* **Memória RAM**: 32 GB RAM de sistema.
* **Armazenamento**: 100 GB SSD NVMe (para imagens Docker, coleções Qdrant e pesos dos modelos quantizados Ollama GGUF).

### Software do Sistema Operacional
* **SO**: Ubuntu 22.04 LTS (ou subsistema WSL2 no Windows 11).
* **Drivers NVIDIA**: Driver 535+ com NVIDIA Container Toolkit instalado.
* **Docker & Docker Compose**: Docker Engine 24.0+ e Compose v2+.
* **Python**: Versão 3.11+.
* **Node.js**: Versão 18.x ou 20.x LTS com `npm`.

---

## 🐳 Passo 1: Infraestrutura Containerizada (Docker)

O sistema utiliza PostgreSQL (conector de leitura R4, memória R9, perfil
R10, catálogo do MCP B2B R12) e Qdrant (banco de dados vetorial para RAG
multimodal). O `docker-compose.yml` **já existe no repositório**
(`backend/docker-compose.yml`) — não precisa criar nada, só subir:

1. Navegue até a pasta do backend:
   ```bash
   cd backend
   ```

2. Suba os dois serviços (comando real, Docker Compose v2 — sem hífen):
   ```bash
   docker compose up -d postgres qdrant
   ```

3. Verifique a execução dos containers:
   ```bash
   docker compose ps
   ```

> **Portas deslocadas do padrão de propósito** — esta é uma decisão
> registrada no próprio `docker-compose.yml`: as portas do HOST são
> **5433** (Postgres) e **6335**/**6336** (Qdrant HTTP/gRPC), não as
> portas padrão 5432/6333/6334 — para não conflitar com Postgres/Qdrant de
> outros projetos rodando na mesma máquina de desenvolvimento. Dentro do
> container a porta continua a padrão; só o mapeamento host:container
> muda. `POSTGRES_DSN`/`QDRANT_PORT` em `.env.example` já refletem isso —
> não altere só um lado do par porta-host/env var.

---

## 🤖 Passo 2: Configuração da Inferência GPU Local (Ollama)

O Ollama é responsável por servir localmente os modelos de linguagem em GPU sem dependência externa.

1. **Instalação do Ollama no Host Linux**:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. **Verificação de Aceleração por GPU**:
   Certifique-se de que a GPU NVIDIA é detectada pelo Ollama:
   ```bash
   nvidia-smi
   ```

3. **Download dos Modelos Necessários para o MVP**:
   Execute o pull dos modelos homologados para inferência local:
   ```bash
   # Modelo Principal de Linguagem / Roteamento (Llama 3.1 8B ou Qwen 2.5 7B)
   ollama pull llama3.1:8b
   ollama pull qwen2.5:7b

   # (Opcional) Outros modelos suportados
   ollama pull phi4
   ```

4. **Testar Serviço Ollama**:
   O Ollama roda por padrão na porta `11434`. Teste o endpoint HTTP:
   ```bash
   curl http://localhost:11434/api/tags
   ```

---

## 🐍 Passo 3: Configuração do Backend (FastAPI & Python)

> **Ferramenta real: `uv`, não `pip`/`venv` puro** — este projeto usa
> [`uv`](https://docs.astral.sh/uv/) (`backend/pyproject.toml` +
> `backend/uv.lock`), não `requirements.txt`. `uv` baixa/gerencia o próprio
> interpretador Python isoladamente, sem depender de pacotes extras do SO.
> Alternativa sem `uv`: `python3.11 -m venv .venv && source
> .venv/bin/activate && pip install -e ".[dev]"` — só funciona se o Python
> 3.11+ e seu pacote `venv` já estiverem instalados no sistema.

1. **Navegue até o diretório do backend**:
   ```bash
   cd backend
   ```

2. **Crie o ambiente virtual com `uv`**:
   ```bash
   uv venv .venv
   source .venv/bin/activate
   ```

3. **Instale as dependências** (modo editável, inclui `pytest`/`ruff`):
   ```bash
   uv pip install -e ".[dev]"
   ```

4. **Configuração de Variáveis de Ambiente (`.env`)**:
   Copie o modelo real do projeto — **não crie um `.env` do zero**, os
   nomes de variável abaixo são os que o backend de fato lê
   (`backend/src/app/config.py`):
   ```bash
   cp .env.example .env
   ```
   Principais grupos de variáveis (ver `backend/.env.example` para a lista
   completa e comentada — inclui RAG, crawler, agendamento, MCP B2B):
   ```ini
   # Aplicação
   APP_ENV=development
   LOG_LEVEL=INFO

   # Modelo local (Ollama)
   LOCAL_MODEL_BASE_URL=http://localhost:11434
   LOCAL_MODEL_NAME=llama3.1:8b

   # Modelo externo via OpenRouter (roteador, transbordo/fallback)
   EXTERNAL_MODEL_BASE_URL=https://openrouter.ai/api/v1
   EXTERNAL_MODEL_API_KEY=changeme
   EXTERNAL_MODEL_NAME=   # formato "provider/model", ex.: anthropic/claude-3.5-haiku

   # Qdrant (RAG texto/imagem) — porta 6335, ver Passo 1
   QDRANT_HOST=localhost
   QDRANT_PORT=6335

   # PostgreSQL — porta 5433, ver Passo 1
   POSTGRES_DSN=postgresql+asyncpg://postgres:postgres@localhost:5433/assistente

   # STT local (faster-whisper)
   STT_MODEL_SIZE=small

   # MCP do Google Calendar — ver Passo 5 abaixo (servidor de terceiro
   # self-hosted, não credenciais direto no .env do backend)
   CALENDAR_MCP_URL=http://127.0.0.1:8090/mcp
   ```
   Requisitos multimodais/OCR (Tesseract) não são configurados por env var
   neste projeto — o binário `tesseract` só precisa estar no `PATH` do
   sistema (`sudo apt install tesseract-ocr tesseract-ocr-por`).

5. **Execução de Migrações do Banco de Dados (Alembic)**:
   ```bash
   .venv/bin/alembic upgrade head
   ```

6. **Iniciar Servidor Backend em Desenvolvimento**:
   ```bash
   .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   Documentação Swagger em `http://localhost:8000/docs`.

---

## 📚 Passo 4: Inicialização da Base RAG e Vetores

Para que o RAG funcione nos domínios de Vendas, Suporte e Atendimento —
scripts reais de `backend/scripts/` (rodar a partir de `backend/`, com
Postgres/Qdrant no ar e a migração do Alembic já aplicada):

1. **Ingerir os documentos de exemplo do RAG** (PDFs/textos já incluídos
   em `backend/scripts/sample_docs/`, um domínio por subpasta):
   ```bash
   .venv/bin/python scripts/ingest_sample_docs.py
   ```

2. **(Opcional) Ingerir uma tabela do banco relacional** — conector de
   leitura R4, tabela fixture `produtos` criada/semeada pela própria
   migração do Alembic (passo anterior):
   ```bash
   .venv/bin/python scripts/ingest_db_table.py --table produtos --domain vendas
   ```

> Não existem scripts `seed_products`/`ingest_catalog_images` neste
> projeto — o catálogo de produtos de exemplo já vem semeado pela migração
> do Alembic (tabela `produtos`); imagens de catálogo para a busca
> multimodal (CLIP) são ingeridas via `POST /api/rag/images`
> (`backend/src/app/api/image_search.py`), sem UI dedicada no frontend
> ainda nem script de linha de comando — chame o endpoint diretamente.

---

## 🔌 Passo 5: Configuração dos Provedores e Clientes MCP

A plataforma opera com arquitetura **Dual MCP**:

1. **Cliente MCP (Google Calendar) — atualizado em 2026-09-23**:
   - O backend **não fala mais direto com o MCP remoto oficial do Google**
     (`calendarmcp.googleapis.com`) — esse serviço está em Developer
     Preview e não aceita contas Gmail pessoais (ver `docs/ARCHITECTURE.md`
     §5). Em vez disso, consome um MCP de terceiro self-hosted,
     [`calendar-mcp-server`](https://github.com/deciduus/calendar-mcp)
     (pacote PyPI, Python), rodando como processo local separado.
   - Instale/rode com `uvx` (não precisa `pip install` manual): crie um
     OAuth Client ID tipo **"App para computador"** no Google Cloud
     Console (com a Google Calendar API habilitada), rode
     `calendar-mcp-server auth` uma vez (`GOOGLE_CLIENT_ID`/
     `GOOGLE_CLIENT_SECRET` do client criado, via variável de ambiente) e
     depois `calendar-mcp-server serve --transport http --port 8090` a
     cada sessão. Não existe URI de redirecionamento a configurar no
     Console — o fluxo usa `http://localhost:8080` (porta do próprio
     `calendar-mcp-server`, não a 8000 do backend).
   - Passo a passo completo, com troubleshooting: `docs/GUIA_TESTE_AGENDAMENTO.md`
     §2.2, e o startup consolidado em `goup.md`.
   - O backend só precisa saber onde esse processo está escutando
     (`CALENDAR_MCP_URL=http://127.0.0.1:8090/mcp`, ver Passo 3 acima) —
     não guarda nenhuma credencial OAuth do Google.

2. **Provedor MCP B2B Próprio (Catálogo e Transações B2B) — ainda não implementado**:
   - Faz parte do escopo do MVP (R12, Fase 5 do `docs/ROADMAP.md`), mas
     **nenhuma tarefa da Fase 5 foi concluída ainda** — `src/app/mcp_server/`
     existe como pasta vazia (`__init__.py` sem conteúdo). Não há
     endpoint/comando real para testar hoje; os exemplos de `curl` que
     existiam aqui antes eram aspiracionais, não refletiam o código.
   - Quando a Fase 5 for implementada, atualize esta seção com o comando
     real de start do servidor MCP (`MCP_B2B_HOST`/`MCP_B2B_PORT`, já
     configuráveis em `.env.example`, mas ainda sem consumidor) e a forma
     real de testar as 4 ferramentas (compatibilidade, frete, cotação,
     reserva/pedido) — ver `docs/ARCHITECTURE.md` §6.

---

## 💻 Passo 6: Configuração e Build do Frontend (Next.js)

1. **Navegue até o diretório do frontend**:
   ```bash
   cd ../frontend
   ```

2. **Instale os pacotes Node.js**:
   ```bash
   npm install
   ```

3. **Configure as Variáveis de Ambiente (`frontend/.env.local`)**:
   ```ini
   NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
   ```

4. **Execução em Desenvolvimento**:
   ```bash
   npm run dev
   ```
   *O site estará acessível em `http://localhost:3001`.*

5. **Build para Produção**:
   ```bash
   npm run build
   npm run start
   ```

---

## 📊 Passo 7: Logs, Monitoramento e Troubleshooting

### Logs do Sistema
* **Backend (FastAPI)**: logging estruturado (JSON) só em **stdout** — não há arquivo de log próprio (`backend/logs/app.log` não existe neste projeto). Redirecione você mesmo se quiser persistir (`uvicorn ... > backend.log 2>&1 &`, ver `goup.md`).
* **Ollama**: Verifique logs do serviço via `journalctl -u ollama -f` (Linux) ou no terminal Ollama.
* **Qdrant**: `docker logs -f backend-qdrant-1`
* **PostgreSQL**: `docker logs -f backend-postgres-1`
* **calendar-mcp-server** (agendamento, R11): stdout do processo — ver `goup.md` (`/tmp/tcc-calendar-mcp.log` se subiu pelo script de lá).

### Problemas Frequentes & Soluções (Troubleshooting)

| Sintoma | Causa Provável | Solução |
|---|---|---|
| **Erro `Out of Memory` (VRAM GPU)** | Modelo Ollama muito grande para 16GB VRAM ou concorrência excessiva (ex.: STT/CLIP disputando a mesma GPU, ver `docs/ARCHITECTURE.md` §7). | Alterne para um modelo mais leve (`LOCAL_MODEL_NAME` em `.env`) ou evite rodar identificação de imagem/áudio simultânea a testes pesados de chat. |
| **Resposta lenta ou timeout no Chat** | Falha na comunicação local com Ollama ou fallback externo instável. | Verifique se o serviço Ollama responde em `http://localhost:11434` e valide sua `EXTERNAL_MODEL_API_KEY`. |
| **Extração de agendamento lenta/travando (~50s+)** | Modelo local com capability `thinking` habilitada gera raciocínio interno longo mesmo para respostas curtas (achado real, ver `docs/ARCHITECTURE.md` §5, 2026-09-23). | Já corrigido no código (`OllamaClient.generate()` manda `think: false`) — se voltar a acontecer com um modelo novo, confirme via `ollama show <modelo>` se ele tem a capability `thinking`. |
| **Erro ao processar imagem (OCR)** | Binário `tesseract` não encontrado no PATH do sistema. | Instale o Tesseract: `sudo apt install tesseract-ocr tesseract-ocr-por` (sem variável de ambiente própria neste projeto — só precisa estar no PATH). |
| **Erro na gravação/transcrição de áudio** | Modelo `faster-whisper` (`STT_MODEL_SIZE`) não baixado ou falta da biblioteca `ffmpeg`. | Instale o ffmpeg: `sudo apt install ffmpeg` e certifique-se que a GPU tem VRAM livre (STT roda na mesma GPU do modelo local). |
| **Containers não sobem** | Conflito de porta (`5433` ou `6335`/`6336` já em uso — não `5432`/`6333`, que são as portas *internas* do container, ver Passo 1). | Verifique processos em uso com `sudo lsof -i :5433` ou altere as portas publicadas no `backend/docker-compose.yml` (lembre de atualizar `POSTGRES_DSN`/`QDRANT_PORT` em `.env` junto). |
| **Agendamento falha com "MCP do Google Calendar indisponível"** | `calendar-mcp-server` não está rodando na porta 8090, ou o token expirou. | Ver `docs/GUIA_TESTE_AGENDAMENTO.md` §5 e `goup.md` — confirme com `curl http://127.0.0.1:8090/mcp` (400 = processo no ar; sem resposta = subir de novo). |
