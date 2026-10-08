# Especificação Arquitetural: Ledger Unificado de Uso de IA — Item D (Origem Admin)

> **Data:** 08 de Outubro de 2026
> **Status:** Proposta de Arquitetura / Design Spec
> **Domínio:** Telemetria e Custos de IA (admin, cross-cutting)
> **Escopo desta spec:** só o item **D** do plano registrado em
> `docs/ROADMAP.md` ("Extra fora do MVP — Ledger Unificado de Uso de IA") —
> conectar à função `registrar_uso_ia` (item A) os dois pontos de uso de IA
> do admin que ainda não estavam conectados: geração de gráficos dinâmicos
> via LLM (`app.services.analytics_agent`) e extração de catálogo por
> texto/visão (`app.catalog_extractor.extractor`). Só backend. A
> reconstrução do painel `/admin/metricas` (os 8 cards do frontend e o
> endpoint `/api/admin/metrics/tokens-and-costs`) é o item **E**, spec
> própria, a seguir — decisão do usuário (2026-10-08) de tratar os dois
> como specs sequenciais, não um documento único, mesmo sem pausa de
> aprovação entre eles.

---

## 1. Contexto e Objetivo

O item C (origem B2B) fechou sem nenhuma tarefa de implementação: o único
ponto de uso de IA do servidor MCP B2B (`converter_reserva_venda`, via
`ComprovanteEvaluator`) já emite `origem="b2b"` corretamente desde o item B
(Tarefa 6 tornou `origem`/`llm_ambiente` parâmetros obrigatórios do
construtor). O item D cobre os dois pontos que o roadmap já nomeava desde
a criação do plano A-E:

1. **Geração de gráficos dinâmicos** (`analytics_agent.py`,
   `_generate_sql_with_llm`/`process_dynamic_chart_request`) — já captura
   `prompt_tokens`/`completion_tokens` do stream do LLM (achado de
   2026-10-05, comentário já existente no código), mas descarta
   `model_name` e todos os campos de custo do chunk. O chamador
   (`orchestrator.py`, bloco de geração de gráfico dentro do chat admin)
   grava esses tokens em `RouterDecision` mas **hardcoda**
   `cost_prompt_usd=0.0`/`cost_completion_usd=0.0`/`custo_estimado_usd=0.0`
   nos dois pontos de retorno, mesmo quando `analytics_llm` caiu para o
   cliente externo pago (`analytics_llm = local_client if local_client is
   not None else external_client`, mesmo padrão de fallback do ponto #9 do
   item B). Esse `RouterDecision`/`ConversaMensagem.metricas` é o sistema
   de métricas **antigo** que o item E vai substituir — não faz parte
   desta spec corrigir o hardcode ali; a instrumentação nova captura o
   custo real direto do chunk, independente desse caminho antigo.
2. **Extração de catálogo por texto/visão** (`extractor.py`) —
   `extract_page_products_local` (extração de texto via LLM local, 3 call
   sites dentro de `extract_catalog_stream`) não tem **nenhuma**
   telemetria hoje. `extract_page_products_vision` (extração por visão, 4
   call sites — 2 passando `local_client` como `vision_client`, 2 passando
   o `vision_client` externo do estado da aplicação) já captura
   tokens/custo/modelo e persiste via `record_ingestion_cost` →
   `IngestionCostEvent`, a tabela **antiga** de telemetria de ingestão
   (distinta de `ConversaMensagem.metricas`) que o item A já tinha
   identificado como um dos "dois esquemas diferentes" a resolver, e
   explicitamente deferiu essa decisão para quando a origem "admin" (este
   item) fosse desenhada.

