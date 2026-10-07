# Roadmap de Implementação

Checklist de tarefas do MVP, organizado por fases com dependências (sem
prazos fixos — a ordem é lógica, não temporal). Cada item referencia o
requisito funcional (`Rn`, ver `docs/ARCHITECTURE.md`, Seção 3). Marque
`- [x]` ao concluir e mantenha os comentários `# MVP: ...` combinados no
código (ver `CLAUDE.md`).

Convenção de status: `- [ ]` pendente · `- [~]` em andamento · `- [x]` feito.

## Fase 0 — Fundamentos e Infraestrutura

- [x] Provisionar ambiente com GPU (mínimo 16GB de VRAM) e stack de
      inferência local (Ollama ou vLLM) — confirmado: NVIDIA RTX 4080 com
      16376MiB de VRAM (`nvidia-smi`), Ollama 0.30.6 instalado e rodando
      (`localhost:11434`), modelo carregado 100% na GPU (`ollama ps`)
- [x] Criar estrutura inicial do repositório conforme `docs/CONVENTIONS.md`
      (monorepo `backend/` + `frontend/`, pastas de módulo vazias)
- [x] Configurar `.env.example` e carregamento de configuração
      (pydantic-settings ou equivalente) — `backend/src/app/config.py`
- [x] Configurar logging estruturado com ID de conversa (pré-requisito de R9)
      — `backend/src/app/logging_config.py` (contextvar + formatter JSON).
      Correção de 2026-09-25: nada preenchia o contextvar e todo log saía com
      `conversation_id: null`; agora `POST /api/chat/messages` o define no
      início da requisição e do stream SSE (`app.api.chat`).
- [x] Configurar lint/format (ruff/black) e pipeline de testes (pytest) —
      `backend/pyproject.toml` ([tool.ruff], [tool.pytest.ini_options])
- [x] Roteiro de teste local para o loop "agente implementa na nuvem,
      desenvolvedor valida na máquina com GPU" —
      `./testar.sh` na raiz atualiza o código, reinicia o backend, roda
      `backend/scripts/teste_local.py` e dá push do relatório em
      `testes_locais/` (primeira suíte: `vendas`, R12). Ver
      `docs/TESTE_LOCAL.md`.

## Fase 1 — Modelo Local e Roteador Básico (R1, R3)

- [x] Subir modelo open-source quantizado 7B–8B via **Ollama** (decisão
      fechada, ver `docs/ARCHITECTURE.md` tabela de escopo) — cliente HTTP
      implementado (`app.router.ollama_client`) com testes; Ollama instalado
      e rodando no ambiente de desenvolvimento (`ollama --version` 0.30.6,
      API respondendo em `localhost:11434`); `OllamaClient` verificado com
      chamada real (não mockada) contra `gemma4:12b-it-q4_K_M`, já disponível
      localmente — resposta correta, todos os campos de `LLMResponse`
      (tokens, breakdown de duração, custo zero) conferidos. A comparação
      entre os 9 candidatos (qual modelo usar como `LOCAL_MODEL_NAME` final)
      fica para a Fase 10 — ver nota ali
- [x] Implementar cliente de modelo externo via **OpenRouter**
- [x] Implementar classificador de intenção simples (regras + LLM) para
      decidir entre modelo local, modelo externo e RAG — domínios
      Vendas/Suporte/Atendimento tentam local+RAG primeiro, escalando para
      externo se fora de escopo, RAG vazio ou complexidade alta;
      Agendamento sempre local. Estratégia de sinal de complexidade
      (heurística ou LLM) selecionável por config
      (`ROUTER_COMPLEXITY_STRATEGY`)
- [x] **Revisitar a resolução de ambiguidade entre domínios no
      classificador (2026-10-04).** Medindo o matcher de verdade mensagem a
      mensagem contra o dataset de `eval/router_intents/` (não só a nota de
      prosa da rodada de 2026-09-30, que estava imprecisa): dos 19 erros da
      heurística pura, só 11 eram "0 domínios casados" (sinônimo fora da
      lista de `_DOMAIN_KEYWORDS`), 7 já casavam 2 domínios ao mesmo tempo
      (conflito real, não lacuna de vocabulário) e 1 era um match único
      errado. Ampliadas 12 keywords (`vendas`: desconto/vende/compatível;
      `suporte`: não liga/manutenção/barulho/resetar/configurar/biometria;
      `atendimento`: reclamar/atraso; `agendamento`: técnico), cada uma
      validada contra as 40 mensagens rotuladas antes de aplicar (zero
      regressão). **Decisão consciente de não resolver os 7 casos de
      conflito por ordem de prioridade fixa**: a mesma dupla de keywords tem
      o gabarito esperado em direções opostas em casos diferentes do
      dataset — uma prioridade fixa acertaria um e erraria o outro, e
      destravaria o atalho rápido da heurística, pulando a consulta ao LLM
      que hoje resolve esses 7 casos corretamente em produção
      (`heuristica_llm`). Resultado: heurística pura sobe de 52,5% para
      77,5% (31/40); `heuristica_llm` continua em 95,0% (não dependia da
      heurística para os 7 casos de conflito) — o caso de match-único-errado
      corrigido (agora cai no LLM em vez de decidir sozinho) passou a errar
      por julgamento genuíno do LLM, mesma categoria de caso discutível já
      documentada. Detalhes completos e tabela comparativa em
      `backend/eval/router_intents/README.md`; testes novos em
      `backend/tests/test_classifier.py`.
- [x] Garantir que o classificador considera as últimas 1–3 mensagens da
      conversa (não só a mensagem isolada), para resolver confirmações
      curtas a ofertas feitas pelo próprio assistente (ex.: aceite de
      agendamento proposto)
- [x] Adicionar log básico de decisões do roteador (intenção escolhida,
      custo/latência estimados)

## Fase 2 — Entrada Multimodal e RAG Textual (R2, R4, R5)

