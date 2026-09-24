# Design — Monitor de Tom (R8, Fase 4B)

> Spec resultante de sessão de brainstorm com o desenvolvedor em 2026-09-23.
> Cobre os dois itens pendentes de R8 em `docs/ROADMAP.md` (Fase 4):
> "Implementar classificador leve de sentimento/urgência" e "Implementar
> alerta e transferência simulada para atendente humano + log dos casos
> escalonados" — tratados como uma única entrega coerente (um classificador
> sem ação nenhuma não serve pra nada). **Fora do escopo desta spec**: o
> banner visual no frontend consumindo o alerta (item próprio da Fase 8,
> "Implementar banner de transferência para atendente humano") — fica para
> um próximo ciclo de `/proximo-passo`, decisão explícita do desenvolvedor
> para não encadear dois itens do roadmap na mesma entrega.

## 1. Objetivo

Fechar R8 (`docs/ARCHITECTURE.md` linha 76): monitorar o tom de cada
mensagem do cliente em paralelo ao roteamento normal (ver Seção 4 de
`docs/ARCHITECTURE.md`, fluxo "(b) Monitoramento de tom") e, quando a
urgência/insatisfação ultrapassa um limiar, disparar um alerta (evento SSE)
e registrar o caso persistentemente para follow-up humano — sem interromper
a resposta normal do domínio (Vendas/Suporte/Atendimento/Agendamento), que
continua sendo gerada normalmente.

## 2. Decisão de arquitetura: paralelo, não substitui a resposta

O Monitor de Tom **não é mais um domínio de intenção** (diferente de
Agendamento) — é uma checagem transversal que roda sobre toda mensagem,
independente do domínio classificado. Corresponde ao "paralelo" do diagrama
de `docs/ARCHITECTURE.md` Seção 2.

Em `app.router.orchestrator.handle_message`: a análise de tom roda logo no
início, **antes** da classificação de domínio (não depende do resultado
dela, então não precisa esperar) — mas de forma sequencial dentro do mesmo
fluxo (sem `asyncio.gather`/concorrência real), para manter a ordem dos
eventos SSE simples e previsível. Quando escala pela primeira vez na
conversa: (a) a resposta normal do domínio continua sendo gerada e
streamada normalmente, (b) um evento SSE `escalonamento` é emitido antes do
`done`, (c) o caso é persistido no Postgres (Seção 5), (d) um log
estruturado é emitido (`tom_escalonado`, mesmo padrão de `router_decision`).

**Decisão: sem mecanismo de saída** (mesmo espírito da limitação já aceita
para o fluxo de agendamento) — uma vez escalada, a conversa fica marcada
como "já escalada" pelo resto da sessão do processo; não há como
"des-escalar". `# MVP: aceitável para o protótipo — a decisão de
retomar/encerrar o atendimento simulado fica com o "atendente" (fora do
sistema), não há fila real de atendimento humano (ver
docs/ARCHITECTURE.md §7, risco já aceito)`.

## 3. Classificação: heurística → provedor configurável

Novo módulo puro `backend/src/app/router/tone_monitor.py` (mesmo padrão de
`app.router.classifier`/`app.router.scheduling` — sem I/O de FastAPI,
dependências injetadas como parâmetros):

```python
class ToneResult(BaseModel):
    escalate: bool
    motivo: str | None  # "urgencia" | "insatisfacao" | None quando escalate=False
    confidence: float
    provider_efetivo: str  # "heuristica_llm" | "jev_openrouter"
    # Mesma convenção do classificador de intenção (docs/ARCHITECTURE.md
    # §5, ClassificationResult.provider_efetivo): só distingue qual dos
    # DOIS provedores configuráveis (TONE_MONITOR_PROVIDER) decidiu de
    # fato — "heuristica_llm" cobre tanto o atalho da heurística quanto o
    # fallback ao LLM local (são o mesmo provedor configurado, a
    # telemetria não precisa granularidade interna a esse caminho);
    # "jev_openrouter" só aparece quando o Jev de fato respondeu. Se o Jev
    # falhar, degrada para "heuristica_llm" mesmo que
    # TONE_MONITOR_PROVIDER="jev_openrouter" estivesse configurado — igual
    # ao achado importante 1 da revisão final do Jev, essencial pra não
    # corromper a comparação de provedores da Fase 10.

async def analyze_tone(
    message: str,
    recent_messages: list[str],
    strategy_provider: str,  # "heuristica_llm" | "jev_openrouter"
    llm_client: LLMClient,
    external_client: Any,  # OpenRouterClient, quando strategy_provider="jev_openrouter"
) -> ToneResult: ...
```

