# Especificação Arquitetural: Ledger Unificado de Uso de IA — Item E (Painel)

> **Data:** 08 de Outubro de 2026
> **Status:** Proposta de Arquitetura / Design Spec
> **Domínio:** Telemetria e Custos de IA (admin, backend + frontend)
> **Escopo desta spec:** o item **E** (último) do plano registrado em
> `docs/ROADMAP.md` ("Extra fora do MVP — Ledger Unificado de Uso de IA") —
> reconstruir o painel `/admin/metricas` sobre a tabela `ai_usage_events`,
> estratificado por origem × ambiente × modelo, substituindo o endpoint
> `GET /api/admin/metrics/tokens-and-costs` e os cards atuais. Fecha o
> ciclo A→E: A criou a tabela e a função central, B/C/D conectaram todos os
> pontos de uso de IA do chat, do MCP B2B e do admin, e E é o que finalmente
> mostra o resultado para o administrador.

---

## 1. Contexto e Objetivo

O problema que originou todo o plano A→E (relato do usuário em 2026-10-08):
não era possível identificar no painel `/admin/metricas` o que foi gasto em
visão computacional **interna** (CLIP/modelo local, grátis) versus
**externa** (API paga). A causa não era o painel, era a telemetria por baixo
dele: dois esquemas sem a dimensão "origem" e um painel que inferia "isto é
visão?" por heurística de nome de modelo (`"gemma" in model_name.lower()`,
`"vl"`, `"vision"`...).

Os itens A–D resolveram a telemetria. Hoje `ai_usage_events` recebe 15
pontos de registro com as dimensões certas — `origem` (chat/b2b/admin),
`ambiente` (interno/externo), `modelo`, `operacao`, tokens e custo. O
painel, porém, continua lendo os dois esquemas antigos
(`ConversaMensagem.metricas` + `IngestionCostEvent`) e continua com a
heurística. Pior: desde o item D a extração de catálogo por visão parou de
escrever em `IngestionCostEvent`, então o card "Ingestão & Dados" está
parado — consequência aceita e explicitamente deferida para este item.

**Objetivo:** `ai_usage_events` passa a ser a **fonte única** do painel de
uso de IA. A heurística de inferência de visão é removida, não portada — ela
existia só porque a dimensão que o ledger agora tem não existia.

### Decisões do dono do projeto (2026-10-08)

1. **Substituir, não complementar.** O painel inteiro passa a ler o ledger.
   Os cards antigos e o endpoint antigo saem; não há seção de convivência.
2. **Histórico pré-ledger é descartado.** O que foi medido antes de A/B/D em
   `ConversaMensagem.metricas` e `IngestionCostEvent` não aparece mais e não
   é migrado — é tráfego de desenvolvimento, não medição válida; os números
   que importam para o TCC serão gerados na Fase 10 (Avaliação
   Experimental), já em cima do ledger. **Sem backfill**: inferir
   `origem`/`operacao` dos dados antigos exigiria exatamente a heurística
   que este item remove.
3. **`IngestionCostEvent` permanece no banco sem leitor.** A tabela, o
   modelo e sua migração ficam; só deixam de ser lidos. Não se remove a
   tabela (migração destrutiva sem ganho) — ela é marcada como morta por
   comentário no modelo.

### Achado durante o design: o crawler ficou fora do ledger

`app/rag/crawler_classifier.py:72` (`classify_page`) é o **único** ponto de
uso de IA do sistema que ainda escreve na telemetria antiga, via
`app.services.ingestion_metrics.record_ingestion_cost`. Os itens A–D nunca o
cobriram: o item D limitou seu escopo à extração de catálogo e à geração de
gráficos.

Enquanto o painel lia `IngestionCostEvent`, isso era invisível. Com o ledger
como fonte única, o custo da classificação LLM de páginas crawleadas
desapareceria do painel por completo. **Este item migra esse ponto** —
`origem="admin"`, `operacao="classificacao_crawler"` — senão a "fonte única"
nasce incompleta. É o último ponto de uso de IA fora do ledger; depois dele
`record_ingestion_cost` fica sem nenhum chamador em produção.

---

## 2. Contrato da API

### 2.1 Endpoint novo

`GET /api/admin/metrics/ai-usage` substitui
`GET /api/admin/metrics/tokens-and-costs`, que é **removido** junto com os
modelos `MetricSummary` e `DailyMetric`.

Endpoint novo (em vez de refatorar o antigo no lugar) porque o payload muda
por completo: os consumidores são apenas a página `/admin/metricas` e os
testes, todos reescritos neste item, então não há contrato externo a
preservar — e um nome novo deixa claro na URL o que o painel passou a medir.

