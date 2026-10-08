# Especificação Arquitetural: Ledger Unificado de Uso de IA — Item B (Origem Chat)

> **Data:** 08 de Outubro de 2026
> **Status:** Proposta de Arquitetura / Design Spec
> **Domínio:** Telemetria e Custos de IA (admin, cross-cutting)
> **Escopo desta spec:** só o item **B** do plano registrado em
> `docs/ROADMAP.md` ("Extra fora do MVP — Ledger Unificado de Uso de IA") —
> conectar todos os pontos de uso de IA alcançáveis a partir de
> `app.api.chat`/`app.router.orchestrator` à função `registrar_uso_ia`
> (item A, já mergeado em master, migração já aplicada no Postgres de
> desenvolvimento). Os itens C (origem B2B), D (origem Admin) e E (painel)
> continuam fora do escopo, cada um com sua própria spec.

---

## 1. Contexto e Objetivo

O item A entregou a tabela `ai_usage_events` e a função `registrar_uso_ia`,
mas **nenhum ponto de chamada real foi conectado ainda** — é fundação pura,
sem efeito observável. Este item B conecta a origem `"chat"`: todo ponto
onde `app.api.chat`/`app.router.orchestrator` (direta ou indiretamente)
aciona um modelo/engine de IA, local ou externo, texto ou visão.

Investigação de código (nesta mesma sessão) encontrou **10 pontos
concretos** de uso de IA alcançáveis a partir do chat, agrupados em 5
famílias — mais do que os 4 grupos originalmente nomeados no roadmap, que
descreviam a intenção em alto nível, não a contagem real de call sites:

1. **Geração de texto principal** (local ou externo, decidido por
   `backend_escolhido`) — `handle_message`.
2. **Extração de slots estruturados** — Vendas (`sales_catalog`) e
   Agendamento (`scheduling`), sempre via cliente **local**.
3. **Classificação de intenção e monitor de tom — caminho
   heurística+LLM** (`classifier`/`tone_monitor`), sempre via cliente
   **local**.
4. **Classificação de intenção e monitor de tom — caminho TypeSafe Jev**
   (`openrouter_client._perguntar_systemone_jev`), sempre **externo**.
   Achado confirmado nesta sessão: o endpoint `/systemone` retorna
   `model`/`usage.input_tokens`/`usage.output_tokens`/`usage.cost`/`id`/
   `provider` (verificado com chamada real às credenciais de
   desenvolvimento), mas o código atual descarta tudo exceto
   `answers[question_key]` — **nenhuma métrica é capturada hoje, nem
   contagem de chamada**.
5. **Identificação de produto por imagem** (`image_identification`) —
   CLIP interno (grátis, sem conceito de tokens) ou fallback de visão
   externa (pago, já extrai tokens/custo localmente mas não persiste em
   lugar nenhum).
6. **Avaliação de comprovante de pagamento** (`comprovante_evaluator`) —
   julgamento por LLM de texto (sempre local) e, quando OCR falha, visão
   computacional local ou externa (fallback) — hoje só tokens são
   capturados em `ParecerComprovante`, nenhum custo.

---

## 2. Mapeamento Completo: os 10 Pontos de Instrumentação