### 3.1. Heurística (primeiro passo, sempre roda)

Reaproveita `_normalize` de `app.router.classifier` (minúsculas sem
diacríticos). Lista de palavras/expressões de urgência e insatisfação em
português (ex.: "urgente", "péssimo", "absurdo", "cancelar tudo",
"processar", "reclamação procon", "nunca mais compro") + sinais estruturais:
mensagem com 10+ caracteres alfabéticos onde ≥70% estão em maiúsculas, ou
3+ pontos de exclamação seguidos (`!{3,}`, regex). Qualquer sinal forte
encontrado → `escalate=True` direto, sem chamar LLM/Jev
(`provider_efetivo="heuristica_llm"`, mesma convenção da Seção 3 acima).
Nenhum sinal → ambíguo, cai na Seção 3.2.

`# MVP: heurística simples de palavras-chave, mesmo espírito de
`app.router.classifier._DOMAIN_KEYWORDS` — sem NLP mais robusto, lista a
refinar contra casos reais quando existirem (mesma nota já aceita pro
classificador de intenção)`.

### 3.2. Fallback ambíguo — provedor configurável (`TONE_MONITOR_PROVIDER`)

Mesmo padrão de dois provedores já usado por `intent_router_provider`
(`docs/ARCHITECTURE.md` §5, decisão do Jev):

- **`heuristica_llm`** (default): chama `llm_client.generate(prompt)`
  (Ollama local, já com `think: false` desde o fix desta sessão). Prompt
  curto pedindo JSON `{"escalar": bool, "motivo": "...", "confianca":
  0.0}`. Resposta não-parseável → `escalate=False`,
  `provider_efetivo="heuristica_llm"` (mesmo espírito de
  `_classify_heuristic_fallback`: ambíguo sem sinal claro não escala por
  padrão, lado seguro contra falso positivo).
- **`jev_openrouter`**: novo método
  `OpenRouterClient.classify_tone_jev(message, recent_messages) ->
  tuple[bool, float]`, chamando o mesmo endpoint dedicado
  `POST {base_url}/systemone` já usado por `classify_intent_jev`
  (`docs/ARCHITECTURE.md` §5), mas com uma pergunta do tipo **`noul`**
  (sim/não com probabilidade calibrada) em vez de `choice` — encaixe mais
  natural que pedir um domínio entre 5 opções:
  ```json
  {
    "model": "~typesafe/jev-latest",
    "state": "Contexto prévio:\n{contexto}\n\nMensagem: {mensagem}",
    "questions": {
      "escalar": {
        "type": "noul",
        "instructions": "O cliente está demonstrando urgência ou insatisfação forte que justifique transferência para atendimento humano?",
        "criteria": {
          "true": "Mensagem com tom de urgência, raiva, ameaça de cancelamento/processo, ou insatisfação explícita e forte.",
          "false": "Tom neutro ou normal de atendimento, mesmo com dúvida ou reclamação leve."
        }
      }
    }
  }
  ```
  Resposta: `answers.escalar.noul` (probabilidade 0.0–1.0) vira
  `confidence`; `escalate = noul >= 0.5`. Qualquer falha (timeout, erro
  HTTP, chave ausente) degrada para `provider_efetivo="heuristica_llm"`
  (`escalate=False`, mesmo padrão de fallback gracioso do
  `classify_intent_jev`) — nunca derruba a mensagem do usuário.

## 4. Estado por conversa (evita repetir o alerta)

Dict em memória por processo, mesmo padrão MVP de `_conversation_history`
(`app.api.chat`) e `booking_slots` (`app.router.scheduling`):
`_conversas_escaladas: set[str]` (só guarda o `conversation_id`, sem dado
sensível) em `tone_monitor.py`, com `marcar_escalada`/`ja_escalada`
análogos a `set_booking_slots`/`get_booking_slots`. `# MVP: perdido em
restart do processo, mesma limitação já aceita pro histórico de
conversa/estado de agendamento`.

## 5. Persistência: tabela `tom_escalonamentos`

Postgres já provisionado (`docker-compose.yml`, mesmo usado por
`rag_documents`/`produtos`) — sem infraestrutura nova. Migração Alembic
`backend/migrations/versions/0006_tom_escalonamentos.py`:

