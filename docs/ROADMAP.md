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
- [ ] Revisitar a resolução de ambiguidade entre domínios no classificador
      (hoje: qualquer ambiguidade — 0 ou 2+ domínios casados por palavra-chave
      — colapsa para `fora_escopo`, que escala ao modelo externo) assim que o
      conjunto de teste rotulado de `eval/router_intents/` existir (Fase 10),
      para decidir se outra ordem de prioridade ou outra estratégia de
      desempate melhora a acurácia de roteamento
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
      `conversation_id`); campo `audio` (base64) processado via STT quando
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
      > NOTA: a lógica de negócio que faz o assistente *solicitar* um
      > comprovante (e assim ativar o modo OCR do lado do servidor) depende de
      > estado de conversa das Fases 4/6; por ora o modo documento é acionado
      > pelo frontend ao sinalizar `image_intent="documento"`.
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
      `tom_escalonamentos` — o banner visual no frontend fica para a Fase 8,
      ver `docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md` §9)

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
- [x] ~~Garantir e documentar que autenticação por parceiro e exposição
      pública **não** fazem parte do MVP~~ — **revisto em 2026-09-25**: o
      fornecedor está fora da rede local, então o MCP B2B precisa de
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

## Fase 6 — Memória e Classificação do Usuário (R9, R10)

