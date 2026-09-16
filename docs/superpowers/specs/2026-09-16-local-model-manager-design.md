# Design — Gerenciador de Modelos Locais (Ollama) (além do MVP)

> Spec resultante de sessão de brainstorming em 2026-09-16. Pedida
> explicitamente pelo usuário como ferramenta administrativa extra, em
> paralelo à Fase 10 do roadmap (que continua sendo o processo formal de
> escolha do `LOCAL_MODEL_NAME` de produção, via benchmark offline contra o
> sistema completo — ver `docs/ROADMAP.md`, Fase 10, e a nota da Fase 1 que
> explica por que essa escolha foi deliberadamente adiada). Esta
> funcionalidade **não faz parte do MVP original** — fica registrada aqui e
> no roadmap para não ser confundida com item do escopo original nem
> esquecida na revisão final (Fase 11), mesmo padrão já usado para os
> perfis de collection do RAG
> (`docs/superpowers/specs/2026-09-15-rag-collections-config-design.md`).

## 1. Objetivo

Hoje o modelo local de chat (`LOCAL_MODEL_NAME`) é fixo por variável de
ambiente, lido uma vez na inicialização do backend
(`app.state.local_client = OllamaClient(model=settings.local_model_name, ...)`).
O usuário quer uma tela administrativa para: (a) ver quais modelos já estão
baixados no Ollama local, (b) trocar qual deles o chat usa **em runtime**,
sem reiniciar o backend, e (c) baixar um modelo novo — tanto da biblioteca
padrão do Ollama quanto um GGUF hospedado no Hugging Face (`ollama pull
hf.co/<usuário>/<repo>[:quant]`, suportado nativamente pelo Ollama desde
2024, sem precisar de um motor de inferência adicional) — sem que o
download trave o backend, com progresso real acompanhado pelo frontend.

Motivação explícita: testar candidatos a modelo local manualmente (inclusive
os 9 da Fase 10, e outros do Hugging Face) sem esperar o processo formal de
avaliação terminar.

Fora do escopo desta entrega: qualquer mudança no processo da Fase 10
(continua sendo o benchmark offline formal que decide o `LOCAL_MODEL_NAME`
de produção); gerenciamento de modelos que não sejam de chat (embedding,
STT) — isso já existe separadamente (perfis de collection do RAG cobrem
embedding); remoção/exclusão de modelos baixados; execução de modelos fora
do Ollama (transformers/vLLM direto) — decisão explícita do usuário de ficar
só no Ollama + GGUF do HF.

## 2. Decisões de arquitetura

**Modelo ativo só em memória.** A seleção de "qual modelo o chat usa agora"
vive só em `app.state`/na instância de `OllamaClient` (um atributo mutável
`model`, hoje fixo no construtor) — sem tabela nova no Postgres. Reseta para
o `LOCAL_MODEL_NAME` do `.env` a cada restart do backend. `# MVP: escolha
manual de teste, não a escolha de produção (essa continua vindo do `.env`,
decidida ao final pela Fase 10) — sem necessidade de sobreviver a um
restart`.

**Download em background, progresso real via polling (não streaming HTTP
direto ao navegador).** Disparar `POST /api/pull` do Ollama e devolver a
resposta HTTP diretamente ao navegador manteria uma conexão aberta por
todo o tempo do download (minutos, para modelos grandes), arriscando
timeout de proxy/browser. Em vez disso: o backend consome o streaming NDJSON
do Ollama numa tarefa assíncrona em background (`asyncio.create_task`,
iniciada e esquecida pela requisição HTTP que a disparou, que retorna
`202 Accepted` na hora) e guarda o progresso mais recente num dicionário em
memória (`app.state.model_pull_progress: dict[str, PullProgress]`, chaveado
pelo nome do modelo). O frontend consulta um endpoint de status a cada ~1s
enquanto o download está em andamento, e para de consultar quando o status
vira `"done"` ou `"error"`.

**Percentual é por camada, não agregado no modelo inteiro.** O Ollama baixa
um modelo em várias camadas (blobs) sequenciais, cada uma com seu próprio
`completed`/`total` em bytes na linha de progresso NDJSON; ele não expõe um
total agregado de todas as camadas antecipadamente de forma simples. `# MVP:
o percentual mostrado é o da camada sendo baixada no momento (reinicia a
cada nova camada), não um progresso suave de 0-100% do modelo inteiro —
agregar isso exigiria somar o tamanho de todas as camadas do manifesto
antes de começar, complexidade desnecessária para uma ferramenta
administrativa de teste`.