- [x] Implementar entrada de texto e áudio no chat — `POST
      /api/chat/messages` (`backend/src/app/api/chat.py`,
      `backend/src/app/models/chat.py`), encaminhando ao orchestrator com
      histórico em memória por processo (últimas 1-3 mensagens por
      `conversation_id`; desde a Fase 6 esse histórico vem do Postgres, ver
      `app.memory.store`); campo `audio` (base64) processado via STT quando
      presente, com fallback para `payload.message` se a transcrição vier
      vazia (`# MVP: ...`). Resposta passou a ser **streaming via SSE**
      (`text/event-stream`, eventos `conversation`/`transcription`/`status`/
      `token`/`done`/`error`) em vez do JSON síncrono original — ver decisão
      registrada em `docs/ARCHITECTURE.md` §5 ("Streaming SSE do chat") e
      contrato completo em `docs/FRONTEND.md` §4. A busca do RAG
      (`orchestrator.handle_message`) tenta primeiro a mensagem isolada e,
      se vier vazia e houver histórico recente, tenta de novo com o
      histórico concatenado — evita escalar desnecessariamente para o
      externo em mensagens de acompanhamento (ex.: "quais outras opções?")
      — ver decisão registrada em `docs/ARCHITECTURE.md` §5 ("RAG com
      contexto de fallback")
- [x] Implementar STT (áudio → texto) com suporte a pelo menos dois formatos
      comuns (ex.: wav e mp3) — `backend/src/app/stt/whisper_client.py`
      (faster-whisper, GPU local), formato detectado pelo conteúdo dos bytes
- [x] Implementar ingestão de PDFs/textos e busca vetorial (RAG) —
      `backend/src/app/rag/` (`embeddings.py`: sentence-transformers
      `paraphrase-multilingual-MiniLM-L12-v2`, config `RAG_EMBEDDING_MODEL`;
      `chunking.py`: tamanho fixo com overlap, preferindo cortar em quebra
      de linha quando há uma dentro da janela; `pdf_extract.py`:
      `pdfplumber` com detecção de layout em 2 colunas (ver decisão
      registrada em `docs/ARCHITECTURE.md` §5, 2026-09-17 — trocado de
      `pypdf`, que embaralhava a ordem de leitura em catálogos com produtos
      lado a lado);
      `qdrant_client.py`: `QdrantRAGClient`, busca filtrada por `domain` via
      payload filtering na collection `docs_texto`). `NullRAGClient` trocado
      pelo cliente real em `app.main`; conteúdo dos documentos recuperados
      passa a ser injetado no prompt do LLM em `orchestrator.py`
      (`_build_prompt`), preservando a decisão de roteamento (sinal vazio x
      não-vazio) já existente. Ingestão de exemplo:
      `backend/scripts/ingest_sample_docs.py` +
      `backend/scripts/sample_docs/{vendas,suporte,atendimento}/*.txt`.
      Testado contra o Qdrant real (`docker-compose.yml`, porta 6335) e com
      `AsyncQdrantClient(location=":memory:")` nos testes automatizados.
      Fora deste item: reranking (BM25 + score, ver tabela de escopo),
      deduplicação/re-ingestão incremental, conector de BD relacional e
      crawler de sites (itens separados da Fase 2, ver abaixo)
- [x] Implementar conector de leitura a um banco de dados relacional
      (`# MVP: somente leitura, sem sincronização incremental`) —
      `backend/src/app/rag/db_connector.py` (leitura genérica via reflexão de
      tabela do SQLAlchemy, `read_table_as_text`), tabela fixture `produtos`
      criada/semeada por migração
      (`backend/migrations/versions/0003_produtos_fixture.py`), script CLI
      `backend/scripts/ingest_db_table.py` (mesmo padrão de
      `ingest_sample_docs.py`) reaproveitando `app.rag.ingest.ingest_bytes`
      (um documento por linha lida) — decisão registrada em
      `docs/ARCHITECTURE.md` §5
- [x] Implementar crawler disparado manualmente pelo admin a partir de uma
      URL semente (interna ou externa), com profundidade e teto de páginas
      parametrizáveis por execução, sem agendamento (`# MVP: escopo
      restrito`) — ver
      `docs/superpowers/specs/2026-09-19-crawler-paginas-design.md`
- [x] Progresso do crawler em tempo real (SSE): endpoint
      `GET /api/rag/crawler/run/stream` emite eventos por página
      (`visitando`/`ingerida`/`enfileirada`/`erro`/`done`); `crawl_stream()`
      é um gerador assíncrono que centraliza o BFS. No frontend,
      `runCrawlerStream()` consome o SSE (fetch+getReader, mesmo padrão do
      chat) e o `CrawlerPanel` mostra URL atual, contadores ao vivo e um
      heartbeat ("última atividade há Xs") com aviso de possível travamento
      após silêncio prolongado. O `POST /api/rag/crawler/run` clássico
      (síncrono), mantido em paralelo durante a validação do novo fluxo, foi
      **removido** depois que o streaming foi confirmado — o SSE é agora o
      único endpoint de disparo do crawl (dívida técnica quitada). Junto,
      caíram o wrapper `crawl()` e os schemas `CrawlRunRequest`/
      `CrawlRunResponse` do backend e a função `runCrawler()` clássica do
      frontend (o tipo `CrawlRunResponse` do frontend segue como shape do
      evento `done`).
- [x] Implementar endpoint HTTP de upload para ingestão de documentos no RAG
      (`POST /api/rag/documents`, `backend/src/app/api/rag.py`), complementando
      `backend/scripts/ingest_sample_docs.py` — decisão registrada em
      `docs/ARCHITECTURE.md` §5. Reaproveita `app.rag.ingest.ingest_bytes`
      (refatorado a partir de `ingest_file`, que agora delega para a mesma
      função a partir de `path.read_bytes()`); erros de formato de arquivo
      (`.csv` etc.) viram 400, domínio inválido 422 (`Literal` do Pydantic),
      texto não-UTF-8/PDF corrompido também 400 (`UnicodeDecodeError`/
      `PdfExtractionError` tratados explicitamente — sem isso viravam 500
      crus),
      Qdrant indisponível 503

## Extra fora do MVP — Registro e Configuração de Ingestão do RAG

> Pedido explícito do usuário, fora do escopo original do MVP (ver
> `docs/ARCHITECTURE.md` §5 e
> `docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md`).
> Três entregas combinadas na mesma sessão de brainstorming (2026-09-14).

- [x] **Entrega A** — registro de documentos ingeridos (Postgres,
      `rag_documents`) + exclusão (registro + pontos no Qdrant), com página
      `/admin/ingestao` reorganizada em abas (Radix UI)
- [x] **Entregas B+C+D** — perfis de collection configuráveis (chunk
      size/overlap, modelo de embedding/dimensão/métrica de distância,
      HNSW, quantização de vetores, payload indexing) combinadas numa só
      entrega (ficaram interdependentes na sessão de brainstorming de
      2026-09-15), com playground de busca comparativo entre collections e
      reingestão de um documento em outra collection. Ver
      `docs/superpowers/specs/2026-09-15-rag-collections-config-design.md`.
- [x] **Ingestão restrita ao canal MCP B2B** — collections ganham finalidade
      (`purpose`: `chat` vs `mcp_b2b`); o admin ingere documentação exclusiva
      do canal MCP B2B numa collection dedicada `mcp_b2b`, que nunca é ativada
      (ativação bloqueada com 409) nem buscada pelo chat público (guarda de
      defesa em profundidade em `ActiveCollectionRagClient.search`). Só a
      **ingestão + isolamento** (metade 1); o **consumo** dessa collection
      pelo servidor MCP B2B fica na Fase 5 (R12). Segue fora do MVP:
      autenticação por parceiro, isolamento multi-tenant, exposição pública
      (revisto em 2026-09-25: exposição com chave por parceiro entrou no
      MVP, ver Fase 5).
      Ver `docs/superpowers/specs/2026-09-21-ingestao-mcp-b2b-design.md`.
- [x] **Expansão de Finalidades (`purpose`) e UX do Painel de Ingestão (2026-10-03)** —
      Collections ganham suporte a finalidade `admin` (além de `chat` e `mcp_b2b`),
      criando collections exclusivas para buscas administrativas. Painel de Ingestão
      `/admin/ingestao` reorganizado com Master Card unificado e filtros na tabela de
      documentos (nome, domínio, collection, período).
- [x] **Scroll Interno Responsivo com Cabeçalhos Sticky (2026-10-03)** —
      Tabelas de produtos (`/admin/produtos`), catálogo público (`/produtos`) e documentos
      de ingestão (`/admin/ingestao`) passam a utilizar containers com `max-h-[...vh]` e
      scroll interno, preservando os cabeçalhos fixos no topo (sticky header) e melhorando
      significativamente a navegação em celulares (mobile).
- [x] **Especificação Arquitetural de Transbordo para Atendimento Humano (2026-10-03)** —
      Design completo de central de suporte ao vivo (*Human-in-the-Loop / Live Agent Takeover*)
      com locks atômicos, fila simultânea de múltiplos operadores e pausa da IA durante o
      atendimento. Ver `docs/superpowers/specs/2026-10-03-atendimento-humano-transbordo-design.md`.
- [x] **Destaque de Provedor Externo e Roteamento Local de Saudações (2026-10-03)** —
      Respostas do assistente geradas por LLM externo ganham destaque em fundo vermelho clarinho
      (`bg-red-50`). Mensagens `fora_escopo` de baixa complexidade (como saudações "boa noite", "olá")
      passam a ser atendidas diretamente pelo LLM local (Ollama) com o novo `_FORA_ESCOPO_PLAYBOOK`,
      evitando chamadas desnecessárias à nuvem.
- [x] **Uma Collection Ativa Independente por Finalidade e UX da Tabela (2026-10-03)** —
      Evolução do sistema RAG para suportar uma collection ativa independente por `purpose` (`chat`,
      `mcp_b2b` e `admin`). A ativação de uma collection para um purpose desativa apenas a collection
      anterior do mesmo purpose. Adicionado painel visual com cards de collections ativas por finalidade
      na aba Configuração de `/admin/ingestao`, abas de filtro rápido por finalidade na tabela, ativação
      imediata no modal de criação e criação rápida com ativação automática. Substituição dos botões
      de texto "Ativar" e "Excluir" por ícones SVG compactos para eliminar a rolagem horizontal da tabela.
      Portal flutuante adaptativo (`CollectionOptionCard.tsx`) com contagem de arquivos e todos os
      parâmetros técnicos no hover. Playground restrito a comparar collections da mesma finalidade.
- [x] **Desacoplamento do CRUD de Produtos do RAG e Autoridade Única no SQL (2026-10-03)** —
      Remoção do hook de sincronização automática de produtos no RAG (`product_sync.py`), eliminando a
      geração de arquivos sintéticos de texto (`produto_*.txt`) no Qdrant. Catálogo, preços, compatibilidades
      e estoque por CD unificados 100% no PostgreSQL (`SalesCatalogClient` e `app.db.catalog`). Expurgo
      completo dos 14 documentos sintéticos legados do PostgreSQL, do Qdrant e do disco.
- [x] **Catálogo B2B: Estoque Detalhado por CD e Agrupamento de Preços (2026-10-03)** —
      Na tabela de produtos (`/admin/produtos`), exibição do estoque total com tooltip detalhado
      revelando a quantidade por Centro de Distribuição (CD-SP, CD-MG, CD-PR). Agrupamento dos preços
      de revendedor e de venda com destaque visual. Padronização terminológica formal de "fornecedor"
      para "revendedor" em toda a base de código, schemas e migrations.
- [x] **Características Multimodais do Modelo no Hover (2026-10-03)** —
      Componente `ModelCharacteristicsPanel` exibido ao passar o mouse sobre os cards de modelos
      locais e externos em `/admin/modelos`, apresentando janelas de contexto, capacidades de entrada
      e saída (texto, imagem, áudio), provedores e preços por milhão de tokens. Cache persistido no
      PostgreSQL (`model_characteristics`) com expiração de 7 dias e botão de atualização forçada manual.
      Três fontes de dados (OpenRouter API, Ollama `/api/show`, Hugging Face Hub API) e `Tooltip`
      estendido com gatilho customizado — decisão registrada em `docs/ARCHITECTURE.md` §5. Verificação
      manual end-to-end feita via curl contra os três endpoints de características (OpenRouter, Ollama
      instalado e preview Hugging Face), com ambos os modelos de texto e multimodais confirmados.
      Testes novos: `backend/tests/test_model_catalog_characteristics.py`, `backend/tests/test_model_catalog_api.py`,
      `backend/tests/test_model_catalog_schemas.py`, `backend/tests/test_db_models.py`,
      `frontend/tests/components/ModelCharacteristicsPanel.test.tsx`,
      `frontend/tests/lib/hooks/useModelCharacteristics.test.ts`,
      `frontend/tests/lib/api/modelCatalog.test.ts`, `frontend/tests/components/Tooltip.test.tsx`,
      `frontend/tests/components/OpenRouterModelCard.test.tsx`,
      `frontend/tests/components/LocalModelsTable.test.tsx` e
      `frontend/tests/components/PullModelForm.test.tsx`.
- [x] **Residência na VRAM, Warmup de Boot e Persistência de Configurações (2026-10-03)** —
      Configuração do parâmetro `keep_alive` (`"-1"`) no `OllamaClient` para manter o modelo local
      permanentemente carregado na VRAM da GPU, eliminando o cold start de 10-30s após 5 minutos de
      inatividade. Warmup assíncrono não bloqueante via `lifespan` do FastAPI (`preload()`) disparado
      no boot do servidor. Persistência permanente de todos os parâmetros de execução (`RuntimeSettings`)
      na tabela `app_settings` do PostgreSQL (migration Alembic `0017_app_settings.py`), restaurados
      automaticamente no startup. Endpoints operacionais `POST /preload` e `POST /unload` e interface
      completa em `/admin/modelos` com monitor de VRAM em tempo real (GB), seletor de tempo de retenção
      e botões de ação imediata.

## Extra fora do MVP — Gerenciador de Modelos Locais (Ollama)

> Pedido explícito do usuário, fora do escopo original do MVP (ver
> `docs/ARCHITECTURE.md` §5 e
> `docs/superpowers/specs/2026-09-16-local-model-manager-design.md`).

- [x] **Gerenciador de modelos locais** — tela `/admin/modelos` para
      listar/ativar em runtime/baixar (Ollama ou Hugging Face GGUF) modelos
      locais de chat, sem bloquear o backend durante o download. Não
      substitui a escolha formal de produção da Fase 10. Seção "Parâmetros
      de execução" na mesma tela ajusta em runtime a temperatura do modelo
      local, os timeouts local/externo e a flag de fallback de domínio do
      RAG (`GET`/`PUT /api/admin/runtime-settings`) — decisão registrada em
      `docs/ARCHITECTURE.md` §5
- [x] **Provedor alternativo do classificador de intenção — TypeSafe Jev
      (OpenRouter)** — `intent_router_provider` (`"heuristica_llm"` default
      ou `"jev_openrouter"`) na mesma seção "Parâmetros de execução",
      alternando o classificador do roteador entre a heurística local
      (padrão) e o modelo de decisão estruturada Jev via endpoint dedicado
      `POST https://openrouter.ai/api/v1/systemone` do OpenRouter, com
      fallback gracioso para a heurística em qualquer falha — decisão
      registrada em `docs/ARCHITECTURE.md` §5
- [x] **Modelo externo (OpenRouter) trocável em runtime** — card na tela
      `/admin/modelos` com sugestões de modelos populares e gratuitos e
      histórico local; campo `external_model_name` em
      `/api/admin/runtime-settings` (commit `d1c567a`, 2026-09-27; decisão
      registrada em `docs/ARCHITECTURE.md` §5 na revisão de 2026-09-28)
- [x] **Contabilizador de Tokens Internos/Externos, Custos Segregados (Texto + Visão) e Relatórios de Chats Encerrados** —
      Implementado o subsistema de contabilidade de tokens (internos vs. externos) com segregação de custo
      de entrada ($USD) e saída ($USD) para modelos remotos (OpenRouter), incluindo modelo de texto e visão
      computacional externa (`describe_image`). Ciclo de vida da conversa (`conversas.status` aberta/encerrada, `encerrada_em`,
      `motivo_encerramento`, migração Alembic `0018_conversas_status_custos.py`) com botão de encerramento
      manual no widget e worker de inatividade de 30 minutos em background (`inactivity_closure_worker`).
      Endpoint analítico `GET /api/admin/metrics/tokens-and-costs` e dashboard de relatórios em `/admin/metricas` com KPIs
      em tempo real e detalhamento diário (2026-10-04).
      Design Spec em [`docs/superpowers/specs/2026-10-03-contabilizador-tokens-custos-design.md`](docs/superpowers/specs/2026-10-03-contabilizador-tokens-custos-design.md).
      Plano de implementação em [`docs/superpowers/plans/2026-10-03-contabilizador-tokens-custos.md`](docs/superpowers/plans/2026-10-03-contabilizador-tokens-custos.md).
- [x] **Dashboards e Gráficos Dinâmicos Gerados via Chat com Persistência Permanente & Agente Analítico LLM** —
      Permite ao Administrador solicitar gráficos analíticos em linguagem natural no chat
      com pipeline dinâmico inteligente (`AnalyticsAgent`):
      1) Interpreta dados customizados digitados diretamente pelo usuário no prompt (ex: "SP: 150, RJ: 90");
      2) Executa consultas analíticas dinâmicas em Text-to-SQL seguro via PostgreSQL (`safe_sql.py` com SELECT estrito, whitelist de tabelas e limite 50);
      3) Persiste a estrutura declarativa, configurações Recharts e dados na tabela `admin_charts` do
      PostgreSQL (migration `0019_admin_charts.py`).
      Exibição de cards ricos inline (`CardGrafico` / `ChatChartCard`), endpoints REST administrativos
      (`/api/admin/charts`) com suporte a refresh inteligente (`dynamic_sql:` e dados do usuário),
      fixar/desafixar e exclusão, galeria permanente no frontend em `/admin/dashboards` com Recharts,
      e modal de criação manual `CreateChartModal` para inserção direta de dados pelo administrador (2026-10-04).
      Design Spec em [`docs/superpowers/specs/2026-10-04-dashboards-dinamicos-admin-design.md`](docs/superpowers/specs/2026-10-04-dashboards-dinamicos-admin-design.md).
      Planos de implementação em [`docs/superpowers/plans/2026-10-04-dashboards-dinamicos-admin.md`](docs/superpowers/plans/2026-10-04-dashboards-dinamicos-admin.md) e [`docs/superpowers/plans/2026-10-04-llm-dynamic-charts-agent.md`](docs/superpowers/plans/2026-10-04-llm-dynamic-charts-agent.md).
- [x] **Download de Documentos RAG de Origem Direta no Chat via Cards Ricos** —
      Identificar automaticamente documentos fonte no RAG com alto grau de relevância (`score >= 0.65`)
      na busca vetorial do Qdrant e emitir o card rico `CardDocumentoDownload` na resposta do chat.
      Servimento seguro de PDFs/textos via endpoint `GET /api/rag/documents/{id}/download`, com controle
      de permissão por finalidade (`purpose="admin"` exige token) e botão de download direto no widget.
      Design Spec em [`docs/superpowers/specs/2026-10-04-download-documentos-rag-chat-design.md`](docs/superpowers/specs/2026-10-04-download-documentos-rag-chat-design.md).
      Plano de implementação em [`docs/superpowers/plans/2026-10-04-download-documentos-rag-chat.md`](docs/superpowers/plans/2026-10-04-download-documentos-rag-chat.md).

## Extra fora do MVP — Gestão de Produtos no Admin, Ingestão de Catálogos (PDF/Imagens) e Catálogo Visual CLIP

> Pedido explícito do usuário, fora do escopo original do MVP (ver
> `docs/ARCHITECTURE.md` §5 e
> `docs/superpowers/specs/2026-09-25-admin-produtos-catalogo-design.md`).

- [x] **Modelo de Dados & Migração Alembic `0013`** — campos `preco_base_fornecedor` e `imagem_url` adicionados à tabela `produtos`; nova tabela `produto_imagens` criada no Postgres para suportar múltiplas fotos associadas a cada produto com FK cascade e chave para o vetor no Qdrant.
- [x] **Armazenamento e Servimento Estático Seguro** — armazenamento físico em `data/product_images/` com área de rascunho temporária `temp/` para conferência, servimento estático seguro com validação de path traversal e detecção MIME em `GET /api/uploads/produtos/{filename}`.
- [x] **Catálogo Visual CLIP Integrado** — enriquecimento de payload dos vetores no Qdrant (`catalogo_imagens`) com `produto_id` e `imagem_url`, permitindo que fotos cadastradas ou importadas pelo admin sejam imediatamente encontradas pela busca visual no chat.
- [x] **API Administrativa de Produtos & Extração com SSE** — CRUD completo de produtos (`GET/POST/PUT/DELETE /api/admin/produtos`), upload avulso de imagens com indexação CLIP imediata, e pipeline híbrido de extração página a página de PDFs multipáginas e múltiplas imagens (`POST /api/admin/produtos/catalogo/extrair/stream`) com streaming SSE e gravação do lote aprovado (`POST /api/admin/produtos/catalogo/confirmar`).
- [x] **Interface Administrativa Human-in-the-Loop** — tela `/admin/produtos` acessível pelo menu ⚙️ com tabela de produtos, cálculo de margem comercial, cadastro/edição modal e assistente de importação de catálogos com conferência prévia página a página.
- [x] **Importação de catálogo por arrastar/colar e arquivos de texto** — `CatalogImportModal` aceita soltar arquivos sobre o modal, colar (Ctrl+V: imagem, arquivo ou texto, que vira `.txt`), acumula arquivos com remoção individual e recusa tipos não suportados; backend passou a aceitar `.txt`/`.md`/`.csv` (blocos de 6000 caracteres, modelo local). Testes em `test_catalog_extractor.py` e `CatalogImportModal.test.tsx`.

