# Streaming (SSE) da resposta do chat — Design

> Spec de apoio ao plano de implementação. Ver `docs/ROADMAP.md` Fase 8
> ("Implementar envio de texto e exibição do streaming de resposta (SSE)")
> e `docs/FRONTEND.md` §3/§4.

## Motivação

Hoje `POST /api/chat/messages` é síncrono: o cliente espera a resposta
inteira (RAG + geração completa) antes de ver qualquer coisa. Dois
problemas práticos, ambos observados em teste manual real:

1. **Cold-start do modelo local invisível.** O Ollama descarrega o modelo
   da VRAM depois de um tempo ocioso (`keep_alive`). Recarregar
   `gemma4:12b-it-q4_K_M` leva ~15-17s sozinho (medido: `load_duration:
   14.7s`) — sem nenhum feedback, o usuário só vê a UI travada, e se a soma
   de cold-start + geração passar do timeout configurado, a requisição
   falha com "Serviço temporariamente indisponível" mesmo o sistema estando
   saudável (só lento na primeira chamada).
2. **Sem feedback incremental.** Respostas mais longas (ex.: listar vários
   produtos) demoram vários segundos sem nenhum indício de progresso.

## Decisão de transporte: POST único retornando `text/event-stream`

Duas opções foram consideradas:

**A — POST único que já retorna o stream (escolhida).** Uma requisição
`POST /api/chat/messages` cuja resposta é `text/event-stream`, lida via
`fetch` + `ReadableStream` no frontend (não `EventSource`, que só suporta
GET). RAG e classificação continuam síncronos *antes* do stream começar;
só a geração da resposta final do LLM é incremental.