**Formato exato da API do Ollama, verificado nesta sessão contra a
instância local rodando (versão 0.30.6, `GET /api/version` respondendo em
`localhost:11434`):** `GET /api/tags` devolve
`{"models": [{"name": str, "model": str, "modified_at": str (ISO),
"size": int (bytes), "digest": str, "details": {...}, "capabilities":
[str, ...]}]}` — confirmado empiricamente. O formato de `POST /api/pull`
(`{"model": "<nome>", "stream": true}`, respondendo um stream de linhas
NDJSON como `{"status": "pulling manifest"}`,
`{"status": "pulling <digest>", "digest": "sha256:...", "total": int,
"completed": int}`, terminando em `{"status": "success"}`, ou
`{"error": "<mensagem>"}` em caso de falha) é o formato estável e
documentado publicamente da API do Ollama para essa versão, mas **não foi
exercitado contra o servidor real nesta sessão de brainstorming** (evitado
de propósito, para não disparar um download real de vários GB sem
necessidade) — a Task de implementação que mexe nisso deve confirmar o
formato exato rodando um `curl -N -X POST http://localhost:11434/api/pull
-d '{"model": "<algum modelo pequeno já baixado>", "stream": true}'`
contra a instância local antes de escrever o parser, mesmo espírito de
verificar bibliotecas externas antes de codar contra elas.

## 3. Backend

### 3.1. `app/router/ollama_client.py`

- `OllamaClient.model` vira uma property com getter e setter (em vez de só
  `self._model` fixado no `__init__`), para permitir troca em runtime sem
  recriar a instância (que compartilha o `httpx.AsyncClient` reaproveitado).
- Novo método `async def list_local_models(self) -> list[LocalModel]` —
  `GET {base_url}/api/tags`, mapeia cada item para um dataclass/NamedTuple
  simples `LocalModel(name: str, size_bytes: int, modified_at: str)`
  (mantém só os campos que a UI usa; `digest`/`details`/`capabilities` não
  são expostos nesta entrega).
- Novo método `async def pull_model_streaming(self, name: str) ->
  AsyncIterator[PullProgressLine]` — `POST {base_url}/api/pull` com
  `{"model": name, "stream": True}`, usando
  `self._client.stream("POST", ...)` do httpx para consumir o corpo linha a
  linha (`response.aiter_lines()`), parseando cada linha JSON em
  `PullProgressLine(status: str, digest: str | None, total: int | None,
  completed: int | None, error: str | None)`. Erros HTTP (`response.
  raise_for_status()`) e uma linha `{"error": ...}` no meio do stream são
  ambos possíveis formas de falha — o consumidor (§3.2) trata as duas.

### 3.2. `app/api/local_models.py` (novo)

- `GET /api/admin/local-models` → `LocalModelsListResponse` (
  `{models: [LocalModelResponse], active_model: str}`) — chama
  `list_local_models()` e lê `local_client.model` para marcar qual está
  ativo (campo `is_active: bool` por item, calculado comparando o nome).
- `POST /api/admin/local-models/activate` — corpo `{"name": str}`; valida
  que `name` está entre os modelos de `list_local_models()` (404 se não);
  se estiver, `local_client.model = name`; `204`.
- `POST /api/admin/local-models/pull` — corpo `{"name": str}`. Se já existe
  uma entrada `"pulling"` para esse nome em
  `app.state.model_pull_progress`, não inicia uma segunda tarefa (evita
  pull duplicado concorrente do mesmo modelo) — só devolve `202` apontando
  para o progresso já em andamento. Caso contrário, grava
  `{"status": "pulling", "percent": None, "detail": "iniciando..."}` nesse
  dicionário e dispara `asyncio.create_task(_consumir_pull(name, ...))`
  (função interna que itera `pull_model_streaming`, atualizando a entrada
  do dicionário a cada linha recebida — `percent = completed/total*100` 
  quando ambos presentes na linha, senão mantém o último percent conhecido;
  ao terminar com sucesso, `{"status": "done", ...}`; ao terminar com erro
  — HTTP ou linha `{"error": ...}` — `{"status": "error", "detail": 
  <mensagem>}`). Devolve `202` com `{"name": name}` imediatamente, sem
  esperar a tarefa.