- [x] **Estoque por CD, desconto por volume e compatibilidade no admin** —
      abas no formulário de produto, rotas
      `/api/admin/produtos/{id}/estoque|descontos-volume|compatibilidades` e
      combobox com busca para escolher o produto compatível (commits
      `a6c530d`, `9f3db9a`, `d596282`, 2026-09-27; registrado na revisão de
      2026-09-28)
- [x] **Intervalo de páginas na extração de catálogos PDF** — campo
      `page_range` (`1-5`, `2, 5, 8`, `3-`, `-4`) no upload do extrator
      (commit `bae66bd`, 2026-09-27; registrado na revisão de 2026-09-28)
- [x] **Robustez da visão externa na importação de catálogo** — achado em
      teste manual (2026-10-03): upload de imagem avulsa dependia só da
      visão externa (sem fallback local, que não tem chamada multimodal) e
      uma falha transitória (`429` de modelo `:free` do OpenRouter) virava
      silenciosamente "nenhum produto detectado". `OpenRouterClient.describe_image`
      ganhou retry com backoff curto para status transitório (`429`/`5xx`);
      `CatalogPageResult` ganhou campo `erro` que o `CatalogImportModal`
      exibe distinto de "nenhum produto encontrado". `.env`/`.env.example`:
      `EXTERNAL_VISION_MODEL_NAME` passou a ter um default (`google/gemma-4-31b-it:free`).
      Testes em `test_openrouter_client.py` e `test_catalog_extractor.py`
      (backend) e `CatalogImportModal.test.tsx` (frontend).
