# Design — Características de Modelo (Multimodalidade) no Hover da Administração de Modelos (além do MVP)

> Spec resultante de sessão de brainstorming em 2026-10-03. Pedida
> explicitamente pelo usuário como melhoria da tela `/admin/modelos`. Esta
> funcionalidade **não faz parte do MVP original** — fica registrada aqui e
> no roadmap para não ser confundida com item do escopo original, mesmo
> padrão já usado para
> `docs/superpowers/specs/2026-09-16-local-model-manager-design.md` (que
> esta spec estende).

## 1. Objetivo

Hoje as duas seções de `/admin/modelos` (`OpenRouterModelCard.tsx` para o
modelo externo, `LocalModelsTable.tsx` para o modelo local Ollama) mostram
só listas fixas no código (`POPULAR_MODELS`/`FREE_MODELS`/
`POPULAR_LOCAL_PRESETS`) com descrição textual genérica escrita à mão, sem
nenhuma característica real do modelo e sem indicação de multimodalidade.
`PullModelForm.tsx` (baixar modelo local) aceita tags do Ollama ou do
Hugging Face (`hf.co/usuário/repo`) sem mostrar nada sobre o que será
baixado.

O usuário quer que, ao passar o mouse sobre qualquer caixa de modelo, apareça
um painel com as características principais do modelo — **sobretudo quais
modalidades de entrada/saída ele suporta** (não um badge binário
"multimodal sim/não", mas a lista explícita: texto, imagem, áudio,
arquivo...). Essas características devem ser buscadas numa fonte externa e
**salvas** (persistidas, não só cacheadas em memória), com um botão de
refresh manual para forçar nova busca quando o usuário quiser.

Fora do escopo desta entrega: criar uma busca/catálogo navegável (substituir
as listas fixas por uma busca real nos ~466 modelos do OpenRouter ou na
biblioteca do Ollama) — decisão explícita do usuário de manter as listas
fixas como estão e só enriquecer cada item já exibido com características
buscadas por tag.

## 2. Decisões de arquitetura

**Três fontes de dados, uma por proveniência da tag:**

1. **OpenRouter `/api/v1/models`** (pública, sem autenticação, verificada
   nesta sessão: 466 modelos). Usada para os cards de `OpenRouterModelCard`
   (`source="openrouter"`). Um único fetch traz todos os modelos — filtra
   pelo `id` (tag) pedido. Dá `architecture.input_modalities`/
   `output_modalities`, `context_length`, `pricing.prompt`/`completion`,
   `knowledge_cutoff`.
2. **Ollama local `/api/show`** (`POST http://localhost:11434/api/show`,
   `{"name": "<tag>"}`). Usada para modelos **já baixados** em
   `LocalModelsTable` (`source="ollama"`). Verificado nesta sessão contra a
   instância local (Ollama 0.30.6): devolve `capabilities: [str, ...]`
   (ex.: `"vision"`, `"tools"`, `"completion"`, `"embedding"`),
   `details.parameter_size`, `details.quantization_level`,
   `model_info["<family>.context_length"]`.
3. **Hugging Face Hub `/api/models/{repo}`** (pública, sem autenticação).
   Usada só quando a tag informada em `PullModelForm` segue o formato
   `hf.co/<usuário>/<repo>[:quant]` **e ainda não foi baixada** — é o único
   caso em que nem OpenRouter nem Ollama têm informação (`/api/show` só
   funciona pós-download). `source="huggingface"`. Dá `pipeline_tag`
   (ex.: `"image-text-to-text"` = multimodal texto+imagem,
   `"text-generation"` = só texto) e `tags`.

**Mapeamento de modalidade por fonte:**
- OpenRouter: usa `architecture.input_modalities`/`output_modalities`
  diretamente (já vêm como lista, ex.: `["text", "image", "file"]`).
- Ollama: `"vision" in capabilities` → `input_modalities` inclui `"image"`;
  caso contrário só `["text"]`. `output_modalities` sempre `["text"]` (Ollama
  não expõe geração de imagem/áudio nos modelos de chat suportados aqui).
- Hugging Face: tabela fixa `PIPELINE_TAG_MODALIDADES` mapeando
  `pipeline_tag` conhecidos (`image-text-to-text`, `visual-question-
  answering`, `text-generation`, `text2text-generation`, etc.) para
  `(input_modalities, output_modalities)`. `pipeline_tag` não mapeado →
  `input_modalities=["desconhecido"]` (nunca inventa modalidade).