**Autenticação:** `Depends(require_admin)`, idêntica ao endpoint atual
(mesmo fallback de `admin_auth`/token quando `app.api.admin_auth` não está
disponível). Sem mudança.

**Filtros (idênticos aos de hoje, reaproveitados sem reescrita):**
`period` ∈ {`today`, `7d`, `30d`, `all`}, ou `start_date`+`end_date` em
`YYYY-MM-DD`. Data mal formada → `400`, não cai silenciosamente no período
default (achado da revisão de 2026-10-04). O fuso é o calendário **local**
do administrador (`settings.agendamento_timezone`), não UTC — também achado
de 2026-10-04: bucketar em UTC cortava o dia às 21h de Brasília. Essa
lógica de recorte é movida para uma função auxiliar reutilizável, não
duplicada.

### 2.2 Bloco de métricas (forma compartilhada)

Todo agrupamento devolve o mesmo bloco:

```jsonc
{
  "chamadas": 1312,                  // COUNT(*)
  "tokens_entrada": 820100,          // int | null
  "tokens_saida": 91200,             // int | null
  "custo_usd": 0.2346,               // float | null
  "chamadas_sem_custo_medido": 18    // COUNT(*) - COUNT(custo_usd)
}
```

**A distinção `null` × `0.0` é a razão de existir do ledger e o painel a
preserva.** No ledger, `None` significa "não capturado / não se aplica"
(tokens do CLIP, por exemplo) e `0.0` significa "zero conhecido" (CLIP e
modelo local são genuinamente grátis) — decisão dos itens A/B/D. Portanto:

- `custo_usd: null` — nenhuma chamada do grupo teve custo medido. Sai
  naturalmente do `SUM()` do SQL, que devolve `NULL` quando todos os valores
  são `NULL`. **Nunca `COALESCE(..., 0)`**: transformar não-medido em zero é
  precisamente o erro que o painel antigo cometia.
- `custo_usd: 0.0` — custo medido e igual a zero (grátis).
- `chamadas_sem_custo_medido` — quantas chamadas do grupo não têm custo
  medido, para que um grupo parcialmente instrumentado não se apresente como
  um total confiável.

Mesma regra para `tokens_entrada`/`tokens_saida`.

### 2.3 Resposta completa

```jsonc
{
  "period": "7d",
  "atendimento": { "chats_encerrados": 42 },
  "totais":       { /* bloco de métricas */ },
  "por_origem":   [ { "origem": "chat",  ...bloco }, { "origem": "b2b", ...}, { "origem": "admin", ...} ],
  "por_ambiente": [ { "ambiente": "interno", ...bloco }, { "ambiente": "externo", ...bloco } ],
  "por_modelo":   [ { "modelo": "clip", "ambiente": "interno", ...bloco }, ... ],
  "por_operacao": [ { "operacao": "geracao_resposta", "origem": "chat", "ambiente": "interno", ...bloco }, ... ],
  "diario": [
    {
      "data": "2026-10-08",
      "chats_encerrados": 7,
      "totais": { /* bloco */ },
      "por_origem": [ { "origem": "chat", ...bloco }, ... ]
    }
  ]
}
```

Notas de contrato:

- `por_origem`/`por_ambiente` trazem **apenas os valores presentes** no
  período; o frontend renderiza as origens conhecidas que faltarem como
  zero/vazio. O backend não fabrica linhas de origem sem evento.
- `atendimento.chats_encerrados` **não vem do ledger** — vem de `Conversa`
  (`status == "encerrada"`, bucketado por `encerrada_em`). É volume de
  atendimento, não uso de IA, e por isso viaja num bloco próprio em vez de
  misturado aos totais. Permanece no painel porque o administrador o usa, e
  no mesmo payload para não exigir uma segunda requisição.
- `diario` ordenado por `data` **decrescente** (mais recente primeiro), como
  hoje.

---

## 3. Camada de Agregação

### 3.1 Duas consultas, as duas agregadas no banco

O endpoint atual puxa **todas** as linhas cruas de três tabelas e agrega em
laços Python. O ledger é uma tabela própria com índices em `origem`,
`operacao` e `criado_em`, então a agregação desce para o SQL:

**Q1 — agregação cross-dimensional:**

```sql
SELECT origem, ambiente, modelo, operacao,
       COUNT(*)                        AS chamadas,
       SUM(tokens_entrada)             AS tokens_entrada,
       SUM(tokens_saida)               AS tokens_saida,
       SUM(custo_usd)                  AS custo_usd,
       COUNT(*) - COUNT(custo_usd)     AS chamadas_sem_custo_medido
FROM ai_usage_events
WHERE criado_em >= :inicio AND criado_em <= :fim
GROUP BY origem, ambiente, modelo, operacao
```

