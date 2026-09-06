# Design — Fase 1: Modelo Local e Roteador Básico (R1, R3)

> Spec resultante de sessão de brainstorming em 2026-09-05. Cobre apenas a
> Fase 1 do `docs/ROADMAP.md`. Decisões de arquitetura já foram propagadas
> para `docs/ARCHITECTURE.md`, `docs/ROADMAP.md` e `docs/TECHNOLOGY_STACK.md`
> — este documento detalha o desenho de implementação, não repete o "porquê"
> de cada escolha, que vive nesses três arquivos.

## 1. Objetivo

Implementar o módulo `backend/src/app/router/`: serviço de LLM local (Ollama),
cliente de LLM externo (OpenRouter), classificador de intenção (domínio +
complexidade) e a lógica de orquestração que decide entre modelo local,
modelo externo e RAG — com log estruturado de cada decisão.

Fora do escopo desta fase (não implementar aqui): ingestão/indexação real do
RAG (Fase 2, só a interface é definida agora), MCP Google Calendar (Fase 4),
playbook de Vendas com oferta proativa de agendamento (Fase 3), persistência
de `router_logs` em banco (Fase 6).

## 2. Componentes

### 2.1 `llm_client.py`

Interface comum (`Protocol`) implementada por dois clientes:

```python
class LLMResponse(BaseModel):
    text: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_duration_ms: float
    load_duration_ms: float | None  # só disponível no Ollama
    eval_duration_ms: float | None  # só disponível no Ollama
    estimated_cost_usd: float  # 0.0 para local

class LLMClient(Protocol):
    async def generate(self, prompt: str, **kwargs) -> LLMResponse: ...
```

- **`OllamaClient`** — chama a API HTTP local (`OLLAMA_BASE_URL`, default
  `http://localhost:11434`), modelo ativo via `OLLAMA_MODEL`. Mapeia
  `prompt_eval_count`/`eval_count` e `load_duration`/`eval_duration` da
  resposta do Ollama para `LLMResponse`. `estimated_cost_usd = 0.0`.
- **`OpenRouterClient`** — API compatível com OpenAI, modelo via
  `OPENROUTER_MODEL` (variável de config, sem default fixado nesta fase —
  decidir na hora de rodar o benchmark real). Chave em
  `OPENROUTER_API_KEY` (`.env.example`, sem valor real versionado).
  `estimated_cost_usd` calculado a partir de uma tabela pequena de
  preço-por-token em config (por modelo), multiplicando pelos tokens de
  entrada/saída devolvidos pela API.

### 2.2 `classifier.py`

```python
class ClassificationResult(BaseModel):
    domain: Literal["vendas", "suporte", "atendimento", "agendamento", "fora_escopo"]
    complexity: Literal["baixa", "alta"]
    confidence: float  # 0-1, capturado/logado; não usado como gatilho de decisão nesta fase
```

- Recebe a mensagem atual **+ últimas 1–3 mensagens da conversa** (parâmetro
  `recent_messages: list[str] | None`, passado pelo chamador — não depende
  da memória persistida da Fase 6). Necessário para resolver confirmações
  curtas a ofertas feitas pelo próprio assistente (ex.: aceite de
  agendamento proposto durante uma resposta de Vendas).
- Camada de regras rápidas primeiro (heurística de palavras-chave por
  domínio — lista inicial a refinar contra o conjunto de teste de
  `eval/router_intents/`, ex.: "orçamento/comprar/preço" → vendas,
  "não funciona/quebrado/erro" → suporte, "nota fiscal/troca/devolução" →
  atendimento, "visita/agendar/marcar" → agendamento). Se as regras
  resolverem domínio e complexidade com confiança suficiente, não chama LLM.
- Caso as regras sejam inconclusivas, aciona a estratégia configurada em
  `ROUTER_COMPLEXITY_STRATEGY`:
  - `heuristic` — regras adicionais (tamanho da mensagem, nº de perguntas,
    presença de jargão técnico) decidem complexidade sem chamar LLM;
    domínio ainda pode precisar de uma chamada LLM simples se as regras de
    domínio também falharem.
  - `llm` — uma única chamada ao `OllamaClient` com saída estruturada
    (`format="json"` do Ollama, validada contra `ClassificationResult`)
    devolve domínio + complexidade + confiança juntos.
  - Se a chamada LLM devolver JSON inválido/não parseável: cai para a
    estratégia heurística só naquela requisição (log de aviso), não trava a
    mensagem.

### 2.3 `rag_client.py` (interface apenas — implementação na Fase 2)

```python
class Document(BaseModel):
    content: str
    source: str
    score: float

class RAGClient(Protocol):
    async def search(self, query: str, domain: str) -> list[Document]: ...
```

Nesta fase, uma implementação stub (`NullRAGClient`) que sempre devolve
lista vazia é suficiente para o `orchestrator.py` ser testável — a
implementação real (Qdrant) entra na Fase 2 sem alterar o orchestrator.

### 2.4 `orchestrator.py`

Fluxo de decisão (ver também `docs/ARCHITECTURE.md`, tabela de escopo, linha
"Roteador/Orquestrador"):