**`is_multimodal` é um campo derivado, não a forma de exibição.** Calculado
como `len(set(input_modalities) - {"text"}) > 0`. Fica na resposta da API
para uso futuro (ex.: ordenar/filtrar), mas a UI sempre renderiza a lista
explícita de `input_modalities`/`output_modalities` como chips — nunca só um
badge "multimodal sim/não" (correção explícita do usuário durante o
brainstorming).

**Persistência em tabela nova do Postgres, com staleness de 7 dias e refresh
manual.** `model_characteristics` (migração `0016`): chave natural
`(source, tag)`. Ao pedir características: se existe linha com
`fetched_at` há menos de 7 dias, devolve direto do banco sem chamar a fonte
externa; senão busca na fonte e faz upsert. Um endpoint de refresh dedicado
ignora a staleness e força nova busca (pedido explícito do usuário — sem
isso, a única forma de atualizar seria esperar 7 dias ou mexer no banco à
mão). `raw_payload: JSON` guarda a resposta crua da fonte inteira, para a UI
evoluir sem precisar de coluna nova nem rebuscar dados já obtidos.

**Falha de rede/fonte indisponível nunca quebra o card.** Se a busca falhar
e não houver nenhuma linha em cache (nem stale) → API devolve `404` com
`detail`; o frontend mostra um texto discreto ("características
indisponíveis no momento") em vez de erro bloqueante. Se houver linha stale
em cache e a busca falhar → serve a stale silenciosamente (o usuário só
percebe se usar o refresh manual, que aí sim mostra o erro).

## 3. Backend

### 3.1. Tabela nova (`app/db/models.py`, migração `0016`)

```python
class ModelCharacteristics(Base):
    """Características de um modelo (multimodalidade, contexto, specs),
    buscadas em fontes externas (OpenRouter/Ollama/Hugging Face) e
    cacheadas — ver docs/superpowers/specs/2026-10-03-caracteristicas-
    modelo-hover-design.md. Staleness de 7 dias; refresh manual disponível
    via endpoint dedicado."""

    __tablename__ = "model_characteristics"
    __table_args__ = (UniqueConstraint("source", "tag", name="uq_model_characteristics_source_tag"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source: Mapped[str]  # "openrouter" | "ollama" | "huggingface"
    tag: Mapped[str]
    is_multimodal: Mapped[bool] = mapped_column(default=False)
    input_modalities: Mapped[list] = mapped_column(_JsonVariant, default=list)
    output_modalities: Mapped[list] = mapped_column(_JsonVariant, default=list)
    context_length: Mapped[int | None]
    parameter_size: Mapped[str | None]       # só Ollama
    quantization: Mapped[str | None]         # só Ollama
    pricing_prompt_per_1k: Mapped[float | None]      # só OpenRouter
    pricing_completion_per_1k: Mapped[float | None]  # só OpenRouter
    knowledge_cutoff: Mapped[str | None]     # só OpenRouter
    raw_payload: Mapped[dict] = mapped_column(_JsonVariant, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

### 3.2. Módulo novo `app/model_catalog/characteristics.py`

- `ModelSource = Literal["openrouter", "ollama", "huggingface"]`
- `STALENESS = timedelta(days=7)`
- `PIPELINE_TAG_MODALIDADES: dict[str, tuple[list[str], list[str]]]` — tabela
  fixa citada acima.
- `async def _fetch_openrouter(tag: str, http_client: httpx.AsyncClient) -> dict | None`
  — GET `https://openrouter.ai/api/v1/models` (cache em memória do processo
  da lista completa, TTL de 1h — 466 modelos não mudam a cada minuto, evita
  rebaixar a lista inteira a cada tag diferente pedida em sequência), acha
  por `id == tag`, mapeia campos. `None` se a tag não existir na lista.
- `async def _fetch_ollama(tag: str, ollama_client: OllamaClient) -> dict | None`
  — usa `OllamaClient.get_model_details(tag)` (novo método, §3.3). `None`
  se o Ollama devolver 404 (modelo não baixado).