| # | Local (arquivo:função) | origem | ambiente | modelo | operacao | tokens/custo |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| 1 | `orchestrator.py` / `handle_message` (geração principal) | `chat` | `backend_escolhido` (`"interno"`/`"externo"`) | `chunk_final.model_name` | `geracao_resposta` | reais, de `chunk_final` |
| 2 | `sales_catalog.py` / `extract_sales_slots` | `chat` | `"interno"` (constante — sempre `local_client`) | `response.model_name` | `extracao_slots_vendas` | reais, de `response` |
| 3 | `scheduling.py` / `extract_booking_slots` | `chat` | `"interno"` (constante) | `response.model_name` | `extracao_slots_agendamento` | reais |
| 4 | `tone_monitor.py` / `_analyze_with_heuristic_llm` | `chat` | `"interno"` (constante) | `response.model_name` | `monitor_tom_heuristica_llm` | reais |
| 5 | `classifier.py` / `_classify_with_llm` | `chat` | `"interno"` (constante) | `response.model_name` | `classificacao_heuristica_llm` | reais |
| 6 | `classifier.py` / `_classify_with_jev` | `chat` | `"externo"` (constante) | `model` real da resposta Jev | `classificacao_jev` | `usage.input_tokens`/`output_tokens`/`cost` |
| 7 | `tone_monitor.py` / `_analyze_with_jev` | `chat` | `"externo"` (constante) | idem | `monitor_tom_jev` | idem |
| 8a | `image_identification.py` / `identify_product_by_image` (branch CLIP) | `chat` | `"interno"` | `"clip"` | `identificacao_imagem_clip` | tokens=`None` (sem conceito); custo=`0.0` (conhecido, grátis) |
| 8b | `image_identification.py` / `identify_product_by_image` (branch visão externa) | `chat` | `"externo"` | nome real do modelo de visão | `identificacao_imagem_visao_externa` | reais, já extraídos localmente (`v_prompt_tokens` etc.) |
| 9 | `comprovante_evaluator.py` / `avaliar_texto` (julgamento LLM) | `chat` | **inferido em runtime** (ver nota abaixo) | `response.model_name` | `comprovante_texto_llm` | reais |
| 10a | `comprovante_evaluator.py` / `avaliar_documento` (branch visão local) | `chat` | `"interno"` | nome do modelo local | `comprovante_visao_interna` | reais |
| 10b | `comprovante_evaluator.py` / `avaliar_documento` (branch visão externa, fallback) | `chat` | `"externo"` | nome do modelo externo | `comprovante_visao_externa` | reais — **gap de custo original que motivou o item B/C** |