```
mensagem + recent_messages
      │
      ▼
classifier.classify(...) → domain, complexity, confidence
      │
      ├─ domain == "agendamento" → sempre OllamaClient
      │
      ├─ domain == "fora_escopo" → sempre OpenRouterClient (sem tentar RAG)
      │
      └─ domain in {"vendas", "suporte", "atendimento"}:
              │
              ▼
         rag_client.search(mensagem, domain)
              │
              ├─ erro de conexão/infra (Qdrant fora do ar) → FALHA DURA:
              │     erro claro ao usuário, log de falha, SEM fallback
              │     automático pro externo (evita resposta sem grounding
              │     real de catálogo/estoque/preço)
              │
              ├─ busca OK, sem resultado relevante → OpenRouterClient
              │     (sinal de negócio válido: fora do que o catálogo cobre)
              │
              └─ busca OK, achou conteúdo relevante:
                    ├─ complexity == "alta" → OpenRouterClient
                    └─ complexity == "baixa" → OllamaClient
```

Falhas de infraestrutura tratadas como erro duro (sem fallback automático
pro externo, para não mascarar o problema nem gerar custo/risco de resposta
sem grounding):
- `OllamaClient` indisponível/timeout → erro claro ao usuário
  ("não consegui processar agora, tente novamente em instantes") + log de
  falha. Timeout configurável (`LOCAL_LLM_TIMEOUT_S`, default 30s).
- `OpenRouterClient` indisponível/erro/rate limit → idem (já é o destino
  final, não há para onde mais escalar). Timeout configurável
  (`EXTERNAL_LLM_TIMEOUT_S`, default 30s).

Cada decisão gera um registro de log estruturado via `logging_config.py`
já existente (contextvar de ID de conversa + formatter JSON), campos:
`domain`, `complexity`, `confidence`, `complexity_strategy_usada`,
`backend_escolhido` (`local`/`externo`), `motivo_escalonamento`
(`fora_escopo`/`rag_vazio`/`complexidade_alta`/`nenhum`), `latencia_ms`,
`tokens_entrada`, `tokens_saida`, `custo_estimado_usd`. **Sem persistência
em banco nesta fase** — isso é a tabela `router_logs` da Fase 6.

## 3. Configuração (`config.py` / `.env.example`)

Novas variáveis:
- `OLLAMA_BASE_URL` (default `http://localhost:11434`)
- `OLLAMA_MODEL` (modelo local ativo em produção/dev — distinto dos 9
  candidatos usados só na avaliação comparativa em `eval/`)
- `OPENROUTER_API_KEY` (sem valor real versionado)
- `OPENROUTER_MODEL` (sem default fixado nesta fase)
- `ROUTER_COMPLEXITY_STRATEGY` (`heuristic` | `llm`, default `heuristic`
  — mais barato, sem chamada extra de LLM)
- `LOCAL_LLM_TIMEOUT_S` (default `30`)
- `EXTERNAL_LLM_TIMEOUT_S` (default `30`)

## 4. Avaliação comparativa de modelos locais

9 configurações (ver `docs/ARCHITECTURE.md`, tabela de escopo, e
`docs/ROADMAP.md`, Fase 1):

1. Llama 3.1 8B
2. Qwen2.5 7B
3. Qwen3 14B — Q4_K_M
4. Qwen3 14B — Q5_K_M
5. Qwen3 8B — Q5_K_M
6. Qwen3 8B — Q8_0
7. Phi-4-mini/Phi-4 (3.8B–7B)
8. Gemma-4-12B — 4-bit
9. Gemma-4-12B — 8-bit

`# MVP: confirmar disponibilidade do Gemma-4-12B no registro do Ollama
(ollama.com/library) antes de rodar — modelo ainda não verificado`.

Script em `backend/eval/latency/` itera as 9 configs (troca de modelo via
`ollama pull` + campo `model` na requisição), roda o mesmo conjunto de
prompts em cada uma, grava por config: latência (média/p95, com breakdown
`load_duration`/`eval_duration`), tokens de entrada/saída. Script em
`backend/eval/router_intents/` roda a bateria de 30–50 mensagens rotuladas
contra cada config para medir acurácia do classificador nessa config.
Resultado por config em `eval/latency/results.json` /
`eval/router_intents/results.json` (uma entrada por configuração).

A comparação "local x externo" do `docs/EVALUATION.md` #3 roda separada,
uma vez, usando a config local "vencedora" da comparação entre as 9 contra
o `OPENROUTER_MODEL` escolhido no momento do benchmark.

## 5. Testes (`backend/tests/`)

- `classifier.py`: casos por domínio (incluindo `fora_escopo`), casos
  ambíguos entre domínios, complexidade baixa/alta nas duas estratégias,
  caso de JSON malformado caindo pra heurística.
- `orchestrator.py`: matriz de decisão com `LLMClient`/`RAGClient`
  mockados — cobre explicitamente a distinção entre "RAG vazio (sem
  match, busca OK)" x "RAG indisponível (erro de conexão)" resultando em
  caminhos diferentes, e "Ollama indisponível" retornando erro claro sem
  fallback silencioso pro externo.
- `llm_client.py`: contrato comum testado com um client fake, sem precisar
  de Ollama/OpenRouter reais.
- Testes que batem em Ollama de verdade marcados `@pytest.mark.gpu`.

## 6. Itens explicitamente fora desta fase

- Implementação real do `RAGClient` (Qdrant) — Fase 2.
- Playbook de Vendas com oferta proativa de agendamento — Fase 3 (já
  registrado em `docs/ROADMAP.md`).
- MCP Google Calendar / intenção de agendamento com coleta de dados — Fase 4.
- Persistência de `router_logs` em PostgreSQL — Fase 6.
- Escolha final do `OPENROUTER_MODEL` — decidir na hora de rodar o
  benchmark real, não bloqueia esta fase.