- `async def _fetch_huggingface(tag: str, http_client: httpx.AsyncClient) -> dict | None`
  — só executa se `tag.startswith("hf.co/")`; extrai `repo` (remove
  prefixo `hf.co/` e sufixo `:quant` se houver), GET
  `https://huggingface.co/api/models/{repo}`. `None` se não for formato
  `hf.co/...` ou a API devolver 404.
- `async def get_or_fetch(session, source, tag, *, force_refresh=False, ollama_client=None, http_client=None) -> ModelCharacteristicsRow | None`
  — lookup por `(source, tag)`; linha fresca (não `force_refresh` e
  `fetched_at` dentro da staleness) → devolve direto. Senão chama o
  fetcher da fonte; sucesso → upsert e devolve; falha com linha stale
  existente → devolve a stale; falha sem linha nenhuma → `None`.

### 3.3. `app/router/ollama_client.py`

Novo método `async def get_model_details(self, name: str) -> dict | None` —
`POST {base_url}/api/show` com `{"name": name}`; `404`/erro → `None`; devolve
o JSON cru (o parsing fica em `_fetch_ollama`, que já conhece o formato
específico de característica que precisa extrair).

### 3.4. `app/api/model_catalog.py` (novo)

- `GET /api/admin/model-catalog/characteristics?source=...&tag=...` →
  `ModelCharacteristicsResponse`; `404` se `get_or_fetch` devolver `None`.
- `POST /api/admin/model-catalog/characteristics/refresh` — corpo
  `CharacteristicsRefreshRequest {source, tag}` → mesma resposta, com
  `force_refresh=True`; `404` nas mesmas condições.

### 3.5. Schemas (`app/models/model_catalog.py`, novo)

```python
ModelSource = Literal["openrouter", "ollama", "huggingface"]

class ModelCharacteristicsResponse(BaseModel):
    source: ModelSource
    tag: str
    is_multimodal: bool
    input_modalities: list[str]
    output_modalities: list[str]
    context_length: int | None
    parameter_size: str | None
    quantization: str | None
    pricing_prompt_per_1k: float | None
    pricing_completion_per_1k: float | None
    knowledge_cutoff: str | None
    fetched_at: datetime

class CharacteristicsRefreshRequest(BaseModel):
    source: ModelSource
    tag: str = Field(..., min_length=1)
```

### 3.6. Wiring (`app/main.py`)

- `app.state.model_catalog_http_client = httpx.AsyncClient()` — dedicado
  (mesmo padrão de `app.state.crawler_http_client`), usado pelos fetchers
  de OpenRouter e Hugging Face.
- `app.include_router(model_catalog_router)`.

## 4. Frontend

### 4.1. `components/ui/Tooltip.tsx` (estendido, não recriado)

- Novo prop opcional `trigger?: React.ReactNode` — quando presente, os
  handlers de hover/foco envolvem esse elemento em vez do botão "?" padrão
  (que continua sendo o default, preservando os 7 usos atuais sem
  mudança). `content` passa de `string` para `React.ReactNode` (strings
  continuam válidas, sem quebra).

### 4.2. `lib/types/modelCatalog.ts` / `lib/api/modelCatalog.ts` (novos)

Mesmo padrão de `lib/types/localModels.ts`/`lib/api/localModels.ts`:
`getModelCharacteristics(source, tag)`, `refreshModelCharacteristics(source, tag)`.

### 4.3. `lib/hooks/useModelCharacteristics.ts` (novo)

Hook `useModelCharacteristics(source, tag)` — Map em memória do módulo
(chave `${source}:${tag}`) para não re-buscar entre cards diferentes que já
carregaram a mesma tag na sessão da aba; estado `{data, loading, error}` +
`refresh()` (chama o endpoint de refresh, atualiza o cache e o estado).
Busca inicial dispara no mount do componente que usa o hook (não espera o
hover — com ~17 tags fixas nas duas telas, isso é 17 requisições leves no
carregamento da página, não um problema de escala).

### 4.4. `components/admin/ModelCharacteristicsPanel.tsx` (novo)