Decisão do usuário (2026-10-08, já tomada ao brainstormar este item):
**migrar**, não duplicar. As chamadas a `record_ingestion_cost` dentro de
`extract_page_products_vision` são **removidas e substituídas** por
`registrar_uso_ia` — sem dual-write, sem preocupação em preservar os dados
já gravados em `IngestionCostEvent` ("dados antigos não interessam"). O
card "Ingestão & Dados" do painel atual para de receber linhas novas a
partir desta mudança (os dados já gravados continuam no banco, só não
crescem mais) — consequência aceita, o item E decide o que fazer com esse
card.

---

## 2. Mapeamento: os 4 Pontos de Instrumentação

| # | Local (arquivo:função) | origem | ambiente | modelo | operacao | referencia_id |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| 1 | `analytics_agent.py` / `_generate_sql_with_llm` (geração de gráfico) | `admin` | parâmetro novo, inferido em `orchestrator.py` (`"interno" if analytics_llm is local_client else "externo"`) | `chunk.model_name` (hoje descartado) | `geracao_grafico_dinamico` | `None` |
| 2 | `extractor.py` / `extract_page_products_local` (3 call sites, todos dentro de `extract_catalog_stream`) | `admin` | `"interno"` (constante — sempre `local_client`, confirmado pelos 3 call sites) | `res.model_name` (hoje nem capturado) | `extracao_catalogo_texto_local` | `None` |
| 3a | `extractor.py` / `extract_page_products_vision`, call site que passa `local_client` como `vision_client` (1 de 4 — branch de imagem avulsa, tentativa de visão local antes do fallback externo, linha ~594) | `admin` | `"interno"` (parâmetro novo por call site) | já extraído (`model`) | `extracao_catalogo_visao_interna` | `source_identifier` (já é parâmetro existente da função, reaproveitado) |
| 3b | `extractor.py` / `extract_page_products_vision`, call sites que passam o `vision_client` externo do estado (3 de 4 — PDF forçado a `provider=="external"` linha ~473; PDF fallback após texto local falhar, linha ~497; imagem avulsa fallback final, linha ~606) | `admin` | `"externo"` (parâmetro novo por call site) | já extraído | `extracao_catalogo_visao_externa` | `source_identifier` |

`referencia_id` só é `source_identifier` nos pontos #3a/#3b porque esse
parâmetro **já existe** na assinatura de `extract_page_products_vision` e
já é passado em todos os 4 call sites (`f"{filename}#p{num_pagina_pdf}"`
ou `filename`) — reaproveitá-lo é gratuito. Os pontos #1 e #2 **não**
ganham `referencia_id`: dar a #1 um `conversation_id` exigiria uma
assinatura nova atravessando duas funções (`process_dynamic_chart_request`
→ `_generate_sql_with_llm`) que hoje não o recebem, e dar a #2 um
identificador de origem exigiria plumbing nova nos 3 call sites — mesmo
cálculo de custo/benefício que levou o item B a só dar `referencia_id` ao
seu próprio ponto #1 (geração de resposta principal do chat) e nenhum
outro.

`origem` é sempre a constante `"admin"` nos 4 pontos.

---

## 3. Mecanismo de Execução e Tratamento de Erro

Idêntico ao item B: toda chamada passa por
`spawn_background_task(registrar_uso_ia(...))` (nunca `await` direto),
`registrar_uso_ia` nunca lança exceção, e a instrumentação é posicionada
depois da chamada de IA ter retornado com sucesso mas antes de qualquer
parsing que possa falhar — então um parse inválido não cancela um custo
já incorrido. Nenhuma decisão nova aqui, mesmo contrato do item A/B.

---

## 4. Mudanças de Plumbing Necessárias

### 4.1 Geração de gráficos — `analytics_agent.py` / `orchestrator.py`

