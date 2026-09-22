# Arquitetura — Assistente Virtual Multimodal com Roteador Inteligente

> Fonte: adaptado do documento de proposta ao orientador (TCC). Este documento
> é a referência técnica única de arquitetura e escopo — mantenha-o
> atualizado conforme decisões mudam durante o desenvolvimento. `CLAUDE.md` e
> `.agents/rules/project.md` apontam para cá; não duplique decisões neles.

## 1. Objetivo do projeto

Assistente virtual multimodal (texto, imagem e áudio) capaz de atender
clientes em quatro domínios: Vendas, Suporte Técnico, Atendimento ao Usuário e
Agendamento de Visita. O sistema combina um modelo de IA executado localmente
em GPU (16GB) com a possibilidade de acionar modelos externos quando
necessário, apoiado por um Roteador/Orquestrador que interpreta a intenção do
usuário e decide o caminho mais adequado — incluindo busca aumentada por
recuperação (RAG) em bases de dados, documentos, sites e imagens, e o
acionamento de MCPs (Model Context Protocol) em duas direções:

- **Como cliente** de um MCP externo, para marcar visitas diretamente no
  Google Calendar.
- **Como provedor** de um MCP próprio, que expõe catálogo de produtos,
  estoque, preços e manuais, além de ferramentas de validação de
  compatibilidade, frete, cotação e reserva/pedido — tanto para o próprio chat
  quanto para IAs de parceiros integradores.

Além da conversa em si, o sistema reconhece o perfil do usuário (cliente,
lead ou contato esporádico), mantém memória entre interações e monitora o
tom da conversa para acionar um atendente humano quando necessário.

## 2. Visão geral da arquitetura

Fluxo macro: entrada multimodal → pré-processamento (STT para áudio, OCR para
imagem) → Roteador/Orquestrador (intenção + perfil do usuário) → módulos de
domínio (RAG, modelo local, modelo externo, monitor de tom, classificação de
usuário) → MCPs (Google Calendar consumido; MCP B2B provido) → resposta ao
usuário.

```
Entrada multimodal (texto / áudio / imagem)
        │
        ▼
Pré-processamento (STT / OCR)
        │
        ▼
Roteador / Orquestrador  ──── (paralelo) ──── Monitor de tom
        │                                          │
        ├──► RAG (BD, PDFs, sites, imagens)        ├──► Atendente humano
        ├──► Modelo local (GPU 16GB)                    (transferência)
        ├──► Modelo externo
        ├──► MCP Google Calendar (agendamento)
        └──► MCP B2B (catálogo, estoque, preços — provido)
        │
        ▼
   Resposta ao usuário
```

Este diagrama cobre a arquitetura de IA/backend. A interface que o usuário
efetivamente usa (site institucional, produtos, pedidos e o widget de chat
que expõe esse fluxo) é documentada separadamente em `docs/FRONTEND.md`.

## 3. Requisitos funcionais

| # | Requisito |
| --- | --- |
| R1 | Modelo de IA rodando localmente em GPU de 16GB, sem depender de nuvem para as tarefas essenciais. |
| R2 | Entrada de chat multimodal: aceitar texto, imagem e áudio. |
| R3 | Roteador/Orquestrador que identifica a intenção do usuário e decide entre modelo interno ou externo. |
| R4 | RAG capaz de buscar em banco de dados, textos, PDFs, sites e banco de imagens. |
| R5 | Conversão de áudio em texto (STT) antes da análise e contextualização no chat. |
| R6 | Tratamento de imagem: uso dirigido (ex.: comprovante solicitado) ou uso espontâneo (busca de produto interno, com fallback para busca externa) — via OCR e identificação de imagem. |
| R7 | Domínios de atendimento: Vendas, Suporte Técnico, Atendimento ao Usuário e Agendamento de Visita, com identificação de intenção pelo orquestrador. |
| R8 | Monitoramento contínuo do tom da conversa, com transferência para atendente humano em casos de urgência ou insatisfação. |
| R9 | Armazenamento da conversa com identificação única, permitindo retomar com um resumo do histórico recente. |
| R10 | Classificação do usuário ao longo da conversa como Cliente, Lead ou Cliente Esporádico. |
| R11 | Módulo de agendamento de visita, reconhecido como intenção própria pelo roteador, que aciona um MCP — preferencialmente o do Google Calendar — para criar o evento. |
| R12 | Exposição de um MCP próprio pela empresa (servidor/provedor), disponibilizando catálogo, estoque, preços e documentação técnica, além de ferramentas de validação de compatibilidade, frete, cotação e reserva/pedido, para uso por IAs de parceiros integradores e, internamente, pelo próprio Roteador/Orquestrador. |

**Assimetria intencional entre domínios:** Vendas e Agendamento de Visita
contam, desde o MVP, com ferramentas de ação (o MCP B2B da Seção 6 e o MCP do
Google Calendar, respectivamente). Suporte Técnico e Atendimento ao Usuário
são resolvidos, no protótipo, pela combinação de LLM e RAG (textos, PDFs,
manuais, crawler do site), sem uma camada de ação dedicada — abrir/acompanhar
chamados via ticketing é evolução futura (ver Seção 6 e `docs/ROADMAP.md`).

## 4. Fluxos de decisão: imagem e monitoramento de tom

**(a) Tratamento de imagem:** imagem recebida → o sistema **solicitou** um
comprovante/documento (fluxo dirigido)? → **sim:** OCR + validação. → **não**
(padrão — o cliente nunca envia imagem para OCR sem solicitação): fluxo de
**identificação de produto**.

