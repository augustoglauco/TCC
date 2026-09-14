# Design — Registro e Exclusão de Documentos Ingeridos no RAG (R4, além do MVP)

> Spec resultante de sessão de brainstorming em 2026-09-14. Esta funcionalidade
> **não está no MVP descrito em `docs/ROADMAP.md`** — foi pedida
> explicitamente pelo usuário como investimento extra antes de retomar o
> roadmap (Fase 2: conector de BD relacional e crawler ainda pendentes). É a
> primeira de três entregas combinadas nessa mesma sessão:
>
> - **A (esta spec):** registro de documentos ingeridos + exclusão.
> - **B (spec futura):** chunk size/overlap configuráveis por ingestão.
> - **C+D (spec futura):** configuração avançada da collection do Qdrant
>   (modelo de embedding/dimensão/métrica de distância, HNSW, quantização,
>   payload indexing).
>
> Decisão registrada em `docs/ARCHITECTURE.md` §5 (ver seção 8 abaixo).

## 1. Objetivo

Toda ingestão de documento no RAG (via `POST /api/rag/documents` ou via
`backend/scripts/ingest_sample_docs.py`) passa a criar um registro persistente
no Postgres. A partir desse registro, um documento pode ser listado e
excluído — a exclusão remove tanto a linha do registro quanto os pontos
correspondentes na collection do Qdrant.

Esta é a primeira funcionalidade do projeto a usar de fato o Postgres — as
dependências (`sqlalchemy[asyncio]`, `asyncpg`, `alembic`) e o serviço no
`docker-compose.yml` (porta 5433) já existiam, mas nunca foram exercitados
(`app/db/__init__.py` está vazio, `migrations/` só tem `.gitkeep`).

Fora do escopo desta entrega: chunk size/overlap configuráveis (entrega B),
troca de modelo de embedding/dimensão/métrica ou parâmetros avançados do
Qdrant (entrega C+D), deduplicação/re-ingestão incremental (mantém-se
`# MVP: sem deduplicação` já existente — reenviar o mesmo arquivo continua
criando um registro novo e independente), soft delete (decidido: exclusão é
definitiva).

## 2. Modelo de dados

Tabela `rag_documents` (Postgres), criada via Alembic (primeira migração do
projeto):

