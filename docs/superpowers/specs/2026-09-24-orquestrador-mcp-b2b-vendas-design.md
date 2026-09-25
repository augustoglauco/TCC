# Design — Orquestrador como integrador do MCP B2B em Vendas (R12, Fase 5)

> Spec resultante de sessão de brainstorm com o desenvolvedor em 2026-09-24.
> Cobre o quarto item da Fase 5 (`docs/ROADMAP.md`): "Integrar o
> Roteador/Orquestrador como 'mais um integrador' do MCP B2B para intenções
> de Vendas (cotação, compatibilidade, estoque)". Os dois itens anteriores da
> fase (backend único de dados, servidor MCP com os 4 resources + as 4
> tools) já estão implementados e commitados.

## 1. Objetivo

Fechar a parte final de R12/`docs/ARCHITECTURE.md` §6 ("o próprio
Roteador/Orquestrador deve ser tratado como 'mais um integrador' desse MCP
para intenções de Vendas"): quando o domínio da conversa é `vendas` e o
cliente menciona um produto do catálogo, a resposta do assistente passa a
usar dados estruturados reais (estoque, cotação com desconto por volume,
compatibilidade) em vez de depender só do RAG textual genérico.

## 2. Decisão de escala: por que não dá pra casar nome por substring

O desenvolvedor revelou, durante o brainstorm, intenção de cadastrar **~1000
produtos** no catálogo. Isso invalida a abordagem inicialmente cogitada
("extrai o nome do produto via LLM, casa por `ILIKE` contra o catálogo, usa
só se o match for único"): termos genéricos ("gerador", "cabine") casam
dezenas de produtos num catálogo desse tamanho, então "match único" quase
nunca dispara.

**Decisão:** resolução em duas etapas, sem infraestrutura nova (sem
embeddings/Qdrant dedicado a produtos, sem extensão `pg_trgm` — mantém
paridade SQLite/Postgres para os testes, mesmo espírito de
`app.rag.db_connector`):

1. **Busca de candidatos por SQL** (sem LLM) — extrai termos significativos
   da mensagem, filtra contra o catálogo via `ILIKE`, devolve até 10
   candidatos (id, nome, categoria).
2. **Desambiguação por LLM** (uma chamada) — o LLM recebe a mensagem do
   cliente **junto com a lista de candidatos já filtrada** e escolhe o
   `produto_id` correto entre eles (ou nenhum). Copiar um ID de uma lista
   real e pequena é uma tarefa muito mais confiável para o LLM do que
   inventar um nome livre que depois precisa ser casado — e o comportamento
   não degrada com o tamanho do catálogo, já que a etapa 1 sempre limita a
   lista a ~10 itens antes do LLM entrar em cena.

Se a etapa 1 não encontrar nenhum candidato, a etapa 2 (chamada LLM) nem
roda — evita custo/latência extra em mensagens de Vendas que não mencionam
nenhum produto reconhecível.

## 3. Novo módulo: `app.router.sales_catalog`

```python
class CandidatoProduto(BaseModel):
    id: int
    nome: str
    categoria: str


class VendaSlots(BaseModel):
    produto_id: int | None = None
    produto_relacionado_id: int | None = None
    quantidade: int | None = None


class DadosCatalogoVendas(BaseModel):
    produto_nome: str
    estoque_total: int
    cotacao: tuple[Decimal, Decimal, Decimal] | None = None  # (unitário, % desconto, subtotal), só se quantidade veio
    produto_relacionado_nome: str | None = None
    compativel: bool | None = None  # só se produto_relacionado_id veio


_STOPWORDS = frozenset({"de", "da", "do", "das", "dos", "para", "com", "uma", "um",
                         "que", "tem", "têm", "vocês", "voce", "você", "preciso",
                         "queria", "quero", "gostaria", "ola", "olá", "por", "favor"})


def _extrair_termos_busca(message: str) -> list[str]:
    """Tokeniza a mensagem em palavras significativas para a busca de
    candidatos (etapa 1, ver §2) — minúsculas, sem pontuação, descarta
    palavras com 2 caracteres ou menos e a stopword list acima. Heurística
    de MVP, não NLP de verdade: o objetivo é só reduzir o catálogo a um
    punhado de candidatos plausíveis antes do LLM desambiguar (etapa 2), não
    extrair a intenção com precisão."""
    ...


class SalesCatalogClient:
    """Injetado em `handle_message` (mesmo padrão opcional de
    `calendar_client`/`scheduling_config`) — construído uma vez em
    `app.main` a partir do `db_sessionmaker` já existente, igual a
    `create_b2b_mcp_server(session_factory, ...)`. Não é um cliente MCP de
    verdade (ver §4): chama `app.db.catalog` diretamente, no mesmo
    processo."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def buscar_candidatos(self, termos: list[str], limite: int = 10) -> list[CandidatoProduto]:
        """`OR` de `ILIKE '%termo%'` contra `Produto.nome`/`Produto.categoria`
        por termo, `LIMIT limite`. Sem ranking por relevância — a
        desambiguação de verdade é a etapa 2 (LLM); esta etapa só reduz o
        universo de ~1000 para ~10."""
        ...

    async def consultar_detalhes(
        self, produto_id: int, produto_relacionado_id: int | None, quantidade: int | None
    ) -> DadosCatalogoVendas | None:
        """Reaproveita `app.db.catalog.obter_produto`/`listar_estoque`
        (soma entre centros de distribuição — o resumo do chat não precisa
        do detalhe por CD, que já está disponível via o resource MCP
        `estoque://` para quem precisar) + `calcular_item_cotacao` (só se
        `quantidade` veio) + `sao_compativeis` (só se `produto_relacionado_id`
        veio). Devolve `None` se `produto_id` não existir mais (produto
        deletado entre a busca de candidatos e esta chamada — janela de
        corrida pequena, aceitável no protótipo). Se `produto_relacionado_id`
        vier preenchido mas não corresponder a um produto real (mesma janela
        de corrida), trata como se não tivesse vindo (`compativel=None`,
        linha omitida do bloco de texto) — não afirma "não compatível" para
        um produto que nem existe mais."""
        ...


async def extract_sales_slots(
    message: str,
    recent_messages: list[str],
    candidatos: list[CandidatoProduto],
    llm_client: LLMClient,
) -> VendaSlots:
    """Uma chamada LLM: prompt lista os candidatos (id, nome, categoria) e
    pede pra extrair produto_id/produto_relacionado_id/quantidade da
    mensagem, respondendo só com IDs da lista de candidatos (ou null).
    Mesmo padrão de `app.router.scheduling.extract_booking_slots`: prompt →
    JSON → parse com `ValidationError`/`JSONDecodeError` tratado
    (`_strip_code_fence`), fallback pra `VendaSlots()` vazio em qualquer
    falha de parsing (não quebra o turno)."""
    ...
```

## 4. Transporte: chamada direta a `app.db.catalog`, não MCP de verdade

**Decisão do desenvolvedor:** `SalesCatalogClient` chama `app.db.catalog`
diretamente (mesmo processo), **não** abre uma conexão MCP real contra
`mcp-b2b-server` (porta 8100). Motivos:

- É a mesma função Python que `app.mcp_server.b2b` já usa por baixo dos
  panos para servir os resources/tools externos — nenhuma lógica nova,
  só mais um consumidor do backend único de dados já estabelecido
  (`docs/ARCHITECTURE.md` §6, "implemente um único backend... exponha duas
  frentes sobre ele").
- Evita que o chat (fluxo principal do produto) passe a depender de um
  processo separado (`scripts/run_mcp_b2b_server.py`) estar de pé — hoje
  ele não precisa estar rodando para o chat funcionar, e a leitura literal
  de "mais um integrador desse MCP" é entendida aqui como simetria
  arquitetural (mesmo backend de dados, mesmas regras de negócio), não como
  mandato de sempre usar o protocolo MCP via rede mesmo dentro do próprio
  backend.
- Consistente com o padrão já usado pelo RAG (`app.rag.db_connector`), que
  também lê a mesma base sem passar pelo servidor MCP.

## 5. Fluxo em `orchestrator.handle_message`

Novo parâmetro opcional `sales_catalog_client: SalesCatalogClient | None =
None` (mesmo padrão de opcionalidade de `calendar_client`/
`scheduling_config` — ausente em testes que não passam essa dependência,
comportamento de Vendas cai para o RAG puro, igual a hoje).

No bloco `else` (domínio não é `fora_escopo`) de `handle_message`, onde a
busca RAG já roda (`orchestrator.py:582-609`):

1. Se `classification.domain == "vendas"` e `sales_catalog_client is not
   None`: roda a busca RAG (já existente) **em paralelo** com a consulta de
   vendas nova, via `asyncio.TaskGroup` (mesmo idioma já usado para
   `tone_coro`/`classify()`, ver `docs/ARCHITECTURE.md` §5, correção de
   2026-09-24) — as duas são buscas independentes.

   **Nota de implementação:** a busca RAG hoje levanta `RAGConnectionError`
   direto (`orchestrator.py:596-601`, `except RAGConnectionError: ... raise`)
   e esse `raise` precisa continuar chegando ao chamador de `handle_message`
   do jeito que chega hoje. Dentro de um `TaskGroup`, uma exceção de uma
   task filha vem embrulhada num `ExceptionGroup` (PEP 654) — o bloco em
   volta do `TaskGroup` precisa de `except* RAGConnectionError` (não
   `except RAGConnectionError`) pra desembrulhar e re-levantar a exceção
   original, mesmo padrão já resolvido para `classify()` no bloco de
   classificação (ver correção do `asyncio.gather` → `TaskGroup` registrada
   em `docs/ARCHITECTURE.md` §5). A consulta de vendas em si (passo 2
   abaixo) nunca deveria disparar isso, já que ela mesma captura suas
   próprias exceções — mas o `except*` precisa existir de qualquer forma
   pra não mudar o comportamento de erro do RAG que já existe hoje.
2. A consulta de vendas em si, dentro de um `try/except Exception` amplo
   (loga e devolve `None`, nunca propaga — mesmo espírito de `analyze_tone`
   nunca derrubar o turno):
   a. `termos = _extrair_termos_busca(message)`; se vazio, para aqui (sem
      bloco extra).
   b. `candidatos = await sales_catalog_client.buscar_candidatos(termos)`;
      se vazio, para aqui.
   c. `slots = await extract_sales_slots(message, recent_messages,
      candidatos, local_client)` — reaproveita `local_client` já recebido
      por `handle_message`, sem cliente novo.
   d. Se `slots.produto_id is None`, para aqui (LLM não achou match entre os
      candidatos).
   e. `dados = await sales_catalog_client.consultar_detalhes(slots.produto_id,
      slots.produto_relacionado_id, slots.quantidade)`.
3. Se `dados` não for `None`, formata um bloco de texto e passa pra
   `_build_prompt` via novo parâmetro opcional `dados_catalogo: str | None
   = None`:

   ```
   Dados do catálogo interno (produto identificado: {produto_nome}):
   - Estoque disponível: {estoque_total} unidade(s)
   - Cotação para {quantidade} unidade(s): R$ {subtotal} ({percentual}% de desconto aplicado)  # só se cotacao is not None
   - Compatível com {produto_relacionado_nome}: sim/não  # só se compativel is not None
   ```

   Anteposto ao bloco de contexto RAG já existente em `_build_prompt`
   (mesma lógica de concatenação de `partes`, ver `orchestrator.py:57-83`)
   — **complementa**, não substitui: manuais/garantia/detalhes não
   estruturados continuam vindo do RAG, conforme decidido no brainstorm.

## 6. Não roda para outros domínios nem sem produto identificado

- Domínios que não são `vendas` nunca chamam `SalesCatalogClient` — sem
  custo extra de latência/LLM fora de Vendas.
- Uma mensagem de Vendas sem produto identificável (0 candidatos na etapa 1,
  ou o LLM não escolhe nenhum candidato na etapa 2) segue o fluxo atual sem
  nenhuma mudança visível — só RAG + playbook de Vendas, como hoje.

## 7. Testes

Backend (pytest, mesmo padrão de mock de LLM/DB já usado no resto do
projeto):

- `sales_catalog.py`:
  - `_extrair_termos_busca`: filtra stopwords/palavras curtas, minúsculas.
  - `SalesCatalogClient.buscar_candidatos`: encontra por nome/categoria,
    respeita o limite, catálogo vazio devolve lista vazia.
  - `SalesCatalogClient.consultar_detalhes`: com/sem quantidade (cotação
    presente/ausente), com/sem produto relacionado (compatibilidade
    presente/ausente), produto_id inexistente devolve `None`.
  - `extract_sales_slots`: escolhe o produto certo entre candidatos, devolve
    `produto_id=None` quando nenhum candidato serve, resposta LLM não-JSON
    cai em fallback vazio sem quebrar (mesmo espírito de
    `scheduling.extract_booking_slots`).
- `orchestrator.py`:
  - Domínio vendas com produto identificado → prompt final contém o bloco
    "Dados do catálogo interno".
  - Domínio vendas sem `sales_catalog_client` (não passado) → comportamento
    idêntico ao atual (sem bloco extra), nenhuma regressão nos testes já
    existentes de Vendas.
  - Domínio vendas com mensagem sem produto reconhecível → sem bloco extra,
    sem chamar `extract_sales_slots` (zero candidatos, corta antes do LLM).
  - Falha em `SalesCatalogClient` (ex.: erro de banco) → não derruba o
    turno, resposta segue sem o bloco extra, log estruturado emitido.
  - Domínios que não são vendas → `SalesCatalogClient` nunca é chamado
    (spy/mock não invocado).

`eval/` (Fase 10) não é tocado por esta entrega.

## 8. Mudanças em `.env.example`

Nenhuma — sem configuração nova. O limite de candidatos (10) fica como
constante no módulo (`_SALES_CANDIDATOS_LIMITE`), mesmo padrão de
`DEFAULT_MANUAIS_TOP_K` em `app.mcp_server.b2b`.

## 9. Não-objetivos explícitos (fora desta entrega)

- `consultar_frete` e `reservar_pedido` continuam como MCP tools só para
  integradores externos — não entram no fluxo automático do chat. Reserva
  em particular teria efeito colateral real (cria pedido, decrementa
  estoque) e exigiria um fluxo de confirmação explícita como o do
  agendamento (Fase 4A) — escopo maior, decisão consciente de deixar para
  um item futuro se o desenvolvedor pedir.
- Nenhuma UI nova no frontend — os dados aparecem só como texto na resposta
  do LLM, não como card estruturado (isso já é item pendente separado,
  Fase 8: "Implementar cards ricos: produto, confirmação de agendamento,
  cotação/reserva").
- Sem toggle de runtime settings para ligar/desligar este comportamento
  (YAGNI — sem precedente de necessidade real, ao contrário do
  `intent_router_provider`/`tone_monitor_provider`, que alternam entre
  implementações concorrentes já validadas).
- Sem busca semântica/embeddings dedicada a produtos — a busca de
  candidatos (§2, etapa 1) é `ILIKE` simples; se isso se provar insuficiente
  em uso real com os ~1000 produtos, é uma evolução futura registrável
  separadamente, não antecipada aqui.
- Sem ranking de relevância na busca de candidatos — a etapa 1 devolve até
  10 candidatos sem ordenar por qualidade de match; a desambiguação real é
  a etapa 2 (LLM).