**Nota sobre o ponto #9 (`comprovante_texto_llm`):** diferente de #2-5, o
`llm_client` de `ComprovanteEvaluator` no fluxo de chat **não** é uma
constante local. `orchestrator.py:1275` calcula
`llm_to_use = local_client if local_client is not None else external_client`
antes de chamar `processar_conversao_comprovante(..., llm_client=llm_to_use,
...)` — ou seja, cai para o cliente externo quando o backend local está
indisponível (achado só percebido na revisão desta spec, corrigindo uma
suposição inicial errada de que todo o grupo "extração/classificação"
seguia o mesmo padrão constante de #2-5). `ambiente` para este ponto é
inferido comparando identidade de objeto (`"interno" if llm_to_use is
local_client else "externo"`) no momento da chamada a `registrar_uso_ia`,
dentro de `avaliar_texto` — não uma constante de módulo.

`referencia_id`: só o ponto #1 (geração principal) passa
`referencia_id=conversation_id`. Os outros 9 pontos passam `None` —
decisão do usuário (2026-10-08): o valor de poder cruzar cada evento
secundário de volta à conversa exata não compensa o acoplamento de passar
`conversation_id` por 9 assinaturas de função que hoje não o recebem.

`origem` é sempre a constante `"chat"` nos 10 pontos — é a dimensão que dá
nome a este item.

---

## 3. Mecanismo de Execução: Fire-and-Forget via `spawn_background_task`

Todos os 10 pontos chamam `spawn_background_task(registrar_uso_ia(...))`
(`app.background_tasks`, já usado por `app.api.chat`/`app.api.local_models`)
em vez de `await registrar_uso_ia(...)` inline. Decisão do usuário
(2026-10-08), confirmada após discussão do risco da alternativa (await
inline nos pontos de maior valor): nenhum dos 10 pontos deve acrescentar
latência de escrita no banco ao caminho crítico de resposta do chat —
inclusive os pontos que capturam custo real (Jev, visão externa).

Consequência aceita: em caso de crash do processo entre o fim da chamada de
IA e a execução da task em background, o evento pode se perder. Isso é
consistente com o contrato já estabelecido em `registrar_uso_ia`
("telemetria é conveniência, nunca pode derrubar a chamada de IA real") —
nenhum ponto novo introduz uma garantia mais forte que a função em si não
oferece.

`spawn_background_task` não precisa de nenhuma mudança — assinatura já
aceita qualquer coroutine.

---

## 4. Mudanças de Plumbing Necessárias por Família

A maioria dos 10 pontos (#1-5, #9) já tem todos os dados prontos na
variável de resposta do LLM local (`LLMStreamChunk`/`response.model_name`/
`response.prompt_tokens`/etc.) — a chamada a `registrar_uso_ia` é só uma
linha nova em cada um, sem extração adicional. Três famílias exigem mudança
de código além da chamada:

### 4.1 Jev (#6, #7) — `openrouter_client.py`

`_perguntar_systemone_jev` (linha ~372) hoje retorna só
`response.json()["answers"][question_key]`. Passa a também capturar
`model`, `usage.get("input_tokens")`, `usage.get("output_tokens")`,
`usage.get("cost")` do mesmo `response.json()` já parseado, e repassar
esses quatro valores para os dois chamadores
(`classify_intent_jev`/`classify_tone_jev`), que por sua vez os repassam
para `_classify_with_jev`/`_analyze_with_jev` — os pontos reais de
instrumentação. Nenhum desses quatro campos é obrigatório na resposta real
(já confirmado por chamada real ao `/systemone` nesta sessão, mas a
instrumentação usa `.get()` com fallback `None`, nunca assume presença).

### 4.2 Identificação de imagem (#8a, #8b) — `image_identification.py`

Nenhuma extração nova: a branch de visão externa (linhas ~166-181) já
calcula `v_prompt_tokens`, `v_comp_tokens`, `v_cost_prompt`, `v_cost_comp`,
`v_model_name` localmente via `getattr(raw, ...)`. Só adiciona a chamada a
`registrar_uso_ia` nesse ponto (custo = `v_cost_prompt + v_cost_comp`) e,
na branch CLIP (linhas ~143-164), uma chamada equivalente com
`tokens_entrada=None, tokens_saida=None, custo_usd=0.0`.

### 4.3 Comprovante — ambiente do julgamento por LLM (#9) — `comprovante_evaluator.py` / `sales_catalog.py` / `orchestrator.py`

`ComprovanteEvaluator` só recebe `llm_client` (o objeto já escolhido) — não
tem, dentro de si, como saber se esse objeto é o cliente local ou o
externo, porque não guarda referência aos dois para comparar. Só o call
site em `orchestrator.py:1275` sabe isso (`llm_to_use = local_client if
local_client is not None else external_client`). Logo, `ambiente` para o
ponto #9 precisa ser **passado explicitamente** pelo chamador, não
inferido dentro do evaluator:

1. `ComprovanteEvaluator.__init__` ganha um parâmetro novo
   `llm_ambiente: str | None = None`, guardado em `self.llm_ambiente`.
2. `processar_conversao_comprovante` (`sales_catalog.py`) ganha o mesmo
   parâmetro e o repassa ao construtor do evaluator.
3. `orchestrator.py` (as duas chamadas, linhas ~1288 e ~1307) passa
   `llm_ambiente="interno" if llm_to_use is local_client else "externo"`.
4. `avaliar_texto` usa `self.llm_ambiente` (com fallback `"interno"` se
   `None` — nenhum chamador fora do chat precisa ser alterado neste item,
   e um valor ausente é mais provável vir de um teste/fluxo futuro que
   ainda não repassa o parâmetro do que de uma ambiguidade real).

Nota (correção pós-implementação, revisão final do item B, 2026-10-08):
ambos `origem` e `llm_ambiente` foram tornados parâmetros de construtor
obrigatórios (keyword-only, sem defaults), não opcionais como descrito
acima. Decisão deliberada tomada durante implementação (commit 2243d5a)
para evitar rotulagem incorreta no ledger: um padrão com defaults
silenciosos teria mislabelado os chamadores de fora do chat (MCP B2B em
`mcp_server/b2b.py` e admin em `api/admin_pedidos_conversao.py`), tornando
impossível depois rastrear cada evento de volta à sua origem verdadeira.
Como efeito colateral dessa mudança, todos os 4 call sites de
`ComprovanteEvaluator` agora passam `origem`/`llm_ambiente` explícitos
(chat ×2 em `orchestrator.py`, b2b ×1 em `mcp_server/b2b.py`, admin ×2 em
`api/admin_pedidos_conversao.py`) — dimensões corretas do ledger são
garantidas por construção, não inferência.

### 4.4 Comprovante — visão (#10a, #10b) — `comprovante_evaluator.py`

`ParecerComprovante` já extrai `prompt_tokens`/`completion_tokens` do
`vision_client.describe_image` mas **não extrai custo** — este é o gap que
motivou a investigação original do item B/C. Adiciona a extração de custo
(mesmo padrão de `image_identification.py`:
`getattr(raw_vision, "cost_prompt_usd", 0.0) + getattr(raw_vision,
"cost_completion_usd", 0.0)`) **só localmente**, dentro do loop
`for vision_client in (self.local_vision_client, self.vision_client):` —
usado na hora de chamar `registrar_uso_ia` e descartado depois. Decisão do
usuário (2026-10-08): **não** adicionar um campo novo em
`ParecerComprovante` para isso — YAGNI, nenhum outro código lê custo desse
dataclass hoje, e ele continua carregando só o que já carregava
(`prompt_tokens`/`completion_tokens`).

---

## 5. Tratamento de Erro

Nada novo a decidir: `registrar_uso_ia` já nunca lança exceção (contrato do
item A) e `spawn_background_task` roda em task separada da resposta
principal — nenhuma falha de telemetria (rede, banco, parsing de
`usage` ausente no Jev) pode afetar a resposta ao usuário em nenhum dos 10
pontos. Dados ausentes (ex.: Jev sem `usage` no payload) resultam em
`None` passado a `registrar_uso_ia`, nunca numa exceção na extração.

---

## 6. Testes

Para cada um dos 10 pontos: teste verifica que `registrar_uso_ia` (ou
`spawn_background_task`, mockado) é chamado com os valores corretos de
`origem`/`ambiente`/`modelo`/`operacao`/tokens/custo, usando os mocks de
cliente LLM/visão já existentes nos testes de
`orchestrator`/`classifier`/`tone_monitor`/`image_identification`/
`comprovante_evaluator`. `registrar_uso_ia` em si **não** é re-testado
(já coberto pelo item A) — só a chamada correta em cada call site.

Casos adicionais:
- Jev: teste com payload `usage` ausente/parcial → `registrar_uso_ia`
  chamado com `None` nos campos faltantes, sem exceção.
- Identificação de imagem: branch CLIP chama com `tokens=None, custo=0.0`;
  branch visão externa chama com os valores reais extraídos.
- Comprovante — ponto #9: `local_client` disponível → `ambiente="interno"`;
  `local_client=None` (fallback) → `ambiente="externo"` — cobrindo a
  inferência em runtime descrita em §4.3.
- Comprovante — pontos #10a/#10b: branch visão local/externa chama com
  custo extraído localmente; branch texto (OCR bem-sucedido, sem chamada
  de visão) não chama os pontos #10a/#10b, só o #9 quando há julgamento
  por LLM.

---

## 7. Fora de Escopo Desta Spec (itens C/D/E do roadmap)

- MCP B2B (`converter_reserva_venda`, que já chama o mesmo
  `ComprovanteEvaluator` deste item) — origem `"b2b"` é item C.
- Extração de catálogo por visão e geração de gráficos via LLM — origem
  `"admin"` é item D.
- Qualquer mudança em `/admin/metricas`/`app/api/admin_metrics.py` — item E.
- Mudar `ParecerComprovante` ou qualquer interface pública existente para
  expor custo — decisão explícita de não fazer isso neste item (§4.4).

---

## 8. Próximos Passos

1. `openrouter_client.py`: `_perguntar_systemone_jev` passa a capturar e
   repassar `model`/`usage.input_tokens`/`usage.output_tokens`/`usage.cost`.
2. `classifier.py`/`tone_monitor.py`: pontos #5, #6, #7, #4 chamam
   `spawn_background_task(registrar_uso_ia(...))`.
3. `sales_catalog.py`/`scheduling.py`: pontos #2, #3.
4. `orchestrator.py`: ponto #1 (geração principal).
5. `image_identification.py`: pontos #8a, #8b.
6. `comprovante_evaluator.py` + `sales_catalog.py` + `orchestrator.py`:
   parâmetro `llm_ambiente` para o ponto #9 (§4.3), extração de custo local
   para os pontos #10a/#10b (§4.4).
7. Testes dos 10 pontos (Seção 6).
8. Atualizar `docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md` se a mudança em
   `_perguntar_systemone_jev` alterar algum prompt mapeado (não deveria —
   é só captura de metadados da resposta, não do prompt enviado).
9. Marcar item B como `[x]` em `docs/ROADMAP.md`.
