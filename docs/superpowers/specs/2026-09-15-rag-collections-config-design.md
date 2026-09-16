# Design — Perfis de Collection Configuráveis + Playground de Busca (R4, além do MVP)

> Spec resultante de sessão de brainstorming em 2026-09-15. Combina as
> **Entregas B e C+D** anunciadas como "spec futura" em
> `docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md`
> (Entrega A, já implementada): chunk size/overlap configuráveis (B) e
> configuração avançada da collection do Qdrant — modelo de embedding,
> dimensão, métrica de distância, HNSW, quantização, payload indexing (C+D).
> Ficaram interdependentes na sessão de brainstorming e por isso viram uma
> única spec/entrega.
>
> Como no caso da Entrega A, esta funcionalidade **não está no MVP** descrito
> em `docs/ROADMAP.md` — foi pedida explicitamente pelo usuário como
> investimento extra antes de retomar a Fase 2 (conector de BD relacional e
> crawler ainda pendentes). Decisão registrada em `docs/ARCHITECTURE.md` §5
> (ver seção 9 abaixo).

## 1. Objetivo

Hoje existe uma única collection fixa no Qdrant (`docs_texto`), com modelo de
embedding, métrica de distância e chunk size/overlap fixos por config global.
O usuário quer poder **criar múltiplas collections com perfis de configuração
diferentes**, escolher qual delas está "ativa" para o chat real, reingerir um
documento já enviado em outra collection para comparar, e usar um
**playground de busca comparativo** para rodar a mesma pergunta contra várias
collections lado a lado (resultados, score, latência) antes de decidir qual
configuração vale a pena promover a ativa.

Motivação explícita do usuário: quer gastar um tempo extra nisso antes de
seguir o roadmap porque considera a etapa de ingestão importante o bastante
para justificar experimentação de configuração — não é uma feature de
produção do MVP, é uma ferramenta de teste/comparação para quem opera o RAG.

Fora do escopo desta entrega: benchmark formal com conjunto rotulado de
perguntas (precisão/recall/LLM-as-judge) — isso é a Fase 10 do roadmap
(Avaliação Experimental) e não deve ser antecipado aqui; o playground desta
entrega é comparação visual/manual, não uma métrica agregada de qualidade.

## 2. Decisão de arquitetura: Postgres como fonte de verdade

Cada collection é descrita por uma linha em `rag_collections` (Postgres), que
guarda tanto os parâmetros nativos do Qdrant (HNSW, quantização, payload
indexes, métrica, dimensão) quanto os que o Qdrant não conhece (modelo de
embedding, chunk size/overlap). O backend usa essa linha tanto para criar a
collection real no Qdrant quanto para saber qual embedder/chunking usar em
cada ingestão/busca daquela collection.

**Alternativa descartada:** ler HNSW/quantização de volta do próprio Qdrant
(`get_collection`) em vez de duplicar no Postgres, evitando drift se alguém
mexer na collection por fora do app. Mais robusto, mas exige tradução do
formato de resposta do Qdrant a cada tela, e ninguém além desta feature mexe
nas collections — risco de drift baixo para um protótipo de TCC de operador
único. Descartada em favor da opção mais simples.

**Perfis são imutáveis após a criação.** Não há edição de uma collection
existente — mudar qualquer parâmetro significa criar uma nova collection.
Isso evita o problema de "o que fazer com vetores já gravados quando o
parâmetro muda" (ver §1 da sessão de brainstorming): cada configuração vive
na sua própria collection, comparável lado a lado no playground, sem misturar
vetores de formas diferentes na mesma collection.

## 3. Modelo de dados

### 3.1. Tabela nova `rag_collections`

