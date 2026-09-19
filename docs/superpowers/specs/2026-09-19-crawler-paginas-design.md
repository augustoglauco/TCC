# Crawler de páginas para o RAG — Design

> Spec de apoio ao plano de implementação. Ver `docs/ROADMAP.md` Fase 2
> ("Implementar crawler restrito a um conjunto pré-definido de páginas") e
> `docs/ARCHITECTURE.md` §"Escopo do MVP e Evolução Futura" (R4).

## Motivação

R4 exige que o RAG busque em BD, textos, PDFs, sites e banco de imagens —
conector de BD e ingestão de PDF/texto já existem (Fase 2); falta o crawler
de sites. O texto original do roadmap/architecture ("conjunto pré-definido de
páginas, até ~5") descrevia mal a intenção real, esclarecida durante o
brainstorming desta entrega: não é uma lista fixa de URLs nem um crawl restrito
ao próprio site da empresa — é um crawler de navegação real (segue links a
partir de uma URL semente, que pode ser interna ou externa), com profundidade
e teto de páginas **parametrizáveis por execução**, disparado manualmente
pelo admin via frontend. `docs/ARCHITECTURE.md` e `docs/ROADMAP.md` precisam
ser corrigidos para refletir isso (regra 9 do `CLAUDE.md` — documentação
desatualizada é bug), na mesma entrega desta implementação.

Diferente de PDF/texto (conteúdo confiadamente do domínio escolhido no
upload) e do conector de BD (`--domain` fixo por chamada), uma página web
pode ter conteúdo de qualquer domínio — por isso o crawler precisa
**classificar** cada página antes de decidir o `domain` de ingestão, com uma
confirmação humana para os casos incertos.

## Decisões principais

### 1. Classificação: LLM externo por página, com fila de revisão por confiança

Cada página visitada é classificada por uma chamada ao LLM externo
(`OpenRouterClient`, já usado como fallback do roteador), reaproveitando o
padrão de prompt JSON de `app.router.classifier` (`{"domain": ..., "confidence":
0.0-1.0}`, parseado com o mesmo `_strip_code_fence` + `json.loads` +
validação Pydantic). Alternativas consideradas e descartadas:

- **Mapeamento por prefixo de URL** — determinístico e sem custo de API, mas
  só funcionava bem quando a hipótese era "crawler restrito ao próprio site"
  (rotas conhecidas). Com URL semente arbitrária (qualquer site), não há
  estrutura de rotas conhecida a priori.
- **Heurística de palavras-chave por chunk** (reaproveitando
  `_match_domain_by_keywords` do roteador) — mesma fragilidade de ambiguidade
  já registrada como pendência aberta do roteador (`docs/ROADMAP.md`, item
  "Revisitar a resolução de ambiguidade entre domínios no classificador").

Decisão: `confidence >= CRAWLER_CONFIDENCE_THRESHOLD` (config em runtime,
default `0.7`) ingere direto; abaixo do limiar, a página fica **fora do
RAG** até um humano aprovar via fila de revisão na página admin — nunca
ingerida "provisoriamente" com domain incerto.

Falha de parse do JSON de classificação (LLM devolveu algo não-parseável) é
tratada como `confidence=0.0` — cai na fila, nunca assume confiança alta por
omissão.

### 2. Navegação: BFS com profundidade e teto de páginas parametrizáveis por execução

Cada disparo do crawler recebe `url` (semente), `depth` e `max_pages`
opcional (default vindo de `CRAWLER_MAX_PAGES`, sem teto rígido no backend —
o admin pode pedir mais que o default). BFS a partir da semente:

- Restrito ao **mesmo host** da URL semente (não segue para outros domínios).
- **Visited-set** por URL normalizada (sem fragmento `#...`), essencial para
  não cair em loop com links de retorno comuns em sites reais.
- Para ao atingir `depth` (nível de hops a partir da semente) **ou**
  `max_pages` (páginas efetivamente visitadas), o que vier primeiro.
- Só segue/processa resposta com `content-type: text/html`; outros tipos
  (imagem, PDF linkado, etc.) são ignorados nesta entrega (RAG multimodal é
  Fase 3, fora de escopo aqui).

`# MVP: execução síncrona por chamada HTTP, sem fila de background nem
agendamento — reflete a decisão original de "sem agendamento" do escopo do
crawler; uma execução com depth/max_pages altos bloqueia a requisição até
terminar.`

### 3. Dedup por URL — evita duplicar pontos no Qdrant ao recrawlear

Limitação aceita em `app.rag.ingest` (PDF/texto/BD): reingerir a mesma fonte
cria um `document_id` novo e duplica pontos no Qdrant, sem verificação
prévia. Para o crawler isso seria visitado com frequência (mesma URL
recrawleada em execuções diferentes), então esta entrega resolve isso
**especificamente para o path do crawler**, sem alterar `ingest_bytes` nem os
outros ingestion paths:

Antes de gravar pontos no Qdrant para uma URL (tanto no caminho de
auto-ingestão dentro do `/run` quanto no `/approve` da fila), um passo de
**substituição por URL**:

1. Busca em `rag_documents` por `filename == url AND collection_id == <ativa>
   AND origin == "crawler"`.
2. Se existir: `qdrant_client.delete_by_document_id(collection.name,
   str(documento_antigo.id))` (método já existente, hoje só usado por
   `reingest_document`) + remove a linha antiga de `rag_documents`.
3. Segue o `ingest_bytes` normal (gera novo `document_id`, novos pontos,
   novo registro com `filename=url`, `origin="crawler"`).

Resultado: recrawlear a mesma URL substitui os pontos antigos em vez de
duplicar.

Página ainda **pendente** de revisão (não chegou a virar ponto no Qdrant) que
é recrawleada antes de alguém revisar: a linha em `crawler_pending_pages` é
**atualizada** (mesma URL = `unique`, upsert por `url` — novo texto/domain
proposto/confidence, `updated_at` atualizado), não duplicada.

## Dados

### Tabela nova `crawler_pending_pages` (migração Alembic)

| campo | tipo | nota |
|---|---|---|
| `id` | UUID PK | |
| `url` | str, **unique** | chave do upsert em recrawl |
| `extracted_text` | text | preservado para ingestão na aprovação |
| `domain_proposed` | str | sugestão do LLM |
| `confidence` | float | |
| `created_at` / `updated_at` | timestamptz | `updated_at` muda no upsert |

Linha é **deletada** ao aprovar ou rejeitar — a tabela só reflete o que está
pendente agora; histórico de aprovação/rejeição não é requisito.

### Config nova (runtime settings, não variável de ambiente pura)

Estendendo `app.api.runtime_settings` (`GET/PUT /api/admin/runtime-settings`,
mesmo padrão já usado por `rag_search_domain_fallback` — valores só em
memória, resetam a cada restart):

- `crawler_max_pages_default` (int, default `20`) — pré-preenche o form do
  admin.
- `crawler_confidence_threshold` (float, 0-1, default `0.7`) — usado no
  gate; exibido no admin para dar contexto de por que algo caiu na fila.

Valores iniciais vêm de variáveis de ambiente (`CRAWLER_MAX_PAGES=20`,
`CRAWLER_CONFIDENCE_THRESHOLD=0.7`) em `app.config`, como seed do estado em
memória — mesmo padrão dos outros runtime settings.

## Backend

### `app.rag.crawler` (novo)

- `fetch_page(client: httpx.AsyncClient, url: str) -> FetchedPage | None` —
  timeout curto (10s), só aceita `content-type: text/html`; falha de
  rede/timeout/status≠2xx devolve `None` (chamador decide logar/reportar).
- `extract_text_and_links(html: str, base_url: str) -> tuple[str, list[str]]`
  — via `beautifulsoup4` (**nova dependência**, mesmo espírito de
  `pdfplumber` para PDF): remove `script`/`style`/`nav`/`footer`, texto
  visível com espaços colapsados; links resolvidos com `urljoin` e
  normalizados (sem fragmento).
- `crawl(seed_url: str, depth: int, max_pages: int) -> CrawlResult` — BFS
  descrito acima; `CrawlResult` traz `pages: list[FetchedPage]` e
  `errors: list[str]` (URLs que falharam o fetch).

### `app.rag.crawler_classifier` (novo, ou função em `crawler.py`)

- `classify_page(llm_client: LLMClient, text: str) -> PageClassification`
  (`domain: str`, `confidence: float`) — mesmo padrão de prompt/parsing de
  `app.router.classifier._classify_with_llm`, com fallback
  `confidence=0.0` em qualquer falha de parse/validação.

### `app.rag.crawler_ingest` (novo)

- `replace_previous_ingestion(session, qdrant, collection, url) -> None` —
  passo de dedup-por-URL descrito acima.
- `ingest_or_queue(session, qdrant, collection, embedder, url, text,
  classification) -> Literal["ingested", "queued"]` — aplica o gate de
  confiança, chama `replace_previous_ingestion` + `ingest_bytes` (ingestão) ou
  faz upsert em `crawler_pending_pages` (fila).

### Endpoints (`app.api.crawler`, novo router, `prefix="/api/rag/crawler"`)

- `POST /run` — body `{url: HttpUrl, depth: int, max_pages: int | None}` →
  roda o crawl completo sync, classifica e aplica o gate por página, devolve
  `{pages_visited: int, auto_ingested: list[str], queued: list[str], errors:
  list[str]}`. Falha de Qdrant durante uma página específica não aborta o
  crawl inteiro — aquela URL cai em `errors`, resto continua.
- `GET /pending` — lista `crawler_pending_pages` (url, domain_proposed,
  confidence, trecho do texto).
- `POST /pending/{id}/approve` — body `{domain: RagDomain}` → roda
  `replace_previous_ingestion` + `ingest_bytes` com esse domain, deleta a
  linha. Qdrant indisponível aqui → 503 (mesmo padrão do upload existente em
  `app.api.rag`).
- `POST /pending/{id}/reject` — deleta a linha, sem ingerir.

Validação de `depth`/`max_pages` negativos e `domain` fora de `RagDomain` via
schema Pydantic (422).

### `app.api.runtime_settings`

`RuntimeSettingsResponse`/`RuntimeSettingsUpdateRequest` ganham
`crawler_max_pages_default` e `crawler_confidence_threshold`.

## Frontend

Nova seção em `/admin/ingestão` (`frontend/app/admin/ingestao/`), abaixo do
upload de documentos existente:

**Form de disparo:**
- Campo URL semente, campo `depth`, campo `max_pages` (pré-preenchido via
  `GET /api/admin/runtime-settings`, editável por execução).
- Botão "Rodar crawler" → `POST /api/rag/crawler/run`, estado de loading
  (execução síncrona), resumo ao terminar (páginas visitadas, auto-ingeridas,
  na fila, erros).

**Fila de revisão** (visível quando `GET /pending` não é vazia):
- Tabela: URL, trecho do texto, `<select>` de domain pré-selecionado com a
  proposta do LLM, confidence, botões Aprovar/Rejeitar.
- Aprovar → `POST /pending/{id}/approve {domain: <select>}`; Rejeitar →
  `POST /pending/{id}/reject`; ambos removem a linha da lista ao suceder.
- Texto pequeno mostrando `crawler_confidence_threshold` atual, para dar
  contexto de por que algo caiu na fila.

## Testes

- `crawler.py`: BFS com `httpx.MockTransport` (sem rede real) — restrição de
  mesmo host, visited-set evitando loop em link de retorno, corte por
  `depth`, corte por `max_pages`, skip de content-type não-HTML.
- Extração texto/links do HTML: fixtures simples, cobre remoção de
  `script`/`style`/`nav`/`footer` e resolução de links relativos.
- Classificação: `LLMClient` mockado — JSON válido, JSON com code fence,
  JSON malformado → `confidence=0.0`.
- `replace_previous_ingestion`: ingerir a mesma URL duas vezes contra Qdrant
  `:memory:` (mesmo padrão já usado nos testes de RAG) e conferir que só
  sobra um conjunto de pontos vivo.
- Endpoints (`/run`, `/pending`, `/approve`, `/reject`): integração com DB de
  teste + Qdrant `:memory:` + `httpx.MockTransport`, incluindo o caso de
  upsert da linha pendente ao recrawlear a mesma URL ainda não revisada.

## Fora de escopo desta entrega

- Teto rígido de `max_pages` no backend — decisão explícita: só o valor
  default é configurável, sem limite superior imposto pelo servidor.
- Respeitar `robots.txt` ou rate limiting no site alvo.
- Histórico de páginas aprovadas/rejeitadas (a fila só reflete o pendente
  atual).
- Reranking dos resultados de busca no RAG (item separado, ver tabela de
  escopo em `docs/ARCHITECTURE.md`).
- Agendamento/recrawl automático periódico — disparo é sempre manual via
  admin, como já decidido no escopo original do crawler.

## Documentação a corrigir junto com a implementação

`docs/ARCHITECTURE.md` e `docs/ROADMAP.md` descrevem hoje o crawler como
"conjunto pré-definido de páginas (até ~5)" — impreciso frente ao desenho
acima (navegação real, profundidade/teto parametrizáveis, sem teto fixo de
páginas). Atualizar os dois na mesma entrega (regra 9 do `CLAUDE.md`).