| Coluna | Tipo | Nota |
| --- | --- | --- |
| `id` | serial/uuid (seguir padrão das migrações existentes) | PK |
| `conversation_id` | text | não-nulo |
| `mensagem` | text | mensagem que disparou a escalada (truncada se necessário) |
| `motivo` | text | nullable |
| `confianca` | float | |
| `provider_efetivo` | text | `"heuristica_llm"` \| `"jev_openrouter"` |
| `criado_em` | timestamp with time zone | default `now()` |

**Decisão: não faz parte da Fase 6** (memória/persistência de conversa) —
escopo diferente (lista de casos para revisão humana, não resumo/histórico
de conversa). Registrado aqui para não ser confundido com escopo da Fase 6
nem esquecido na revisão final (Fase 11).

## 6. Contrato de API

### 6.1. Evento SSE novo: `escalonamento`

Emitido em `app.api.chat` (mesmo stream de `POST /api/chat/messages`),
**antes** do evento `done`, só quando `analyze_tone` retorna
`escalate=True` **e** a conversa ainda não tinha escalado
(`tone_monitor.ja_escalada(conversation_id)` era `False`):

```
event: escalonamento
data: {"motivo": "urgencia", "confianca": 0.87}
```

Contrato completo a documentar em `docs/FRONTEND.md` §4 junto da
implementação (regra 9 do `CLAUDE.md`) — mesmo arquivo que já documenta
`conversation`/`transcription`/`status`/`token`/`done`/`error`.

### 6.2. Endpoint de listagem: `GET /api/admin/tom/escalonamentos`

Lista os casos persistidos, mais recentes primeiro, `LIMIT 100` fixo, sem
paginação (`# MVP: sem cursor/paginação — mesma simplicidade de outras
listagens administrativas do projeto`). Sem UI
dedicada nesta entrega — só a API, para inspeção manual/demonstração.

## 7. Configuração / Admin

Novas variáveis em `.env.example`/`config.py`:
- `TONE_MONITOR_ENABLED` (bool, default `true`)
- `TONE_MONITOR_PROVIDER` (`"heuristica_llm"` \| `"jev_openrouter"`,
  default `"heuristica_llm"`)

Ajustáveis em runtime via `GET`/`PUT /api/admin/runtime-settings`, exibidas
em `/admin/modelos` → "Parâmetros de execução" — mesmo padrão de
`intent_router_provider`/demais parâmetros já existentes (decisão
registrada em `docs/ARCHITECTURE.md` §5). Quando `TONE_MONITOR_ENABLED=false`,
`handle_message` pula a chamada a `analyze_tone` inteiramente (sem custo
algum, nem heurística).

## 8. Testes

- `backend/tests/test_tone_monitor.py`: heurística (casos com/sem sinal
  forte), fallback LLM local (mock), fallback Jev (mock via
  `httpx.MockTransport`, mesmo padrão de `test_openrouter_client.py`),
  fallback gracioso em falha de cada provedor, `provider_efetivo` correto
  em cada caminho.
- `backend/tests/test_openrouter_client.py`: novo `classify_tone_jev` —
  sucesso (`noul` alto → `escalate=True`), `noul` baixo → `escalate=False`,
  falha HTTP → propaga exceção (fallback gracioso é responsabilidade de
  `tone_monitor.py`, não do cliente, mesmo desenho de `classify_intent_jev`).
- `backend/tests/test_orchestrator.py`: mensagem única com sinal forte →
  `RouterDecision`/evento continuam normais E evento `escalonamento`
  emitido; segunda mensagem na mesma conversa (já escalada) → evento não
  repete; `TONE_MONITOR_ENABLED=false` → `analyze_tone` nunca chamado.
- `backend/tests/test_chat_api.py`: evento SSE `escalonamento` aparece
  antes do `done` no stream real via `TestClient`.
- `backend/tests/test_tom_escalonamentos_api.py`: `GET
  /api/admin/tom/escalonamentos` reflete zero casos, um caso persistido
  aparece na listagem, ordem mais-recente-primeiro.
- `backend/tests/test_config.py`: defaults de
  `TONE_MONITOR_ENABLED`/`TONE_MONITOR_PROVIDER`.

## 9. Fora do escopo desta entrega

- Banner visual no frontend consumindo o evento `escalonamento` (Fase 8,
  item próprio do roadmap — próximo `/proximo-passo`).
- Fila real de atendimento humano / transferência de contexto real —
  já fora do MVP geral (`docs/ARCHITECTURE.md` §7, `CLAUDE.md` "Fora de
  escopo").
- Mecanismo de "des-escalar" uma conversa já marcada.
- Painel administrativo visual para `tom_escalonamentos` (só a API por
  ora).