Componente de apresentação puro: recebe `{data, loading, error, onRefresh}`
e renderiza — chips de `input_modalities`/`output_modalities` (não-texto
destacado com cor, ex. imagem/áudio/vídeo em azul, texto em cinza neutro),
contexto formatado (`"128K tokens"`), campos extras condicionais por
`source` (preço e corte de conhecimento se OpenRouter; parâmetros e
quantização se Ollama), horário relativo de `fetched_at`, e um ícone de
refresh (chama `onRefresh`, mostra spinner enquanto `loading`). Estado sem
dado e sem erro (ainda carregando pela 1ª vez) → skeleton leve. Sem dado e
com erro → texto discreto "características indisponíveis no momento".

### 4.5. Integração nos componentes existentes

- `OpenRouterModelCard.tsx`: cada card de `POPULAR_MODELS`/`FREE_MODELS`/
  `historyModels` passa a envolver o card inteiro com `<Tooltip trigger={...}>`
  usando `useModelCharacteristics("openrouter", model.tag)`.
- `LocalModelsTable.tsx`: mesma integração nos cards de modelos instalados
  (`source="ollama"`, `tag=modelo.name`) e nos presets
  (`POPULAR_LOCAL_PRESETS`, mesmo `source="ollama"` — se ainda não baixado,
  a API devolve `404` e o painel mostra "características indisponíveis",
  já que presets usam tags da biblioteca Ollama, não `hf.co/...`).
- `PullModelForm.tsx`: abaixo do campo de texto, quando o valor digitado
  bate com `/^hf\.co\//i`, mostra o mesmo `ModelCharacteristicsPanel` com
  `source="huggingface"`, busca disparada com debounce de 500ms após parar
  de digitar (evita martelar a API do Hugging Face a cada tecla). Tags que
  não seguem esse formato não mostram painel nenhum aqui (Ollama só sabe
  depois de baixado, não há pré-visualização possível).

## 5. Testes

**Backend:**
- `tests/test_model_catalog_characteristics.py` — `_fetch_openrouter`/
  `_fetch_ollama`/`_fetch_huggingface` com `httpx.MockTransport`; mapeamento
  de `capabilities`→modalidades (Ollama) e `pipeline_tag`→modalidades (HF,
  incluindo um `pipeline_tag` não mapeado → `"desconhecido"`);
  `get_or_fetch`: cache fresco não rechama a fonte, cache stale rechama e
  faz upsert, `force_refresh=True` ignora staleness, falha com stale
  existente devolve a stale, falha sem cache devolve `None`.
- `tests/test_model_catalog_api.py` — `TestClient`: 200 com dado novo, 200
  servindo cache, 404 quando a fonte não tem a tag e não há cache, endpoint
  de refresh força nova busca.
- `tests/test_ollama_client.py`: novo teste para `get_model_details`.

**Frontend:**
- `tests/hooks/useModelCharacteristics.test.ts` — cache entre chamadas,
  `refresh()` atualiza estado e cache.
- `tests/components/ModelCharacteristicsPanel.test.tsx` — chips corretos
  por modalidade, estado de loading/erro, clique no refresh chama callback.
- Atualiza `OpenRouterModelCard.test.tsx`/`LocalModelsTable.test.tsx`:
  hover/mount dispara a busca e mostra o painel.
- Atualiza `PullModelForm.test.tsx`: digitar `hf.co/...` (com fake timers
  pro debounce) mostra o painel; tag sem esse formato não mostra nada.

## 6. Registro em `docs/ARCHITECTURE.md` e `docs/ROADMAP.md`

Nota curta em `docs/ARCHITECTURE.md` §5 (mesmo padrão das entregas fora do
MVP) e entrada nova em `docs/ROADMAP.md` sob "Extra fora do MVP".

## 7. Não-objetivos explícitos

- Sem busca/catálogo navegável — as listas fixas (`POPULAR_MODELS`/
  `FREE_MODELS`/`POPULAR_LOCAL_PRESETS`) continuam como estão, só ganham o
  painel de características.
- Sem busca por palavra-chave na biblioteca do Hugging Face — só consulta
  direta por `hf.co/<repo>` exato.
- Sem geração de imagem/áudio como `output_modalities` dos modelos Ollama
  (os modelos de chat suportados aqui não geram mídia, só texto).
- Sem invalidação automática do cache em memória da lista do OpenRouter
  entre deploys (TTL de 1h é suficiente; reinicia junto do processo).
- Sem autenticação nova além da já aceita para as demais páginas
  `/admin/*`.