Decisões de 2026-09-25 em `docs/ARCHITECTURE.md` §5 ("Fase 6, memória da
conversa e classificação do usuário").

- [ ] Implementar persistência da conversa por ID único — tabelas
      `conversas`/`conversa_mensagens` no Postgres (mensagens do cliente e
      do assistente), gravadas antes do evento `done`
- [ ] Implementar resumo automático periódico da conversa (não só ao final)
      — a cada 6 mensagens, em segundo plano, com o resumo no prompt
- [ ] Retomar a conversa no widget — `GET /api/chat/conversations/{id}/messages`
      e carregamento ao abrir o chat
- [ ] Implementar heurística inicial de classificação Cliente/Lead/Esporádico
      com base em histórico de compras/perguntas — base de clientes fictícia,
      e-mail captado no momento natural (pós-venda, agendamento), perfil no
      evento `done` e no painel de métricas

## Fase 7 — Frontend: Site Institucional, Produtos e Pedidos (ver `docs/FRONTEND.md`)

- [x] Criar o projeto Next.js (TypeScript) em `frontend/` conforme
      `docs/FRONTEND.md` §5 — scaffold com App Router, Tailwind CSS, ESLint +
      Prettier, Vitest + Testing Library; pastas `app/`, `components/`,
      `lib/`, `public/`, `tests/` populadas (não recriadas)
- [~] Implementar Home institucional e Contato — `app/page.tsx` e
      `app/contato/page.tsx` com conteúdo estático real (institucional/dados
      de contato fictícios); sem chamada de API (não há dados dinâmicos
      previstos para essas páginas no MVP)
- [~] Implementar listagem e detalhe de produtos (`/produtos`), consumindo a
      API do backend — apenas os stubs de rota (`app/produtos/page.tsx`,
      `app/produtos/[id]/page.tsx`) foram criados nesta etapa, sem consumir a
      API (que ainda não existe no backend); falta a integração real
- [~] Implementar autenticação simplificada (login/cadastro) e página de
      perfil — apenas stubs de rota (`app/conta/login/page.tsx`,
      `app/conta/perfil/page.tsx`), sem lógica de autenticação
- [~] Implementar fluxo de pedidos (carrinho/checkout) e histórico de pedidos
      — apenas stubs de rota (`app/pedidos/page.tsx`,
      `app/pedidos/historico/page.tsx`), sem carrinho/checkout real
- [x] Implementar página de Suporte/Central de Ajuda (esse conteúdo também é
      alvo do crawler do RAG, R4) — `app/suporte/page.tsx` com FAQ estático
      real (sem API; conteúdo fica pronto para o crawler indexar na Fase 2/3)
- [~] Implementar página de Agendamentos (leitura dos agendamentos criados
      via chat, R11) — apenas stub de rota (`app/agendamentos/page.tsx`), sem
      consumir a API (que ainda não existe no backend)
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
- [~] Implementar upload de imagem (`ImageUploader`) e gravação de áudio
      (`AudioRecorder`) — gravação de áudio concluída:
      `components/chat/AudioRecorder.tsx` (toggle, indicador visual de
      gravação, tratamento de permissão negada e de navegador sem suporte),
      integrado ao `ChatModal` (envio automático ao parar, bolha do usuário
      populada com `transcribed_message`, retry reenvia o mesmo áudio); falta
      só o `ImageUploader`, que continua dependendo de R6 no backend (ainda
      não implementado)
- [x] Implementar persistência do ID de conversa (retomar conversa entre
      sessões/páginas, R9) — `lib/hooks/useChatStore.ts`
      (`getOrCreateConversationId`), persistido em `localStorage`
- [ ] Implementar cards ricos: produto, confirmação de agendamento,
      cotação/reserva — depende de R6/R11/R12 no backend, ainda não
      implementados
- [x] Implementar indicador de domínio identificado pelo roteador
      (opcional, útil para a demonstração ao orientador) — rótulo discreto em
      `components/chat/MessageBubble.tsx`
- [x] Implementar indicador visual de origem do modelo (local x externo) —
      bolha do assistente em azul quando `backend_used` retornado pela API é
      `"externo"`, mesmo arquivo (`MessageBubble.tsx`)
- [ ] Implementar banner de transferência para atendente humano (monitor de
      tom, R8) — depende de R8 no backend, ainda não implementado
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

- [ ] Testes de integração cobrindo os quatro domínios de atendimento
      (backend)
- [~] Testes E2E do frontend cobrindo os fluxos críticos: chat (texto,
      imagem, áudio), pedido, login (ver `docs/FRONTEND.md` §6) — fluxo de
      chat texto e áudio feitos adiantado, junto do widget (Fase 8):
      `frontend/tests/e2e/chat.spec.ts` (Playwright), cobrindo envio de
      mensagem, erro/retry e gravação de áudio via dispositivo de mídia fake
      do Chromium (`--use-fake-device-for-media-stream` /
      `--use-fake-ui-for-media-stream`, `playwright.config.ts`); `# MVP: mocka
      POST /api/chat/messages via page.route em vez de rodar contra o
      backend/Ollama/STT reais`. Faltam imagem, pedido e login — dependem de
      R6/R12 e do fluxo de pedidos (Fase 7) ainda não implementados
- [ ] Ajustes de robustez nas frentes mais custosas: RAG multimodal e monitor
      de tom
- [ ] Revisão de tratamento de erro para dependências externas
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
- [ ] Achados menores do code-review parqueados na entrega das ferramentas
      MCP B2B (2026-09-24), não corrigidos ainda:
      1. `RagSearchConfigSection` (`frontend/app/admin/ingestao/page.tsx`)
         engole silenciosamente erro no carregamento inicial de
         `getRuntimeSettings()` — o toggle de isolamento de domínio do RAG
         (`rag_search_domain_fallback`) renderiza desmarcado sem indicar se
         é o valor real ou uma falha de rede; não chama `onError` como os
         demais loaders do mesmo formulário. Sem cobertura de teste (o
         teste antigo desse controle foi removido junto da reorganização
         do form, sem substituto na página que passou a hospedá-lo).
      2. Os 4 handlers de tool novos em `app.mcp_server.b2b`
         (`validar_compatibilidade`/`consultar_frete`/`cotar`/
         `reservar_pedido`) duplicam entre si o mesmo bloco "produto não
         encontrado" + `try/except SQLAlchemyError → ToolError" — mesmo
         padrão já duplicado 3x nos 4 resources de leitura desta fase, sem
         um helper compartilhado.
      3. `FreteItemIn`/`CotacaoItemIn`/`PedidoItemIn`
         (`app/models/mcp_b2b.py`) redeclaram cada uma o mesmo par
         `produto_id: int` / `quantidade: int = Field(gt=0)` em vez de um
         schema base comum.
      4. `cotar`/`consultar_frete` (`app.mcp_server.b2b`) e `criar_pedido`
         (`app.db.catalog`) buscam produto por produto num loop
         (`obter_produto` por item) em vez de uma única query em lote
         (`select(...).where(Produto.id.in_(ids))`) — irrelevante no
         tamanho atual do catálogo fictício (5 produtos), mas descrito
         pelo code-review como um padrão N+1 que escalaria mal com um
         catálogo maior; para `criar_pedido` também estende o tempo de
         retenção da transação de escrita.
      5. `allowedDevOrigins` (`frontend/next.config.ts`) tem o IP da LAN e
         o domínio DuckDNS de uma máquina/rede específica hardcoded no
         repositório — funciona só para quem desenvolve nessa mesma
         rede; qualquer outra pessoa (ou a mesma rede com IP diferente via
         DHCP) reproduziria o bug de acesso mobile já corrigido. Aceito
         como limitação de projeto de um único desenvolvedor (TCC), não
         um descuido — registrado aqui só para rastreabilidade, não
         necessariamente para corrigir.
      Todos de baixa severidade (estilo/robustez, não correção); avaliar
      se compensa corrigir junto de um item maior desta fase ou como
      tarefa isolada.

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
- [ ] Montar conjunto de teste rotulado para acurácia do roteador + matriz de
      confusão entre os quatro domínios
- [ ] Montar conjunto de perguntas de referência para qualidade do RAG
      (avaliação manual em escala 1–5 + LLM-as-judge)
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

## Explicitamente fora do MVP (não implementar sem decisão registrada em `docs/ARCHITECTURE.md`)

- Integração com CRM.
- Fine-tuning de modelo e otimização de latência em produção.
- Autorização de produção do MCP B2B: OAuth, permissões por ferramenta,
  rate limiting, auditoria completa, expiração/rotação de chaves (a
  exposição pública com chave estática por parceiro entrou no MVP em
  2026-09-25, ver `docs/ARCHITECTURE.md` §6).
- Integração real com fila de atendimento humano e sistema de ticketing.
- Reagendamento/cancelamento de visita e checagem de disponibilidade em
  múltiplas agendas.