O resultado é pequeno e limitado pela cardinalidade das dimensões (3 origens
× 2 ambientes × ~14 operações, na prática muito menos), e dele o Python
deriva **todas** as visões não-diárias (`totais`, `por_origem`,
`por_ambiente`, `por_modelo`, `por_operacao`) por roll-up. Uma única ida ao
banco para cinco visões, e os números fecham entre si por construção — não
há como um filtro divergir entre duas consultas.

**Q2 — recorte diário:** seleciona seis colunas estreitas por evento no
período (`criado_em`, `origem`, `ambiente`, `tokens_entrada`,
`tokens_saida`, `custo_usd`) e bucketa por **dia local** em Python.

Por que o dia não é agrupado em SQL: o bucket é o dia do calendário local do
administrador, e não existe expressão portável entre SQLite (testes, `sqlite
+aiosqlite:///:memory:`) e PostgreSQL (produção) para truncar um
`timestamptz` num fuso arbitrário — `date_trunc(... AT TIME ZONE ...)` é
PostgreSQL, `date(x, '-3 hours')` é SQLite, e o projeto não tem nenhum SQL
dialect-specific hoje. Agrupar com `CAST(criado_em AS DATE)` reintroduziria
exatamente o bug corrigido em 2026-10-04 (dia cortado às 21h). A escolha —
manter o bucketing diário em Python com `ZoneInfo`, como hoje — fica
registrada por comentário no código, para que uma leitura futura não a
confunda com descuido.

### 3.2 Roll-up em Python

Função pura, testável isoladamente, sem dependência de sessão de banco:
recebe as linhas de Q1 e devolve os cinco blocos. A sua regra central é a
soma que respeita `null`:

> somar dois blocos — `None + None = None`; `None + x = x`; a contagem de
> `chamadas_sem_custo_medido` é sempre somada.

Essa é a única lógica sutil do item e por isso vive numa função própria, com
testes diretos, em vez de embutida no handler do endpoint.

### 3.3 Onde o código mora

`app/api/admin_metrics.py` tem 405 linhas hoje e sai deste item menor,
porque a heurística de visão e os três laços de acumulação desaparecem. Para
não repetir o acúmulo de responsabilidades:

- `app/api/admin_metrics.py` — o endpoint: autenticação, parsing de
  filtros, as duas consultas, montagem da resposta.
- `app/services/ai_usage_report.py` (**novo**) — o roll-up puro (§3.2) e os
  modelos Pydantic da resposta. Sem FastAPI, sem sessão de banco.

O recorte de período (período nomeado/datas explícitas → limites UTC a
partir do fuso local, com `400` em data inválida) vira uma função auxiliar
em `admin_metrics.py`, usada pelas duas consultas e pela de chats
encerrados.

---

## 4. Frontend — `/admin/metricas`

A página (`frontend/app/admin/metricas/page.tsx`, 907 linhas) é
reconstruída. O cabeçalho e o filtro de período já existentes são
**preservados** — seletor de período, calendário de datas, botão de
atualizar e o KPI de chats encerrados continuam funcionando como hoje; muda
o que está abaixo deles.

Seções, de cima para baixo:

1. **Por Origem** — três cards (Chat, B2B, Admin): custo USD, chamadas,
   tokens de entrada/saída. Responde "de onde partiu o gasto".
2. **Por Ambiente** — dois cards (Interno, Externo) + um consolidado geral.
   Responde a pergunta que originou o plano: quanto foi grátis (GPU local) e
   quanto foi pago (API externa). O consolidado exibe
   `chamadas_sem_custo_medido` quando maior que zero.
3. **Por Modelo** — tabela: modelo, ambiente, chamadas, tokens, custo.
   Responde "qual modelo custou o quê" — `clip` e o modelo local aparecem
   com custo `$0.0000`, os externos com o custo real.
4. **Por Operação** — tabela: operação, origem, ambiente, chamadas, tokens,
   custo. O nível mais fino: separa `identificacao_imagem_clip` de
   `identificacao_imagem_visao_externa`, `monitor_tom_jev` de
   `monitor_tom_heuristica_llm`, etc.
5. **Diária** — tabela: data, chats encerrados, chamadas, custo total e
   custo por origem.

**Regra de renderização de `null` × `0.0`** (o contrato da §2.2 chegando aos
olhos do administrador):

- `null` → `—`, com `title` explicando "não medido";
- `0.0` → `$0.0000` / `0`.

Um `—` e um `$0.0000` significam coisas diferentes e o painel não os
confunde. Essa regra vive num helper único (`formatarCusto`/
`formatarTokens`), não repetida célula a célula.

O card "Visão Computacional" não tem sucessor direto: a pergunta que ele
tentava responder passa a ser respondida pelas seções 2 e 4 (ambiente ×
operação), com dado real em vez de heurística de nome de modelo.

---

## 5. Testes