```python
class RagCollection(Base):
    __tablename__ = "rag_collections"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(unique=True)  # nome da collection no Qdrant
    embedding_model: Mapped[str]
    vector_dimension: Mapped[int]  # deduzida do modelo na criação, só exibição
    distance_metric: Mapped[str]  # "cosine" | "euclid" | "dot" | "manhattan"
    chunk_size: Mapped[int]
    chunk_overlap: Mapped[int]
    hnsw_m: Mapped[int]
    hnsw_ef_construct: Mapped[int]
    hnsw_full_scan_threshold: Mapped[int]
    hnsw_max_indexing_threads: Mapped[int]
    hnsw_on_disk: Mapped[bool]
    hnsw_payload_m: Mapped[int | None]
    quantization_type: Mapped[str]  # "none" | "scalar" | "product" | "binary"
    quantization_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    payload_indexes: Mapped[list] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

`quantization_config` guarda os sub-parâmetros conforme `quantization_type`
(ver §6.2 — schema validado no Pydantic da API, não no banco). `payload_indexes`
é uma lista de `{"field": str, "schema_type": str, "text_params": {...} | null}`
(ver §6.2).

Só uma linha pode ter `is_active=True` — garantido na aplicação (transação
que desativa a atual antes de ativar a nova), não por constraint de banco
(SQLite em memória nos testes não suporta índice parcial condicional de forma
portável; volume de escrita é baixíssimo, sem necessidade de garantia a nível
de banco).

Migração de dados existentes: a migração Alembic cria `rag_collections` e
insere uma linha para a collection `docs_texto` já existente, com os valores
atuais (`paraphrase-multilingual-MiniLM-L12-v2`, 384, cosine, chunk_size=800,
overlap=100, HNSW/quantização nos defaults do Qdrant, `is_active=True`,
payload_indexes vazio — os índices em `domain`/`document_id` já usados em
filtro continuam existindo como estavam, sem migração de índice). Isso evita
quebrar o comportamento atual: o sistema continua funcionando com uma única
collection ativa até o usuário criar outras.

### 3.2. Mudanças em `rag_documents`

- Adiciona `collection_id: Mapped[UUID]` (FK para `rag_collections.id`).
- Adiciona `storage_path: Mapped[str]` — caminho do arquivo original em disco.
- **Remove** `embedding_model`, `chunk_size`, `chunk_overlap` — passam a vir
  do join com `rag_collections` (a Entrega A duplicava esses valores porque
  não existia ainda um conceito de "perfil"; agora que existe, manter a
  duplicação seria redundância sem propósito). Migração Alembic preenche
  `collection_id` das linhas existentes apontando para a collection
  `docs_texto` migrada em §3.1, e dropa as três colunas antigas.
- `storage_path` das linhas existentes fica `NULL` (documentos ingeridos antes
  desta entrega não têm arquivo salvo — não há reingest possível para eles,
  mesmo espírito de "sem backfill" já usado na Entrega A §9 para o próprio
  registro).

Arquivo original salvo em
`backend/data/rag_uploads/<document_id>_<filename>` (`# MVP: disco local
gerenciado pelo processo do backend, sem object storage — coerente com o
ambiente de desenvolvimento único deste protótipo de TCC`). Excluir um
documento (endpoint já existente da Entrega A) passa a remover também esse
arquivo do disco, ignorando silenciosamente se o arquivo já não existir
(`FileNotFoundError` capturada — pode acontecer para documentos migrados sem
`storage_path`, ou numa segunda tentativa de exclusão).

## 4. Qdrant: criação de collection com parâmetros completos

`app/rag/qdrant_client.py` ganha uma função (não-método, já que não há mais
"a" collection fixa) `create_collection_profile(client, profile: RagCollection) -> None`:

- Monta `VectorParams(size=profile.vector_dimension, distance=<mapeado de distance_metric>)`.
- Monta `HnswConfigDiff(m=..., ef_construct=..., full_scan_threshold=...,
  max_indexing_threads=..., on_disk=..., payload_m=...)` a partir dos campos
  do perfil.
- Monta `quantization_config` conforme `quantization_type`:
  - `"none"` → `None`.
  - `"scalar"` → `ScalarQuantization(scalar=ScalarQuantizationConfig(type=Int8, quantile=..., always_ram=...))`.
  - `"product"` → `ProductQuantization(product=ProductQuantizationConfig(compression=<x4|x8|x16|x32|x64>, always_ram=...))`.
  - `"binary"` → `BinaryQuantization(binary=BinaryQuantizationConfig(always_ram=...))`.
- Chama `client.create_collection(collection_name=profile.name, vectors_config=..., hnsw_config=..., quantization_config=...)`.
- Para cada entrada de `payload_indexes`, chama
  `client.create_payload_index(collection_name=profile.name, field_name=..., field_schema=<mapeado>)`
  — `field_schema` mapeia `schema_type` (`keyword`/`integer`/`float`/`bool`/`geo`/`datetime`/`uuid`/`text`)
  para o schema do Qdrant; quando `schema_type == "text"`, usa
  `TextIndexParams(tokenizer=..., min_token_len=..., max_token_len=..., lowercase=...)`
  a partir de `text_params`.
- Erros de conexão viram `RAGConnectionError`, mesmo padrão dos outros
  métodos da classe.

**Nota de teste (verificado nesta sessão):** o backend local/em-memória do
`qdrant-client` (`QdrantLocal`, usado nos testes via
`AsyncQdrantClient(location=":memory:")`) aceita `hnsw_config` e
`quantization_config` só por compatibilidade de assinatura — **ignora esses
parâmetros silenciosamente**, e `create_payload_index` no modo local é um
no-op com aviso (`"Payload indexes have no effect in the local Qdrant"`).
Confirmado lendo `qdrant_client.local.qdrant_local.QdrantLocal.create_collection`
e `.create_payload_index` diretamente. Isso significa que os testes
automatizados só podem verificar que `create_collection_profile` **chama** o
client com os argumentos corretos (via client real com `AsyncMock`/spy, não
via comportamento observável do backend local) — a aplicação de fato desses
parâmetros é responsabilidade do Qdrant real e fica coberta por um smoke test
manual contra o `docker-compose.yml` (porta 6335), não por CI. `# MVP: sem
verificação automatizada de que HNSW/quantização/payload-index tiveram efeito
real no Qdrant — o backend local usado em testes não os aplica, e rodar
Qdrant real em CI está fora do escopo deste protótipo`.

## 4.1. Wiring: de onde a busca do chat descobre a collection ativa

Hoje `QdrantRAGClient` é construído uma vez em `app.main` com
`collection_name`/`embedder` fixos vindos de config, e implementa o Protocol
`RAGClient` (`search(query, domain) -> list[Document]`) usado pelo
orchestrator — a assinatura desse Protocol **não muda**. O que muda é a
implementação interna: `QdrantRAGClient` deixa de guardar um
`_collection_name`/`_embedder` fixos para ingestão/busca (passa a expor só o
`AsyncQdrantClient` de baixo nível, reusado por `create_collection_profile` e
`search_in_collection`), e seu método `search` passa a:

1. Abrir uma sessão de DB curta (mesmo padrão de `Depends` já usado nos
   endpoints de registro) e consultar `rag_collections` por `is_active=True`;
2. Resolver o embedder dessa collection via `EmbedderRegistry`;
3. Delegar para `search_in_collection(client, collection.name, embedder, query, domain, DEFAULT_TOP_K, DEFAULT_SCORE_THRESHOLD)`.

Isso é uma coupling nova: busca do RAG passa a depender do Postgres (antes só
a ingestão dependia, desde a Entrega A). `# MVP: sem cache do id da
collection ativa em memória — um round trip extra ao Postgres por mensagem
de chat é aceitável neste protótipo; cache com invalidação no
POST .../activate ficaria para uma evolução futura se a latência se mostrar
um problema real`.

## 5. Ingestão, reingestão e cache de embedders

- `app/rag/embedders_registry.py` (novo): `EmbedderRegistry` — dict
  `{model_name: TextEmbedder}` protegido por lock, com `get(model_name) ->
  TextEmbedder` que cria sob demanda. Evita recarregar o mesmo modelo em
  disco/VRAM a cada ingestão/busca quando várias collections compartilham
  modelo, e evita ficar com N cópias do mesmo modelo carregado.
- `ingest_bytes` ganha parâmetro `collection: RagCollection` (em vez de usar
  a collection fixa do client): grava o arquivo recebido em
  `storage_path`, usa `collection.chunk_size`/`chunk_overlap` no chunking,
  usa `EmbedderRegistry.get(collection.embedding_model)` para embeddings, e
  faz upsert na collection `collection.name` do Qdrant. Cria o registro em
  `rag_documents` com `collection_id=collection.id`.
- `POST /api/rag/documents/{document_id}/reingest` (novo): body
  `{"target_collection_id": UUID}`. Lê `storage_path` do documento de
  origem, roda o mesmo pipeline de extração+chunking+embedding+upsert usando
  o perfil da collection destino, cria um **novo** documento
  (`origin="reingest"`, mesmo `storage_path` do original — não duplica o
  arquivo em disco). 404 se o documento de origem não existir, 404 se a
  collection destino não existir, 409 se o documento de origem não tiver
  `storage_path` (documento migrado antes desta entrega, sem arquivo salvo).
- `backend/scripts/ingest_sample_docs.py`: passa a receber/usar a collection
  ativa (consulta `rag_collections` por `is_active=True`) em vez da constante
  fixa anterior.

## 6. API

### 6.1. Collections

- `POST /api/rag/collections` — cria o perfil e a collection real no Qdrant.
  Corpo (schema completo em `app/models/rag.py`):
  ```
  name: str
  embedding_model: str  # nome curado (dropdown) ou digitado livre — mesmo campo
  distance_metric: Literal["cosine", "euclid", "dot", "manhattan"]
  chunk_size: int
  chunk_overlap: int
  hnsw: {m, ef_construct, full_scan_threshold, max_indexing_threads, on_disk, payload_m}
  quantization: {type: "none"|"scalar"|"product"|"binary", ...sub-params}
  payload_indexes: [{field, schema_type, text_params?}]
  ```
  `vector_dimension` não vem no corpo — o backend carrega o embedder (via
  `EmbedderRegistry`) e chama `get_dimension()`. Erros: `name` duplicado →
  409; modelo de embedding não carrega (nome inválido/download falha) → 422
  com a mensagem original da lib; Qdrant indisponível → 503.
- `GET /api/rag/collections` → lista de perfis + contagem de documentos
  (`COUNT` via join, não campo persistido).
- `POST /api/rag/collections/{id}/activate` → transação: desativa a
  atualmente ativa, ativa esta. 404 se não existir.
- `DELETE /api/rag/collections/{id}` → **exclusão em cascata**: remove a
  collection no Qdrant (`delete_collection`), todas as linhas de
  `rag_documents` daquela collection e os arquivos correspondentes em disco,
  numa única operação (ordem: Qdrant → arquivos → Postgres, mesmo raciocínio
  de "log de órfão sem rollback distribuído" já aceito na Entrega A §3 caso
  alguma etapa falhe no meio). Bloqueado (409, mensagem clara) **apenas** se
  `is_active=True` — precisa promover outra collection a ativa antes.

### 6.2. Documentos (mudanças sobre a Entrega A)

- `POST /api/rag/documents` (upload) ganha campo opcional `collection_id`
  (default: collection ativa) no formulário multipart.
- `GET /api/rag/documents` — resposta ganha `collection_id`/`collection_name`
  (via join), no lugar de `embedding_model`/`chunk_size`/`chunk_overlap`
  soltos (que agora só existem no nível da collection).
- `POST /api/rag/documents/{document_id}/reingest` — ver §5.

### 6.3. Playground

- `POST /api/rag/playground/search` — corpo `{query: str, domain: RagDomain,
  collection_ids: list[UUID]}` (mínimo 1). Para cada collection: busca
  usando o embedder e `top_k`/`score_threshold` padrão (mesmos defaults
  globais de hoje — não configuráveis por perfil nesta entrega, YAGNI),
  medindo latência com `time.perf_counter()` ao redor da chamada ao Qdrant.
  Resposta: lista de
  `{collection_id, collection_name, latency_ms, results: [{content, source, score}]} |
  {collection_id, collection_name, error: str}` — uma collection com erro
  (ex.: Qdrant fora do ar, o que não deveria acontecer já que é o mesmo
  Qdrant de todas, mas cobre o caso de a collection ter sido excluída entre
  a lista carregar na tela e a busca rodar) não derruba as demais.
- Refatoração mínima necessária: extrai de `QdrantRAGClient.search` a lógica
  de montar `Filter`/`query_points`/mapear resposta para `Document` numa
  função livre `search_in_collection(client, collection_name, embedder,
  query, domain, top_k, score_threshold)`, reusada tanto pelo `search` normal
  (que passa a collection ativa) quanto pelo endpoint de playground (que
  itera as collections pedidas).

## 7. Frontend (`/admin/ingestao`)

Modelos de embedding no formulário de criação de collection: dropdown com
4 opções curadas —
`paraphrase-multilingual-MiniLM-L12-v2` (384, atual/default),
`paraphrase-multilingual-mpnet-base-v2` (768),
`intfloat/multilingual-e5-base` (768),
`intfloat/multilingual-e5-large` (1024) — mais uma opção **"Outro (digitar
nome)"** que revela um campo de texto livre para qualquer modelo
sentence-transformers/Hugging Face. A dimensão exibida na tela é sempre
somente-leitura, preenchida depois que o backend confirma a criação (não dá
pra saber a dimensão de um modelo digitado livre sem carregá-lo primeiro).

- **Aba "Configuração"** deixa de ser "em breve":
  - Tabela de collections: nome, modelo, dimensão, métrica, resumo HNSW
    (`m=.. / ef=..`), quantização (badge do tipo), nº de payload indexes, nº
    de documentos, badge "Ativa".
  - Botão "Nova collection" abre modal/formulário completo (controle bruto:
    todos os campos de §6.1, com valores default do Qdrant pré-preenchidos —
    `m=16`, `ef_construct=100`, `full_scan_threshold=10000`, quantização
    "Nenhuma", dois payload indexes pré-sugeridos e editáveis:
    `domain` (keyword) e `document_id` (keyword), já que são os campos hoje
    usados em filtro/exclusão).
  - Botão "Ativar" por linha (desabilitado/oculto na já ativa).
  - Botão "Excluir" por linha → modal de confirmação avisando quantos
    documentos serão apagados junto (cascata, §6.1); desabilitado com
    tooltip explicativo se for a collection ativa.
- **Aba "Documentos ingeridos"**: nova coluna "Collection"; ação extra por
  linha "Reingerir em outra collection" → modal com seletor da collection
  destino (lista as outras, exceto a de origem) e mensagem de erro se o
  documento não tiver arquivo salvo (documento antigo, migrado sem
  `storage_path`).
- **Aba "Enviar documento"**: ganha seletor de collection destino (default:
  ativa, combo com as demais).
- **Nova aba "Playground"**: campo de pergunta, seletor de domínio,
  multi-select de collections (mínimo 1), botão "Comparar" → cartões lado a
  lado por collection (chunks retornados com score, latência em ms; cartão
  de erro isolado se aquela collection falhar).

Novos componentes: `components/admin/CollectionsTable.tsx`,
`CollectionFormModal.tsx`, `ReingestModal.tsx`,
`components/admin/playground/PlaygroundForm.tsx` +
`ComparisonResultCard.tsx`. `frontend/lib/api/rag.ts` ganha
`listCollections()`, `createCollection()`, `activateCollection()`,
`deleteCollection()`, `reingestDocument()`, `runPlaygroundSearch()`.

## 8. Testes

- `rag_collections`: CRUD com SQLite em memória (mesmo padrão da Entrega A) —
  criar, listar com contagem, ativar (garante só uma ativa), excluir
  (bloqueado se ativa; cascata remove documentos ao excluir uma inativa com
  documentos).
- `create_collection_profile`: chamado contra `AsyncQdrantClient(location=":memory:")`
  — verifica que não lança exceção e que a collection existe depois
  (`collection_exists`); **não** verifica que HNSW/quantização/payload-index
  foram de fato aplicados (ver nota de §4) — isso é coberto por um roteiro de
  smoke test manual contra o Qdrant real do `docker-compose.yml`, documentado
  no `CHANGELOG`/PR desta entrega, não em CI.
- `search_in_collection`: testado isoladamente (extraído de `search`),
  garantindo que o comportamento do endpoint de chat (usa a collection
  ativa) não muda.
- Reingest: fixture cria um arquivo fake em disco, ingere numa collection A
  (`:memory:`), reingere numa collection B (`:memory:` separada), confere
  novo documento + chunk_count + pontos em B.
- Playground: injeta múltiplos `QdrantRAGClient`/collections via `Depends`
  sobrescrito; confere formato de resposta por collection e que uma
  `RAGConnectionError` isolada não derruba a resposta inteira (`error` no
  item daquela collection, demais completos).
- Exclusão de collection: confere remoção do arquivo em disco (usa
  `tmp_path` do pytest) e do registro, e que tentar excluir a ativa retorna
  409 sem apagar nada.
- Frontend: testes de componente para `CollectionsTable`/`CollectionFormModal`
  (criar, ativar, excluir com confirmação), `ReingestModal`, e do fluxo do
  Playground (mock da API, renderização dos cartões de comparação,
  isolamento de erro por cartão) — Vitest + Testing Library, mesmo padrão da
  Entrega A.

## 9. Registro em `docs/ARCHITECTURE.md`

Adicionar, na seção "Escopo do MVP e Evolução Futura" (junto da nota já
existente sobre a Entrega A), uma nota curta: perfis de collection
configuráveis (chunking, modelo de embedding, parâmetros nativos do Qdrant) +
playground de busca comparativo são funcionalidade adicional fora do MVP
original, implementada a pedido explícito do usuário (Entregas B+C+D
combinadas) antes de retomar os itens pendentes da Fase 2 (conector de BD,
crawler). Documentada aqui e no roadmap para não ser confundida com item do
MVP original nem esquecida na revisão final (Fase 11).

## 10. Não-objetivos explícitos

- Sem migração automática de documentos existentes para uma nova collection
  — reingest é sempre manual, um documento por vez, disparado pelo usuário.
- Sem benchmark formal (precisão/recall/LLM-as-judge) — o playground é
  comparação visual/manual; benchmark formal fica na Fase 10 do roadmap.
- Sem edição de collection existente — perfis são imutáveis; mudar um
  parâmetro é criar uma nova collection.
- Sem quota/limite de número de collections.
- Sem `top_k`/`score_threshold` configuráveis por perfil nesta entrega —
  continuam globais (`DEFAULT_TOP_K`/`DEFAULT_SCORE_THRESHOLD`), inclusive no
  playground.
- Sem verificação automatizada (CI) de que HNSW/quantização/payload-index
  tiveram efeito real no Qdrant — ver nota de teste em §4/§8.
- Sem autenticação/autorização nova além da já aceita para `/admin/ingestao`
  e os demais endpoints de RAG (mesma limitação da Entrega A).
- Sem object storage (S3 etc.) para os arquivos originais — disco local
  gerenciado pelo processo do backend.