- [x] **Investigar visão multimodal no modelo local** — decisão tomada em
      2026-10-06 (`docs/ARCHITECTURE.md` §4, "visão multimodal local
      resolvida"): o `LOCAL_MODEL_NAME` já em produção
      (`gemma4:12b-it-q4_K_M`) já tem capability `vision` nativa (projetor
      CLIP embutido, achado não óbvio), confirmado em teste isolado contra
      imagens reais de produto/comprovante com os prompts exatos de
      produção — não é preciso baixar nem manter residente um segundo
      modelo (Qwen2.5-VL, Gemma 3 etc. foram mapeados como alternativas e
      descartados por ora). A *implementação* (religar visão no fluxo de
      chat/catálogo usando esse achado) é o item novo logo abaixo, ainda
      pendente.

## Fase 3 — RAG Multimodal, Tratamento de Imagem e Domínios (R4, R6, R7)

- [x] Implementar entrada de imagem no chat (fluxo básico)
- [x] Implementar OCR para imagens dirigidas (ex.: comprovante solicitado
      pelo sistema)
- [x] Implementar busca multimodal via embeddings (ex.: CLIP) sobre um
      catálogo de imagens ampliado (`# MVP: catálogo ampliado, não completo`)
- [x] Implementar reranking básico dos resultados de busca por imagem —
      `app.rag.image_search.rerank_image_results`: busca pool maior
      (`top_k * 3`) e reordena com bônus por domínio consultado antes de
      cortar para `top_k` (score exibido inalterado). Decisão registrada em
      `docs/ARCHITECTURE.md` §5; testes em `tests/test_rag_clip.py`
- [x] Implementar fallback para busca externa de imagem quando não encontrado
      no catálogo interno — motor `app.rag.image_identification`
      (`identify_product_by_image`): CLIP interno (aceita se score >=
      `IMAGE_INTERNAL_CONFIDENCE`) → visão externa via OpenRouter
      (`describe_image`, retorna JSON {produto, e_do_portfolio, confianca}) →
      se do portfólio e confiança >= `IMAGE_EXTERNAL_CONFIDENCE`, busca
      detalhes no RAG de texto pelo nome (+ contexto recente); senão "não
      identificado". Endpoint `POST /api/rag/images/identify` e integração no
      chat (imagem sem `image_intent` = identificação, que é o padrão; OCR só
      com `image_intent="documento"`). Três parâmetros parametrizáveis em
      runtime (`EXTERNAL_VISION_MODEL_NAME`, `IMAGE_INTERNAL_CONFIDENCE`,
      `IMAGE_EXTERNAL_CONFIDENCE`) via `/admin/modelos`. Decisão registrada em
      `docs/ARCHITECTURE.md` §4; testes em `tests/test_image_identification.py`,
      `tests/test_image_api.py`, `tests/test_openrouter_client.py`,
      `tests/test_runtime_settings_api.py`.
      > NOTA (atualizada em 2026-10-06): o frontend (MVP) nunca chegou a
      > implementar um botão/estado dedicado de "enviar comprovante" — nunca
      > preenche `image_intent`. Depender só dele deixava o modo documento
      > inatingível mesmo quando o assistente já tinha pedido o comprovante:
      > uma foto legendada "segue comprovante" caía sempre na identificação
      > de produto. `app.api.chat` agora também ativa o modo documento
      > quando a legenda/mensagem junto da imagem bate com a mesma heurística
      > de texto do comprovante sem anexo
      > (`sales_catalog.detectar_intencao_comprovante`) — `image_intent`
      > explícito continua aceito (ex.: telas de admin). Teste de regressão:
      > `test_chat_api_endpoint_comprovante_imagem_sem_image_intent_explicito`
      > em `tests/test_chat_conversao_reserva.py`.
- [x] Separar fluxo/prompts por domínio: Vendas, Suporte Técnico, Atendimento
      ao Usuário, Agendamento de Visita — `app.router.playbooks` (prompt de
      sistema por domínio), anteposto pelo orchestrator em `_build_prompt`
      (com ou sem RAG); `fora_escopo` sem playbook. Decisão registrada em
      `docs/ARCHITECTURE.md` §5; testes em `tests/test_playbooks.py` e
      `tests/test_orchestrator.py`
- [x] Escrever playbooks iniciais de atendimento para Suporte Técnico e
      Atendimento ao Usuário — `app.router.playbooks` (`_SUPORTE_PLAYBOOK`,
      `_ATENDIMENTO_PLAYBOOK`)
- [x] Escrever playbook de Vendas com oferta proativa de agendamento de
      visita quando a conversa indica intenção de compra e o portfólio de
      produtos é compatível (ver `docs/ARCHITECTURE.md`, linha "Domínios"
      da tabela de escopo) — `_VENDAS_PLAYBOOK`: oferece o agendamento como
      pergunta ao final, sem confirmar/inventar data (a criação real do
      evento é R11, Fase 4)

## Fase 4 — Agendamento via MCP e Monitor de Tom (R8, R11)

> R11 (agendamento via MCP Calendar) implementado como Fase 4A — ver
> `docs/superpowers/specs/2026-09-21-agendamento-mcp-calendar-design.md`.
> R8 (monitor de tom) implementado como Fase 4B (backend) — ver
> `docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md`. Banner
> visual no frontend consumindo o evento `escalonamento` fica para a
> Fase 8 (item próprio do roadmap).

- [x] Implementar cliente MCP para o Google Calendar (trocado em 2026-09-23
      do MCP oficial do Google, em Developer Preview, para um MCP de
      terceiro self-hosted — `calendar-mcp-server` — ver decisão revista em
      `docs/ARCHITECTURE.md` §5)
- [x] Implementar nova intenção de agendamento no roteador (coleta de
      data/hora e dados básicos na conversa)
- [x] Implementar confirmação automática por e-mail após criar o evento
- [x] Implementar tratamento de erro claro para falha de conexão/autenticação
      do MCP do Google Calendar (sugerir nova tentativa ou transferir para
      atendente)
- [x] Implementar classificador leve de sentimento/urgência (heurística +
      LLM leve)
- [x] Implementar alerta e transferência simulada para atendente humano + log
      dos casos escalonados (evento SSE `escalonamento` + tabela
      `tom_escalonamentos` — banner visual no frontend implementado na Fase 8,
      ver `docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md` §9)
- [x] **Central de Atendimento Humano ao Vivo (Live Agent Takeover / Transbordo)** —
      Implementado o módulo completo de atendimento humano simultâneo conforme especificação
      `docs/superpowers/specs/2026-10-03-atendimento-humano-transbordo-design.md`
      (migração `0021_atendimento_humano_transbordo`, `app.services.atendimento_service`,
      `app.api.admin_atendimento`, pausa da IA em `app.api.chat` quando
      `conversa.status` está em `aguardando_humano`/`em_atendimento_humano`, e UI do
      operador em `/admin/atendimento` com fila e abas de atendimento — achado desta
      revisão de documentação de 2026-10-05: a caixa não tinha sido marcada quando a
      feature foi entregue):
      - Alterações de banco de dados (`conversas.status`, `atendente_id`, `motivo_escalonamento`, `escalado_em`).
      - Endpoints de claim atômico e transmissão de mensagens operador ↔ cliente (`/api/admin/atendimento/*`).
      - Pausa automática do gerador de respostas da IA durante o atendimento humano ativo.
      - Interface do operador no frontend (`/admin/atendimento`) com fila de espera, abas de atendimento e resumo de contexto do cliente.
      > Correção (2026-10-06, três bugs reportados ao vivo na Central de
      > Atendimento): (1) "Assumir Chat" sempre falhava com "Failed to fetch"
      > — a migração `0018` criou `conversas.status` como `VARCHAR(20)`, e a
      > `0021` passou a gravar `"em_atendimento_humano"` (21 caracteres) sem
      > alargar a coluna; todo claim quebrava com
      > `StringDataRightTruncationError` (500 sem corpo/CORS, que o navegador
      > relata como "Failed to fetch") — nova migração `0023` alinha a coluna
      > a `VARCHAR(50)` (o `Mapped[str]` do model já declarava isso, só
      > faltava a migração). (2) O cronômetro da fila mostrava "NaNh NaNm" —
      > `listar_fila_espera`/`listar_meus_chats` nunca incluíam
      > `tempo_espera_segundos` (nem `mensagens_count`/`criada_em`
      > /`atualizada_em`) no dict retornado, então o frontend calculava a
      > partir de `undefined`. (3) Um cliente cadastrado e logado aparecia
      > como "Cliente Visitante" — as mesmas funções (e `obter_detalhes_
      > atendimento`, o painel "Contexto do Cliente") nunca montavam a chave
      > `cliente` que o frontend lê; `item.cliente?.nome` caía sempre no
      > texto fixo. `app.services.atendimento_service` ganhou os três campos
      > que faltavam nas três funções. Testes em
      > `tests/test_atendimento_service.py`. Gap conhecido: a truncagem de
      > `VARCHAR` não é reforçada pelo SQLite usado nos testes unitários —
      > só foi reproduzida chamando o endpoint direto contra o Postgres real;
      > não há teste automatizado que pegaria uma regressão igual no futuro.
      > Correção (2026-10-06, quarto bug — "atendente responde mas a
      > mensagem não aparece no chat do cliente"): dois problemas distintos.
      > (a) `ConversaMensagemOut.papel` (contrato de
      > `GET /api/chat/conversations/{id}`, o endpoint que o widget do
      > cliente usa para reexibir/retomar a conversa) só aceitava
      > `"cliente"`/`"assistente"` — não incluía `"atendente"`. Assim que a
      > conversa tinha uma mensagem do atendente, o endpoint quebrava com
      > `ValidationError` (500), derrubando o histórico inteiro (não só a
      > mensagem dele) para o cliente que reabria/recarregava o chat. (b)
      > mesmo corrigido, nada no `ChatModal` fazia esse endpoint ser
      > reconsultado enquanto o widget já estava aberto — não existe
      > WebSocket/SSE do servidor para empurrar a mensagem do atendente ao
      > cliente; a única sincronização era a busca única ao montar o
      > `ChatWidget` (R9). Fix: `app.api.chat` passa `atendente_nome` e
      > inclui `"atendente"` no `Literal`; o frontend ganhou
      > `fetchConversationSnapshot` (histórico + `status` num só fetch) e o
      > `ChatModal` agora repolla a cada 4s enquanto `status` for
      > `aguardando_humano`/`em_atendimento_humano`, substituindo as
      > mensagens em tela pelas do servidor — e para sozinho quando o
      > atendente encerra/devolve a conversa. A bolha "atendente" (estilo
      > verde dedicado) já existia em `MessageBubble`, nunca tinha sido
      > alimentada. Testes em `tests/test_chat_transbordo_pausa.py`
      > (backend) e `ChatModal.test.tsx`/`chatHistory.test.ts`/
      > `ChatWidget.test.tsx` (frontend).
      > Correção (2026-10-07, "a página de atendente fica com scroll
      > sempre para baixo"): o `useEffect` de scroll-to-bottom em
      > `MeusChatsTabs` (painel do atendente) e o polling recém-adicionado
      > acima em `ChatModal` (painel do cliente) tinham o mesmo problema —
      > `detalhes`/`fetchConversationSnapshot` são repollados a cada
      > 3s/4s e cada busca traz um array de mensagens novo (nova
      > referência) mesmo sem mensagem nova de fato; usar esse array
      > inteiro como dependência/gatilho disparava `scrollIntoView` (ou
      > `replaceMessages`, que o disparava por tabela) a cada poll,
      > prendendo a tela sempre no fundo e impedindo rolar para cima para
      > reler o histórico. `MeusChatsTabs` passou a depender de
      > `detalhes?.mensagens.length`; o polling do `ChatModal` só chama
      > `replaceMessages` quando a contagem de mensagens muda. Testes
      > novos em `AdminAtendimentoPage.test.tsx` e `ChatModal.test.tsx`
      > (ambos verificados contra a versão com o bug antes do fix, para
      > confirmar que pegam a regressão).
      > Correção (2026-10-07, "quando o atendente responde não chega no
      > chat, só se o cliente mandar outra mensagem"): o polling do
      > `ChatModal` (achado acima) só *começava* quando
      > `humanAttendanceStatus` já estava verdadeiro — e isso só acontecia
      > via evento SSE `status` (que só chega numa resposta a uma mensagem
      > DO CLIENTE) ou na checagem única ao montar o `ChatWidget`. Se o
      > atendente assumisse a conversa com o widget do cliente já aberto e
      > parado (sem o cliente mandar nada), nada nunca ligava o polling — a
      > mensagem do atendente só "chegava" (e só então posicionava a tela
      > corretamente) depois que o cliente mandasse outra mensagem, o que
      > finalmente disparava o `status` e, por tabela, o polling. O
      > polling agora roda sempre que o widget está aberto (não mais só
      > quando já se sabe que está em atendimento humano) — é o próprio
      > polling que detecta a entrada nesse modo. MVP: sem WebSocket/SSE do
      > servidor para esse evento, o custo é uma requisição leve a cada 4s
      > por widget aberto, mesmo em conversas que nunca escalam. Testes
      > atualizados em `ChatModal.test.tsx`.
      > Correção (2026-10-07, "quando o cliente encerra o chat, o chat no
      > atendente não encerra"): em `app/admin/atendimento/page.tsx`, o
      > bloco que deveria limpar `activeChatId`/`detalhes` quando a
      > conversa ativa some de `meusChats` (porque o cliente encerrou, ou
      > ela foi devolvida para a IA) só tinha o comentário da intenção —
      > `if (...) { /* chat foi fechado ou devolvido */ }`, corpo vazio,
      > nunca implementado. `MeusChatsTabs` não olha o `status` da
      > conversa para decidir o que mostrar, então o painel continuava
      > exibindo o histórico e os botões de ação como se a conversa
      > seguisse ativa. Implementado o `setActiveChatId(null)`/
      > `setDetalhes(null)` que o comentário já previa — o painel volta ao
      > estado vazio ("Central de Conversas em Andamento") no poll de 5s
      > seguinte. Teste em `AdminAtendimentoPage.test.tsx` (verificado
      > contra a versão com o bug antes do fix).
      > Melhoria (2026-10-07, a pedido do desenvolvedor): `claim_conversa`
      > agora grava automaticamente, como mensagem do próprio atendente
      > (`papel="atendente"`, `atendente_nome` do atendente que assumiu),
      > o aviso "Um atendente irá atendê-lo agora." assim que o claim
      > sucede — chega ao cliente pelo mesmo polling do `ChatModal` (achado
      > acima), sem esperar o atendente digitar a primeira linha. Não
      > duplica no claim perdido de uma corrida (só grava dentro do `if
      > sucesso`). Testes em `test_atendimento_service.py` e
      > `test_admin_atendimento_api.py`.
      > Melhoria (2026-10-07, a pedido do desenvolvedor): mesmo padrão para
      > `devolver_para_ia` ("Redirecionado para atendente virtual",
      > atendente_nome lido antes de ser limpo) e `finalizar_atendimento`
      > ("O Atendente encerrou o atendimento."). Como as duas ações tiram a
      > conversa do status humano no mesmo instante em que a mensagem é
      > gravada, o guard de replace do polling do `ChatModal` (achado
      > acima) precisou de um ajuste — ele só substituía mensagens quando
      > `novoStatus` (o status pós-poll) era humano; no tick em que a
      > transição acontece, `novoStatus` já vem `null`, então a mensagem de
      > despedida nunca era entregue ao vivo (só reapareceria num reload).
      > Passou a considerar `novoStatus || statusAnterior`, cobrindo esse
      > tick de transição sem voltar a interferir numa conversa normal de
      > IA nos ticks seguintes. Testes em `test_atendimento_service.py` e
      > `ChatModal.test.tsx` (verificados contra a versão sem o ajuste,
      > para confirmar que pegam a regressão).

## Fase 5 — MCP B2B Provido pela Empresa (R12)

- [x] Modelar o backend único de dados (catálogo, estoque, preços, manuais)
      reaproveitado tanto pelo RAG quanto pelo servidor MCP
- [x] Implementar servidor MCP interno expondo os 4 recursos de leitura
      (catálogo, estoque, tabela de preços, manuais) — `app.mcp_server.b2b`,
      rodando como processo próprio (`scripts/run_mcp_b2b_server.py`, porta
      `MCP_B2B_PORT`/8100), ver decisão registrada em `docs/ARCHITECTURE.md`
      §5
- [x] Implementar as 4 ferramentas do MCP B2B: validação de compatibilidade,
      consulta de frete e prazos, cotação automática, reserva/pedido —
      `@server.tool(...)` em `app.mcp_server.b2b`, sobre as tabelas novas
      `produto_compatibilidades`/`pedidos`/`pedido_itens` (migração `0009`)
      e a lógica de preço/desconto em `app.db.catalog`, ver decisão
      registrada em `docs/ARCHITECTURE.md` §5
- [x] Integrar o Roteador/Orquestrador como "mais um integrador" do MCP B2B
      para intenções de Vendas (cotação, compatibilidade, estoque) — novo módulo
      `app.router.sales_catalog` (`SalesCatalogClient`, two-stage resolution:
      candidates por SQL + LLM choice), desambiguação por LLM necessária por
      catálogo ~1000 produtos (spec §2), chamada direta a `app.db.catalog` no mesmo
      processo (spec §4). Injeção de dependência em `main.py` + `chat.py`
      (+ `test_chat_api.py`/`test_main_app.py`). Ver decisão registrada em
      `docs/ARCHITECTURE.md` §5 e
      `docs/superpowers/specs/2026-09-24-orquestrador-mcp-b2b-vendas-design.md`.
- [x] Corrigir consulta genérica por categoria em Vendas (bug relatado
      2026-09-26): "tem geradores no estoque?" respondia "não tenho
      informações" porque o fluxo só resolvia produto único
      (`llm_sem_produto`), enquanto a busca por modelo específico funcionava.
      `VendaSlots.categoria` + `SalesCatalogClient.listar_categorias`/
      `consultar_categoria` + `DadosCatalogoCategoria` listam os produtos da
      categoria com estoque; `_DOMAIN_KEYWORDS["vendas"]` ganhou
      `"estoque"`/`"disponível"` para a heurística concordar com o
      `DOMAIN_CRITERIA`. Testes em `tests/test_sales_catalog.py` e
      `tests/test_orchestrator.py`. Ver decisão em `docs/ARCHITECTURE.md` §5
      (2026-09-26) e a spec §11.
- [x] Corrigir viés de categoria e adicionar listagem completa do catálogo em
      Vendas (bug relatado 2026-09-29): "você poderia me fornecer os
      produtos em estoque disponíveis?" (sem produto nem categoria)
      respondia só sobre "geradores" — o few-shot do prompt de extração
      citava essa categoria como único exemplo, e mesmo sem o viés a
      pergunta genérica não tinha para onde ir (`_consultar_vendas` cortava
      antes do LLM quando a busca por palavra-chave não achava candidato).
      Few-shot trocado por um placeholder genérico; `VendaSlots.listar_tudo`
      + `SalesCatalogClient.listar_todos_produtos()` (reaproveitando
      `DadosCatalogoCategoria` com `categoria=None`) listam o catálogo
      inteiro quando nem produto nem categoria são citados; orquestrador
      sempre chama a extração por LLM mesmo com `candidatos` vazio. Testes
      em `tests/test_sales_catalog.py` e `tests/test_orchestrator.py`. Ver
      decisão em `docs/ARCHITECTURE.md` §5 (2026-09-29).
- [x] Substituir o script manual de ingestão do catálogo no RAG por
      sincronização automática (correção de 2026-09-29): o conector BD→RAG
      (R4, Fase 2) só alimentava o Qdrant via
      `backend/scripts/ingest_db_table.py`, rodado uma única vez sobre o
      catálogo fixture original e nunca mais desde então — o RAG textual de
      Vendas ficava desatualizado em relação ao catálogo real. Novo módulo
      `app.rag.product_sync` (`sync_produto_no_rag`/`remover_produto_do_rag`)
      chamado pelas rotas de CRUD de produtos (`app.api.admin_products`:
      criar, editar, excluir, estoque, desconto por volume, confirmação de
      lote do extrator) — cada produto vira um documento próprio
      (`produto_{id}.txt`) na collection ativa, reingerido (delete+ingest)
      a cada mudança. Testes em `tests/test_product_sync.py`. Ver decisão em
      `docs/ARCHITECTURE.md` §5 (2026-09-29).
- [x] Corrigir estoque por centro de distribuição respondido errado em
      Vendas (bug relatado 2026-09-29): perguntar pelo estoque de um CD
      específico ou "por centro de distribuição" respondia com o total
      somado entre todos os CDs — o bloco do chat (`DadosCatalogoVendas`) só
      levava `estoque_total`, nunca o detalhamento por CD (que já era
      buscado internamente só para somar). `DadosCatalogoVendas.estoque_por_cd`
      (schema novo `EstoqueCentroDistribuicao`) leva o detalhamento para o
      bloco do prompt, com instrução explícita para o LLM preferi-lo quando
      perguntado por CD. Testes em `tests/test_sales_catalog.py` e
      `tests/test_orchestrator.py`. Ver decisão em `docs/ARCHITECTURE.md` §5
      (2026-09-29).
- [x] ~~Garantir e documentar que autenticação por parceiro e exposição
      pública **não** fazem parte do MVP~~ — **revisto em 2026-09-25**: o
      revendedor está fora da rede local, então o MCP B2B precisa de
      exposição pública. Substituído pelo item abaixo. Deste item ficou o
      padrão `MCP_B2B_HOST=127.0.0.1`: o acesso externo passa pelo proxy
      HTTPS, nunca direto na porta 8100.
- [x] Expor o MCP B2B publicamente com chave por parceiro — DuckDNS +
      Caddy (HTTPS, porta 8443) na frente do servidor em `127.0.0.1:8100`;
      `Authorization: Bearer <chave>` verificado pelo `TokenVerifier` do SDK
      (`MCP_B2B_PARTNER_KEYS`, várias chaves com nome); servidor não sobe
      sem chave; log `mcp_b2b_ferramenta` com o parceiro de cada chamada.
      Código e testes em `app.mcp_server.auth`, `tests/test_mcp_b2b_auth.py`,
      `infra/caddy/` e suíte `mcp_b2b`. Validado na máquina real em
      2026-09-25 (`testes_locais/20260925-1208-mcp_b2b.md`, 6/6): 401 sem
      chave e com chave errada, sessão MCP completa com a chave, porta 8100
      fechada para a rede, HTTPS do Caddy e a URL pública DuckDNS
      respondendo (o roteador tem NAT loopback, então o caminho pelo
      roteador foi testado de dentro da rede).
      Ver decisão em `docs/ARCHITECTURE.md` §6
- [x] Cliente independente de demonstração do MCP B2B (`cliente-b2b/`),
      projeto Python + Streamlit desacoplado do `backend/` — `src/client.py`
      (`B2BMCPClient`, sessão assíncrona via SDK `mcp`) consome os recursos
      (`catalogo://produtos[/{id}]`, `estoque://produtos/{id}`,
      `precos://produtos/{id}`, `manuais://busca/{domain}?query=`) e as 4
      ferramentas do servidor real; `src/app.py` é o Portal do Parceiro com
      abas de catálogo/recursos, cotação, frete, compatibilidade e emissão
      de pedido, com Modo Desenvolvedor para inspecionar o JSON-RPC bruto.
      `# MVP: reservar_pedido aplica um único centro de distribuição a todo
      o carrinho (a ferramenta exige um por item; o cliente não modela
      split de pedido entre centros)`. Testes em `tests/test_client.py`
      (mocks da `ClientSession`) e `tests/test_app_helpers.py`. Spec em
      `docs/superpowers/specs/2026-09-29-cliente-mcp-b2b-design.md` — nota:
      a primeira implementação (client.py) assumiu URIs/parâmetros
      genéricos divergentes do servidor real (`app.mcp_server.b2b`); corrigido
      nesta entrega para usar os nomes/formatos efetivos (ver
      `docs/ARCHITECTURE.md` §6). Validado ao vivo contra o servidor real
      (2026-09-30, infra local: Postgres/Qdrant no ar, `scripts/run_mcp_b2b_server.py`
      em `127.0.0.1:8100`): todos os 4 recursos e as 4 ferramentas
      responderam corretamente. O teste ao vivo revelou que o SDK `mcp`
      embrulha um 401 num `MCPError` JSON-RPC genérico sem o código HTTP
      (mesma limitação documentada em `scripts/cliente_mcp_b2b.py`), então a
      detecção de chave recusada por *string matching* na mensagem da
      exceção (que passava nos testes com mocks) nunca disparava contra o
      servidor real — corrigido com um preflight HTTP cru antes de abrir a
      sessão MCP (`B2BMCPClient._verificar_autenticacao`), mesma técnica do
      script de referência. `reservar_pedido` também validado ao vivo (baixa
      real de estoque conferida antes/depois: CD-SP 12 → 11 após reservar 1
      unidade do produto 1).
- [x] Ampliar o acesso do parceiro B2B à busca de manuais (correção de
      2026-09-30, a pedido explícito do desenvolvedor): o parceiro deve
      acessar todo o conteúdo do RAG principal e do específico do canal
      B2B — só o cliente final (chat público) não deve ver documentos
      exclusivos do B2B. Antes, `manuais_busca` buscava só em collections
      `purpose="mcp_b2b"` (isolamento nos dois sentidos, decisão de
      2026-09-21/24). Agora `b2b_collections` em `app.mcp_server.b2b`
      inclui `purpose="mcp_b2b"` **e** a collection `purpose="chat"` ativa;
      o caminho inverso (chat público nunca busca `purpose="mcp_b2b"`)
      continua vedado, inalterado. Testes atualizados em
      `tests/test_mcp_b2b_server.py`; validado ao vivo contra `docs_texto`
      (collection ativa de produção) com resultados reais do RAG principal
      aparecendo na busca do parceiro. Ver decisão em
      `docs/ARCHITECTURE.md` §5 (2026-09-30).
- [x] Modo admin do chat sobre o RAG completo (2026-09-30, a pedido
      explícito do desenvolvedor): o Admin quer usar o próprio widget de
      chat (não só o playground de `/admin/ingestao`) para pesquisar seus
      documentos exclusivos, que ninguém mais deve acessar. Nova finalidade
      de collection `purpose="admin"` (ao lado de `chat`/`mcp_b2b`);
      `activate_collection`/`ActiveCollectionRagClient.search` generalizados
      de `purpose == "mcp_b2b"` para `purpose != "chat"`. Detecção do Admin
      no chat exige mais que `ChatMessageRequest.user_email` (livre, nunca
      validado) — novo `ChatMessageRequest.auth_token`, verificado no
      servidor por `app.api.auth.verificar_admin_por_token` (token de
      `/login` de fato emitido, perfil recalculado no servidor, nunca aceito
      do requisitante). Novo `AdminAllCollectionsRagClient`
      (`app.rag.admin_all_collections_client`) busca a collection `chat`
      ativa + toda `mcp_b2b` + toda `admin`; `app.api.chat.send_message`
      troca para ele quando `_verificar_modo_admin_seguro` confirma o token
      (falha *fechada* para "sem modo admin" em qualquer erro, ao contrário
      das demais funções `_..._seguro`). Lógica de busca paralela em N
      collections extraída para `app.rag.multi_collection_search`,
      reaproveitada por `manuais_busca` (MCP B2B) e pelo novo cliente admin.
      Seletor "Finalidade" do `/admin/ingestao` ganhou a opção "Exclusiva do
      Admin"; badges/bloqueio de ativação em `CollectionsTable`
      generalizados. Testes: `tests/test_auth_admin_token.py`,
      `tests/test_rag_admin_all_collections_client.py`, casos novos em
      `test_rag_active_collection_client.py`/`test_rag_collections_registry.py`
      (purpose=admin) e em `test_chat_api.py` (confirma a troca de cliente
      RAG com `auth_token` de admin e que `user_email` sozinho, mesmo
      `admin@...`, não troca); frontend com testes em
      `CollectionFormModal.test.tsx`/`CollectionsTable.test.tsx`. Ver decisão
      em `docs/ARCHITECTURE.md` §6 (2026-09-30) e
      `docs/Manuais/HOWTO_ADMINISTRADOR.md`.
      **Correção (2026-10-03):** criar collection com "Exclusiva do Admin"
      pelo `/admin/ingestao` falhava com `422 Input should be 'chat' or
      'mcp_b2b'` — `CollectionPurpose` (`app.models.rag`) não tinha sido
      atualizado para incluir `"admin"` junto com o resto da entrega (gap
      entre sessões concorrentes no mesmo repositório). Regressão coberta em
      `test_criar_collection_admin_expoe_purpose_na_resposta`
      (`test_rag_collections_api.py`).

## Fase 6 — Memória e Classificação do Usuário (R9, R10)

Decisões de 2026-09-25 em `docs/ARCHITECTURE.md` §5 ("Fase 6, memória da
conversa e classificação do usuário").

- [x] Implementar persistência da conversa por ID único — tabelas
      `conversas`/`conversa_mensagens` no Postgres (mensagens do cliente e
      do assistente), gravadas antes do evento `done`. Implementado
      (`app.memory.store`, migração `0010`, `app.api.chat`). Validado no
      Postgres real (`testes_locais/20260925-1243-memoria.md`, R1)
- [x] Implementar resumo automático periódico da conversa (não só ao final)
      — a cada 6 mensagens, em segundo plano, com o resumo no prompt.
      Implementado (`app.memory.resumo`, `_build_prompt`). Validado com o
      LLM local (R2: resumo em 2 s, usado na resposta seguinte)
- [x] Retomar a conversa no widget — `GET /api/chat/conversations/{id}`
      e carregamento no `ChatWidget` ao montar. Implementado (backend +
      `fetchConversationHistory`/`loadHistory` no frontend). Backend
      validado no teste local (R1, GET da conversa) e retomada conferida no
      navegador (2026-09-25: mensagens voltam após F5). Depois, a pedido do
      desenvolvedor, cada resposta passou a guardar as métricas do `done`
      (coluna `metricas`, migração `0012`), e o painel ⚙️ reaparece igual nas
      mensagens recarregadas
- [x] Implementar heurística inicial de classificação Cliente/Lead/Esporádico
      com base em histórico de compras/perguntas — base de clientes fictícia,
      e-mail captado no momento natural (pós-venda, agendamento), perfil no
      evento `done` e no painel de métricas. Implementado
      (`app.user_profile.classificacao`, migração `0011` com 3 clientes
      fictícios, pedido de e-mail no pós-venda em `_build_prompt`,
      `MessageBubble`). Validado no teste local (R3 a R9: pedido de e-mail
      no pós-venda, cliente, esporádico x2, lead, não classificado, e-mail
      lembrado)
- [x] Mensagem de boas-vindas ao abrir o chat com a conversa vazia, com
      convite opcional para informar o e-mail junto com a pergunta (R10) —
      bolha só de interface (`WELCOME_MESSAGE` em `ChatModal.tsx`), pedido do
      desenvolvedor em 2026-09-25
- [x] E-mail guardado na chegada da mensagem (não se perde se o LLM falhar)
      e mensagem só com o e-mail respondida sem LLM (`resposta_fixa`, sem
      revelar se há cadastro) — correções do teste local de 2026-09-25 (R6/R9
      falharam com 429 do OpenRouter)
- [x] Botão "limpar conversa" no chat — apaga as mensagens e zera resumo e
      perfil da conversa (`DELETE /api/chat/conversations/{id}`,
      `limpar_conversa`); o prompt do resumo deixou de citar "geradores"
      (commit `4ec4888`, 2026-09-27; registrado na revisão de 2026-09-28).
      `# MVP: o e-mail da conversa é mantido`
- [x] Contexto da mensagem de acompanhamento depois da identificação por
      imagem (R9, correção de 2026-09-27, `docs/ARCHITECTURE.md` §5 item 4b)
      — a troca da imagem é gravada na memória, o prompt leva a última troca
      e, em referências como "o produto acima", a busca e o filtro do RAG
      usam a última resposta. Implementado (`carregar_contexto.ultima_troca`,
      `_buscar_documentos_rag`, `_build_prompt`, `app.api.chat`) e testado
      com fakes e conferido no navegador em 2026-09-28 (imagem → "possui
      detalhes do produto acima?" continuou no mesmo produto)
- [x] Descrição comercial e especificações técnicas no bloco do catálogo
      (R12, correção de 2026-09-27, `docs/ARCHITECTURE.md`, decisão
      "Orquestrador como integrador do MCP B2B em Vendas", item 6) — pedindo
      detalhes, o bloco só tinha estoque e cotação e o LLM respondia sobre
      preço e estoque. Agora leva descrição, ficha técnica, dimensões e peso
      (truncados), manda responder o que foi perguntado, e a busca de
      candidatos usa a última resposta em "o produto acima". Validado no
      teste local (`testes_locais/20260927-2100-vendas.md`, V11/V12)
- [x] Identificação por imagem com os detalhes do cadastro (R6/R12, decisão
      de 2026-09-27, `docs/ARCHITECTURE.md` §4, passo 4) — produto é dado do
      banco e PDFs ficam para manuais: achado o produto (`produto_id` da foto
      ou nome casando com um único produto), a resposta traz a ficha do banco
      (descrição, especificações técnicas, dimensões, peso) com o nome do
      cadastro; sem produto no banco, cai no RAG como antes. Testado com
      fakes e conferido no navegador em 2026-09-28
- [x] Produto achado no banco não escala para o externo por RAG vazio
      (correção de 2026-09-28, mesmo item 6 da decisão do orquestrador) — a
      pergunta seguinte à imagem acertou o produto, mas foi para o externo
      (`rag_vazio`) porque nenhum PDF falava dele. Testado com fakes e
      conferido no navegador em 2026-09-28 (resposta no local)
- [x] Pergunta curta depois da imagem ("possui detalhes?", sem "acima" ou
      "esse") — a busca no catálogo passa a usar sempre a última resposta
      como complemento do histórico, e os classificadores LLM a recebem no
      contexto (correção de 2026-09-28; no navegador caía em `fora_escopo`
      e ia para o externo, que deu 429). Testado com fakes e conferido no
      navegador em 2026-09-28

## Fase 7 — Frontend: Site Institucional, Produtos e Pedidos (ver `docs/FRONTEND.md`)

- [x] Criar o projeto Next.js (TypeScript) em `frontend/` conforme
      `docs/FRONTEND.md` §5 — scaffold com App Router, Tailwind CSS, ESLint +
      Prettier, Vitest + Testing Library; pastas `app/`, `components/`,
      `lib/`, `public/`, `tests/` populadas (não recriadas)
- [x] Implementar Home institucional e Contato — `app/page.tsx` e
      `app/contato/page.tsx` com conteúdo estático real (institucional/dados
      de contato fictícios); sem chamada de API (não há dados dinâmicos
      previstos para essas páginas no MVP). Revisado em 2026-09-29: conteúdo
      já completo, sem placeholders — apenas o status estava desatualizado
- [x] Implementar listagem e detalhe de produtos (`/produtos`), consumindo a
      API do backend — listagem pronta (commit `7b53dd1`, 2026-09-27):
      `GET /api/products` paginado (12 por página), filtro por categoria e
      busca, produtos com estoque primeiro e depois por nome, cards com
      carrossel de imagens e zoom (`ProductCard`, `ImageZoomModal`). Detalhe
      implementado em `app/produtos/[id]/page.tsx` consumindo
      `GET /api/products/{id}`, com galeria de fotos, zoom, ficha técnica,
      especificações, medidas/peso, tabela de estoque por CD, descontos por
      volume e botões para comprar e cotar no chat.
- [x] Implementar autenticação simplificada (login/cadastro) e página de
      perfil — endpoints `POST /api/auth/login` e `GET /api/auth/me`, persistência
      Zustand `useAuthStore`, página `/conta/login` com contas simuladas
      (Ana Recorrente, Bruno Único, Carla Antiga) e senha mock 12345, página
      `/conta/perfil` com detalhes de relacionamento e pedidos, integração de
      e-mail ao Chat e aos fluxos de pedidos. Ampliado em 2026-09-29 (R10):
      cadastro próprio (`POST /api/auth/register`, página `/conta/cadastro`)
      e perfil Administrador (e-mail `admin@example.com`/`admin@*`,
      `GET /api/auth/users` lista todos os usuários) — menu ⚙️ passa a
      aparecer só para Admins, com atalhos "Gerenciar Usuários"
      (`/admin/usuarios`, com link "Ver Pedidos" por usuário) e "Criar Nova
      Conta"; `/pedidos/historico?email=...` ganha modo de inspeção
      administrativa. Ver decisão em `docs/ARCHITECTURE.md` §5 (2026-09-29).
- [x] Implementar fluxo de pedidos (carrinho/checkout), cotação B2B e histórico de pedidos
      — API REST no backend (`POST/GET /api/orders`, `POST /api/orders/quote`,
      `POST /api/orders/freight`, migração `0014`), store Zustand `useCartStore`,
      página `/pedidos` com carrinho interativo, cálculo de frete por CEP,
      simulador de descontos por volume B2B e página `/pedidos/historico`
      consumindo a API.
- [x] Implementar página de Suporte/Central de Ajuda (esse conteúdo também é
      alvo do crawler do RAG, R4) — `app/suporte/page.tsx` com FAQ estático
      real (sem API; conteúdo fica pronto para o crawler indexar na Fase 2/3)
- [x] Implementar gestão e página de Agendamentos (R11, Fase 7) — modelo de dados e migração Alembic `0015` (`agendamentos` com status, origem, datas e vínculos com Google Calendar e chat); extensão do cliente MCP do Google Calendar (`delete_event`, `list_events`, retorno de `google_event_id`); persistência automática no Postgres ao confirmar visita no Chat; endpoints REST da API em `/api/agendamentos` (`/meus`, `/{id}/cancelar`, `/admin`, `/admin/manual`, `/admin/google-events`); página do cliente `/agendamentos` com listagem própria, cancelamento sincronizado com o Google e CTA para o chat; painel administrativo em `/admin/agendamentos` com abas (sistema por usuário com filtros e consulta à agenda corporativa do Google Calendar em tempo real via MCP), modal de agendamento manual com checagem de conflitos e atalho no menu de engrenagem (`AdminGearMenu`).
      Ampliado em 2026-09-29 (R11): eventos criados pelo sistema passam a ser
      marcados (`[Sistema]`/`[origem:sistema]`) e a checagem de disponibilidade
      e a aba "Consulta em Tempo Real" passam a considerar só esses eventos,
      não qualquer compromisso da agenda; duração padrão da visita sobe de 30
      para 60 minutos (`DURACAO_VISITA`), com campo `duracao_minutos`
      configurável no agendamento manual do admin; botões "Agendar Visita
      pelo Chat" passam a pré-preencher a mensagem com os dados do usuário
      logado (`useChatStore.openVisitChat`). Ver decisão em
      `docs/ARCHITECTURE.md` §5 (2026-09-29).
- [x] Implementar página administrativa de ingestão de documentos
      (`/admin/ingestao`, fora do menu principal; link discreto no rodapé,
      `components/layout/Footer.tsx`) consumindo `POST /api/rag/documents` —
      decisão registrada em `docs/ARCHITECTURE.md` §5 e `docs/FRONTEND.md` §8

## Fase 8 — Frontend: Widget de Chat (ver `docs/FRONTEND.md` §3)

- [x] Implementar botão flutuante + modal de chat (`ChatWidget`,
      `ChatModal`), presente em todas as rotas — `components/chat/ChatWidget.tsx`,
      `components/chat/ChatModal.tsx`, incluído em `app/layout.tsx`. Era
      `ChatPanel.tsx` (painel fixo) originalmente; migrado para modal
      (`components/ui/Modal.tsx`, Radix Dialog) sem mudar a lógica de
      envio/áudio/métricas, só a apresentação — ver `docs/FRONTEND.md` §3
- [x] Implementar envio de texto e exibição do streaming de resposta (SSE) —
      `POST /api/chat/messages` devolve `text/event-stream` (`app/api/chat.py`),
      com evento `status` avisando cold-start do modelo local
      (`OllamaClient.is_model_ready`, `GET /api/ps`) antes de gerar. Frontend:
      `lib/api/chat.ts` reescrito para consumir o stream SSE via parser manual
      de blocos `event:`/`data:` e devolver `Promise<void>`, entregando a
      resposta incrementalmente por callbacks (`onConversationId`/
      `onTranscription`/`onStatus`/`onToken`/`onDone`/`onError`) em vez de
      `response.json()`. `ChatModal.tsx` adaptado para usar essa nova assinatura,
      exibindo o texto token a token na UI com indicador visual de status —
      decisão registrada em `docs/ARCHITECTURE.md` §5. Fix 2026-09-18: com
      `ROUTER_COMPLEXITY_STRATEGY=llm`, o check de `is_model_ready()` também
      passou a rodar antes da classificação (não só antes de
      `generate_stream`) — a classificação de mensagem ambígua chama o
      modelo local e, no Ollama real, é essa chamada que paga o cold-start;
      sem o check ali, o evento `status` nunca era emitido, mesmo a espera
      real tendo ocorrido (`backend/src/app/router/orchestrator.py`, ver
      `docs/FRONTEND.md` §4)
- [x] Implementar upload de imagem (`ImageUploader`) e gravação de áudio
      (`AudioRecorder`) — gravação de áudio:
      `components/chat/AudioRecorder.tsx` (toggle, indicador visual de
      gravação, tratamento de permissão negada e de navegador sem suporte),
      integrado ao `ChatModal` (envio automático ao parar, bolha do usuário
      populada com `transcribed_message`, retry reenvia o mesmo áudio).
      Imagem: `components/chat/ImageUploader.tsx` no `ChatModal` (commit
      `40c7fbc`, R6), e desde 2026-09-27 também arrastar e soltar imagem ou
      áudio sobre o chat (commit `a435ccd`; registrado na revisão de
      2026-09-28). Identificação por imagem conferida no navegador em
      2026-09-28
- [x] Implementar persistência do ID de conversa (retomar conversa entre
      sessões/páginas, R9) — `lib/hooks/useChatStore.ts`
      (`getOrCreateConversationId`), persistido em `localStorage`
- [x] Implementar cards ricos: produto, confirmação de agendamento,
      cotação/reserva (2026-09-29). Nota desatualizada corrigida antes de
      implementar: o texto original dizia depender de R6/R11/R12 no backend
      "ainda não implementados" — as três dependências já tinham sido
      entregues (busca por imagem CLIP na Fase 3, agendamento via MCP
      Calendar na Fase 4A/7, integração MCP B2B em Vendas na Fase 5).
      Backend: `app.models.chat.ChatCard` (união discriminada por `tipo` —
      `CardProduto`/`CardCotacao`/`CardAgendamento`), construído em
      `orchestrator._construir_card_vendas` (a partir do mesmo resultado de
      `_consultar_vendas` já usado no bloco de texto) e em
      `_handle_agendamento` (ao confirmar a visita), viajando no campo
      opcional `card` do evento SSE `done`. Frontend:
      `components/chat/cards/{ProductCard,QuoteCard,AppointmentCard,ChatCard}.tsx`
      (dispatcher por `card.tipo`), renderizado em `MessageBubble` logo
      abaixo do texto da resposta. `# MVP: só produto único vira card —
      DadosCatalogoCategoria (listagem por categoria/catálogo completo,
      correção de 2026-09-29) ainda não tem card próprio`. Testes em
      `tests/test_orchestrator.py`, `tests/test_sales_catalog.py`,
      `tests/test_chat_api.py` (backend) e
      `tests/components/Chat{ProductCard,QuoteCard,AppointmentCard}.test.tsx`
      + `MessageBubble.test.tsx` (frontend). Ver decisão em
      `docs/ARCHITECTURE.md` §5.
- [x] Implementar indicador de domínio identificado pelo roteador
      (opcional, útil para a demonstração ao orientador) — rótulo discreto em
      `components/chat/MessageBubble.tsx`
- [x] Implementar indicador visual de origem do modelo (local x externo) —
      bolha do assistente em azul quando `backend_used` retornado pela API é
      `"externo"`, mesmo arquivo (`MessageBubble.tsx`)
- [x] Implementar banner de transferência para atendente humano (monitor de
      tom, R8) — componente `components/chat/EscalonamentoBanner.tsx`,
      integrado ao `ChatModal.tsx`, consumindo o evento SSE `escalonamento`
      emitido pelo backend (`backend/src/app/api/chat.py`). Exibe aviso
      contextual de atendimento humano prioritário com motivo (`urgencia` vs.
      `insatisfacao`), badge explicativo de "Alerta de Tom" e botão para
      dispensar o aviso (`onDismiss`). Suportado tanto no fluxo de mensagem de
      texto quanto no envio de áudio via callback `onEscalonamento` em
      `lib/api/chat.ts`.
- [x] Implementar estados de erro (ex.: falha do MCP do Google Calendar) com
      opção de tentar novamente — versão inicial cobre erro de rede/503 do
      próprio `POST /api/chat/messages` (`ChatModal`, bolha de erro com botão
      "Tentar novamente", sem retry automático); o caso específico de falha
      do MCP do Google Calendar será coberto quando R11 existir no backend

## Extra fora do MVP — Telemetria de Inferência no Chat

> Pedido explícito do usuário, fora do escopo original do MVP (ver
> `docs/ARCHITECTURE.md` §5).

- [x] **Telemetria por mensagem** — `POST /api/chat/messages` devolve
      modelo usado, tokens de entrada/saída, latência, TTFT, TPS, custo
      estimado e métricas de RAG (tempo/qtd./score médio); `ChatModal`
      mostra um painel com essas métricas e permite exportar a conversa em
      CSV/JSON (`frontend/lib/utils/exportMetrics.ts`) — pensado para
      alimentar a avaliação experimental da Fase 10, não como feature de
      produto. TTFT só é preenchido para o backend local (ver
      `docs/ARCHITECTURE.md` §5).
- [x] **Fonte por chunk na telemetria de RAG** — `rag_chunks` (fonte/arquivo
      + score de cada chunk usado no contexto) adicionado ao payload de
      `rag_avg_score`/`rag_chunks_count` já existente; exibido no painel do
      `ChatModal` (seção "Fontes" do bloco RAG) e no export CSV/JSON. Hoje a
      busca RAG só recupera de arquivos ingeridos — sem fonte de internet
      (ver `docs/ARCHITECTURE.md` §5).
- [x] **Painel de métricas por mensagem escondido por padrão** — o painel de
      telemetria (antes sempre visível abaixo de cada resposta) passou a
      ficar escondido por padrão; uma engrenagem pequena (⚙️, mesmo tamanho
      de fonte do rótulo de domínio) ao lado do rótulo de domínio no topo da
      bolha alterna a exibição (`MessageBubble.tsx`, `showDetails`). Não
      afeta o export CSV/JSON do `ChatModal`, que continua agregando a
      telemetria de todas as mensagens independente do painel estar aberto.

## Fase 9 — Integração Ponta a Ponta e Robustez

- [x] Testes de integração cobrindo os quatro domínios de atendimento
      (backend) — `tests/test_integration_domains.py`, através do endpoint
      HTTP real (`chat_router` via `TestClient`, parseando o SSE), não
      chamando `handle_message` direto como `test_orchestrator.py`.
      Diferença para `test_chat_api.py`: lá `calendar_client`/
      `scheduling_config`/`sales_catalog_client` ficam sempre `None` de
      propósito; aqui as quatro dependências externas (LLM local/externo,
      RAG, calendário, catálogo de vendas) são dublês, mas todas ficam
      ligadas, para exercitar o mecanismo que de fato distingue cada
      domínio: Vendas consulta o catálogo e gera card de cotação; Suporte só
      usa RAG (nunca o catálogo); Atendimento injeta o histórico de compras
      do cliente autenticado no prompt; Agendamento roda a máquina de
      estados real (slots → confirmação → criação de evento) em duas
      requisições HTTP sequenciais com o mesmo `conversation_id`. Como
      Vendas e Agendamento fazem uma chamada de extração estruturada (JSON)
      via `generate()` antes da resposta final, a fake de LLM
      (`_DomainAwareLLMClient`) inspeciona um marcador exclusivo de cada
      prompt de extração para devolver o JSON certo, em vez de uma única
      resposta fixa.
- [x] Testes E2E do frontend cobrindo os fluxos críticos: chat (texto,
      imagem, áudio), pedido, login (ver `docs/FRONTEND.md` §6). Chat
      texto/áudio feitos adiantado, junto do widget (Fase 8):
      `frontend/tests/e2e/chat.spec.ts` (Playwright), cobrindo envio de
      mensagem, erro/retry e gravação de áudio via dispositivo de mídia fake
      do Chromium (`--use-fake-device-for-media-stream` /
      `--use-fake-ui-for-media-stream`, `playwright.config.ts`); `# MVP: mocka
      POST /api/chat/messages via page.route em vez de rodar contra o
      backend/Ollama/STT reais`. Imagem/pedido/login concluídos agora que
      R6/R12 e o fluxo de pedidos (Fase 7) já estão implementados:
      `imagem.spec.ts` (identificação de produto e caso não-identificado, `#
      MVP: mocka o SSE — não decodifica a imagem de verdade nem chama
      CLIP/visão externa`), `pedido.spec.ts` (login → carrinho pré-preenchido
      por `?produto=` → checkout → confirmação; e o gate de login exigido),
      `login.spec.ts` (login manual, login rápido por conta de demonstração,
      erro de senha incorreta). Achado ao escrever `imagem.spec.ts`: 2 dos 3
      testes de `chat.spec.ts` já estavam quebrados
      (`getByRole("button", {name: "Enviar"})` virou ambíguo — casa também o
      botão "Enviar imagem" do `ImageUploader`, adicionado depois que esses
      testes foram escritos) — corrigido com `exact: true` nos 4 specs.
- [x] Ajustes de robustez nas frentes mais custosas: RAG multimodal e monitor
      de tom — e revisão de tratamento de erro para dependências externas
      (os dois itens abaixo, escopados e resolvidos juntos: a investigação
      cobriu as duas frentes de uma vez). Levantamento prévio (subagente de
      pesquisa) achou a maior parte já bem tratada — timeouts configurados,
      exceções tipadas por dependência (`RAGConnectionError`,
      `VisionModelIndisponivelError`, `GoogleCalendarConnectionError`,
      `LocalBackendIndisponivelError`/`ExternalBackendIndisponivelError`),
      Monitor de Tom já roda em paralelo com a classificação
      (`asyncio.TaskGroup`) e já degrada com segurança em qualquer exceção,
      não só JSON malformado — não mexido, para não relitigar o que já
      funciona. 4 gaps genuínos encontrados e corrigidos:
      1. **MCP do Google Calendar sem timeout explícito** — herdava o
         timeout de leitura padrão do SDK `mcp` (300s); um
         `calendar-mcp-server` travado (não caído, só sem responder) podia
         prender um turno de agendamento por minutos. Novo
         `Settings.calendar_mcp_timeout_s` (15s), passado a
         `GoogleCalendarMCPClient` → `create_mcp_http_client`. Teste em
         `tests/test_google_calendar_client.py`.
      2. **Carga/inferência do CLIP sem timeout** — única dependência
         externa do projeto sem teto de tempo nenhum; um primeiro uso sem o
         modelo em cache (download) ou uma inferência patológica travava a
         requisição indefinidamente. Novo `Settings.clip_timeout_s` (30s) em
         `ClipEmbedder`, via `asyncio.wait_for` sobre o `asyncio.to_thread`
         (não mata a thread — Python não permite —, só para de esperar por
         ela) — timeout vira `RAGConnectionError`, já tratado nos endpoints
         existentes. Teste em `tests/test_rag_clip.py`.
      3. **Sem limite de tamanho em upload de imagem** — nenhum dos
         endpoints de imagem (ingestão de catálogo, busca, identificação no
         chat, OCR) checava tamanho: o corpo inteiro ia pra memória sem
         teto, risco real de OOM/DoS. Novo `imagem_excede_tamanho_maximo`
         (`app.ocr.image_processor`, `MAX_IMAGE_BYTES=10MB`), checado em
         `_validate_image` (`app.api.image_search`), no fluxo de
         identificação de `app.api.chat` e dentro de
         `extract_text_from_bytes` (cobre OCR). Testes em
         `tests/test_image_api.py`/`test_ocr_image_processor.py`.
      4. Monitor de Tom: os dois `except Exception` (LLM local e Jev) só
         logavam `str(exc)`, sem o tipo — uma falha de infraestrutura de
         verdade (Ollama fora do ar) e um bug de programação inesperado
         ficavam indistinguíveis no log. Adicionado `tipo: type(exc).__name__`
         em ambos.
      Nenhuma simplificação de MVP já documentada em `docs/ARCHITECTURE.md`
      §7 foi contestada — só gaps de implementação não discutidos antes,
      por isso sem decisão nova ali.
- [x] Investigar resposta vazia de `OllamaClient.generate_stream()` com
      modelos com capability `thinking` — achado durante a verificação E2E
      do Monitor de Tom (2026-09-24, não é bug do Monitor de Tom em si).
      Reproduzido direto contra o Ollama (`qwen3.5:9b`): o raciocínio pode
      consumir todo o orçamento de geração antes de chegar na resposta,
      `done: true` com `response` vazio em 100% das linhas. Resolvido
      reavaliando a decisão original (`docs/ARCHITECTURE.md` §5, correção
      de 2026-09-24): `think: false` passa a valer também em
      `generate_stream()`, igual a `generate()` — verificado ao vivo contra
      Ollama real (mesmo prompt que antes zerava a resposta, agora responde
      normalmente)
- [x] Corrigir acesso ao frontend quebrado fora da máquina de dev (IP da LAN,
      domínio DuckDNS) — achado durante teste manual no celular (2026-09-24,
      não é bug de nenhum requisito específico). Duas causas em sequência:
      (1) `crypto.randomUUID()` exige contexto seguro (https/localhost),
      indisponível ao acessar via HTTP pelo IP da LAN — `generateId()`
      (`frontend/lib/utils/generateId.ts`) adiciona fallback; (2) Next.js 16
      bloqueia por padrão o dev server (HMR + assets) para origens fora de
      localhost — `allowedDevOrigins` em `frontend/next.config.ts` libera o
      IP da LAN e o domínio DuckDNS. Regressão descoberta em seguida: as 6
      chamadoras de API do frontend hardcodeavam
      `NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"` — em qualquer
      origem que não fosse a própria máquina de dev, "localhost" no
      navegador aponta pro dispositivo do usuário, não pro backend, e todo
      fetch falhava. Resolvido com `frontend/lib/api/apiBaseUrl.ts`
      (deriva `<protocolo>//<hostname da página>:8000` em runtime) e
      `Settings.cors_allowed_origins` no backend virando lista separada por
      vírgula (antes só `http://localhost:3001`) — ver
      `docs/FRONTEND.md` §4. Commits `412c053`, `d7f0e4a`, `ab9c468`,
      `7d8426b`.
- [x] Achados menores do code-review parqueados na entrega das ferramentas
      MCP B2B (2026-09-24) — todos corrigidos (commits `d5300cb`, `451f2dc`,
      2026-09-29):
      1. `RagSearchConfigSection` não engole mais o erro de
         `getRuntimeSettings()` — chama `onError`
         (`frontend/app/admin/ingestao/page.tsx:232`) e ganhou teste
         dedicado (`IngestaoDocumentosPage.test.tsx:90`).
      2. Os 4 handlers de tool em `app.mcp_server.b2b`
         (`validar_compatibilidade`/`consultar_frete`/`cotar`/
         `reservar_pedido`) agora reaproveitam dois helpers compartilhados:
         `_abrir_sessao_bd` (traduz `SQLAlchemyError → ToolError`) e
         `_obter_e_validar_produtos` (busca em lote + validação "não
         encontrado") — `mcp_server/b2b.py:359-379`.
      3. `FreteItemIn`/`CotacaoItemIn`/`PedidoItemIn`
         (`app/models/mcp_b2b.py`) agora herdam todas de `ItemQuantidadeIn`.
      4. `cotar`/`consultar_frete`/`criar_pedido` buscam produtos em lote via
         `obter_produtos_por_ids` (`select(...).where(Produto.id.in_(ids))`)
         em vez de `obter_produto` item a item.
      5. `allowedDevOrigins` (`frontend/next.config.ts`) aceita
         `ALLOWED_DEV_ORIGINS` (env, lista separada por vírgula); os
         defaults hardcoded (IP da LAN, domínio DuckDNS) continuam como
         fallback — aceito como limitação de projeto de um único
         desenvolvedor (TCC), não pendência.

## Fase 10 — Avaliação Experimental (ver `docs/EVALUATION.md`)

- [ ] Rodar a avaliação comparativa entre as 9 configurações de modelo local
      candidatas (Llama 3.1 8B; Qwen2.5 7B; Qwen3 14B Q4_K_M/Q5_K_M; Qwen3 8B
      Q5_K_M/Q8_0; Phi-4-mini/Phi-4; Gemma-4-12B 4-bit/8-bit — ver
      `docs/ARCHITECTURE.md` tabela de escopo), medindo custo/latência e
      qualidade de resposta **contra o sistema completo** (RAG real da Fase 2,
      playbooks de domínio da Fase 3), não isoladamente — decidida
      deliberadamente para o final do roadmap, e não na Fase 1, porque uma
      medição precoce sem RAG/playbooks reais não reflete a qualidade real de
      cada candidato e arriscaria descartar/escolher um modelo com base em
      sinal incompleto. Resultado: escolha do `LOCAL_MODEL_NAME` final.
      `Gemma-4-12B` (4-bit) já confirmado disponível localmente
      (`gemma4:12b-it-q4_K_M`); os demais 8 ainda precisam ser baixados
      (`ollama pull`). `# MVP: primeira chamada após trocar de modelo tem
      custo de carga (cold start) bem maior que chamadas subsequentes —
      verificado empiricamente (~13s incluindo load vs. resposta quase
      imediata com modelo já quente); o script de benchmark deve descartar
      uma chamada de "aquecimento" por configuração antes de medir latência,
      com timeout maior que o LOCAL_LLM_TIMEOUT_S (30s) de produção`
- [x] Montar conjunto de teste rotulado para acurácia do roteador + matriz de
      confusão entre os quatro domínios — `backend/eval/router_intents/`
      (`dataset.json`: 40 mensagens, 10 por domínio, 8 deliberadamente
      ambíguas, ancoradas no catálogo/RAG reais já no sistema;
      `run_eval.py`: roda `app.router.classifier.classify` de verdade contra
      os três provedores). Rodado ao vivo (2026-09-30, Ollama +
      `gemma4:12b-it-q4_K_M` + OpenRouter reais): `heuristica` 52,5%,
      `heuristica_llm` **95,0%**, `jev_openrouter` 92,5% — nenhuma
      degradação silenciosa de provedor. Achado principal: 18 dos 19 erros
      da heurística pura são `fora_escopo` por sinônimo fora da lista fixa
      de `_DOMAIN_KEYWORDS` (não confusão entre domínios) — dado concreto
      para decidir o item pendente da Fase 1 ("revisitar a resolução de
      ambiguidade entre domínios no classificador"), ainda não resolvido
      aqui de propósito (é uma mudança de código separada, este item só
      constrói o instrumento de medição). Achado secundário ao escrever o
      script: `classify(provider="heuristica_llm")` só chama o LLM local de
      fato se `strategy="llm"` também for passado — sem isso (default
      `strategy="heuristic"`), cai direto no fallback heurístico sem
      nunca tentar o LLM, silenciosamente idêntico a `provider="heuristica"`
      (script corrigido para espelhar `efetiva_complexity_strategy` de
      `app.api.chat`; produção já fazia isso certo, só o script do eval
      errou primeiro). Resultado e tabela em
      `backend/eval/router_intents/README.md`.
- [x] Montar conjunto de perguntas de referência para qualidade do RAG
      (avaliação manual em escala 1–5 + LLM-as-judge) — conjunto de 20
      perguntas com gabarito já existia em
      `backend/eval/rag_quality/bateria_perguntas_rag.md` (commit
      `9603557`); extraído para `dataset.json` e rodada a avaliação em
      `run_eval.py`, reproduzindo o caminho real de produção do domínio
      Suporte (busca RAG + prompt + geração pelo modelo local, sem passar
      pelo classificador de intenção — já avaliado à parte) e julgando com
      um LLM-as-judge externo (prompt novo, documentado em
      `docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md`). **Correção de
      2026-10-01:** ao checar "quais documentos são pertinentes" antes de
      planejar o experimento seguinte de chunking, 2 das 20 perguntas (Q8 e
      Q19) citavam `Comparativo de funções - Intelbras Defense IA & Lite -
      V1.pdf` como fonte — um PDF que existe em `docs/Manuais_fornecedor/`
      mas **nunca foi ingerido no RAG**; nenhum chunking algum dia acertaria
      essas duas. Removidas de `dataset.json` (18 perguntas avaliadas de
      fato; continuam documentadas, marcadas, em
      `bateria_perguntas_rag.md`). Rodado ao vivo com o conjunto corrigido
      (2026-10-01, Ollama + `gemma4:12b-it-q4_K_M` + OpenRouter reais): nota
      média geral **2,78/5**, fonte correta recuperada em **78%** (14/18)
      das perguntas; nota média 3,0 com fonte certa x 2,0 sem (amostra
      pequena, n=4, nesse segundo grupo). Achado secundário sobre a própria
      ferramenta de medição: um PDF real tem espaço duplo no nome do
      arquivo, diferente do gabarito — a checagem de "fonte correta"
      precisou normalizar espaços antes de comparar; e chamadas sequenciais
      ao LLM-as-judge esbarram em rate limit (429) do OpenRouter às vezes —
      `run_eval.py` ganhou retry com backoff exponencial. **Nota manual
      (1–5) fica pendente de propósito** (`results.json`, campo
      `nota_manual: null`) — preenchê-la com outra chamada de LLM seria um
      segundo LLM-as-judge disfarçado, não a segunda fonte de sinal
      independente que `docs/EVALUATION.md` pede; exige o
      desenvolvedor/orientador olhar as 18 respostas geradas. Resultado e
      tabela completos em `backend/eval/rag_quality/README.md`.
- [x] Experimento complementar (a pedido explícito do desenvolvedor, fora
      da lista original de avaliações): busca por bisseção do `chunk_size`
      ideal — `backend/eval/rag_quality/chunk_size_search.py` cria
      collections temporárias (só os 11 PDFs reais do domínio Suporte,
      `chunk_overlap` sempre 12,5% do `chunk_size`), mede contra as mesmas
      18 perguntas e **sempre apaga a collection ao final** — nunca toca na
      collection de produção. Bisseção em vez de grade completa (custo:
      cada ponto reingere os 11 PDFs + roda as 18 perguntas) — começa nos
      extremos de uma sequência comum de duplicação (200/1600) e segue
      dividindo a metade que melhorou, comparando contra o baseline de 800
      já medido (não remedido). Rodado ao vivo (2026-10-01, 7 pontos em 5
      rodadas): melhor ponto encontrado **`chunk_size=375`** (nota 3,61 x
      2,78 dos 800 atuais, ~30% de melhora relativa) — mas com taxa de
      fonte correta PIOR (72%) que a de 800 (78%), 550 (83%) e 1600 (83%):
      o ganho não vem de recuperar melhor, vem de o modelo gerar melhor a
      partir de um contexto mais enxuto. Trajetória não monótona
      (800→900 cai, 900→550 sobe) — com 18 perguntas e uma rodada por
      ponto, isso indica uma região razoável (~300-550), não um ótimo
      provado; repetir cada ponto reduziria o ruído a um custo
      proporcional, fora de escopo aqui. Achado operacional: o modelo
      externo configurado (`EXTERNAL_MODEL_NAME`) é um tier `:free` do
      OpenRouter, com rate limit apertado — `run_eval.py` ganhou pausa
      proativa entre chamadas do juiz (3s) além do retry/backoff (base 8s).
      Nenhuma mudança aplicada à collection de produção — decisão de trocar
      o `chunk_size` real (requer recriar `docs_texto` e reingerir tudo)
      fica para quando o desenvolvedor decidir, não automática aqui.
      Detalhes em `backend/eval/rag_quality/README.md`.
- [x] Resiliência a prompt injection (direta, indireta via RAG, e via
      comprovante OCR) e abuso das ferramentas MCP B2B — plano de
      segurança anterior fictício (`PLANO_ANTI_AI_ATTACK.md`) descartado e
      substituído por isolamento real por delimitador + detecção log-only
      + eval comportamental com LLM real. Ver
      `docs/superpowers/specs/2026-10-07-seguranca-prompt-injection-mcp-design.md`
      e `backend/eval/prompt_injection/README.md` (resultado real).
- [ ] Medir latência (média e p95) do modelo local (configuração vencedora
      da comparação acima) x modelo externo para o mesmo conjunto de prompts
- [ ] Consolidar os resultados das quatro avaliações em um relatório curto
      para apresentação ao orientador

## Fase 11 — Preparação da Entrega

- [ ] Revisar todos os 12 requisitos funcionais contra o que foi de fato
      implementado (checklist final)
- [ ] Atualizar `docs/ARCHITECTURE.md`, `docs/FRONTEND.md` e este roadmap com
      o estado final do protótipo
- [ ] Preparar demonstração cobrindo os quatro domínios + agendamento + MCP
      B2B, usando a interface completa (site + widget de chat)
- [x] Achado da revisão de 2026-10-04 (ver `docs/ARCHITECTURE.md` §7):
      extraída a dependência compartilhada `require_admin`
      (`app.api.admin_auth`, antes duplicada como `_require_admin` em
      `admin_charts`/`admin_metrics`/`runtime_settings`) e aplicada a todos
      os routers `/api/admin/*` e `/api/rag/*` que ainda não checavam token
      de administrador no servidor: `admin_products`, `local_models`,
      `model_catalog`, `rag_collections`, `rag`, `rag_playground`, `crawler`,
      `tom_escalonamentos`. Antes, a única proteção desses endpoints era a
      UI do Next.js esconder a tela de quem não está logado como Admin.
- [x] Achado da revisão de 2026-10-04 (ver `docs/ARCHITECTURE.md` §6):
      `backend/src/app/rag/product_sync.py` e
      `backend/tests/test_product_sync.py` estavam órfãos desde o
      desacoplamento do CRUD de produtos do RAG (2026-10-03) — removidos
      fisicamente em 2026-10-04.
- [x] **Transbordo para Atendimento Humano e Fila de Suporte - Human-in-the-Loop (2026-10-05):**
      Implementação completa da especificação arquitetural `docs/superpowers/specs/2026-10-03-atendimento-humano-transbordo-design.md`:
      - Banco de Dados (Alembic 0021): Adicionadas colunas `atendente_id`, `atendente_nome`, `motivo_escalonamento`, `prioridade`, `escalado_em` em `conversas` e `atendente_nome` em `conversa_mensagens` (papel `"atendente"`).
      - Serviço com Lock Atômico (`atendimento_service.py`): Reivindicação concorrente atômica (`claim_conversa`) evitando que dois atendentes assumam o mesmo chat (HTTP 409 em colisão).
      - Pausa Estrita de IA (Zero Custo): Interceptação no chat SSE durante `aguardando_humano` e `em_atendimento_humano`, persistindo as mensagens do cliente sem invocar LLM (0 tokens consumidos).
      - Gatilhos de Transbordo: Automático via monitor de tom (frustração, prioridade 5) e solicitação direta no chat widget (`POST /api/chat/conversations/{id}/transbordo`).
      - REST API Administrativa: Endpoints `/api/admin/atendimento` (`/fila`, `/meus-chats`, `/{id}/claim`, `/{id}/mensagem`, `/{id}/close`) protegidos por `require_admin`.
      - Frontend Central de Atendimento: Página `/admin/atendimento` em 3 colunas (Fila de Espera, Meus Chats Ativos e Painel de Contexto do Cliente com dados cadastrais e compras) e link no `AdminGearMenu.tsx`.
- [x] **Conversão de Reserva para Venda com Comprovação Multimodal (2026-10-05):**
      Implementação completa da especificação e plano (`docs/superpowers/specs/2026-10-05-conversao-reserva-venda-design.md` e `docs/superpowers/plans/2026-10-05-conversao-reserva-venda.md`) cobrindo as 5 modalidades por canal de efetivação:
      - Banco de Dados (Alembic 0022): Novas colunas em `pedidos` (`comprovante_url`, `tipo_conversao`, `convertido_em`, `convertido_por`, `llm_parecer`) e novos status (`venda_concluida`, `pagamento_divergente`).
      - Serviço `ComprovanteEvaluator`: Auditoria multimodal de PDFs (via `pypdf`), imagens (visão/OCR) e texto estruturado com cálculo determinístico de divergência.
      - Modo 1 (Admin - Manual Simples): Endpoint `POST /api/admin/pedidos/{id}/converter-manual-simples` para baixa direta pelo operador (`manual_simples`).
      - Modo 2 (Admin - Manual com IA): Endpoints `POST /api/admin/pedidos/{id}/analisar-comprovante` e `POST /api/admin/pedidos/{id}/confirmar-conversao` para auditoria assistida com parecer e validação humana (`manual_padrao`).
      - Modo 3 (Admin - Automática via Upload): Endpoint `POST /api/admin/pedidos/{id}/converter-auto-admin` com validação autônoma por IA e tratamento de divergências (`auto_admin`).
      - Modo 4 (Chat - Cliente / Assistente Virtual): Conversão automática em tempo real no chat a partir de comprovante em texto ou imagem para qualquer reserva ativa (`auto_chat`), agnóstica a quantidade de itens ou descontos.
      - Modo 5 (MCP B2B Tool): Tool `@server.tool(name="converter_reserva_venda")` no servidor MCP corporativo e suporte no cliente independente Streamlit (`cliente-b2b`) com `auto_mcp_b2b`.
      - Frontend Administrativo: Interface `/admin/pedidos` com filtros por status, KPIs de faturamento, busca rápida e modal de conversão multimodal integrado com atalho no `AdminGearMenu.tsx`.
- [x] **Agente Analítico de Gráficos Dinâmicos: eliminar fallback hardcoded
      + introspecção automática de esquema (achado de 2026-10-06, revisão da
      "Correção de Precisão" de 2026-10-05, implementado em 2026-10-06):**
      decisão registrada em
      `docs/ARCHITECTURE.md` §5 ("Agente Analítico de Gráficos Dinâmicos").
      Substitui a parte deste item que falava em só corrigir
      `vendas_produtos_quantidade`/`vendas_produtos_valor`/
      `vendas_por_categoria`/`vendas_categoria_quantidade` em
      `chart_generator.py` — o objetivo real é que o LLM formule o SQL a
      partir do pedido em linguagem natural usando conhecimento real do
      esquema do banco, sem cair num fallback de consulta hardcoded quando
      falhar (achado concreto do motivo da imprecisão: o esquema escrito à
      mão em `safe_sql.get_catalog_schema_prompt()` não listava
      `venda_concluida` como valor de `pedidos.status`, só
      `reservado/aprovado/cancelado` — o LLM nunca tinha como filtrar venda
      efetivada corretamente).
      1. `analytics_agent.process_dynamic_chart_request`: remover o passo 3
         (fallback para `chart_generator.execute_chart_aggregation`) do
         caminho de geração de gráfico **novo** — se o Text-to-SQL falhar
         (LLM indisponível, SQL rejeitado pela validação de segurança, ou
         zero linhas), devolver `chart=None` com explicação do motivo em
         vez de um gráfico hardcoded potencialmente incorreto.
      2. Orquestrador: quando `chart=None`, responder ao admin com a
         explicação em vez de seguir silenciosamente tentando casar outras
         intenções (achado lateral: hoje isso já acontece em erro não
         tratado, sem nenhum aviso ao admin).
      3. `safe_sql.get_catalog_schema_prompt`: trocar o texto Markdown
         escrito à mão por introspecção real do banco (`sqlalchemy.inspect`,
         dialect-agnostic — Postgres em produção, SQLite nos testes),
         restrita à mesma whitelist `ALLOWED_TABLES`. Colunas tipo-enum sem
         `CHECK` no banco (ex.: `pedidos.status`) continuam com notas
         semânticas curadas à mão, à parte da introspecção automática.
      4. `chart_generator.execute_chart_aggregation`/`SUPPORTED_QUERIES`
         **removidos por completo** (não só desativados) — plano inicial era
         manter só para o refresh de gráficos antigos salvos com `query_key`
         fixa, mas o desenvolvedor confirmou que nenhum gráfico desses
         existe em uso; sem dado real pra migrar, não fazia sentido manter o
         código. `chart_generator.py` fica só com `detect_chart_request`
         (gate de intenção). O terceiro ramo do refresh em
         `app.api.admin_charts` (que recalculava via `query_key` fixa)
         também foi removido — `sql_query` fora de `dynamic_sql:`/
         `dynamic_user_data` simplesmente não é recalculado.
      As duas correções de precisão originais (filtrar `venda_concluida`;
      "vendas por categoria" somar vendas reais em vez do catálogo) foram
      implementadas antes dessa remoção ter sido decidida — ficam só
      registradas em `docs/ARCHITECTURE.md` §5 como histórico do bug, já que
      o código onde viviam não existe mais.
      Achado lateral removido no mesmo commit: `chart_generator.
      generate_and_persist_chart` já era código órfão antes de hoje (só os
      próprios testes do módulo chamavam; nenhum caminho de produção).
      Testes: `tests/test_safe_sql.py`, `tests/test_analytics_agent.py`,
      `tests/test_chart_generator.py`, `tests/test_admin_charts_api.py`,
      `tests/test_chat_chart_card.py`. `docs/Manuais/
      PROMPTS_E_INSTRUCOES_LLM.md` e `docs/Manuais/HOWTO_ADMINISTRADOR.md`
      atualizados.
- [x] **Métricas de Chat em Tempo Real (`admin_metrics.py`, achado de
      2026-10-05, implementado em 2026-10-06):** código independente do item
      acima (não importa nada de `chart_generator`/`analytics_agent`/
      `safe_sql` — tela fixa, sem interface conversacional, "Text-to-SQL
      dinâmico" não se aplica aqui por desenho). Decisão registrada em
      `docs/ARCHITECTURE.md` §5.
      - **Conversas ativas:** a consulta de tokens/custos deixou de exigir
        `Conversa.status == "encerrada"` — agora é uma consulta própria
        sobre `ConversaMensagem`, conta qualquer mensagem já respondida no
        período, conversa aberta ou não. O KPI "Chats Encerrados" continua
        exigindo fechada (é o que ele mede de propósito, não mudou).
      - **Agrupamento por Data de Mensagem:** tokens/custos agora bucketam
        por `ConversaMensagem.criada_em`; "Chats Encerrados" continua
        bucketado por `Conversa.encerrada_em` — são duas consultas e dois
        agrupamentos independentes agora, cada um na data que lhe pertence.
      Testes novos/atualizados em `tests/test_admin_metrics_api.py`. Doc de
      usuário atualizado em `docs/Manuais/HOWTO_ADMINISTRADOR.md`.
- [x] **MCP B2B (`converter_reserva_venda`, Modo 5) sem LLM/visão nenhuma
      (achado de 2026-10-06, implementado em 2026-10-06):** decisão
      registrada em `docs/ARCHITECTURE.md` §4 (gap 3) — achado ao revisar se
      as mudanças de comprovante/visão chegaram no MCP B2B e no cliente de
      demonstração do revendedor (`cliente-b2b/`). `create_b2b_mcp_server`
      (`app.mcp_server.b2b`) instanciava `ComprovanteEvaluator()` sem
      nenhum argumento — nem `llm_client`, nem visão local/externa — então
      essa ferramenta nunca usou LLM nenhum (só o fallback heurístico por
      regex) e nunca teve fallback de visão para comprovante em imagem,
      ficando pior que o chat antes mesmo da correção do item acima.
      `cliente-b2b/` não precisou de nenhuma mudança — é um cliente fino
      que só repassa o arquivo/texto pro servidor via chamada de
      ferramenta, toda a avaliação acontece do lado do servidor MCP.
      1. `create_b2b_mcp_server` ganhou `local_client`/`external_client`
         opcionais (mesmo padrão `OllamaClient`/`OpenRouterClient` do resto
         do projeto); `converter_reserva_venda` monta o `ComprovanteEvaluator`
         com a mesma política de custo mínimo (texto/OCR → visão local →
         visão externa) do chat e do admin.
      2. `scripts/run_mcp_b2b_server.py` (processo separado do FastAPI
         principal, não herda `app.state`) passou a instanciar os dois
         clientes a partir de `Settings` (mesmos campos que `app.main` usa)
         e repassar para `create_b2b_mcp_server`.
      Testes novos em `tests/test_mcp_converter_reserva.py` (LLM local
      chamado quando disponível; visão local antes da externa para
      comprovante em imagem; fallback para externa quando a local falha).
      Parâmetros opcionais com default `None` — os testes existentes que
      não passam clientes continuam no mesmo fallback heurístico de antes,
      comportamento inalterado.
- [x] **Unificar política de custo mínimo em processamento de imagem de
      documento (achado de 2026-10-06, implementado em 2026-10-06):** decisão
      registrada em `docs/ARCHITECTURE.md` §4 — para comprovante/pagamento/
      nota fiscal e para folder/página de catálogo (cadastro de produto),
      ordem de tentativa: (1) OCR local + LLM local sobre o texto; (2) se o
      OCR não render texto útil ou a interpretação local falhar, **visão
      local** via Ollama reaproveitando o `LOCAL_MODEL_NAME` já residente
      (sem modelo adicional); (3) só então fallback para visão externa
      (OpenRouter). O fluxo de identificação de produto por imagem qualquer
      já seguia "interno antes de externo" desde a Fase 3, não mudou. Três
      frentes implementadas:
      1. `OllamaClient.describe_image()` (`app.router.ollama_client`) —
         método novo (antes só texto): checa capability `vision` via
         `GET /api/show` antes de mandar a imagem (levanta
         `VisionModelIndisponivelError`, movida para `app.router.llm_client`
         e compartilhada com `OpenRouterClient`, se o modelo ativo não tiver
         visão — trata o caso de o admin trocar `LOCAL_MODEL_NAME` em
         runtime para um modelo só-texto), chama `POST /api/generate` com
         `images`, `think: false`. Testes em `tests/test_ollama_client.py`.
      2. `ComprovanteEvaluator.avaliar_documento` (`app.services.
         comprovante_evaluator`) reordenado para OCR-primeiro (antes, com
         `vision_client` presente, ia direto para visão, pulando o OCR) e
         ganhou `local_vision_client`, tentado antes do `vision_client`
         externo; religado em `processar_conversao_comprovante`
         (`app.router.sales_catalog`, antes só com `llm_client`) e nos dois
         endpoints de `app.api.admin_pedidos_conversao`. Tokens da chamada
         de visão (local e externa) agora contam em `ParecerComprovante`.
         Testes em `tests/test_comprovante_evaluator.py`.
      3. `extract_catalog_stream` (`app.catalog_extractor.extractor`) —
         branch de imagem avulsa (antes sempre `provider_usado="external"`
         direto) ganhou OCR + extração local, depois visão local, antes do
         fallback externo; `provider="external"` explícito do admin continua
         pulando direto para o externo, igual já fazia para páginas de PDF.
         Testes em `tests/test_catalog_extractor.py`.
      Prompts de visão (comprovante e catálogo) sem alteração de texto, só de
      roteamento — catalogados em
      `docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md` com a nota de onde cada um
      agora é chamado. Suíte completa (993 testes) e lint (`ruff check`/
      `ruff format`) verificados nos arquivos alterados.
- [x] Corrigir o `EXTERNAL_VISION_MODEL_NAME` quebrado no `.env` (achado de
      2026-10-06 ao testar visão: `qwen/qwen3.8-27b:free` devolve 404 do
      OpenRouter — "model unavailable for free") — trocado para
      `google/gemma-4-31b-it:free`, o mesmo default já documentado em
      `.env.example` (drift só no `.env` local, nunca commitado — ver
      `.gitignore`). Validado ao vivo: devolve 429 (rate limit temporário do
      provedor gratuito, já tratado com retry/backoff em
      `OpenRouterClient.describe_image`), não mais 404 (modelo inexistente).

## Explicitamente fora do MVP (não implementar sem decisão registrada em `docs/ARCHITECTURE.md`)

- Integração com CRM.
- Fine-tuning de modelo e otimização de latência em produção.
- Autorização de produção do MCP B2B: OAuth, permissões por ferramenta,
  rate limiting, auditoria completa, expiração/rotação de chaves (a
  exposição pública com chave estática por parceiro entrou no MVP em
  2026-09-25, ver `docs/ARCHITECTURE.md` §6).
- Integração com sistema de ticketing externo (Zendesk/Jira/Freshdesk — a
  fila nativa interna de atendimento humano e transbordo com locks atômicos
  e Central /admin/atendimento foi implementada em 2026-10-05).
- Reagendamento/cancelamento de visita e checagem de disponibilidade em
  múltiplas agendas.
