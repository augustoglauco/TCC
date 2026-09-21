# Design — Ingestão de Documentação Restrita ao Canal MCP B2B (R4/R12, além do MVP original)

> Spec resultante de sessão com o desenvolvedor em 2026-09-21. Pedido
> explícito, fora do MVP original descrito em `docs/ROADMAP.md`. Registrada
> aqui e em `docs/ARCHITECTURE.md` §5 (ver §8 abaixo) para não ser confundida
> com item do MVP original nem esquecida na revisão final (Fase 11).

## 1. Objetivo e recorte de escopo

O desenvolvedor (admin) já faz a ingestão de documentos no RAG pela tela
`/admin/ingestao`. Ele quer poder ingerir um novo tipo de conteúdo:
**documentação exclusiva do canal MCP B2B** — informação que **não** deve
aparecer no chat público (Vendas/Suporte/Atendimento), destinada a ser
consultada apenas pelos parceiros/fornecedores autorizados através do servidor
MCP B2B (R12, Fase 5).

Recorte confirmado com o desenvolvedor (validado antes de codar pelo
`scope-guardian`):

- **Quem ingere:** só o admin, pela tela já existente. **Não** há login de
  parceiro nem ingestão feita por terceiros. Isso mantém a feature na
  interpretação "A" do escopo (segmentação de conteúdo), dentro do que já é
  aceito para `/admin/ingestao` (sem autenticação — ver
  `docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md`).
- **O que esta entrega faz AGORA (metade 1 de 2):** ingerir esse conteúdo numa
  **collection dedicada** e **garantir que o RAG do chat público nunca o
  consulte**. Essa metade é útil e verificável por si só: o isolamento tem de
  valer mesmo antes de existir quem consuma o conteúdo.
- **O que fica para a Fase 5 (metade 2 de 2), FORA desta entrega:** o servidor
  MCP B2B que de fato **consulta** essa collection. Hoje não há consumidor —
  o conteúdo fica ingerido e isolado, aguardando a Fase 5. As demais operações
  que os parceiros farão pelo MCP (consultar tabelas/BD, pedidos/compras,
  prestação de contas de pagamento) são a Fase 5 inteira (R12) e **não** são
  tocadas aqui.

Explicitamente **fora do MVP** e **fora desta entrega** (ver
`docs/ROADMAP.md`, "Explicitamente fora do MVP", e Fase 5): autenticação por
parceiro, OAuth, isolamento multi-tenant por parceiro, exposição pública do
MCP, rate limiting, auditoria. Nada disso é implementado aqui.

## 2. Decisão de arquitetura: `purpose` na collection

A busca do RAG do chat hoje resolve **a collection ativa** (`is_active=True`)
em `QdrantRAGClient.search` (ver
`docs/superpowers/specs/2026-09-15-rag-collections-config-design.md` §4.1). Ou
seja, o chat só lê a collection ativa; qualquer outra collection já é, na
prática, invisível ao chat.

Confiar apenas nisso ("basta não ativar a collection do MCP") é frágil: um
clique em "Ativar" na tela de collections exporia o conteúdo restrito ao chat
público. Para tornar o isolamento **explícito e à prova de erro**, adiciono um
campo de finalidade à collection:

```
purpose: Literal["chat", "mcp_b2b"]   # default "chat"
```

- `purpose="chat"` — collection elegível a ser a ativa e a ser buscada pelo
  chat (comportamento atual; é o default, então todas as collections
  existentes continuam "chat").
- `purpose="mcp_b2b"` — collection de conteúdo restrito ao canal MCP B2B.
  **Nunca** pode ser ativada (a ativação é bloqueada) e **nunca** é buscada
  pelo chat. Só será consultada pelo servidor MCP B2B na Fase 5.

**Alternativa descartada:** uma flag booleana de visibilidade por documento
(`rag_documents.restricted`) dentro das collections existentes, filtrada na
busca. Descartada porque (a) o desenvolvedor já escolheu "collection
dedicada", (b) mistura vetores de finalidades diferentes na mesma collection,
contrariando o princípio "uma configuração por collection" já adotado na
entrega de perfis, e (c) o isolamento passaria a depender de um filtro correto
em toda query, em vez de uma collection simplesmente não ser buscada.

