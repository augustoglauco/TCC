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
      — `backend/src/app/logging_config.py` (contextvar + formatter JSON)
- [x] Configurar lint/format (ruff/black) e pipeline de testes (pytest) —
      `backend/pyproject.toml` ([tool.ruff], [tool.pytest.ini_options])

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
      `conversation_id`, resposta síncrona/JSON, sem SSE); campo `audio`
      (base64) processado via STT quando presente, com fallback para
      `payload.message` se a transcrição vier vazia (`# MVP: ...`)
- [x] Implementar STT (áudio → texto) com suporte a pelo menos dois formatos
      comuns (ex.: wav e mp3) — `backend/src/app/stt/whisper_client.py`
      (faster-whisper, GPU local), formato detectado pelo conteúdo dos bytes
- [x] Implementar ingestão de PDFs/textos e busca vetorial (RAG) —
      `backend/src/app/rag/` (`embeddings.py`: sentence-transformers
      `paraphrase-multilingual-MiniLM-L12-v2`, config `RAG_EMBEDDING_MODEL`;
      `chunking.py`: tamanho fixo com overlap; `pdf_extract.py`: `pypdf`;
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
- [ ] Implementar conector de leitura a um banco de dados relacional
      (`# MVP: somente leitura, sem sincronização incremental`)
- [ ] Implementar crawler restrito a um conjunto pré-definido de páginas
      (até ~5), sem agendamento (`# MVP: escopo restrito`)
- [x] Implementar endpoint HTTP de upload para ingestão de documentos no RAG
      (`POST /api/rag/documents`, `backend/src/app/api/rag.py`), complementando
      `backend/scripts/ingest_sample_docs.py` — decisão registrada em
      `docs/ARCHITECTURE.md` §5. Reaproveita `app.rag.ingest.ingest_bytes`
      (refatorado a partir de `ingest_file`, que agora delega para a mesma
      função a partir de `path.read_bytes()`); erros de formato de arquivo
      (`.csv` etc.) viram 400, domínio inválido 422 (`Literal` do Pydantic),
      texto não-UTF-8/PDF corrompido também 400 (`UnicodeDecodeError`/
      `PyPdfError` tratados explicitamente — sem isso viravam 500 crus),
      Qdrant indisponível 503

## Fase 3 — RAG Multimodal, Tratamento de Imagem e Domínios (R4, R6, R7)

- [ ] Implementar entrada de imagem no chat (fluxo básico)
- [ ] Implementar OCR para imagens dirigidas (ex.: comprovante solicitado
      pelo sistema)
- [ ] Implementar busca multimodal via embeddings (ex.: CLIP) sobre um
      catálogo de imagens ampliado (`# MVP: catálogo ampliado, não completo`)
- [ ] Implementar reranking básico dos resultados de busca por imagem
- [ ] Implementar fallback para busca externa de imagem quando não encontrado
      no catálogo interno
- [ ] Separar fluxo/prompts por domínio: Vendas, Suporte Técnico, Atendimento
      ao Usuário, Agendamento de Visita
- [ ] Escrever playbooks iniciais de atendimento para Suporte Técnico e
      Atendimento ao Usuário
- [ ] Escrever playbook de Vendas com oferta proativa de agendamento de
      visita quando a conversa indica intenção de compra e o portfólio de
      produtos é compatível (ver `docs/ARCHITECTURE.md`, linha "Domínios"
      da tabela de escopo)

## Fase 4 — Agendamento via MCP e Monitor de Tom (R8, R11)

- [ ] Implementar cliente MCP para o Google Calendar
- [ ] Implementar nova intenção de agendamento no roteador (coleta de
      data/hora e dados básicos na conversa)
- [ ] Implementar confirmação automática por e-mail após criar o evento
- [ ] Implementar tratamento de erro claro para falha de conexão/autenticação
      do MCP do Google Calendar (sugerir nova tentativa ou transferir para
      atendente)
- [ ] Implementar classificador leve de sentimento/urgência (heurística +
      LLM leve)
- [ ] Implementar alerta e transferência simulada para atendente humano + log
      dos casos escalonados

## Fase 5 — MCP B2B Provido pela Empresa (R12)

- [ ] Modelar o backend único de dados (catálogo, estoque, preços, manuais)
      reaproveitado tanto pelo RAG quanto pelo servidor MCP
- [ ] Implementar servidor MCP interno expondo os 4 recursos de leitura
      (catálogo, estoque, tabela de preços, manuais)
- [ ] Implementar as 4 ferramentas do MCP B2B: validação de compatibilidade,
      consulta de frete e prazos, cotação automática, reserva/pedido
- [ ] Integrar o Roteador/Orquestrador como "mais um integrador" do MCP B2B
      para intenções de Vendas (cotação, compatibilidade, estoque)
- [ ] Garantir e documentar que autenticação por parceiro e exposição
      pública **não** fazem parte do MVP
      (`# MVP: uso interno, sem autenticação por parceiro`)

## Fase 6 — Memória e Classificação do Usuário (R9, R10)

- [ ] Implementar persistência da conversa por ID único
- [ ] Implementar resumo automático periódico da conversa (não só ao final)
- [ ] Implementar heurística inicial de classificação Cliente/Lead/Esporádico
      com base em histórico de compras/perguntas

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

- [x] Implementar botão flutuante + painel de chat (`ChatWidget`,
      `ChatPanel`), presente em todas as rotas — `components/chat/ChatWidget.tsx`,
      `components/chat/ChatPanel.tsx`, incluído em `app/layout.tsx`
- [~] Implementar envio de texto e exibição do streaming de resposta (SSE) —
      envio de texto síncrono concluído (`lib/api/chat.ts`, `ChatPanel`),
      consumindo `POST /api/chat/messages`; falta o streaming via SSE, que
      depende de `GET /api/chat/stream/{conversation_id}` (ainda não existe
      no backend)
- [~] Implementar upload de imagem (`ImageUploader`) e gravação de áudio
      (`AudioRecorder`) — gravação de áudio concluída:
      `components/chat/AudioRecorder.tsx` (toggle, indicador visual de
      gravação, tratamento de permissão negada e de navegador sem suporte),
      integrado ao `ChatPanel` (envio automático ao parar, bolha do usuário
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
      próprio `POST /api/chat/messages` (`ChatPanel`, bolha de erro com botão
      "Tentar novamente", sem retry automático); o caso específico de falha
      do MCP do Google Calendar será coberto quando R11 existir no backend

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
- Exposição pública do MCP B2B a parceiros externos reais (autenticação,
  OAuth, rate limiting, auditoria completa).
- Integração real com fila de atendimento humano e sistema de ticketing.
- Reagendamento/cancelamento de visita e checagem de disponibilidade em
  múltiplas agendas.
