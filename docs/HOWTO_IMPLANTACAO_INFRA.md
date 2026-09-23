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

O sistema utiliza PostgreSQL (banco relacional de mensagens, sessões e catálogo) e Qdrant (banco de dados vetorial para RAG multimodal).

1. Navegue até o diretório raiz do projeto:
   ```bash
   cd /caminho/para/TCC
   ```

2. Crie ou valide o arquivo `docker-compose.yml` na raiz:
   ```yaml
   version: '3.8'
   services:
     postgres:
       image: postgres:15-alpine
       container_name: tcc_postgres
       restart: always
       environment:
         POSTGRES_USER: postgres
         POSTGRES_PASSWORD: postgrespassword
         POSTGRES_DB: tcc_assistant
       ports:
         - "5432:5432"
       volumes:
         - pgdata:/var/lib/postgresql/data

     qdrant:
       image: qdrant/qdrant:v1.7.4
       container_name: tcc_qdrant
       restart: always
       ports:
         - "6333:6333"
         - "6334:6334"
       volumes:
         - qdrantdata:/qdrant/storage

   volumes:
     pgdata:
     qdrantdata:
   ```

3. Inicie os serviços containerizados:
   ```bash
   docker-compose up -d
   ```

4. Verifique a execução dos containers:
   ```bash
   docker-compose ps
   ```

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

1. **Navegue até o diretório do backend**:
   ```bash
   cd backend
   ```

2. **Crie e ative o ambiente virtual Python**:
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   ```

3. **Instale as dependências**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Configuração de Variáveis de Ambiente (`.env`)**:
   Crie o arquivo `backend/.env` baseado no modelo abaixo:
   ```ini
   # Ambiente
   ENV=production
   LOG_LEVEL=INFO

   # Banco Relacional PostgreSQL
   DATABASE_URL=postgresql+asyncpg://postgres:postgrespassword@localhost:5432/tcc_assistant

   # Banco Vetorial Qdrant
   QDRANT_HOST=localhost
   QDRANT_PORT=6333

   # Provedor de Inferência Local (Ollama)
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_DEFAULT_MODEL=llama3.1:8b

   # Provedor de Inferência Externa (OpenRouter API - Transbordo/Fallback)
   OPENROUTER_API_KEY=sk-or-v1-sua-chave-aqui
   OPENROUTER_DEFAULT_MODEL=meta-llama/llama-3.1-70b-instruct

   # Requisitos Multimodais & OCR
   TESSERACT_CMD=/usr/bin/tesseract
   WHISPER_MODEL_SIZE=base

   # MCP do Google Calendar — ver Passo 5 abaixo (servidor de terceiro
   # self-hosted, não credenciais direto no .env do backend)
   CALENDAR_MCP_URL=http://127.0.0.1:8090/mcp
   ```

5. **Execução de Migrações do Banco de Dados (Alembic)**:
   ```bash
   alembic upgrade head
   ```

6. **Iniciar Servidor Backend em Desenvolvimento/Produção**:
   ```bash
   uvicorn src.app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

---

## 📚 Passo 4: Inicialização da Base RAG e Vetores

Para que o RAG Multimodal funcione nos domínios de Vendas, Suporte e Atendimento:

1. **Popular Dados Iniciais do Catálogo de Produtos**:
   ```bash
   python -m src.app.scripts.seed_products
   ```

2. **Indexar Documentos e Manuais (PDFs/Textos)**:
   Insira os arquivos `.pdf` e `.txt` no diretório `backend/data/docs/` e execute o script de ingestão:
   ```bash
   python -m src.app.scripts.ingest_sample_docs
   ```

3. **Gerar Embeddings Multimodais para Imagens de Catálogo (CLIP)**:
   ```bash
   python -m src.app.scripts.ingest_catalog_images
   ```

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

2. **Provedor MCP B2B Próprio (Catálogo e Transações B2B)**:
   - O backend expõe o servidor MCP interno integrado às tabelas do PostgreSQL e repositório de manuais.
   - Teste o status dos endpoints de ferramentas MCP:
     ```bash
     curl http://localhost:8000/api/v1/mcp/b2b/tools
     ```

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
* **Backend (FastAPI)**: Logs gravados em stdout e em `backend/logs/app.log`.
* **Ollama**: Verifique logs do serviço via `journalctl -u ollama -f` (Linux) ou no terminal Ollama.
* **Qdrant**: `docker logs -f tcc_qdrant`
* **PostgreSQL**: `docker logs -f tcc_postgres`

### Problemas Frequentes & Soluções (Troubleshooting)

| Sintoma | Causa Provável | Solução |
|---|---|---|
| **Erro `Out of Memory` (VRAM GPU)** | Modelo Ollama muito grande para 16GB VRAM ou concorrência excessiva. | Alterne para modelo quantizado 4-bit (`llama3.1:8b`) ou ajuste `OLLAMA_NUM_PARALLEL=1`. |
| **Resposta lenta ou timeout no Chat** | Falha na comunicação local com Ollama ou fallback externo instável. | Verifique se o serviço Ollama responde em `http://localhost:11434` e valide sua `OPENROUTER_API_KEY`. |
| **Erro ao processar imagem (OCR)** | Binário `tesseract` não encontrado no PATH do sistema. | Instale o Tesseract: `sudo apt install tesseract-ocr tesseract-ocr-por` e configure `TESSERACT_CMD`. |
| **Erro na gravação/transcrição de áudio** | Modelo Whisper não baixado ou falta da biblioteca `ffmpeg`. | Instale o ffmpeg: `sudo apt install ffmpeg` e certifique-se que PyTorch tem suporte CUDA. |
| **Containers não sobem** | Conflito de porta (`5432` ou `6333` já em uso). | Verifique processos em uso com `sudo lsof -i :5432` ou altere as portas publicadas no `docker-compose.yml`. |