> **Decisão registrada (Fase 3, 2026-09-20 — fluxo de imagem e fallback
> externo):** o padrão para qualquer imagem enviada no chat é a
> **identificação de produto**; o OCR é a exceção, acionado apenas quando o
> sistema solicitou explicitamente um comprovante/extrato. No contrato do
> chat isso é sinalizado por `image_intent`: ausente/`"produto"` → fluxo de
> identificação (padrão); `"documento"` → OCR (comportamento atual). A regra
> de negócio que faz o assistente *pedir* um comprovante (e assim ativar o
> modo OCR do lado do servidor) depende de estado de conversa das Fases 4/6;
> por ora o gatilho do modo documento é carregado pelo frontend quando o
> assistente pede o comprovante.
>
> **Fluxo de identificação de produto** (motor em
> `app.rag.image_identification`, endpoint `POST /api/rag/images/identify` e
> integração no chat):
> 1. **Catálogo interno (CLIP):** embeda a imagem e busca em
>    `catalogo_imagens`. Se o melhor score ≥ `IMAGE_INTERNAL_CONFIDENCE`
>    (limiar alto, default 0.30, configurável em runtime) → retorna o produto
>    do catálogo, sem chamar o externo.
> 2. **Visão externa (fallback):** se o interno não teve confiança
>    suficiente, consulta um modelo de visão via OpenRouter
>    (`EXTERNAL_VISION_MODEL_NAME`) pedindo resposta objetiva em JSON:
>    `{"produto": "<nome>", "e_do_portfolio": bool, "confianca": 0..1}`. O
>    prompt informa o portfólio da empresa: **produtos de segurança —
>    câmeras, sensores, automação, equipamentos de rede, catracas
>    eletrônicas, identificadores biométricos e gravadores de imagem**.
> 3. **Decisão:** se `e_do_portfolio == true` **e**
>    `confianca >= IMAGE_EXTERNAL_CONFIDENCE` (limiar alto, default 0.80,
>    configurável) → usa o nome retornado (mais o contexto de mensagens
>    recentes do usuário, quando houver) para buscar no **RAG de texto**
>    (`docs_texto`) e retorna os detalhes do produto. Caso contrário (não é
>    do portfólio, confiança baixa, ou resposta não-parseável) → responde
>    objetivamente que **não identificou o produto**.
>
> Os três parâmetros (`EXTERNAL_VISION_MODEL_NAME`, `IMAGE_INTERNAL_CONFIDENCE`,
> `IMAGE_EXTERNAL_CONFIDENCE`) têm default no `.env` (apenas para popular o
> frontend) e são ajustáveis em runtime via `GET`/`PUT
> /api/admin/runtime-settings`, exibidos na tela `/admin/modelos`. `# MVP:
> chamada a provedor externo pago no fluxo de imagem — decisão consciente,
> não evolução futura; sem busca reversa de imagem nem catálogo visual
> externo, o "externo" é um modelo de visão que só nomeia/classifica o
> produto`.

**(b) Monitoramento de tom:** nova mensagem no chat → classificador de
sentimento/urgência → ultrapassou o limiar de urgência/insatisfação? →
**não:** fluxo normal continua. → **sim:** alerta e transferência para
atendente humano.

## 5. Escopo do MVP e evolução futura

Três decisões de escopo:

1. Integração com CRM está **fora do escopo** do projeto.
2. Agendamento de visita é uma nova intenção do roteador que aciona um MCP
   **externo** (preferencialmente Google Calendar), em vez de um módulo de
   agenda construído internamente.
3. O MCP de integração B2B (R12) nasce como **servidor interno**, consumido
   primeiro pelo próprio chat, e só evolui para exposição real a parceiros
   externos depois (ver Seção 6).

R4 estabelece que o RAG deve buscar em BD, textos, PDFs, sites e banco de
imagens — por isso, conector a BD relacional, crawler de sites e RAG
multimodal sobre imagens são **obrigatórios no MVP**, não itens adiáveis, mas
entram em versões simplificadas frente a uma versão de produção: o conector
ao BD é somente leitura, sem sincronização incremental; o crawler navega de
verdade a partir de uma URL semente informada pelo admin, com profundidade e
teto de páginas parametrizáveis por execução, disparo sempre manual, sem
agendamento; o catálogo de imagens do RAG multimodal é ampliado, mas ainda
não completo, com reranking básico dos resultados.

**Decisão registrada (Fase 2, resolve divergência entre o comentário original
de `orchestrator.py` e o spec de design da Fase 1):** ao trocar o
`NullRAGClient` pela busca vetorial real no Qdrant, o conteúdo dos documentos
recuperados passa a ser **injetado no prompt do LLM** (a resposta fica
fundamentada no que está nos PDFs/textos indexados), não só usado como sinal
binário (vazio/não-vazio) para a decisão local x externo — esse sinal
continua existindo (ainda decide o roteamento), mas deixa de ser o único
efeito da busca. Sem isso, ter RAG de verdade não mudaria a qualidade da
resposta, só a decisão de roteamento.

**Decisão registrada (Fase 2):** a ingestão de documentos no RAG passa a ter
um segundo caminho além do script `backend/scripts/ingest_sample_docs.py` —
um endpoint HTTP (`POST /api/rag/documents`, upload de PDF/texto +
`domain`) e uma página administrativa simples no frontend (`/admin/ingestao`,
fora da navegação pública) que o consome. O script continua existindo para
ingestão em lote/repetível; o endpoint cobre o caso de adicionar um
documento avulso sem precisar de acesso ao terminal do servidor. Reabre
parcialmente a exclusão geral de "painel administrativo" que constava em
`docs/FRONTEND.md` §8 (ver decisão revista lá) — mantida para
catálogo/estoque/preços, mas não mais uma proibição geral. `# MVP:` mesmas
simplificações do script — sem autenticação (rota não listada na navegação
pública, mas não protegida por login), sem deduplicação/reingestão
incremental (mesma limitação de `app.rag.qdrant_client.upsert_chunks`).