- `GET /api/admin/local-models/pull/{name}/status` → devolve a entrada
  atual de `app.state.model_pull_progress[name]` como
  `PullStatusResponse`; `404` se esse nome nunca teve um pull iniciado
  nesta execução do processo.

### 3.3. Schemas (`app/models/local_models.py`, novo)

```python
class LocalModelResponse(BaseModel):
    name: str
    size_bytes: int
    modified_at: str
    is_active: bool

class LocalModelsListResponse(BaseModel):
    models: list[LocalModelResponse]
    active_model: str

class ActivateModelRequest(BaseModel):
    name: str = Field(..., min_length=1)

class PullModelRequest(BaseModel):
    name: str = Field(..., min_length=1)

class PullStatusResponse(BaseModel):
    status: Literal["pulling", "done", "error"]
    percent: float | None = None
    detail: str | None = None
```

### 3.4. Wiring (`app/main.py`)

- `app.state.model_pull_progress: dict[str, dict] = {}` inicializado junto
  dos outros `app.state.*`.
- `app.include_router(local_models_router)`.

## 4. Frontend

Nova página `frontend/app/admin/modelos/page.tsx`, fora do menu principal,
com o mesmo link discreto no rodapé (`components/layout/Footer.tsx`) já
usado para `/admin/ingestao`.

- `components/admin/LocalModelsTable.tsx` — tabela (nome, tamanho
  formatado em GB, badge "Ativo") + botão "Ativar" por linha (oculto na
  linha já ativa).
- `components/admin/PullModelForm.tsx` — campo de texto (placeholder
  `"ex.: llama3.1:8b ou hf.co/usuario/repo"`) + botão "Baixar". Ao
  submeter: `POST .../pull`, depois inicia um polling (`setInterval` a
  cada ~1s) em `GET .../pull/{name}/status`; mostra uma barra de progresso
  (`percent` quando disponível, senão um indicador indeterminado) + o
  `detail` textual da linha mais recente; para o polling e mostra
  sucesso/erro via toast quando `status` vira `"done"`/`"error"`, e dispara
  um callback `onPulled` para a página recarregar a lista de modelos.

`frontend/lib/types/localModels.ts` e `frontend/lib/api/localModels.ts`
seguem exatamente o padrão já estabelecido em `lib/types/rag.ts`/
`lib/api/rag.ts` (mesmo estilo de `RagApiError`, mesma estrutura de
funções fetch).

## 5. Testes

- `OllamaClient.list_local_models`/`pull_model_streaming`: `httpx.
  MockTransport` (mesmo padrão de `tests/test_ollama_client.py`), incluindo
  um teste de streaming com múltiplas linhas NDJSON simuladas e um teste de
  linha de erro no meio do stream.
- `app/api/local_models.py`: `TestClient` com `local_client` injetado via
  `Depends` sobrescrito (mesmo padrão dos endpoints do RAG) — ativar
  modelo inexistente → 404; pull duplicado não cria segunda tarefa; status
  antes de qualquer pull → 404.
- Frontend: `PullModelForm` com `vi.useFakeTimers()` para simular o
  polling avançando por etapas de progresso até "done", e um caminho de
  erro.

## 6. Registro em `docs/ARCHITECTURE.md` e `docs/ROADMAP.md`

Nota curta em `docs/ARCHITECTURE.md` §5 (mesmo padrão das entregas
anteriores fora do MVP) e uma entrada nova em `docs/ROADMAP.md` sob "Extra
fora do MVP", deixando explícito que isso não substitui nem antecipa a
Fase 10.

## 7. Não-objetivos explícitos

- Não substitui nem altera o processo da Fase 10 (benchmark offline formal).
- Sem persistência do modelo ativo entre restarts do backend.
- Sem exclusão/remoção de modelos baixados pela UI.
- Sem execução de modelos fora do Ollama (transformers/vLLM diretos).
- Sem barra de progresso agregada 0-100% do modelo inteiro — só da camada
  em download no momento.
- Sem autenticação nova além da já aceita para as demais páginas
  `/admin/*` (mesma limitação de `/admin/ingestao`).
- Sem cancelamento de um download em andamento.