**Por que não um enum novo de domínio (ex.: `RagDomain="parceiros"`):**
rejeitado explicitamente pelo `scope-guardian` — `RagDomain` é o conjunto
fechado de domínios de atendimento de R7, amarrado a playbooks e roteador;
mexer nele está fora do MVP. `purpose` é ortogonal a `domain`: uma collection
`mcp_b2b` continua tendo documentos com `domain` (ex.: `vendas`), só não é
lida pelo chat.

## 3. Modelo de dados

### 3.1. `rag_collections` ganha `purpose`

```python
purpose: Mapped[str] = mapped_column(default="chat")  # "chat" | "mcp_b2b"
```

Migração Alembic: adiciona a coluna com `server_default="chat"` (todas as
collections existentes viram `chat`, preservando o comportamento atual) e
depois remove o server_default para que novas linhas sejam controladas pela
aplicação (mesmo padrão de outras colunas). `# MVP:` validação do valor
(`chat`/`mcp_b2b`) fica no Pydantic da API (`Literal`), não numa constraint de
banco — mesmo critério já usado para `distance_metric`/`quantization_type` na
entrega de perfis.

`rag_documents` **não muda**: o documento restrito é um `RagDocument` normal,
apontando (via `collection_id`) para uma collection `purpose="mcp_b2b"`.

## 4. Regras de negócio (o coração do isolamento)

1. **Criação** (`POST /api/rag/collections`): o corpo aceita
   `purpose: Literal["chat","mcp_b2b"] = "chat"`. Criar uma collection
   `mcp_b2b` é permitido; ela nasce sempre com `is_active=False` (não faz
   sentido "ativar" na criação e a ativação é proibida — ver abaixo).
2. **Ativação** (`POST /api/rag/collections/{id}/activate`): **bloqueada com
   409** se a collection alvo for `purpose="mcp_b2b"`. Mensagem clara:
   "Collections restritas ao MCP B2B não podem ser ativadas para o chat."
   Essa é a garantia central: conteúdo restrito nunca vira a collection ativa,
   logo nunca é buscado pelo chat.
3. **Busca do chat** (`QdrantRAGClient.search`, via collection ativa): sem
   mudança de código necessária, porque só a ativa é buscada e uma `mcp_b2b`
   nunca é ativa. **Defesa em profundidade:** `get_active_collection` já
   filtra por `is_active=True`; adiciono uma asserção/guarda barata de que a
   collection resolvida para o chat tem `purpose != "mcp_b2b"` (nunca deveria
   acontecer, mas registra explicitamente a invariante e falha fechado se
   alguém quebrar a regra 2 no futuro).
4. **Ingestão de documento** (`POST /api/rag/documents`): já aceita
   `collection_id` (entrega de perfis §6.2). Para ingerir conteúdo restrito, o
   admin escolhe uma collection `mcp_b2b` no seletor. Nenhuma regra nova de
   ingestão — o pipeline é idêntico; muda só o destino.
5. **Playground** (`POST /api/rag/playground/search`): continua podendo buscar
   em qualquer collection escolhida explicitamente pelo admin, **inclusive as
   `mcp_b2b`** — o playground é ferramenta interna do operador para inspecionar
   o que foi ingerido, não o chat público. (Isso é intencional: o admin
   precisa poder verificar que o conteúdo restrito foi indexado corretamente.)
6. **Exclusão de collection**: sem mudança — cascata já existente. Uma
   `mcp_b2b` é inativa por definição, então nunca cai no bloqueio 409 de
   "collection ativa".

## 5. API (mudanças mínimas sobre a entrega de perfis)

- `POST /api/rag/collections` — corpo ganha `purpose: Literal["chat","mcp_b2b"]`
  (default `"chat"`). Retrocompatível: clientes que não mandam o campo criam
  collection `chat`.
- `POST /api/rag/collections/{id}/activate` — passa a retornar **409** quando a
  collection alvo é `mcp_b2b` (nova regra 4.2). 404 se não existir (inalterado).
- `GET /api/rag/collections` — resposta ganha `purpose` por collection (para a
  tabela do frontend badgear "MCP B2B" vs "Chat").