`_generate_sql_with_llm` ganha um parâmetro novo obrigatório `ambiente:
str` (só uma cadeia de chamada existe — `orchestrator.py` →
`process_dynamic_chart_request` → `_generate_sql_with_llm` — não há outros
chamadores para justificar um default). Dentro do loop
`async for chunk in llm_client.generate_stream(...)`, além de
`prompt_tokens`/`completion_tokens` (já capturados), passa a capturar
também `cost_prompt_usd`/`cost_completion_usd`/`estimated_cost_usd`/
`model_name` do chunk final (`chunk.done`). A chamada a
`registrar_uso_ia` entra logo depois do loop terminar, antes da tentativa
de extrair o bloco JSON da resposta (`re.search`) — o custo já foi
incorrido mesmo que o LLM não tenha respondido um JSON válido.

`process_dynamic_chart_request` ganha o mesmo parâmetro `ambiente: str`
(obrigatório, mesma razão), repassado sem modificação a
`_generate_sql_with_llm`. As duas branches que retornam antes de chamar o
LLM (dados inline do prompt; `llm_client` ausente) simplesmente recebem o
parâmetro sem usá-lo — não há instrumentação a disparar nesses casos
porque nenhuma chamada de IA aconteceu.

`orchestrator.py` (linha ~1170, onde `analytics_llm` já é calculado) ganha
`ambiente_grafico = "interno" if analytics_llm is local_client else
"externo"` ao lado do cálculo de `analytics_llm`, e repassa
`ambiente=ambiente_grafico` nos dois call sites de
`process_dynamic_chart_request` (linhas ~1179 e ~1191 — os dois ramos do
`if hasattr(session_ctx, "__aenter__")`).

### 4.2 Extração de catálogo por texto — `extractor.py`

`extract_page_products_local` não ganha nenhum parâmetro novo — `ambiente`
é a constante `"interno"` direto no corpo da função (os 3 call sites
sempre passam `local_client`, confirmado por leitura de todo
`extract_catalog_stream`). A chamada a `registrar_uso_ia` entra logo após
`res = await local_client.generate(prompt)`, usando `getattr(res,
"model_name", None)`/`"prompt_tokens"`/`"completion_tokens"`/
`"estimated_cost_usd"` (mesmo padrão de extração usado em todo o item B
para respostas de `LLMClient.generate`). O parâmetro `model_name: str |
None = None` já existente na assinatura da função permanece intocado — já
estava presente mas nunca foi usado no corpo; não faz parte desta spec
limpar isso, só não usá-lo como fonte do `modelo` do ledger (a fonte é
`res.model_name`, que é real, não um valor passado por fora).

### 4.3 Extração de catálogo por visão — `extractor.py`

`extract_page_products_vision` ganha um parâmetro novo obrigatório
`ambiente: str` (4 call sites, valores diferentes por call site — ver
tabela §2). Dentro da função:

1. Remove o import local `from app.services.ingestion_metrics import
   record_ingestion_cost` e os dois blocos `if/else` que o chamam.
2. Remove a lógica de estimativa por tamanho de texto (`if p_tok == 0 and
   c_tok == 0: p_tok = max(1, len(used_prompt) // 4) + 500; ...`) e o
   `getattr(..., 0) or 0` que zera em vez de preservar `None` — essa
   fabricação de números existia só para dar ao `IngestionCostEvent` um
   valor não-zero mesmo quando a API de visão não reportava uso real;
   contraria o princípio central do ledger novo (`NULL` = não capturado,
   `0`/`0.0` = capturado como zero real — não um valor inventado). Troca
   por extração direta com `getattr(raw_response, "prompt_tokens", None)`
   etc., mesmo padrão de `image_identification.py`/
   `comprovante_evaluator.py`.
3. A chamada a `registrar_uso_ia` substitui o bloco `record_ingestion_cost`
   removido, usando `operacao="extracao_catalogo_visao_interna" if
   ambiente == "interno" else "extracao_catalogo_visao_externa"` e
   `referencia_id=source_identifier` (parâmetro já existente, repassado
   sem mudança).