**Backend (pytest).** Arquivo novo
`backend/tests/test_admin_metrics_ai_usage.py`:

- `403` sem credencial de admin; `200` com.
- `400` em `start_date`/`end_date` mal formadas.
- Recorte de período no **fuso local**: evento às 22h locais de ontem (= 01h
  UTC de hoje) **não** entra em `period=today`. É o teste de regressão do
  achado de 2026-10-04 e precisa sobreviver à troca de fonte de dados.
- Roll-up: eventos de origens/ambientes/modelos/operações diferentes caem
  nos grupos certos, e `totais` fecha com a soma de `por_origem`.
- **`custo_usd` `null` não vira `0.0`** e conta em
  `chamadas_sem_custo_medido`; um grupo onde todas as chamadas são `null`
  devolve `custo_usd: null`, não `0.0`. Teste direto da função de roll-up,
  sem HTTP.
- `atendimento.chats_encerrados` conta conversas encerradas no período e
  ignora as abertas.
- `diario` ordenado do mais recente para o mais antigo.

**Testes removidos/reescritos** (cobrem o endpoint que deixa de existir):
`backend/tests/test_admin_metrics_api.py`,
`backend/tests/test_admin_metrics_vision.py` e a parte de
`backend/tests/test_ingestion_cost_metrics.py` que exercita a agregação de
ingestão do painel. A cobertura equivalente renasce no arquivo novo, em
cima do ledger; os casos de regressão nomeados acima são portados, não
descartados.

**Crawler:** teste de que `classify_page` registra no ledger com
`origem="admin"`, `operacao="classificacao_crawler"` e o ambiente correto, e
que uma falha no registro não quebra a classificação.

**Frontend (vitest + RTL).** `frontend/tests/components/AdminMetricasPage.test.tsx`
é reescrito: renderiza o payload novo (mock de fetch), confere que um grupo
com `custo_usd: null` mostra `—` e um com `0.0` mostra `$0.0000`, e que as
cinco seções aparecem com os números do mock.

---

## 6. Documentação a Atualizar (regra 9 do `CLAUDE.md`)

- `docs/ROADMAP.md` — marcar o item E; registrar a migração do
  `crawler_classifier` como parte dele.
- `docs/ARCHITECTURE.md` — substituir a descrição do "Relatório Analítico
  Consolidado" (§ linha ~1457) pelo endpoint novo; registrar que o ledger é
  a fonte única do painel, que o histórico pré-ledger foi descartado por
  decisão do dono do projeto e que `IngestionCostEvent` fica como tabela
  morta.
- `docs/FRONTEND.md` — contrato de API da página `/admin/metricas`.
- `docs/Manuais/HOWTO_ADMINISTRADOR.md` — o que o administrador vê agora
  nas cinco seções, e o significado de `—` versus `$0.0000`.
- `docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md` — **sem mudança de prompt**
  neste item: a migração do crawler altera só a telemetria, não o texto
  enviado ao LLM. Verificar que a entrada do prompt do crawler já consta e
  deixá-la como está.

---

## 7. Fora de Escopo

- **Backfill** dos dados antigos para o ledger (decisão 2 da §1).
- **Remover** a tabela/modelo `IngestionCostEvent` ou
  `record_ingestion_cost` (decisão 3 da §1). Após este item a função fica
  sem chamador em produção, mas segue no código; removê-la é limpeza
  separada.
- **`ConversaMensagem.metricas`** continua sendo gravado e lido — alimenta a
  telemetria por mensagem no chat ("Extra fora do MVP — Telemetria de
  Inferência no Chat"), que não é painel de admin e não muda aqui.
- **Estimativa de tokens em `OpenRouterClient.describe_image`** — achado
  deferido nas revisões dos itens B e D (a API às vezes não reporta `usage`
  e o cliente estima por tamanho de texto, contrariando a semântica
  `None`=não-capturado). É infraestrutura do cliente HTTP, não do painel; o
  painel apenas **expõe** o problema via `chamadas_sem_custo_medido`, que é
  o valor imediato. Corrigir o cliente é item próprio.
- Gráficos/visualizações novas no painel (o painel atual é tabular; os
  dashboards dinâmicos via LLM são outra feature, já existente em
  `/admin/dashboards`).
- Exportação CSV, alertas de orçamento, retenção/expurgo do ledger.

---

## 8. Próximos Passos

1. Revisão desta spec pelo dono do projeto.
2. Plano de implementação (skill `writing-plans`) em
   `docs/superpowers/plans/2026-10-08-ledger-uso-ia-item-e-painel.md`.
3. Implementação. Este é o último item do plano A→E: ao concluí-lo, todo
   uso de IA do sistema está registrado num só lugar e visível ao
   administrador estratificado por origem × ambiente × modelo.