- Demais endpoints (`GET/POST /documents`, `reingest`, `playground`,
  `DELETE /collections/{id}`) — sem mudança de contrato; só passam a conviver
  com collections que têm `purpose`.

## 6. Frontend (`/admin/ingestao`, aba "Configuração" e "Enviar documento")

- **Aba "Configuração" → formulário "Nova collection"** (`CollectionFormModal`):
  ganha um seletor de **Finalidade**: "Chat (pública)" (default) vs
  "Restrita ao MCP B2B". Um aviso curto na opção restrita: "Conteúdo não
  aparece no chat; será consultado pelo canal MCP B2B (Fase 5)."
- **Tabela de collections** (`CollectionsTable`): nova coluna/badge
  "Finalidade" (`Chat` / `MCP B2B`). O botão "Ativar" fica **desabilitado com
  tooltip** ("Collections do MCP B2B não podem ser ativadas para o chat") nas
  linhas `mcp_b2b` — espelhando no cliente a regra que o backend também impõe
  (409).
- **Aba "Enviar documento"**: o seletor de collection destino já existe; passa
  a listar também as `mcp_b2b`, com o badge de finalidade ao lado do nome para
  o admin não se confundir sobre onde está mandando o documento.
- `frontend/lib/types/rag.ts` / `lib/api/rag.ts`: tipo de collection ganha
  `purpose`; `createCollection()` passa a enviar `purpose`.

`# MVP:` a tela continua sem autenticação (mesma limitação de toda
`/admin/ingestao`).

## 7. Testes

Backend (pytest, SQLite em memória + Qdrant `:memory:`, mesmo padrão das
entregas anteriores):

- `create_collection` com `purpose="mcp_b2b"` grava e lista corretamente; sem
  `purpose` faz default `"chat"`.
- `activate_collection` de uma `mcp_b2b` → bloqueada; endpoint responde 409 e a
  collection continua inativa (nada muda no banco). Ativar uma `chat` continua
  funcionando.
- **Isolamento (o teste que importa):** com uma collection `chat` ativa e uma
  `mcp_b2b` contendo documentos, a busca do chat (`search` via ativa) retorna
  só o conteúdo `chat`; um documento ingerido na `mcp_b2b` **não** aparece nos
  resultados do chat. Cobre a invariante da regra 4.3.
- `POST /api/rag/documents` com `collection_id` de uma `mcp_b2b` ingere
  normalmente (pipeline inalterado).
- Playground consegue buscar explicitamente numa `mcp_b2b` (regra 4.5).
- Migração: teste de que a coluna nasce `"chat"` para linhas pré-existentes
  (verificação leve, no espírito dos testes de migração já existentes).

Frontend (Vitest + Testing Library): `CollectionFormModal` envia `purpose`;
`CollectionsTable` mostra o badge e desabilita "Ativar" para `mcp_b2b` com
tooltip; seletor de "Enviar documento" lista `mcp_b2b` com badge.

## 8. Registro em `docs/ARCHITECTURE.md`

Adicionar, na seção §5 ("Escopo do MVP e Evolução Futura"), junto das notas de
extras já existentes (registro de documentos, perfis de collection,
gerenciador de modelos), uma nota curta: ingestão de documentação restrita ao
canal MCP B2B via collection dedicada (`purpose="mcp_b2b"`), com garantia de
que o chat público não a consulta — funcionalidade adicional fora do MVP
original, a pedido explícito do desenvolvedor. A **metade de consumo** (o
servidor MCP B2B lendo essa collection) permanece na Fase 5 (R12), não
antecipada aqui.

## 9. Não-objetivos explícitos

- Sem login/autenticação de parceiro, sem isolamento multi-tenant por
  parceiro, sem exposição pública — evolução futura do R12 (ver
  `docs/ROADMAP.md` "Explicitamente fora do MVP").
- Sem o servidor MCP B2B consumindo a collection — Fase 5.
- Sem novo valor no enum `RagDomain` — `purpose` é ortogonal a `domain`.
- Sem edição de collection existente (perfis seguem imutáveis) — mudar a
  finalidade significa criar outra collection.
- Sem filtro de visibilidade por documento — o isolamento é por collection.