```python
class RagDocument(Base):
    __tablename__ = "rag_documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    filename: Mapped[str]
    domain: Mapped[str]
    chunk_count: Mapped[int]
    embedding_model: Mapped[str]
    chunk_size: Mapped[int]
    chunk_overlap: Mapped[int]
    origin: Mapped[str]  # "upload" | "batch_script"
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

`id` é o `document_id` usado tanto como PK no Postgres quanto como campo de
payload em cada ponto do Qdrant daquele documento (ver §3). Não há
`updated_at`/`deleted_at` — exclusão é definitiva (linha removida, não
marcada).

## 3. Qdrant e pipeline de ingestão

**Por que amarrar por `document_id` e não por `filename`+`domain`:** o mesmo
arquivo pode ser enviado mais de uma vez (sem deduplicação, por decisão já
tomada) — duas linhas de registro teriam `filename`+`domain` iguais, e um
filtro por esses campos excluiria as duas de uma vez só ao tentar excluir uma.
Um UUID gerado por ingestão evita essa ambiguidade e é pouca mudança sobre o
que já existe.

- `app/rag/qdrant_client.py`:
  - `upsert_chunks(chunks, source, domain, document_id)` — novo parâmetro
    obrigatório, gravado como campo extra no payload de cada ponto (junto de
    `content`/`source`/`domain`).
  - Novo método `delete_by_document_id(document_id: str) -> None` —
    `client.delete(collection_name, points_selector=Filter(must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]))`.
    Erros de conexão continuam virando `RAGConnectionError`, mesmo padrão dos
    outros métodos da classe.
- `app/rag/ingest.py`:
  - `ingest_bytes`/`ingest_file` passam a gerar `document_id = str(uuid4())`,
    repassar para `upsert_chunks`, e retornar também esse id (além da
    contagem de chunks) para quem chamou poder criar o registro.
  - **Ordem de escrita:** upsert no Qdrant primeiro, registro no Postgres
    depois. Se a escrita no Postgres falhar após o upsert ter sucesso, sobra
    um ponto órfão no Qdrant sem registro — logado como aviso
    (`rag_registro_orfao`), sem tentativa de rollback cross-store.
    `# MVP: sem transação distribuída Qdrant+Postgres — inconsistência rara e
    de baixo impacto (busca ainda funciona, só não aparece no registro) não
    justifica esse custo num protótipo de TCC`.
- `backend/scripts/ingest_sample_docs.py`: mesma mudança — cada arquivo
  ingerido cria seu registro com `origin="batch_script"`.

## 4. Camada de acesso a dados (`app/db/`)

- `app/db/engine.py`: `create_async_engine(settings.postgres_dsn)` +
  `async_sessionmaker`, seguindo o padrão já usado para o Qdrant client
  (injeção via `Depends` em produção, override nos testes) — sem
  singleton/lru_cache global, para não prender uma engine "morta" entre
  testes que sobem/derrubam a conexão.
- `app/db/models.py`: `Base` (declarative) + `RagDocument`.
- `app/rag/registry.py`: funções `create_document(session, ...)`,
  `list_documents(session) -> list[RagDocument]` (mais recente primeiro),
  `delete_document(session, document_id) -> bool` (retorna `False` se não
  existir, para o endpoint decidir o 404).
- Alembic: `backend/alembic.ini` + `backend/migrations/env.py` configurados
  para ler `postgres_dsn` de `app.config.Settings`; primeira migração cria
  `rag_documents`.

## 5. API

Em `app/api/rag.py`:

- `GET /api/rag/documents` → `list[DocumentRegistryResponse]` (novo schema em
  `app/models/rag.py`, espelhando as colunas da tabela).
- `DELETE /api/rag/documents/{document_id}` → chama
  `registry.delete_document` e, se encontrou, `qdrant_client.delete_by_document_id`;
  `404` se o `document_id` não existir no registro. Mesma dependência
  `get_rag_client` já usada pelo endpoint de upload, mais uma nova dependência
  de sessão de DB.
- `upload_document` (endpoint existente) passa a criar o registro após a
  ingestão, usando `chunk_size`/`chunk_overlap`/`embedding_model` correntes
  (constantes de config nesta entrega — variáveis só a partir da entrega B/C).

## 6. Frontend (`/admin/ingestao`)

Visual profissional e fácil de manter: duas pequenas primitivas headless do
**Radix UI** (`@radix-ui/react-dialog`, `@radix-ui/react-tabs`) — únicas
dependências novas do frontend, cobrindo só comportamento/acessibilidade
(foco, tecla Esc, navegação por teclado nas abas). Toda a aparência continua
sendo Tailwind próprio, sem kit de componentes visual completo (sem shadcn
CLI, sem estilos importados de fora) — os componentes de UI vivem no próprio
repo, só a mecânica de interação vem de fora. `# MVP: dependências novas
mínimas (2 primitivas headless), decisão registrada aqui e em
docs/ARCHITECTURE.md §5 — evita tanto reinventar foco/Esc/teclado à mão
quanto puxar um kit visual completo que exigiria manter uma segunda
linguagem de design`.

Página reorganizada em abas:

- **Aba "Enviar documento"** — formulário de upload existente, mesmo
  comportamento, reestilizado no padrão novo (cartão com sombra leve,
  sucesso/erro como toast em vez de bloco estático fixo na página).
- **Aba "Documentos ingeridos"** — tabela com: badge de domínio (cor por
  domínio), contagem de chunks, modelo de embedding, data relativa (ex.: "há
  2 dias", com o timestamp completo em `title` para hover). Botão "Excluir"
  por linha abre um modal de confirmação (`@radix-ui/react-dialog`) em vez de
  `window.confirm` nativo; exclusão bem-sucedida remove a linha da tabela e
  mostra um toast de confirmação.
- **Aba "Configuração"** — desabilitada nesta entrega, cartão "em breve"
  listando o que vai aparecer aqui (chunk size/overlap — entrega B; modelo de
  embedding, dimensão, métrica de distância, HNSW, quantização, payload
  indexing — entrega C+D). Existir já agora evita redesenhar a navegação
  quando essas entregas chegarem.

Novos componentes:
- `components/ui/` (genéricos, não específicos de RAG): `Modal.tsx`,
  `Tabs.tsx`, `Toast.tsx` + hook `useToast` (estado local à página — sem fila
  global nem persistência entre páginas, YAGNI para uma única tela
  administrativa).
- `components/admin/`: `DocumentsTable.tsx`, `DomainBadge.tsx`.
- `frontend/lib/api/rag.ts`: `listDocuments()` e `deleteDocument(id)`.

A lista de documentos é buscada ao montar a aba "Documentos ingeridos" e
recarregada após upload ou exclusão bem-sucedidos.

**Nota de compatibilidade:** `frontend/AGENTS.md` avisa que este Next.js 16
tem breaking changes relevantes vs. conhecimento de treinamento — antes de
implementar, checar `node_modules/next/dist/docs/` por mudanças em App
Router/Server Components que afetem esta página. Impacto esperado baixo (a
página já é `"use client"`), mas vale confirmar antes de codar.

## 7. Testes

- `app/rag/registry.py`: testado com SQLite assíncrono em memória
  (`aiosqlite`, `create_async_engine("sqlite+aiosqlite:///:memory:")`) — o
  schema é simples o bastante (UUID, str, int, timestamp) para isso ser fiel
  ao comportamento real do Postgres; mesmo espírito do
  `AsyncQdrantClient(location=":memory:")` já usado para o Qdrant nos testes
  existentes. `# MVP: teste de unidade da camada de acesso a dados usa SQLite
  em memória em vez do Postgres real — cobre a lógica de CRUD, não
  peculiaridades específicas do dialeto Postgres`.
- `app/rag/qdrant_client.py::delete_by_document_id`: testado contra
  `AsyncQdrantClient(location=":memory:")`, mesmo padrão dos testes
  existentes da classe.
- `api/rag.py`: testes de endpoint com Qdrant e DB (session) injetados via
  `Depends`, sobrescritos nos testes — mesmo padrão já usado para o endpoint
  de upload.
- Frontend: teste de componente/unidade para a tabela e o modal (renderização
  da lista, clique em excluir abre o modal, confirmar chama a API e remove a
  linha, cancelar não chama nada) — Vitest + Testing Library, que já
  funcionam normalmente sobre componentes Radix renderizados em `jsdom`; sem
  necessidade de E2E Playwright dedicado para esta tela administrativa.

## 8. Registro em `docs/ARCHITECTURE.md`

Adicionar, na seção "Escopo do MVP e Evolução Futura" (ou equivalente), uma
nota curta: registro/exclusão de documentos ingeridos é uma funcionalidade
adicional decidida fora do MVP original, implementada a pedido explícito
antes de retomar os itens pendentes da Fase 2 (conector de BD, crawler). Fica
documentada aqui e no roadmap para não ser confundida com item do MVP
original nem esquecida na revisão final (Fase 11).

## 9. Não-objetivos explícitos

- Deduplicação/re-ingestão incremental continua fora de escopo (já era antes
  desta entrega).
- Soft delete, auditoria de exclusões, versionamento de documentos.
- Registrar documentos que já foram ingeridos antes desta entrega existir
  (sem backfill de dados históricos) — ficam órfãos no Qdrant sem linha no
  registro, mesmo status que um erro de escrita no Postgres (§3).
- Autenticação/autorização na página `/admin/ingestao` ou nos novos
  endpoints — mesma limitação já aceita para o endpoint de upload existente.
- Kit de componentes visual completo (shadcn CLI, MUI, Chakra etc.) — só as
  duas primitivas headless do Radix citadas em §6, nada além disso.