Os 4 call sites de `extract_page_products_vision` dentro de
`extract_catalog_stream` (confirmados por leitura completa do arquivo):
`ambiente="externo"` nas linhas ~473 (branch de PDF, forçado por
`provider == "external"`), ~497 (branch de PDF, fallback depois que a
extração local de texto não achou nada) e ~606 (branch de imagem avulsa,
fallback externo final) — 3 call sites. `ambiente="interno"` na linha
~594 (branch de imagem avulsa, tentativa de visão local antes do fallback
externo) — 1 call site. Total 3 externo / 1 interno, não 2+2 (ver tabela
§2, já corrigida para esta contagem).

---

## 5. Testes

Mesmo padrão do item B: para cada um dos 4 pontos, teste que monkeypatcha
`registrar_uso_ia` no módulo sob teste e verifica a chamada com os valores
corretos de `origem`/`ambiente`/`modelo`/`operacao`/tokens/custo/
`referencia_id`, usando os mocks de `llm_client`/`vision_client` já
existentes nos testes de `analytics_agent`/`catalog_extractor`.
`registrar_uso_ia` em si não é re-testado (já coberto pelo item A).

Casos adicionais:
- Geração de gráfico: teste com `analytics_llm` resolvendo para o cliente
  externo (`local_client=None`) → `ambiente="externo"`, `custo_usd`
  refletindo um valor real não-zero do chunk (prova de que o hardcode
  `cost_*=0.0` do `RouterDecision` antigo não é a fonte da nova
  instrumentação).
- Extração de catálogo por visão: um teste por call site (4 no total, ou
  os 4 cobertos indiretamente por testes de `extract_catalog_stream` que
  já exercitam cada branch) confirmando `ambiente`/`operacao` corretos e
  que `record_ingestion_cost` **não** é mais chamado (grep no teste, ou
  monkeypatch que falha o teste se for chamado).
- Extração de catálogo por texto: teste simples confirmando que uma
  chamada a `extract_page_products_local` agora dispara
  `registrar_uso_ia` com `ambiente="interno"` — hoje não dispara nada,
  então o teste atual (se existir) não precisa de ajuste, só ganha uma
  asserção nova.

---

## 6. Fora de Escopo Desta Spec (item E)

- Qualquer mudança em `/admin/metricas` (frontend, os 8 cards) ou em
  `app/api/admin_metrics.py` (`MetricSummary`/`DailyMetric`/o endpoint
  `/api/admin/metrics/tokens-and-costs`) — isso é item E, spec própria.
- Remover o modelo `IngestionCostEvent`/sua migração/a tabela em si —
  esta spec só para de **escrever** nela a partir de
  `extract_page_products_vision`; decidir se a tabela e o card "Ingestão &
  Dados" são removidos, substituídos ou mantidos como histórico morto é
  decisão do item E.
- Qualquer limpeza do parâmetro `model_name` não-usado em
  `extract_page_products_local` — fora do escopo, não afeta a
  instrumentação nova (ver §4.2).

---

## 7. Próximos Passos

1. `analytics_agent.py`: `_generate_sql_with_llm` ganha `ambiente`,
   captura `model_name`/custo do chunk final, chama `registrar_uso_ia`.
2. `analytics_agent.py`: `process_dynamic_chart_request` ganha `ambiente`,
   repassa.
3. `orchestrator.py`: calcula `ambiente_grafico` ao lado de
   `analytics_llm`, repassa nos 2 call sites.
4. `extractor.py`: `extract_page_products_local` ganha a chamada a
   `registrar_uso_ia` (sem parâmetro novo, ambiente constante).
5. `extractor.py`: `extract_page_products_vision` ganha `ambiente`,
   remove `record_ingestion_cost` e a estimativa por tamanho de texto,
   adiciona `registrar_uso_ia`. Atualiza os 4 call sites dentro de
   `extract_catalog_stream` com o valor de `ambiente` de cada (3 externo,
   1 interno — ver §4.3).
6. Testes dos 4 pontos (Seção 5).
7. Marcar item D como `[x]` em `docs/ROADMAP.md`.