**Decisão registrada (além do MVP, a pedido explícito, 2026-09-14):** toda
ingestão de documento no RAG (endpoint HTTP ou script em lote) passa a criar
um registro persistente no Postgres (`rag_documents`) — o primeiro uso real
dessa infraestrutura, até então só prevista em config/`docker-compose.yml`.
A partir desse registro, um documento pode ser listado e excluído (linha do
Postgres + pontos correspondentes no Qdrant, amarrados por um `document_id`
gravado no payload de cada ponto). Esta funcionalidade **não faz parte do
MVP original** — foi implementada por pedido explícito do usuário antes de
retomar os itens pendentes da Fase 2 (conector de BD relacional, crawler).
Fica registrada aqui para não ser confundida com um item do escopo original
nem esquecida na revisão final (Fase 11). Detalhes de implementação:
`docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md`.

**Decisão registrada (além do MVP, a pedido explícito, 2026-09-15):** o
registro de documentos acima evolui para **múltiplos perfis de collection**
configuráveis (chunk size/overlap, modelo de embedding, dimensão, métrica de
distância, HNSW, quantização de vetores, payload indexing do Qdrant) —
Entregas B e C+D anunciadas como "spec futura" na decisão anterior, agora
combinadas numa só entrega por ficarem interdependentes. Cada collection é um
perfil imutável (mudar um parâmetro é criar uma nova collection); uma delas é
marcada como "ativa" e é a que o chat de fato usa, enquanto as demais servem
para comparação num playground de busca administrativo (pergunta única
rodada contra várias collections, resultados/score/latência lado a lado, sem
métrica agregada de qualidade — isso continua reservado para a Fase 10,
Avaliação Experimental). Documentos ganham um arquivo original salvo em
disco (`backend/data/rag_uploads/`), permitindo reingerir o mesmo documento
em outra collection para comparação. Como a entrega anterior, **não faz
parte do MVP original** — fica registrada aqui e no roadmap para não ser
confundida com item do escopo original nem esquecida na revisão final (Fase
11). Detalhes de implementação:
`docs/superpowers/specs/2026-09-15-rag-collections-config-design.md`.

**Decisão registrada (além do MVP, a pedido explícito, 2026-09-21):**
collections ganham um campo de **finalidade** (`purpose`): `chat` (default,
pública, elegível a ser ativada e buscada pelo chat) vs `mcp_b2b` (restrita
ao canal MCP B2B). O admin pode ingerir, pela mesma tela `/admin/ingestao`,
documentação **exclusiva do canal MCP B2B** numa collection dedicada
`purpose="mcp_b2b"`, que **nunca é ativada** (a ativação é bloqueada com 409)
nem buscada pelo chat público — há ainda uma guarda de defesa em profundidade
em `ActiveCollectionRagClient.search` que falha fechado caso a invariante
seja quebrada. A **metade de consumo** desse conteúdo (o servidor MCP B2B de
fato lendo a collection restrita) permanece na **Fase 5 (R12)**, não
antecipada aqui — por ora o conteúdo fica ingerido e isolado, sem consumidor.
Segue **fora do MVP** tudo que caracteriza acesso externo real: autenticação
por parceiro, isolamento multi-tenant, exposição pública, rate limiting e
auditoria (ver seção "Explicitamente fora do MVP" no roadmap). Como as demais
entregas fora do MVP, fica registrada aqui e no roadmap para não ser
confundida com item do escopo original nem esquecida na revisão final (Fase
11). Detalhes de implementação:
`docs/superpowers/specs/2026-09-21-ingestao-mcp-b2b-design.md`.

**Decisão registrada (além do MVP, a pedido explícito, 2026-09-16):** uma
tela administrativa (`/admin/modelos`) passa a permitir listar os modelos
locais já baixados no Ollama, trocar em runtime qual deles o chat usa, e
baixar um novo — tanto da biblioteca padrão do Ollama quanto um GGUF
hospedado no Hugging Face (`ollama pull hf.co/<usuário>/<repo>`, suportado
nativamente pelo Ollama, sem motor de inferência adicional). O download
roda em background (nunca bloqueia o backend), com progresso acompanhado
por polling a partir do frontend. A seleção de modelo ativo fica só em
memória (reseta a cada restart) e **não substitui nem antecipa** a decisão
formal da Fase 10 (escolha do `LOCAL_MODEL_NAME` de produção via benchmark
offline contra o sistema completo) — é uma ferramenta de teste manual em
paralelo. Como as entregas anteriores fora do MVP, fica registrada aqui e
no roadmap para não ser confundida com item do escopo original nem
esquecida na revisão final (Fase 11). Detalhes de implementação:
`docs/superpowers/specs/2026-09-16-local-model-manager-design.md`.

**Decisão registrada (além do MVP, a pedido explícito, 2026-09-17):** a
mesma tela (`/admin/modelos`) ganhou uma seção "Parâmetros de execução"
para ajustar em runtime, também só em memória (reseta a cada restart): a
temperatura do modelo local (`OllamaClient.temperature`, `null` = usa o
default do próprio modelo — nenhuma chamada manda `options.temperature`
até alguém setar um valor explícito, sem mudar o comportamento anterior),
o timeout das chamadas não-streaming ao backend local e ao externo
(`OllamaClient.timeout_s`/`OpenRouterClient.timeout_s`), e a flag
`QdrantRAGClient.search_domain_fallback` (antes só configurável via
`.env`/restart, ver decisão de 2026-09-17 acima sobre o bug de isolamento
de domínio). Um único endpoint, `GET`/`PUT /api/admin/runtime-settings`
(`PUT` com atualização parcial — só os campos enviados mudam), cobre os
quatro parâmetros, já que eles tocam três clients diferentes (Ollama,
OpenRouter, Qdrant) e não fazem sentido debaixo do prefixo
`/api/admin/local-models`. Motivo direto: a temperatura do Ollama também é
usada pela chamada de classificação de intenção do roteador (mesmo
client/model) — baixá-la reduz a instabilidade de classificação
observada em mensagens de acompanhamento ambíguas, sem precisar de uma
chamada de classificação separada com `temperature` fixo. `# MVP: sem
persistência entre restarts, mesmo padrão do modelo ativo acima — não
substitui a escolha formal de hiperparâmetros da Fase 10`.

