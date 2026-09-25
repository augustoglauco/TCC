# Resumo do Status do Projeto (TCC)

> **Projeto**: Assistente virtual multimodal (texto, imagem e áudio) baseado em arquitetura agêntica com inferência local de IA em GPU (16GB), RAG híbrido, roteamento inteligente, monitor de tom, memória de sessão e integração bidirecional via Protocolo MCP (*Model Context Protocol*).
> **Fontes de Verdade**: `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/FRONTEND.md`, `docs/TECHNOLOGY_STACK.md` e `CLAUDE.md`.

---

## 🟢 O que já está PRONTO e CONCLUÍDO

### **Fase 0 — Fundamentos e Infraestrutura**
* Ambiente provisionado em GPU dedicada (NVIDIA RTX 4080 16GB VRAM, CUDA, Ollama).
* Monorepo estruturado (`backend/` FastAPI + `frontend/` Next.js 16).
* Configuração via `pydantic-settings` (`.env`) e logging estruturado com `conversation_id`.
* Script de validação local automatizado (`./testar.sh` → `backend/scripts/teste_local.py`).

### **Fase 1 — Modelo Local e Roteador Inteligente**
* Cliente local **Ollama** (`gemma4:12b-it-q4_K_M` e suporte a 9 candidatos de 7B–14B) + cliente externo **OpenRouter**.
* Classificador de intenção baseado em LLM + regras considerando histórico curto (1 a 3 mensagens).
* Roteamento dinâmico entre os 4 domínios (Vendas, Suporte, Atendimento, Agendamento).

### **Fase 2 — Entrada Multimodal (Áudio) e RAG Textual**
* **Speech-to-Text (STT)** via **Whisper local em GPU** (WAV, MP3).
* Streaming SSE (`text/event-stream`) de respostas token a token no backend e frontend.
* **RAG Textual Híbrido:** Ingestão de PDFs (com `pdfplumber` e layout 2 colunas), textos e busca vetorial no Qdrant.
* **Conector a Banco Relacional:** Leitura de BD relacional Postgres (somente leitura) via SQLAlchemy.
* **Web Crawler BFS:** Disparo manual via streaming SSE, navegação em profundidade com fila de revisão humana.

### **Fase 3 — RAG Multimodal (Imagem) e Playbooks de Domínio**
* **Tratamento de Imagem:** Entrada de imagens, OCR para comprovantes dirigidos (`pytesseract`).
* **Busca Visual CLIP:** Busca vetorial por embeddings de imagem no Qdrant com reranking.
* **Identificação de Produto por Visão:** CLIP interno → fallback para modelo de visão externo via OpenRouter quando a confiança é baixa.
* **Playbooks por Domínio:** Prompts estruturados para Vendas (com oferta proativa de agendamento), Suporte Técnico e Atendimento.

### **Fase 4 — Agendamento via MCP (Google Calendar) e Monitor de Tom**
* **Fase 4A (MCP Cliente):** Integração com `calendar-mcp-server` para consulta de horários e criação de eventos no Google Calendar + e-mail de confirmação.
* **Fase 4B (Monitor de Tom):** Classificação de sentimento/urgência em tempo real, geração do evento SSE `escalonamento` e tabela `tom_escalonamentos`.