**B — POST dispara + `GET /api/chat/stream/{conversation_id}` escuta**
(desenho original, rascunho em `docs/FRONTEND.md` §4, marcado como "a
refinar"). Permitiria reconectar após queda de conexão e múltiplos
ouvintes na mesma geração, mas exige manter a geração rodando em
background no servidor independente de alguém estar ouvindo, um buffer
para replay (GET pode conectar depois do POST, ou depois que a geração já
terminou), e limpeza de gerações órfãs se nenhum GET nunca chegar a
conectar.

**Por que A:** este é um protótipo de TCC de sessão única por aba, sem
requisito de retomar conversas entre dispositivos nem de múltiplas abas
sincronizadas assistindo a mesma resposta. A robustez extra da opção B
(reconexão, múltiplos ouvintes) é engenharia especulativa para um
requisito que ninguém pediu. O custo real de A — se a conexão cair no meio
(rede instável, aba em segundo plano suspendendo a requisição no celular),
a resposta parcial se perde e a pergunta precisa ser reenviada do zero —
é aceitável nesse contexto.

`# MVP: opção B fica registrada aqui como evolução futura, caso surja uma
necessidade concreta de retomar/multiplexar streams (ex.: histórico
persistido entre dispositivos, Fase 6) — não implementar sem essa
necessidade se materializar.`

## Contrato do endpoint

`POST /api/chat/messages` — request body **inalterado**
(`ChatMessageRequest`: `message?`, `conversation_id?`, `audio`).

Response: `Content-Type: text/event-stream`, corpo é uma sequência de
eventos SSE nomeados (`event: <tipo>\ndata: <json>\n\n`), nesta ordem
possível:

1. **`conversation`** — sempre o primeiro evento.
   ```json
   {"conversation_id": "uuid"}
   ```
2. **`transcription`** — só quando o request trouxe `audio` (emitido logo
   após a transcrição via STT terminar, antes do roteamento/RAG).
   ```json
   {"transcribed_message": "texto transcrito"}
   ```
3. **`status`** — só quando o backend escolhido for o local **e** o modelo
   configurado não estiver na lista de modelos carregados do Ollama
   (`GET /api/ps`, checado imediatamente antes de chamar geração).
   ```json
   {"status": "carregando_modelo"}
   ```
4. **`token`** — um por fragmento de texto gerado, zero ou mais vezes.
   ```json
   {"text": "fragmento da resposta"}
   ```
5. **`done`** — sempre o último evento em caso de sucesso; contém os
   mesmos campos que `ChatMessageResponse` já tem hoje (exceto `message`,
   que foi entregue via `token`, e `transcribed_message`, já entregue via
   `transcription`).
   ```json
   {
     "domain": "vendas", "backend_used": "local", "escalation_reason": "nenhum",
     "model_name": "...", "prompt_tokens": 0, "completion_tokens": 0,
     "latency_ms": 0.0, "ttft_ms": 0.0, "tps": 0.0, "confidence": 0.0,
     "complexity": "baixa", "estimated_cost_usd": 0.0,
     "rag_retrieval_ms": 0.0, "rag_chunks_count": 0, "rag_avg_score": 0.0
   }
   ```
6. **`error`** — substitui `done` se algo falhar em qualquer ponto do
   fluxo (RAG indisponível, backend local/externo indisponível, STT
   indisponível). Stream termina logo em seguida.
   ```json
   {"detail": "Serviço temporariamente indisponível, tente novamente."}
   ```

Erros de validação de entrada que hoje são HTTP 4xx **antes** de começar a
processar (áudio base64 inválido, nem `message` nem `audio` presentes)
continuam sendo respostas HTTP normais (400/422), não SSE — o stream só
começa depois que a requisição já é válida o bastante para processar.

## Mudanças no backend

### `app.router.llm_client.LLMClient` (Protocol)

Ganha um segundo método, ao lado de `generate` (que continua existindo e
é usado por `classify()` para a etapa de classificação, que **permanece
não-streaming** — é uma decisão interna, não texto mostrado ao usuário):

```python
class LLMStreamChunk(BaseModel):
    text: str | None = None       # fragmento de texto, quando presente
    done: bool = False            # True só no último chunk
    # Campos abaixo só vêm preenchidos no chunk com done=True:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_duration_ms: float | None = None
    load_duration_ms: float | None = None
    prompt_eval_duration_ms: float | None = None
    eval_duration_ms: float | None = None
    estimated_cost_usd: float = 0.0
    model_name: str | None = None

class LLMClient(Protocol):
    async def generate(self, prompt: str) -> LLMResponse: ...
    def generate_stream(self, prompt: str) -> AsyncIterator[LLMStreamChunk]: ...
    async def is_model_ready(self) -> bool: ...
```

`is_model_ready()` sempre retorna `True` para `OpenRouterClient` (não há
conceito de "modelo descarregado" numa API externa) — só `OllamaClient`
implementa a checagem de verdade.

### `app.router.ollama_client.OllamaClient`

- `is_model_ready()` — `GET /api/ps`, verifica se `self._model` aparece em
  `data["models"][*]["name"]`.
- `generate_stream()` — mesmo padrão já usado por `pull_model_streaming`
  (`self._client.stream("POST", f"{base_url}/api/generate", json={"model":
  ..., "prompt": ..., "stream": True}, timeout=None)`, iterando
  `response.aiter_lines()`, um `json.loads` por linha). Cada linha sem
  `"done": true` vira `LLMStreamChunk(text=data["response"])`; a linha
  final (`"done": true`) vira o chunk com os campos de telemetria
  (mesmo mapeamento que `generate()` já faz hoje a partir de
  `prompt_eval_count`/`eval_count`/`total_duration`/`load_duration`/
  `prompt_eval_duration`/`eval_duration`).
- `timeout=None` no stream (como em `pull_model_streaming`) —
  `LOCAL_LLM_TIMEOUT_S` deixa de se aplicar à chamada de streaming em si;
  ver seção "Timeouts" abaixo.

### `app.router.openrouter_client.OpenRouterClient`

- `is_model_ready()` — retorna `True` sempre (sem chamada de rede).
- `generate_stream()` — `stream: true` no corpo, resposta já vem em SSE
  (formato `data: {...}\n\n`, terminando em `data: [DONE]\n\n`); cada
  chunk tem `choices[0]["delta"].get("content")` como fragmento de texto.
  OpenRouter não devolve `usage` (tokens) em todo chunk por padrão — passar
  `stream_options: {"include_usage": true}` no corpo da requisição (suporte
  padrão da API OpenAI-compatible) para que o **último** chunk antes de
  `[DONE]` inclua `usage.prompt_tokens`/`usage.completion_tokens`, usados
  para o chunk final (`done=True`) com custo estimado.

### `app.router.orchestrator`

`handle_message` é refatorada para um **async generator**
(`AsyncIterator[OrchestratorEvent]`, um union/enum simples de tipos de
evento internos que espelham os eventos SSE — `StatusEvent`, `TokenEvent`,
`DoneEvent`). Classificação e busca RAG continuam exatamente como hoje
(síncronas, `await`), só a parte final (que hoje faz `response =
await client.generate(prompt)`) passa a ser:

```python
if not await client.is_model_ready():
    yield StatusEvent(status="carregando_modelo")

texto_completo = []
chunk_final = None
async for chunk in client.generate_stream(prompt):
    if chunk.text:
        texto_completo.append(chunk.text)
        yield TokenEvent(text=chunk.text)
    if chunk.done:
        chunk_final = chunk

# calcula tps/ttft a partir de chunk_final, mesma lógica de hoje
yield DoneEvent(resposta="".join(texto_completo), domain=..., ...)
```

`RouterDecision` (o modelo Pydantic atual) deixa de ser o valor de
retorno de `handle_message`; vira só o **payload do evento `done`** (os
mesmos campos, menos `resposta` que continua existindo pois é usada
internamente para o log estruturado `router_decision` no final).

### `app.api.chat`

`send_message` deixa de retornar `ChatMessageResponse` e passa a retornar
`fastapi.responses.StreamingResponse(media_type="text/event-stream")`,
envolvendo um async generator que:
1. Faz a parte síncrona de hoje (decodificar áudio, transcrever via STT,
   validar `effective_message`) **antes** de abrir o stream — erros aqui
   continuam HTTP 4xx normais, sem mudança.
2. Abre o stream, emite `conversation` (e `transcription`, se aplicável).
3. Itera `handle_message(...)` (agora generator), traduzindo cada evento
   interno para uma linha SSE (`event: token\ndata: ...\n\n`, etc.).
4. Em caso de exceção (`LocalBackendIndisponivelError`,
   `ExternalBackendIndisponivelError`, `RAGConnectionError`) capturada
   **depois** que o stream já abriu, emite `event: error` e encerra —
   não dá para trocar por um HTTP 503 nesse ponto, a resposta HTTP já
   começou.
5. Atualiza `_conversation_history` ao final, como hoje.

## Detecção de cold-start (o pedido original)

`OllamaClient.is_model_ready()` roda **antes** de `generate_stream()`
propriamente, e só quando o backend escolhido é o local. Se o modelo não
estiver carregado, o evento `status: carregando_modelo` sai imediatamente
(antes de qualquer chamada lenta), dando ao frontend a chance de mostrar
"Aguarde, carregando o modelo local..." enquanto a chamada de
streaming (que vai demorar por causa do cold-start) ainda está em
andamento.

## Timeouts

Streaming não combina bem com um timeout fixo de requisição inteira (uma
resposta longa pode legitimamente levar mais que `LOCAL_LLM_TIMEOUT_S`,
sem que isso signifique falha). Solução: `generate_stream()` usa
`timeout=None` na conexão HTTP (mesmo padrão de `pull_model_streaming`),
e o `# MVP:` correspondente documenta que não há timeout de requisição
inteira para streaming — só o timeout implícito de inatividade do
`httpx`/TCP se a conexão travar de verdade. `LOCAL_LLM_TIMEOUT_S`/
`EXTERNAL_LLM_TIMEOUT_S` continuam valendo para a chamada não-streaming
de classificação.

## Mudanças no frontend

### `frontend/lib/api/chat.ts`

`sendChatMessage` muda de assinatura: em vez de `Promise<ChatMessageResponse>`,
recebe callbacks (`onConversationId`, `onTranscription`, `onStatus`,
`onToken`, `onDone`, `onError`) e retorna `Promise<void>`. Implementação:
`fetch` normal (POST, mesmo body de hoje), depois lê `response.body`
via `getReader()` + `TextDecoder`, faz parsing incremental de linhas
`event:`/`data:` separadas por linha em branco (parser SSE manual — não
tem por que trazer uma lib nova pra isso, é pouco código).

### `frontend/components/chat/ChatModal.tsx`

`submitMessage`/`submitAudio` mudam de `await sendChatMessage(...)` mais
`addMessage` no final, para: `addMessage` da bolha do usuário
imediatamente (como hoje) → `addMessage` de uma bolha do assistente vazia
(`text: ""`) → callbacks vão chamando `updateMessage` nela conforme os
eventos chegam (`status` vira um texto temporário tipo "🤖 Carregando
modelo local..."; o primeiro `token` substitui esse texto temporário em
vez de concatenar; `token`s seguintes concatenam; `done` anexa `metrics`
e os campos de domínio/backend_used à mesma mensagem). `error` funciona
como hoje (bolha de erro separada com "Tentar novamente").

## Testes

- Backend: `OllamaClient.generate_stream`/`is_model_ready` (mock via
  `httpx.MockTransport`, mesmo padrão de `test_ollama_client.py`),
  `OpenRouterClient.generate_stream` idem, `orchestrator.handle_message`
  reescrito para testar como async generator (iterar e coletar os eventos
  emitidos), `api/chat.py` testando o `StreamingResponse` via
  `TestClient` (ler o corpo da resposta como texto e fazer parse manual
  dos eventos SSE no teste, confirmando ordem/conteúdo).
- Frontend: `ChatModal.test.tsx` precisa de um mock de `fetch` que devolve
  um `ReadableStream` fake com os eventos SSE serializados — os testes
  existentes (envio de texto, erro com retry, áudio, fallback de
  transcrição vazia) continuam valendo, só a forma de mockar
  `sendChatMessage` muda de "resolve uma vez" para "chama os callbacks".

## Fora de escopo desta entrega

- Opção B (GET separado, reconexão, múltiplos ouvintes) — registrada como
  evolução futura acima, não implementar agora.
- Cancelamento de geração em andamento (usuário fecha o modal no meio de
  uma resposta) — o stream simplesmente é abandonado do lado do cliente;
  o backend continua gerando até o fim sem saber que ninguém está mais
  ouvindo (mesmo comportamento de hoje quando a aba fecha no meio de uma
  requisição síncrona, não é uma regressão).
- Streaming da transcrição de áudio (STT) em si — continua uma chamada
  síncrona única antes do stream começar.