**Decisão registrada (Fase 2, conector de BD relacional exigido por R4,
2026-09-16):** o conector de leitura a BD relacional reaproveita o mesmo
Postgres já provisionado em `docker-compose.yml` (o mesmo usado por
`rag_documents`/`rag_collections`) — sem infraestrutura nova. Uma tabela
fixture fictícia, `produtos` (`id`, `nome`, `descricao`, `preco`,
`categoria`), é criada e semeada por migração Alembic
(`backend/migrations/versions/0003_produtos_fixture.py`), análoga em
espírito a `backend/scripts/sample_docs/` para PDFs/textos, mas para dados
estruturados; seus dados fictícios são coerentes com o catálogo de exemplo já
usado no RAG (geradores a diesel e acessórios, ver
`backend/scripts/sample_docs/vendas/catalogo_geradores.txt`). A leitura em si
(`app.rag.db_connector.read_table_as_text`) é genérica via reflexão de tabela
do SQLAlchemy (`Table(..., autoload_with=...)`) — recebe nome de
tabela/colunas e devolve linhas transformadas em texto (`coluna: valor` por
linha), não fica acoplada à tabela `produtos`. Cada linha lida é ingerida
como um documento próprio no RAG, reaproveitando `app.rag.ingest.ingest_bytes`
sem duplicar chunking/embedding/upsert (o texto da linha vira o "conteúdo do
arquivo", com um nome sintético `<tabela>_row<N>.txt`). Exposto só como
script CLI (`backend/scripts/ingest_db_table.py --table <nome> --domain
<dominio>`), no mesmo padrão de `backend/scripts/ingest_sample_docs.py` — sem
endpoint HTTP dedicado (diferente da ingestão de PDF/texto, que já tinha essa
necessidade validada via `/admin/ingestao`; aqui o caso de uso é
administrativo/pontual via terminal, sem tela nova no frontend). `# MVP:
somente leitura (sem INSERT/UPDATE/DELETE no BD de origem) e sem
sincronização incremental (execução manual sob demanda, sem agendamento nem
observação de mudanças) — mesma limitação de deduplicação/reingestão já
aceita em `app.rag.qdrant_client.upsert_chunks``.

**Decisão registrada (Fase 2, correção de revisão, 2026-09-16):**
`app.rag.db_connector.read_table_as_text` reforça a garantia de "somente
leitura" acima com a opção de execução `postgresql_readonly=True`
(`connection.execution_options(...)`, dialect-specific do Postgres, banco de
produção deste conector) — faz o próprio banco rejeitar qualquer
INSERT/UPDATE/DELETE acidental durante a leitura, sem precisar de uma role de
BD dedicada (infraestrutura nova, fora de escopo do MVP). Dialetos sem essa
opção (ex.: SQLite, usado nos testes) simplesmente a ignoram.

**Decisão registrada (Fase 2, correção de revisão, 2026-09-16):**
`QdrantRAGClient.create_collection` usa um `asyncio.Lock` por instância para
evitar a corrida TOCTOU entre checar se a collection já existe e criá-la de
fato (duas requisições concorrentes de criação com o mesmo nome não devem
colidir no erro genérico do Qdrant em vez do `CollectionAlreadyExistsError`
tratado). Funciona porque `QdrantRAGClient` é injetado como singleton por
processo (`request.app.state.qdrant_client`, ver `rag_dependencies.py`).
`# MVP: protege apenas concorrência dentro de um único worker Uvicorn — não
protege contra múltiplas instâncias/processos do backend rodando
simultaneamente contra o mesmo Qdrant`, o que é aceitável para o cenário de
desenvolvimento/demonstração deste protótipo (um único processo backend).

**Decisão registrada (Fase 3, R6, OCR para imagens dirigidas):**
`POST /api/chat/messages` passou a aceitar um campo `image` (base64,
PNG/JPG/WEBP). Quando presente, o OCR extrai o texto da imagem via
`pytesseract` (Tesseract 5.x, idiomas `por+eng`) e o concatena à mensagem
efetiva antes de passar ao orchestrator — o texto extraído é injetado como
contexto adicional, não substitui a mensagem de texto digitada (os dois
podem coexistir). Formato detectado por magic bytes, não pela extensão.
Formato inválido → 400; Tesseract indisponível → 503. `# MVP: uso dirigido
(comprovantes, documentos solicitados pelo sistema) — sem classificação
automática de tipo de imagem nem pré-processamento avançado (binarização,
deskew); busca por similaridade visual via CLIP é item separado abaixo`.

**Decisão registrada (Fase 3, R6, busca multimodal via CLIP):**
Busca por similaridade visual implementada via `ClipEmbedder` (CLIP
ViT-B/32, 512 dims, via `sentence-transformers` — já era dependência do
projeto, sem pacote novo) sobre uma collection dedicada `catalogo_imagens`
no Qdrant. Dois endpoints novos: `POST /api/rag/images` (ingestão de imagem
com `domain`) e `POST /api/rag/images/search` (busca por imagem de consulta
ou descrição textual — mesmo espaço vetorial CLIP). A collection é criada
automaticamente na primeira ingestão (dimensão 512, cosine fixos), diferente
das collections de texto que exigem criação explícita via API admin — aceito
porque `catalogo_imagens` é única e de configuração fixa neste protótipo.
`# MVP: catálogo ampliado mas não completo; reranking básico implementado
(ver decisão abaixo); sem deduplicação (mesmo comportamento de
`QdrantRAGClient.upsert_chunks`); score threshold mais baixo (0.20) que o
RAG de texto (0.35) porque scores cosine do CLIP são naturalmente menores`.

**Decisão registrada (Fase 3, reranking básico da busca por imagem):** a
busca por imagem (`app.rag.image_search`) agora recupera um pool maior
(`top_k * 3`) do Qdrant e reordena via `rerank_image_results` antes de cortar
para `top_k`. O rerank mantém a ordem por score do CLIP, mas soma um bônus
pequeno (0.05, só como chave de ordenação — o score exibido não muda) aos
resultados cujo `domain` bate com o domínio consultado, priorizando o domínio
pedido quando o pool é misto. `# MVP: reranking heurístico por domínio, sem
cross-encoder nem segundo modelo — o "básico" pedido no roadmap`.

**Decisão registrada (Fase 3, playbooks/prompts por domínio):** cada domínio
de atendimento de negócio (vendas, suporte, atendimento) tem um prompt de
sistema estático em `app.router.playbooks`, anteposto pelo orchestrator ao
prompt antes de chamar o LLM (com ou sem contexto de RAG). `fora_escopo` não
tem playbook. Reflete a assimetria intencional da Seção 3: Vendas oferece
proativamente o agendamento de visita quando há intenção de compra (a criação
real do evento é R11, Fase 4); Suporte e Atendimento são LLM + RAG, sem camada
de ação. `# MVP: playbooks são strings estáticas, sem versionamento nem edição
em runtime`. **Agendamento (Fase 4A) não usa playbook** — o
`_AGENDAMENTO_PLAYBOOK` estático foi removido (commit `a529f2b`, "remove
playbook morto") e substituído por um fluxo procedural dedicado,
`orchestrator._handle_agendamento` + `app.router.scheduling` (máquina de
estado de coleta/validação/confirmação, ver decisão registrada logo abaixo e
`docs/superpowers/specs/2026-09-21-agendamento-mcp-calendar-design.md`).

**Decisão registrada (Fase 4A, agendamento via MCP Calendar, R11):** três
escolhas de implementação feitas nesta fase, detalhadas em
`docs/superpowers/specs/2026-09-21-agendamento-mcp-calendar-design.md`:
(a) o assistente **consome** o servidor MCP remoto oficial do Google
(`calendarmcp.googleapis.com`) em vez de construir um servidor MCP próprio
que envolveria a API do Calendar — replicar do lado do servidor o que o
Google já publica de forma padronizada não ganharia a interoperabilidade que
é o motivo de existir do MCP (spec §2); (b) autenticação por **consentimento
único do admin** (OAuth `access_type=offline`, refresh token guardado em
`GOOGLE_CALENDAR_TOKEN_PATH`) em vez de autenticação por visitante — o caso de
uso é um backend headless agendando numa única agenda da empresa, não há
usuário final logado a cada visita (spec §3); (c) mensagens ao visitante
durante a coleta/confirmação são **templates determinísticos** (não geradas
por LLM), ver `app.router.scheduling` (`mensagem_campos_faltando`,
`mensagem_pedir_confirmacao`, `mensagem_sucesso`) — decisão para não arriscar
o LLM inventar/alucinar detalhes de confirmação (data, nome, e-mail) numa ação
irreversível (criação real de evento na agenda).

**Decisão registrada (Fase 2, melhoria de qualidade a pedido explícito,
2026-09-17):** `app.rag.pdf_extract.extract_text_from_pdf` trocou de `pypdf`
para `pdfplumber`, com uma heurística de detecção de layout em 2 colunas —
procura um corredor vertical sem nenhuma palavra na faixa central da página
(entre 15% e 85% da largura, corredor com pelo menos 2% da largura da
página **e** pelo menos 15pt em valor absoluto, o que for maior — o
segundo critério evita falso positivo em páginas com pouco texto, onde o
espaçamento natural entre 2-3 palavras já passava do limite relativo) e, se
achar, extrai cada coluna separadamente antes de concatenar. Motivo:
catálogos de produto (ex.: `docs/Manuais_fornecedor/`) têm produtos lado a
lado em colunas, e a extração anterior (`pypdf`, ordem "bruta" dos objetos
do PDF) embaralhava título/bullets de produtos vizinhos num único texto
corrido — verificado com os PDFs reais do projeto antes de implementar.
`chunk_text` (`app.rag.chunking`) também passou a preservar quebras de
linha como pontos de corte preferenciais (antes colapsava tudo em espaço
único), senão o chunking desfazia a estrutura recém-recuperada pela
extração. `# MVP: heurística cobre só 2 colunas e só quando existe um
corredor "limpo" atravessando toda a altura da página — layouts com 3+
colunas ou cabeçalhos de seção fora do padrão (testado com um caso real,
ver commit) caem no fallback de extração de página inteira, que ainda
assim preserva melhor a ordem de leitura do que a extração anterior; não
há regressão, só ausência do ganho extra do split por coluna nesses
casos`. Sem OCR para PDFs escaneados/baseados em imagem (isso continua
sendo R6, Fase 3).

**Decisão registrada (Fase 2/R3, correção de regressão, 2026-09-17):**
`QdrantRAGClient.search` ganhou (em trabalho paralelo de outro agente sobre
o chat) um fallback que, quando a busca filtrada por `domain` não retorna
nada, refazia a busca sem filtro de domínio — quebrando o isolamento entre
domínios (uma pergunta de "vendas" podia trazer conteúdo de "suporte") e
corrompendo o sinal de escalonamento do roteador (RAG vazio → escala pro
modelo externo, ver Seção 2/3): com o fallback, a busca quase nunca fica
vazia, então esse sinal deixa de refletir a realidade. Em vez de remover
esse comportamento, ele virou uma flag explícita —
`Settings.rag_search_domain_fallback` (`RAG_SEARCH_DOMAIN_FALLBACK` em
`.env`), passada para `QdrantRAGClient(search_domain_fallback=...)` —
**desligada por padrão** (mantém o comportamento documentado/correto).
`# MVP: existe só para comparação/experimento entre as duas estratégias,
não é uma opção recomendada para uso normal — ligá-la sacrifica isolamento
entre domínios e o sinal de escalonamento do roteador`.

**Decisão registrada (além do MVP, a pedido explícito, 2026-09-17):**
`POST /api/chat/messages` passa a devolver telemetria detalhada por
mensagem — modelo usado, tokens de entrada/saída, latência total, TTFT
(proxy via `prompt_eval_duration` do Ollama), TPS (via `eval_duration`,
geração pura), custo estimado, e tempo/qtd./score médio da busca no RAG —
inclusive, por chunk usado no contexto, o arquivo de origem e o score
individual (`rag_chunks`, adicionado em 2026-09-18: já existia internamente
em `Document.source`/`score`, só não era exposto na telemetria; hoje a busca
RAG só recupera de arquivos ingeridos, sem fonte de internet) (ver contrato
completo em `docs/FRONTEND.md` §4). O `ChatModal` mostra
essas métricas num painel e permite exportar a conversa em CSV/JSON
(`frontend/lib/utils/exportMetrics.ts`). Motivo: alimentar a avaliação
experimental da Fase 10 (`docs/EVALUATION.md`) com dados reais coletados
durante o desenvolvimento/demonstração, não uma feature de produto para o
usuário final. `# MVP: telemetria só em memória por resposta — não é
persistida em banco (isso seria a tabela `router_logs` da Fase 6); TTFT só
é preenchido para o backend local (Ollama expõe `prompt_eval_duration`),
fica `null` para o externo (OpenRouter não expõe essa granularidade em modo
não-streaming)`.

**Decisão registrada (Streaming SSE do chat, R2/R3, 2026-09-17):**
`POST /api/chat/messages` deixou de devolver um JSON síncrono único e passou
a devolver a resposta como o próprio stream **Server-Sent Events** (SSE),
`Content-Type: text/event-stream` — não existe um endpoint `GET` de stream
separado (uma ideia cogitada inicialmente em `docs/FRONTEND.md`, mas
descartada: manter tudo no mesmo `POST` evita duplicar a lógica de
validação de entrada/histórico de conversa entre dois endpoints). Eventos
emitidos, nesta ordem: `conversation` (id da conversa), `transcription`
(opcional, só quando há áudio transcrito), `status` (opcional, quando o
modelo escolhido ainda não está carregado), `token` (zero ou mais, um por
trecho de texto gerado — o cliente concatena para montar a resposta
completa) e, por fim, `done` (telemetria completa, mesmos campos que antes
iam no JSON síncrono, exceto o texto da resposta em si, que já chegou via
`token`) ou `error` em caso de falha de uma dependência (Ollama, OpenRouter,
Qdrant) **depois** que o stream já abriu — nesse ponto o HTTP já é 200, não
dá mais para trocar por um status de erro. Erros de validação de entrada
anteriores à abertura do stream (áudio base64 inválido, nem `message` nem
`audio`, STT indisponível) continuam HTTP 400/422/503 normal, sem SSE. O
histórico de conversa em memória só é atualizado quando o `done` chega com
sucesso, não em caso de `error`. Contrato completo (payload de cada evento)
em `docs/FRONTEND.md` §4. `# MVP: sem reconexão automática/`Last-Event-ID`
se a conexão cair no meio do stream — o cliente perde os tokens já enviados
e precisa reenviar a mensagem inteira, aceitável para este protótipo`.

**Decisão registrada (RAG com contexto de fallback, R4, 2026-09-17):**
A busca do RAG (`rag_client.search`) usava só a mensagem atual, mesmo o
classificador já considerando as últimas mensagens da conversa (ver linha
"Roteador/Orquestrador" abaixo). Isso fazia uma pergunta de acompanhamento
que omite o assunto já estabelecido (ex.: perguntar sobre câmeras e depois
"quais outras opções?") não encontrar nenhum chunk relevante — mesmo com o
domínio corretamente classificado como `vendas` — e escalar
desnecessariamente para o modelo externo (`motivo_escalonamento: rag_vazio`).
Corrigido em `orchestrator.handle_message`: quando a busca com a mensagem
isolada vem vazia **e** há histórico recente, uma segunda busca é feita com
o histórico concatenado à mensagem atual (mesma janela do classificador,
`_MAX_HISTORY_MESSAGES=3` em `api/chat.py`). A busca direta continua sendo
tentada primeiro e sozinha resolve a maioria dos casos — a segunda tentativa
só dispara quando necessário, para não diluir o embedding da busca com
contexto desnecessário no caso comum de pergunta autocontida. `# MVP: sem
reescrita de query via LLM (mais preciso, mas custaria uma chamada de rede
extra) — concatenação simples do histórico basta para o caso relatado`.

### Tabela de escopo por requisito

| Requisito | MVP (protótipo) | Evolução futura |
| --- | --- | --- |
| Modelo local (RTX40780 GPU 16GB) | Servido via **Ollama** (decisão fechada — simplicidade de setup/gestão de modelos e instrumentação de latência pronta via `eval_count`/`eval_duration`, ver `docs/TECHNOLOGY_STACK.md`). Avaliação comparativa ampliada entre **9 configurações**: Llama 3.1 8B; Qwen2.5 7B; Qwen3 14B (Q4_K_M e Q5_K_M); Qwen3 8B (Q5_K_M e Q8_0); Phi-4-mini/Phi-4 (3.8B–7B); Gemma-4-12B (4-bit e 8-bit) — ver riscos de VRAM na Seção 7 | Fine-tuning de domínio, otimização de latência em produção |
| Entrada multimodal | Texto e áudio (STT) funcionando, com suporte a mais de um formato de áudio (ex.: wav e mp3); imagem com fluxo básico. STT via **faster-whisper rodando na mesma GPU local** (decisão fechada — consistente com a estratégia "local-first" do resto do projeto, sem custo por chamada; ver risco de contenção de VRAM na Seção 7), modelo `small` ou `medium` conforme resultado da Seção 7 | Robustez para áudio ruidoso, formatos adicionais, streaming |
| Roteador/Orquestrador | Classificador de intenção simples (regras + LLM) para local x externo x RAG, com log básico de decisões (custo/latência). Modelo externo acessado via **OpenRouter** (uma chave cobrindo múltiplos provedores). Domínios Vendas/Suporte/Atendimento tentam local+RAG primeiro e só escalam para externo se: fora de escopo, RAG sem resultado relevante, ou complexidade alta; Agendamento é sempre local. Classificador considera as últimas 1–3 mensagens da conversa (não só a mensagem isolada), necessário para resolver confirmações curtas a ofertas feitas pelo próprio assistente (ex.: aceite de agendamento proposto) | Roteador adaptativo com aprendizado contínuo e métricas de custo/qualidade em produção |
| RAG — textos, PDFs, BD e sites (obrigatório) | Ingestão de PDFs/textos + busca vetorial; conector básico de leitura a um BD relacional; crawler disparado manualmente a partir de uma URL semente, com profundidade e teto de páginas parametrizáveis por execução, classificação de domínio por LLM com fila de revisão humana abaixo de um limiar de confiança | Conector com escrita/sincronização incremental, crawler agendado, múltiplas fontes web |
| RAG sobre imagens / tratamento de imagem (obrigatório) | Busca multimodal via embeddings (ex.: CLIP) em catálogo ampliado, com reranking básico + OCR para imagens dirigidas | Catálogo completo, embeddings mais robustos, busca externa refinada |
| Domínios (Vendas/Suporte/Atendimento) | Separação lógica de fluxo e prompts por domínio, com playbooks iniciais para Suporte Técnico e Atendimento ao Usuário. Playbook de Vendas inclui a oferta proativa de agendamento de visita quando a conversa indica intenção de compra e o portfólio de produtos é compatível (o roteador só reclassifica como `agendamento` na resposta seguinte do cliente, usando o contexto curto de conversa citado na linha "Roteador/Orquestrador") | Playbooks completos por domínio, integração com sistema de ticketing |
| Agendamento de visita (MCP consumido) | Nova intenção reconhecida pelo roteador; coleta data/hora e dados básicos; valida expediente e conflito de agenda (na mesma agenda configurada) local/via MCP antes de sequer pedir confirmação; exige confirmação explícita do visitante antes de criar o evento; chama o MCP do Google Calendar e envia confirmação automática por e-mail | Reagendamento/cancelamento, checagem de disponibilidade em múltiplas agendas, confirmação também por SMS |
| MCP de integração B2B (MCP provido) | Servidor MCP de uso interno, reaproveitando a base do catálogo/estoque/preços do RAG; recursos de leitura + as quatro ferramentas já implementadas; sem autenticação por parceiro nem exposição pública | Exposição a integradores externos reais, autenticação por parceiro (API key/OAuth), auditoria de ações transacionais e limites de uso |
| Monitor de tom | Classificador de sentimento/urgência (heurística + LLM leve) com alerta, transferência simulada e log dos casos escalonados | Integração real com fila de atendentes humanos, escalonamento por SLA |
| Memória da conversa | Persistência por ID + resumo automático periódico (não só ao final) | Perfil de cliente enriquecido a partir do histórico de conversas |
| Classificação do usuário | Heurística inicial (histórico de compras/perguntas) — Cliente/Lead/Esporádico, com revisão dos critérios a partir dos primeiros dados coletados | Modelo preditivo, score de propensão, enriquecimento de dados externos |

## 6. MCP de integração com parceiros B2B (recursos e ferramentas)

Enquanto R11 usa o assistente como **cliente** de um MCP externo (Google
Calendar), R12 propõe o caminho inverso: a própria empresa atua como
**servidor/provedor** de MCP, expondo de forma padronizada dados e ações que
hoje ficam presos em sistemas internos, para que IAs de terceiros (sistemas
de revendedores, marketplaces, integradores de projetos) consultem
informações e executem ações transacionais diretamente.

**Recursos (dados, somente leitura):**
- Catálogo de produtos: especificações técnicas, dimensões e pesos.
- Estoque em tempo real: quantidade disponível por centro de distribuição.
- Tabelas de preços: custos atualizados, descontos por volume e campanhas.
- Manuais e documentação: instalação, esquemas elétricos, termos de garantia.

**Ferramentas (ações e automações transacionais):**
- Validação de compatibilidade entre peça/acessório e equipamento principal.
- Consulta de frete e prazos para o CEP do cliente final.
- Cotação automática com base nas exigências do projeto.
- Reserva ou pedido: criar ordens de compra ou pré-reservas de estoque.

**Relação com a arquitetura existente:** os quatro recursos são as mesmas
fontes já usadas internamente pelo RAG (R4) e pela área de produtos/pedidos
do site. Implemente **um único backend** desses dados e exponha duas
frentes sobre ele — RAG/chat consultando internamente, servidor MCP expondo a
mesma base a integradores externos — em vez de duplicar lógica. O próprio
Roteador/Orquestrador deve ser tratado como "mais um integrador" desse MCP
para intenções de Vendas (cotação, compatibilidade, estoque).

**Governança e segurança (relevante para a evolução futura, não para o
MVP):** autenticação por parceiro (API key/OAuth), permissões granulares por
recurso/ferramenta, rate limiting, trilha de auditoria para ações que alterem
estoque ou gerem pedido, tratamento de concorrência em reservas/pedidos.

**Escopo no protótipo (MVP):** versão interna — recursos de leitura sobre uma
base pequena e as quatro ferramentas já implementadas, mas **sem
autenticação por parceiro nem exposição pública**.

## 7. Riscos e limitações conhecidos

- Escopo ambicioso para um único protótipo: conector de BD, crawler, RAG
  multimodal e as quatro ferramentas do MCP B2B são obrigatórios já no MVP;
  pode ser necessário priorizar as frentes mais custosas — RAG multimodal e
  monitor de tom — caso o escopo completo não seja viável de uma só vez.
- Restrição de hardware: 16GB de VRAM limita os modelos locais candidatos a
  versões quantizadas; candidatos maiores (ex.: Qwen3 14B, Gemma-4-12B) só
  entram na avaliação comparativa em quantizações que deixem margem para o
  KV cache — evitar variantes acima de ~12–14B mesmo quantizadas, pelo risco
  de OOM. `Gemma-4-12B` (4-bit, `gemma4:12b-it-q4_K_M`) já confirmado
  disponível no Ollama local — é inclusive o `LOCAL_MODEL_NAME` em uso no
  `.env` de desenvolvimento (ver `docs/ROADMAP.md`, Fase 10); os demais 8
  candidatos da tabela de escopo ainda precisam ser baixados (`ollama pull`)
  antes da avaliação comparativa.
- STT (faster-whisper) roda na mesma GPU que o modelo local de chat —
  contenção de VRAM entre os dois é um risco real. `# MVP: default fechado
  em small (STT_MODEL_SIZE, ~1-2GB de VRAM), sem lógica automática de troca
  de tamanho por VRAM disponível em runtime — ajuste manual para medium/CPU/
  API externa fica para depois do MVP, se necessário`.
- Formato do áudio recebido em `POST /api/chat/messages`: `# MVP: detectado
  a partir do conteúdo (magic bytes, via ffmpeg/faster-whisper), sem campo
  explícito novo no schema (payload.audio continua só base64) — mantém o
  contrato de docs/FRONTEND.md §4 estável`.
- RAG multimodal é a parte mais custosa tecnicamente; o protótipo cobre um
  catálogo ampliado, mas não completo, com embeddings prontos (ex.: CLIP),
  sem treinar modelo próprio.
- Conector a BD terá escopo restrito (leitura simples). Crawler navega de
  verdade a partir de uma URL semente informada pelo admin, com profundidade
  e teto de páginas parametrizáveis por execução (sem teto rígido no
  backend), disparo sempre manual, sem agendamento — nenhum dos dois é
  solução genérica de produção.
- Monitor de tom: classificadores leves tendem a mais falsos
  positivos/negativos; tratar como heurística, não decisão final automatizada.
- Atendimento humano real (fila, transferência de contexto) não será
  implementado de ponta a ponta neste protótipo — é simulado.
- Classificação de cliente/lead/esporádico depende de poucos sinais iniciais;
  tratar como hipótese a validar com mais dados.
- Dependência do MCP do Google Calendar: falhas de conexão/permissão
  precisam de tratamento de erro claro (ex.: tentar novamente, transferir
  para atendente).
- Fluxo de agendamento (Fase 4A) sem mecanismo de saída: uma vez que uma
  conversa entra no fluxo (por palavra-chave OU por já ter estado parcial de
  agendamento salvo), não há como sair a não ser completando um agendamento
  com sucesso — os ramos de horário inválido/falha de MCP preservam os slots
  de propósito (para permitir nova tentativa), o que mantém a conversa presa
  ao fluxo indefinidamente; combinado à palavra-chave isolada "horário" no
  classificador heurístico, uma pergunta como "qual o horário de
  funcionamento?" pode entrar no fluxo por falso positivo. Limitação aceita
  do MVP — deferida para a Fase 10 junto do ajuste de palavras-chave do
  classificador (ver `docs/ROADMAP.md`, Fase 1); um mecanismo de
  abandono/timeout pertence a uma futura fase de memória/gestão de sessão.
- MCP B2B sem autenticação por parceiro/auditoria: ferramentas transacionais
  (reserva, pedido) ficam restritas a uso interno no protótipo.
- Escopo do MVP relativamente amplo (4 ferramentas do MCP B2B, playbooks
  iniciais, crawler/catálogo maiores) aumenta a superfície de testes dentro
  do próprio protótipo.

## 8. Próximos passos após o protótipo

- Avaliar qualidade do roteador com casos reais e ajustar critérios de
  decisão local x externo.
- Amadurecer o RAG: mais fontes de BD/sites, crawler agendado e mais
  abrangente, catálogo de imagens completo, embeddings mais robustos.
- Aprimorar o monitor de tom com modelo dedicado e regras validadas com a
  área de atendimento.
- Planejar integração real com sistema de ticketing (playbooks de Suporte e
  Atendimento) e com o MCP do Google Calendar em produção (autenticação,
  conflitos de agenda, reagendamento/cancelamento).
- Evoluir o MCP B2B do uso interno para exposição real a parceiros:
  autenticação por integrador, permissões granulares, auditoria, limites de
  uso, testes com parceiros piloto.

## 9. Avaliação experimental

Ver `docs/EVALUATION.md` para o detalhamento operacional. Resumo das três
frentes: acerto do roteador na identificação de intenções, qualidade das
respostas do RAG, e comparação de latência entre modelo local e externo.

## 10. Considerações finais

O desenho atende aos doze requisitos de forma modular, permitindo que o
protótipo entregue um fluxo ponta a ponta funcional, com escopo robusto —
incluindo as quatro ferramentas do MCP B2B, playbooks iniciais por domínio e
catálogo de imagens ampliado — servindo de base para as próximas etapas do
trabalho, entre elas a evolução do MCP interno para integração real com
parceiros B2B. A avaliação experimental complementa a entrega com evidências
quantitativas sobre roteador, RAG e latência, dando mais robustez à análise
dos resultados.