### **Fase 5 — Provedor MCP B2B (Catálogo, Estoque, Preços e Ferramentas Transacionais)**
* **Servidor MCP B2B:** Servidor próprio em Python (`scripts/run_mcp_b2b_server.py` na porta 8100).
* **4 Recursos (Leitura):** `catalog://produtos`, `inventory://estoque`, `pricing://tabelas`, `docs://manuais` (RAG B2B).
* **4 Ferramentas Transacionais:** `validar_compatibilidade`, `consultar_frete`, `cotar`, `reservar_pedido`.
* **Roteador Integrado:** O orquestrador usa o catálogo interno (`SalesCatalogClient`) para intenções de Vendas.
* **Exposição Pública com Segurança:** Publicado em `https://augustoglauco.duckdns.org:8443/mcp` via **DuckDNS + Caddy HTTPS**, protegido por chave estática por parceiro (`Authorization: Bearer <chave>`).
* **Manual de Integração:** Documentação oficial criada em [`docs/MANUAL_INTEGRACAO_MCP_B2B.md`](file:///home/augusto/Projetos/TCC/docs/MANUAL_INTEGRACAO_MCP_B2B.md).

### **Fase 6 — Memória de Sessão e Classificação do Usuário**
* **Persistência de Histórico:** Tabelas `conversas` e `conversa_mensagens` no Postgres.
* **Sumarização Automática:** Resumo da conversa gerado a cada 6 mensagens em segundo plano e injetado no prompt.
* **Retomada de Sessão:** Leitura via `GET /api/chat/conversations/{id}` no widget, reaparecendo histórico e painel de métricas.
* **Classificação de Usuário:** Perfilamento em *Cliente*, *Lead* ou *Esporádico* via cruzamento com compras fictícias e captação natural de e-mail.

### **Fases 7 e 8 — Frontend (Next.js + UI Responsiva)**
* **Modal de Chat Responsivo (`ChatModal`):** Suporte a mobile (<390px), envio de texto/imagem/áudio, streaming token a token, métricas de inferência exportáveis em CSV/JSON.
* **Painel Administrativo:**
  * `/admin/modelos` ("Administração Geral"): Gestão de modelos Ollama, download de modelos/HF GGUF, parâmetros de execução (temperatura, timeouts, roteador Jev) e status do Ollama dinâmico.
  * `/admin/ingestao`: Gestão de documentos, perfis de collection Qdrant, playground comparativo, preview de arquivos e topo da aba *Configuração* com o card **"Regras de Busca & Isolamento de Domínios RAG"**.
* **Páginas Institucionais:** Home, Suporte/Central de Ajuda, Contato, Administração.

---

## 🎁 Funcionalidades Extras Desenvolvidas (Além do Escopo Original do MVP)

1. **Configuração de Ingestão do RAG (`/admin/ingestao`)**: Perfis de collection customizados (chunk size/overlap, HNSW, quantização, payload indexing), playground de busca comparativa e isolamento de collections exclusivas para o canal MCP B2B (`purpose="mcp_b2b"`).
2. **Gerenciador de Modelos Locais (`/admin/modelos`)**: Alternância de modelos locais em runtime, downloads em background e painel de parâmetros de inferência.
3. **Telemetria de Inferência & Fontes RAG**: Exibição por mensagem (tokens, TTFT, TPS, latência, custo, score RAG e fontes utilizadas) e exportação da conversa em CSV/JSON.
4. **Infraestrutura de Exposição MCP B2B Pública**: Proxy TLS Caddy com renovação automática de certificado DuckDNS, permitindo testes externos (4G/5G) sem expor portas de banco.
5. **Resiliência a Dispositivos Móveis e Redes**: Correção de contextos seguros (`crypto.randomUUID`), detecção dinâmica de origem da API (`apiBaseUrl.ts`) e `allowedDevOrigins` no dev server.

---

## 🟡 O que está EM ANDAMENTO / REFINAMENTO (`[~]`)

* **Páginas Adicionais do Site (`app/produtos`, `app/pedidos`, `app/agendamentos`)**: Estão com estruturas e stubs funcionais, aguardando a finalização das páginas públicas correspondentes.
* **Testes E2E (Playwright)**: Fluxo de texto e áudio cobertos no frontend; faltam os cenários E2E de imagem e pedido completo.

---

## ⏳ Próximos Passos (Fases Restantes do Roadmap)

1. **Fase 9 — Integração Ponta a Ponta e Robustez**: Testes de integração backend cobrindo os 4 domínios e refatoração de pequenos achados de code-review.
2. **Fase 10 — Avaliação Experimental (Benchmark de Produção)**:
   * Benchmark das 9 configurações de modelos locais candidatas em GPU de 16GB.
   * Matriz de confusão de acurácia do roteador (4x4).
   * Qualidade do RAG (Ground Truth + LLM-as-Judge).
   * Medição empírica de latência (Local vs. Externo OpenRouter).
3. **Fase 11 — Preparação Final da Entrega**: Checklist final dos requisitos R1–R12 e consolidação do protótipo/demonstração.

---

## 💡 Como Continuar

Peça **"próximo passo"** a qualquer momento — analisaremos o `docs/ROADMAP.md` e avançaremos para a próxima tarefa pendente com testes automatizados e atualização contínua da documentação.
