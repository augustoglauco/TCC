# Ledger de Uso de IA — Item D (Origem Admin) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Conectar os 4 pontos de uso de IA do admin (geração de gráficos dinâmicos e extração de catálogo por texto/visão) à função `registrar_uso_ia` (item A), migrando a extração por visão para fora da tabela antiga `IngestionCostEvent` sem dual-write.

**Architecture:** Mesmo padrão dos itens A/B: `spawn_background_task(registrar_uso_ia(...))` logo após cada chamada de IA retornar com sucesso, nunca bloqueando o fluxo. Dois pontos exigem um parâmetro novo `ambiente: str` obrigatório (geração de gráfico e extração por visão) porque o cliente usado varia em runtime; um ponto usa `ambiente="interno"` como constante (extração de texto, sempre local).

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.0 async, pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-10-08-ledger-uso-ia-item-d-origem-admin-design.md`

## Global Constraints

- `origem` é sempre a constante `"admin"` nos 4 pontos deste item.
- `referencia_id` é `None` nos pontos #1 (geração de gráfico) e #2 (extração de texto); é `source_identifier` (parâmetro já existente, reaproveitado) nos pontos #3a/#3b (extração por visão).
- Toda chamada a `registrar_uso_ia` é disparada via `spawn_background_task(registrar_uso_ia(...))` — nunca `await` direto.
- `modelo` nunca pode ser `None`: sempre `<fonte> or "desconhecido"`.
- `tokens_entrada`/`tokens_saida`/`custo_usd` usam os valores reais capturados; `None` quando o dado genuinamente não existe — nunca fabricar uma estimativa (a lógica de estimar tokens por tamanho de texto, hoje presente em `extract_page_products_vision`, é removida, não portada).
- As chamadas a `record_ingestion_cost`/`IngestionCostEvent` dentro de `extract_page_products_vision` são **removidas**, substituídas por `registrar_uso_ia` — sem dual-write. Isso é intencional (decisão do usuário, 2026-10-08), não um descuido a "corrigir" na revisão.
- Nenhuma instrumentação nova pode propagar exceção: `registrar_uso_ia` já nunca lança (contrato do item A).

---

### Task 1: Geração de gráficos dinâmicos (ponto #1)

**Files:**
- Modify: `backend/src/app/services/analytics_agent.py:1-23` (imports), `:112-163` (`_generate_sql_with_llm`), `:166-171` (assinatura de `process_dynamic_chart_request`), `:219-221` (call site interno)
- Modify: `backend/src/app/router/orchestrator.py:1170` (cálculo de `analytics_llm`), `:1179-1196` (os dois call sites de `process_dynamic_chart_request`)
- Test: `backend/tests/test_analytics_agent.py` (7 call sites existentes de `process_dynamic_chart_request` ganham o parâmetro novo; 1 teste novo)

**Interfaces:**
- Consumes: `registrar_uso_ia`/`spawn_background_task` (assinaturas já existentes, ver Global Constraints do plano de item B para a assinatura completa de `registrar_uso_ia` — não muda neste item).
- Produces: `_generate_sql_with_llm(llm_client, prompt, session, ambiente: str) -> tuple[dict | None, int | None, int | None]` (parâmetro novo `ambiente`, posição 4, sem default). `process_dynamic_chart_request(session, prompt, user_email, llm_client=None, *, ambiente: str) -> tuple[AdminChart | None, str, int | None, int | None]` (parâmetro novo `ambiente`, obrigatório, keyword-only).

- [ ] **Step 1: Escrever o teste que falha — geração de gráfico registra uso de IA com custo real**

Em `backend/tests/test_analytics_agent.py`, estenda `_FakeChunk` (linhas 14-22) para aceitar os campos novos, com defaults que preservam o comportamento dos testes já existentes:

```python
class _FakeChunk:
    def __init__(
        self,
        text: str,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        cost_prompt_usd: float | None = None,
        cost_completion_usd: float | None = None,
        estimated_cost_usd: float | None = None,
        model_name: str | None = None,
    ) -> None:
        self.text = text
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.cost_prompt_usd = cost_prompt_usd
        self.cost_completion_usd = cost_completion_usd
        self.estimated_cost_usd = estimated_cost_usd
        self.model_name = model_name
```

Adicione uma nova classe de fake client, ao lado de `_FakeLLMClientSqlComTokens` (linhas 43-56):

```python
class _FakeLLMClientSqlComCustoReal:
    """Simula um LLM externo que reporta tokens, modelo e custo real no
    chunk final — usado para provar que a instrumentação nova captura
    custo de verdade, ao contrário do RouterDecision antigo que hardcoda
    cost_*=0.0 independente do backend escolhido."""

    async def generate_stream(self, prompt: str):
        payload = {
            "sql": "SELECT categoria, COUNT(*) as total FROM produtos GROUP BY categoria",
            "titulo": "Produtos por Categoria",
            "x_key": "categoria",
            "y_keys": ["total"],
        }
        yield _FakeChunk(json.dumps(payload))
        yield _FakeChunk(
            "",
            prompt_tokens=300,
            completion_tokens=50,
            cost_prompt_usd=0.0009,
            cost_completion_usd=0.0003,
            estimated_cost_usd=0.0012,
            model_name="openai/gpt-4o-mini",
        )
```

Adicione o teste (perto de `test_process_dynamic_chart_request_sql_dinamico_retorna_tokens_usados`):

```python
@pytest.mark.asyncio
async def test_process_dynamic_chart_request_externo_registra_uso_ia(db_session, monkeypatch):
    import app.services.analytics_agent as analytics_agent_module

    captured: dict = {}

    async def fake_registrar_uso_ia(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(analytics_agent_module, "registrar_uso_ia", fake_registrar_uso_ia)

    p1 = Produto(
        nome="Gerador X", descricao="Gerador", preco=Decimal("5000.00"), categoria="Geradores"
    )
    db_session.add(p1)
    await db_session.commit()

    llm_client = _FakeLLMClientSqlComCustoReal()

    await process_dynamic_chart_request(
        session=db_session,
        prompt="gere gráfico de produtos por categoria",
        user_email="admin@teste.com",
        llm_client=llm_client,
        ambiente="externo",
    )
    await asyncio.sleep(0)

    assert captured == {
        "origem": "admin",
        "ambiente": "externo",
        "modelo": "openai/gpt-4o-mini",
        "operacao": "geracao_grafico_dinamico",
        "tokens_entrada": 300,
        "tokens_saida": 50,
        "custo_usd": 0.0012,
        "referencia_id": None,
        "session": None,
        "session_factory": None,
        "commit": False,
    }
```

Adicione `import asyncio` no topo do arquivo se ainda não estiver.

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `uv run python -m pytest tests/test_analytics_agent.py -k registra_uso_ia -v`
Expected: FAIL — `TypeError: process_dynamic_chart_request() got an unexpected keyword argument 'ambiente'`.

- [ ] **Step 3: Instrumentar `_generate_sql_with_llm`**

No topo de `backend/src/app/services/analytics_agent.py`, depois dos imports existentes (linha 21, `from app.services.safe_sql import (...)`), adicione:

```python
from app.background_tasks import spawn_background_task
from app.services.ai_usage import registrar_uso_ia
```

Substitua `_generate_sql_with_llm` (linhas 112-163) por:

```python
async def _generate_sql_with_llm(
    llm_client: Any, prompt: str, session: AsyncSession, ambiente: str
) -> tuple[dict[str, Any] | None, int | None, int | None]:
    """Solicita ao LLM que gere a consulta Text-to-SQL e a especificação do
    gráfico. Devolve também `prompt_tokens`/`completion_tokens` usados pela
    chamada (achado de 2026-10-05: eram descartados, então essas chamadas ao
    modelo local nunca contavam em Métricas → Tokens Internos).

    `ambiente` ("interno"/"externo") é obrigatório porque o chamador já
    sabe qual cliente resolveu (`analytics_llm = local_client if
    local_client is not None else external_client` em
    `app.router.orchestrator`) — esta função não tem como inferir sozinha
    qual objeto recebeu."""
    if not llm_client or not hasattr(llm_client, "generate_stream"):
        return None, None, None

    schema_prompt = await get_catalog_schema_prompt(session)
    system_instruction = f"""Você é um analista de dados especialista em PostgreSQL e visualizações de dados.
O usuário solicitou um gráfico: "{prompt}".

{schema_prompt}

Responda OBRIGATORIAMENTE em formato JSON válido contendo:
{{
  "sql": "sua consulta SELECT otimizada aqui",
  "titulo": "Título claro do gráfico",
  "descricao": "Breve descrição dos dados",
  "tipo_grafico": "bar" ou "line" ou "pie" ou "donut" ou "area",
  "x_key": "nome da coluna no eixo X",
  "y_keys": ["nome da coluna métrica no eixo Y"],
  "format": "number" ou "currency" ou "percent",
  "labels": {{ "coluna_y": "Rótulo Amigável" }},
  "explicacao": "Uma frase resumindo os dados apresentados."
}}
NÃO inclua nada fora do bloco JSON.
"""
    try:
        raw_text = ""
        prompt_tokens: int | None = None
        completion_tokens: int | None = None
        cost_prompt_usd: float | None = None
        cost_completion_usd: float | None = None
        estimated_cost_usd: float | None = None
        model_name: str | None = None
        async for chunk in llm_client.generate_stream(system_instruction):
            if chunk.text:
                raw_text += chunk.text
            # Mesmo padrão do stream principal (orchestrator.py): tokens só
            # vêm populados no chunk final.
            if getattr(chunk, "prompt_tokens", None) is not None:
                prompt_tokens = chunk.prompt_tokens
            if getattr(chunk, "completion_tokens", None) is not None:
                completion_tokens = chunk.completion_tokens
            if getattr(chunk, "cost_prompt_usd", None) is not None:
                cost_prompt_usd = chunk.cost_prompt_usd
            if getattr(chunk, "cost_completion_usd", None) is not None:
                cost_completion_usd = chunk.cost_completion_usd
            if getattr(chunk, "estimated_cost_usd", None) is not None:
                estimated_cost_usd = chunk.estimated_cost_usd
            if getattr(chunk, "model_name", None) is not None:
                model_name = chunk.model_name

        spawn_background_task(
            registrar_uso_ia(
                origem="admin",
                ambiente=ambiente,
                modelo=model_name or "desconhecido",
                operacao="geracao_grafico_dinamico",
                tokens_entrada=prompt_tokens,
                tokens_saida=completion_tokens,
                custo_usd=estimated_cost_usd,
            )
        )

        # Extrai bloco JSON
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if match:
            return json.loads(match.group(0)), prompt_tokens, completion_tokens
    except Exception as exc:
        logger.warning("falha_llm_text_to_sql", extra={"erro": str(exc)})

    return None, None, None
```

(`cost_prompt_usd`/`cost_completion_usd` ficam calculados mas não usados fora desta função — mantidos só porque fazem parte do mesmo padrão de extração dos outros campos; não precisa removê-los, mas também não precisa propagá-los a mais lugar nenhum.)

- [ ] **Step 4: Atualizar a assinatura de `process_dynamic_chart_request` e repassar `ambiente`**

Substitua a assinatura e a chamada interna (linhas 166-171 e 219-221) — o resto do corpo da função (linhas 172-296) **não muda**:

```python
async def process_dynamic_chart_request(
    session: AsyncSession,
    prompt: str,
    user_email: str,
    llm_client: Any = None,
    *,
    ambiente: str,
) -> tuple[AdminChart | None, str, int | None, int | None]:
```

E, na chamada interna (linha ~219):

```python
    llm_spec, prompt_tokens, completion_tokens = await _generate_sql_with_llm(
        llm_client, prompt, session, ambiente
    )
```

- [ ] **Step 5: Atualizar os 7 call sites existentes em `test_analytics_agent.py`**

Run: `grep -n "process_dynamic_chart_request(" tests/test_analytics_agent.py`

Em cada uma das 7 ocorrências, adicione `ambiente="interno"` à lista de argumentos nomeados (todos os testes existentes simulam um cliente local ou `llm_client=None` — `"interno"` é o valor correto para todos; nenhum deles testa o caminho externo, que é coberto pelo teste novo do Step 1).

- [ ] **Step 6: Rodar e confirmar que os testes do arquivo passam**

Run: `uv run python -m pytest tests/test_analytics_agent.py -v`
Expected: PASS em todos (os 7 antigos + o novo do Step 1).

- [ ] **Step 7: Instrumentar o call site em `orchestrator.py`**

Na linha 1170 de `backend/src/app/router/orchestrator.py` (onde `analytics_llm` já é calculado), adicione o cálculo de `ambiente` ao lado:

```python
                analytics_llm = local_client if local_client is not None else external_client
                ambiente_grafico = "interno" if analytics_llm is local_client else "externo"
```

Nos dois call sites de `process_dynamic_chart_request` (linhas ~1179-1184 e ~1191-1196), adicione `ambiente=ambiente_grafico`:

```python
                        (
                            chart,
                            explicacao,
                            chart_prompt_tokens,
                            chart_completion_tokens,
                        ) = await process_dynamic_chart_request(
                            session=session,
                            prompt=message,
                            user_email=user_email or "admin",
                            llm_client=analytics_llm,
                            ambiente=ambiente_grafico,
                        )
```

(Aplique a mesma adição de `ambiente=ambiente_grafico` ao segundo call site, que usa `session=session_ctx`.)

- [ ] **Step 8: Verificar e corrigir testes de `orchestrator.py` que exercitam o fluxo de gráfico**

Run: `grep -n "process_dynamic_chart_request\|gerar.*grafico\|chart" tests/test_orchestrator.py tests/test_chat_chart_card.py | grep -i "dynamic\|process_dynamic"`

Se algum teste mockar `process_dynamic_chart_request` diretamente (via `monkeypatch`/`patch`), confirme que o mock aceita `ambiente` como kwarg (a maioria dos mocks em Python aceita kwargs extras sem problema a menos que use `spec=`/`autospec=True` com a assinatura antiga — nesse caso, adicione o parâmetro ao mock). Rode a suíte completa desses dois arquivos:

Run: `uv run python -m pytest tests/test_orchestrator.py tests/test_chat_chart_card.py -v`
Expected: PASS em todos.

- [ ] **Step 9: Commit**

```bash
git add backend/src/app/services/analytics_agent.py backend/src/app/router/orchestrator.py backend/tests/test_analytics_agent.py
git commit -m "feat(telemetria): instrumenta geração de gráficos dinâmicos no ledger de uso de IA (item D, ponto 1)"
```

---

### Task 2: Extração de catálogo por texto (ponto #2)

**Files:**
- Modify: `backend/src/app/catalog_extractor/extractor.py:1-26` (imports), `:177-184` (`extract_page_products_local`)
- Test: `backend/tests/test_catalog_extractor.py`

**Interfaces:**
- Consumes: `registrar_uso_ia`/`spawn_background_task`.
- Produces: nenhuma interface nova — `extract_page_products_local` mantém a assinatura exata (`texto, local_client, model_name=None`).

- [ ] **Step 1: Escrever o teste que falha — extração de texto registra uso de IA**

Em `backend/tests/test_catalog_extractor.py`, adicione (perto de `test_extract_page_products_local_retorna_produtos`):

```python
@pytest.mark.asyncio
async def test_extract_page_products_local_registra_uso_ia(monkeypatch):
    import app.catalog_extractor.extractor as extractor_module

    captured: dict = {}

    async def fake_registrar_uso_ia(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(extractor_module, "registrar_uso_ia", fake_registrar_uso_ia)

    local_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.response = "[]"
    mock_resp.text = mock_resp.response
    mock_resp.model_name = "gemma4:12b-it-q4_K_M"
    mock_resp.prompt_tokens = 450
    mock_resp.completion_tokens = 30
    mock_resp.estimated_cost_usd = 0.0
    local_client.generate = AsyncMock(return_value=mock_resp)

    await extract_page_products_local("texto de teste da página", local_client)
    await asyncio.sleep(0)

    assert captured == {
        "origem": "admin",
        "ambiente": "interno",
        "modelo": "gemma4:12b-it-q4_K_M",
        "operacao": "extracao_catalogo_texto_local",
        "tokens_entrada": 450,
        "tokens_saida": 30,
        "custo_usd": 0.0,
        "referencia_id": None,
        "session": None,
        "session_factory": None,
        "commit": False,
    }
```

Adicione `import asyncio` no topo do arquivo se ainda não estiver (verifique antes de duplicar).

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `uv run python -m pytest tests/test_catalog_extractor.py -k registra_uso_ia -v`
Expected: FAIL — `captured == {}`.

- [ ] **Step 3: Instrumentar `extract_page_products_local`**

No topo de `backend/src/app/catalog_extractor/extractor.py`, depois dos imports existentes de `app.*` (linhas 24-26), adicione:

```python
from app.background_tasks import spawn_background_task
from app.services.ai_usage import registrar_uso_ia
```

Substitua `extract_page_products_local` (linhas 177-184) por:

```python
async def extract_page_products_local(
    texto: str, local_client: Any, model_name: str | None = None
) -> list[dict[str, Any]]:
    prompt = LOCAL_EXTRACTION_PROMPT.replace("{texto}", texto)
    res = await local_client.generate(prompt)
    spawn_background_task(
        registrar_uso_ia(
            origem="admin",
            ambiente="interno",
            modelo=getattr(res, "model_name", None) or "desconhecido",
            operacao="extracao_catalogo_texto_local",
            tokens_entrada=getattr(res, "prompt_tokens", None),
            tokens_saida=getattr(res, "completion_tokens", None),
            custo_usd=getattr(res, "estimated_cost_usd", None),
        )
    )
    raw_response = getattr(res, "response", getattr(res, "text", str(res)))
    return _parse_products_json(raw_response)
```

(O parâmetro `model_name: str | None = None` da assinatura permanece sem uso no corpo — já estava assim antes desta mudança, fora do escopo deste item limpar.)

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `uv run python -m pytest tests/test_catalog_extractor.py -v`
Expected: PASS em todos (incluindo `test_extract_page_products_local_retorna_produtos`, que não muda de comportamento).

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/catalog_extractor/extractor.py backend/tests/test_catalog_extractor.py
git commit -m "feat(telemetria): instrumenta extração de catálogo por texto local no ledger de uso de IA (item D, ponto 2)"
```

---

### Task 3: Extração de catálogo por visão (pontos #3a, #3b)

**Files:**
- Modify: `backend/src/app/catalog_extractor/extractor.py:186-244` (`extract_page_products_vision`), `:470-502` (branch PDF), `:592-611` (branch imagem avulsa)
- Test: `backend/tests/test_catalog_extractor.py`

**Interfaces:**
- Consumes: `registrar_uso_ia`/`spawn_background_task` (já importados pela Task 2).
- Produces: `extract_page_products_vision(image_bytes, vision_client, prompt=None, source_identifier=None, session=None, session_factory=None, *, ambiente: str) -> list[dict[str, Any]]` — ganha o parâmetro keyword-only obrigatório `ambiente`. Os parâmetros `session`/`session_factory` deixam de ser usados internamente (eram só para `record_ingestion_cost`) mas **permanecem na assinatura** para não quebrar os 4 call sites existentes que já os passam — removê-los é escopo além do necessário aqui.

- [ ] **Step 1: Escrever o teste que falha — visão interna (local) registra uso de IA**

Em `backend/tests/test_catalog_extractor.py`, substitua `test_extract_page_products_vision_retorna_produtos` (linhas 30-40) por duas versões — uma para cada ambiente — já que a função ganha um parâmetro obrigatório novo.

`_parse_products_json` chama `raw_text.strip()` direto no valor devolvido por `describe_image` — um `MagicMock` genérico não suporta isso (um `MagicMock.strip()` não devolve uma string de verdade). Use `LocalVisionResult` (`app.router.ollama_client`), a mesma subclasse de `str` já usada em produção para carregar texto + telemetria junto — ela suporta `.strip()` nativamente (é uma string) e já expõe os atributos de telemetria. Adicione o import no topo do arquivo:

```python
from app.router.ollama_client import LocalVisionResult
```

```python
@pytest.mark.asyncio
async def test_extract_page_products_vision_interna_registra_uso_ia(monkeypatch):
    import app.catalog_extractor.extractor as extractor_module

    captured: dict = {}

    async def fake_registrar_uso_ia(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(extractor_module, "registrar_uso_ia", fake_registrar_uso_ia)

    vision_client = AsyncMock()
    raw = LocalVisionResult(
        content=(
            '[{"nome": "Câmera Bullet VIP 1230", "descricao": "Câmera Bullet IP", '
            '"categoria": "CFTV", "preco_base_fornecedor": 210.0, "preco": 320.0, '
            '"especificacoes_tecnicas": "Full HD, IR 30m"}]'
        ),
        prompt_tokens=900,
        completion_tokens=60,
        model_name="gemma4:12b-it-q4_K_M-vision",
    )
    vision_client.describe_image = AsyncMock(return_value=raw)

    produtos = await extract_page_products_vision(
        b"fake-image-bytes",
        vision_client,
        source_identifier="catalogo.pdf#p3",
        ambiente="interno",
    )
    await asyncio.sleep(0)

    assert len(produtos) == 1
    assert captured == {
        "origem": "admin",
        "ambiente": "interno",
        "modelo": "gemma4:12b-it-q4_K_M-vision",
        "operacao": "extracao_catalogo_visao_interna",
        "tokens_entrada": 900,
        "tokens_saida": 60,
        "custo_usd": 0.0,
        "referencia_id": "catalogo.pdf#p3",
        "session": None,
        "session_factory": None,
        "commit": False,
    }
```

(`LocalVisionResult.__new__` já seta `cost_prompt_usd=0.0`/`cost_completion_usd=0.0`/`estimated_cost_usd=0.0` explicitamente — mesmo não declarados nas anotações de tipo da classe, que estão incompletas em relação ao que `__new__` de fato atribui; pré-existente, fora do escopo deste item corrigir. Por isso `getattr(raw_response, "estimated_cost_usd", None)` devolve `0.0` real, não `None`, e `custo_usd` sai `0.0` — correto: visão local é genuinamente grátis, um zero conhecido, não "não capturado".)

- [ ] **Step 2: Escrever o teste que falha — visão externa registra uso de IA**

```python
@pytest.mark.asyncio
async def test_extract_page_products_vision_externa_registra_uso_ia(monkeypatch):
    import app.catalog_extractor.extractor as extractor_module

    captured: dict = {}

    async def fake_registrar_uso_ia(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(extractor_module, "registrar_uso_ia", fake_registrar_uso_ia)

    vision_client = AsyncMock()
    vision_client.vision_model = "openai/gpt-4o-mini"
    vision_client.describe_image = AsyncMock(
        return_value='[{"nome": "Sensor IVP 3000", "descricao": "Sensor infravermelho", '
        '"categoria": "Alarmes", "preco_base_fornecedor": 45.0, "preco": 75.0, '
        '"especificacoes_tecnicas": "Sem fio"}]'
    )

    produtos = await extract_page_products_vision(
        b"fake-image-bytes",
        vision_client,
        source_identifier="foto.jpg",
        ambiente="externo",
    )
    await asyncio.sleep(0)

    assert len(produtos) == 1
    assert captured["origem"] == "admin"
    assert captured["ambiente"] == "externo"
    assert captured["operacao"] == "extracao_catalogo_visao_externa"
    assert captured["referencia_id"] == "foto.jpg"
    # describe_image devolveu uma string pura (sem atributos de telemetria
    # próprios) — tokens/custo ficam None (nada para extrair via getattr).
    # `modelo` cai no fallback `getattr(vision_client, "vision_model", None)`
    # explicitamente setado acima — sem isso, um `AsyncMock()` comum
    # auto-cria um atributo filho (truthy) em vez de devolver `None`,
    # mascarando o fallback real "desconhecido" que só vale quando NENHUM
    # dos dois (raw_response.model_name / vision_client.vision_model) está
    # disponível.
    assert captured["modelo"] == "openai/gpt-4o-mini"
    assert captured["tokens_entrada"] is None
    assert captured["tokens_saida"] is None
```

Adicione `import asyncio` no topo do arquivo se ainda não estiver.

- [ ] **Step 3: Rodar e confirmar que falham**

Run: `uv run python -m pytest tests/test_catalog_extractor.py -k "vision_interna_registra_uso_ia or vision_externa_registra_uso_ia" -v`
Expected: FAIL — `TypeError: extract_page_products_vision() missing 1 required keyword-only argument: 'ambiente'`.

- [ ] **Step 4: Instrumentar `extract_page_products_vision`**

Substitua `extract_page_products_vision` (linhas 186-244) por:

```python
async def extract_page_products_vision(
    image_bytes: bytes,
    vision_client: Any,
    prompt: str | None = None,
    source_identifier: str | None = None,
    session: Any = None,
    session_factory: Any = None,
    *,
    ambiente: str,
) -> list[dict[str, Any]]:
    used_prompt = prompt or VISION_EXTRACTION_PROMPT
    raw_response = await vision_client.describe_image(image_bytes, used_prompt)

    # Telemetria da extração de catálogo por visão — registrada no ledger
    # unificado (app.services.ai_usage), não mais em IngestionCostEvent
    # (decisão do usuário, 2026-10-08: migração sem dual-write; a
    # estimativa de tokens por tamanho de texto que existia aqui foi
    # removida de propósito — fabricava um número quando a API não
    # reportava uso real, contrariando a semântica None=não-capturado do
    # ledger novo).
    p_tok = getattr(raw_response, "prompt_tokens", None)
    c_tok = getattr(raw_response, "completion_tokens", None)
    c_prompt = getattr(raw_response, "cost_prompt_usd", None)
    c_comp = getattr(raw_response, "cost_completion_usd", None)
    c_tot = getattr(raw_response, "estimated_cost_usd", None)
    if c_tot is None and c_prompt is not None and c_comp is not None:
        c_tot = c_prompt + c_comp
    model = getattr(raw_response, "model_name", None) or getattr(
        vision_client, "vision_model", None
    )

    spawn_background_task(
        registrar_uso_ia(
            origem="admin",
            ambiente=ambiente,
            modelo=model or "desconhecido",
            operacao=(
                "extracao_catalogo_visao_interna"
                if ambiente == "interno"
                else "extracao_catalogo_visao_externa"
            ),
            tokens_entrada=p_tok,
            tokens_saida=c_tok,
            custo_usd=c_tot,
            referencia_id=source_identifier,
        )
    )

    return _parse_products_json(raw_response)
```

- [ ] **Step 5: Rodar e confirmar que passam**

Run: `uv run python -m pytest tests/test_catalog_extractor.py -k "vision_interna_registra_uso_ia or vision_externa_registra_uso_ia" -v`
Expected: PASS.

- [ ] **Step 6: Atualizar os 4 call sites dentro de `extract_catalog_stream`**

Run: `grep -n "extract_page_products_vision(" backend/src/app/catalog_extractor/extractor.py`

No branch de PDF (linhas ~470-502), os dois call sites recebem `ambiente="externo"`:

```python
                    if provider == "external":
                        if img_bytes and vision_client:
                            try:
                                raw_prods = await extract_page_products_vision(
                                    img_bytes,
                                    vision_client,
                                    source_identifier=f"{filename}#p{num_pagina_pdf}",
                                    session_factory=session_factory,
                                    ambiente="externo",
                                )
                                provider_usado = "external"
                            except Exception as e:
                                logger.error(f"Erro na visão externa: {e}")
                                erro_pagina = f"Falha ao consultar modelo de visão externo: {e}"
                    else:
                        # Tenta local se houver texto
                        if len(texto_pagina.strip()) >= 30 and local_client:
                            try:
                                raw_prods = await extract_page_products_local(
                                    texto_pagina, local_client
                                )
                                provider_usado = "local"
                            except Exception as e:
                                logger.warning(f"Erro na extração local: {e}")

                        # Fallback se local não retornou nada
                        if not raw_prods and fallback_external and img_bytes and vision_client:
                            try:
                                raw_prods = await extract_page_products_vision(
                                    img_bytes,
                                    vision_client,
                                    source_identifier=f"{filename}#p{num_pagina_pdf}",
                                    session_factory=session_factory,
                                    ambiente="externo",
                                )
                                provider_usado = "external"
                            except Exception as e:
                                logger.error(f"Erro no fallback de visão externa: {e}")
                                erro_pagina = f"Falha ao consultar modelo de visão externo: {e}"
```

No branch de imagem avulsa (linhas ~592-611), o call site de visão local recebe `ambiente="interno"` e o de fallback externo recebe `ambiente="externo"`:

```python
                if not raw_prods and local_client:
                    try:
                        raw_prods = await extract_page_products_vision(
                            content,
                            local_client,
                            source_identifier=filename,
                            session_factory=session_factory,
                            ambiente="interno",
                        )
                        provider_usado = "local"
                    except Exception as e:
                        logger.warning(f"Erro na visão local da imagem {filename}: {e}")

            if not raw_prods and (provider == "external" or fallback_external) and vision_client:
                try:
                    raw_prods = await extract_page_products_vision(
                        content,
                        vision_client,
                        source_identifier=filename,
                        session_factory=session_factory,
                        ambiente="externo",
                    )
                    provider_usado = "external"
                except Exception as e:
                    logger.error(f"Erro na visão externa para imagem {filename}: {e}")
                    erro_pagina = f"Falha ao consultar modelo de visão externo: {e}"
```

(O resto do corpo de `extract_catalog_stream`, fora desses 4 trechos, não muda.)

- [ ] **Step 7: Rodar a suíte completa de `test_catalog_extractor.py`**

Run: `uv run python -m pytest tests/test_catalog_extractor.py -v`
Expected: PASS em todos — incluindo os testes de `extract_catalog_stream` que exercitam cada um dos 4 branches (`test_extract_catalog_stream_com_imagem`, `test_extract_catalog_stream_imagem_sem_ocr_tenta_visao_local_antes_da_externa`, `test_extract_catalog_stream_imagem_cai_para_visao_externa_quando_local_falha`, `test_extract_catalog_stream_imagem_provider_external_pula_visao_local`, `test_extract_catalog_stream_com_pdf_figuras`, `test_extract_catalog_stream_com_filtro_page_range`), que não deveriam precisar de nenhuma mudança (só passam a exercitar código que agora tem um parâmetro a mais, já coberto internamente).

- [ ] **Step 8: Confirmar que `record_ingestion_cost` não é mais chamado por este arquivo**

Run: `grep -n "record_ingestion_cost\|ingestion_metrics" backend/src/app/catalog_extractor/extractor.py`
Expected: nenhuma ocorrência.

- [ ] **Step 9: Rodar a suíte completa do backend**

Run: `cd backend && uv run python -m pytest -q`
Expected: PASS em todos (a mudança de assinatura de `extract_page_products_vision` é só consumida dentro deste mesmo arquivo — confirme que nenhum outro módulo a importa: `grep -rn "extract_page_products_vision" backend/src/` deve mostrar só `extractor.py`).

- [ ] **Step 10: Commit**

```bash
git add backend/src/app/catalog_extractor/extractor.py backend/tests/test_catalog_extractor.py
git commit -m "feat(telemetria): migra extração de catálogo por visão para o ledger de uso de IA (item D, pontos 3a-3b); remove record_ingestion_cost sem dual-write"
```

---

### Task 4: Documentação final

**Files:**
- Modify: `docs/ROADMAP.md` (marcar item D como `[x]`)
- Verify: `docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md`

- [ ] **Step 1: Verificar se algum prompt mapeado mudou**

As mudanças deste item só adicionam captura de metadados da resposta (`model_name`/custo/tokens) e trocam o destino da telemetria — nenhum prompt enviado ao LLM (`system_instruction` em `_generate_sql_with_llm`, `LOCAL_EXTRACTION_PROMPT`, `VISION_EXTRACTION_PROMPT`) foi alterado. Confirme lendo o diff final das Tasks 1-3 (`git diff <commit-antes-da-task-1>..HEAD -- backend/src/app/services/analytics_agent.py backend/src/app/catalog_extractor/extractor.py`) e checando que nenhuma das strings de prompt mudou de conteúdo. Se for, nenhuma entrada de `docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md` precisa mudar — registre isso no commit desta task em vez de editar o arquivo.

- [ ] **Step 2: Marcar item D como concluído em `docs/ROADMAP.md`**

Localize a linha (texto exato, já registrado pelo item C):

```
- [ ] **D — Origem Admin.** Conecta a extração de catálogo por visão
      (`app.catalog_extractor.extractor`) e a geração de gráficos
      dinâmicos via LLM (`app.services.analytics_agent`) à função de A.
      Nota: pelo mesmo motivo do item C, os pontos de comprovante do admin
      (`api/admin_pedidos_conversao.py`) já emitem `origem="admin"`
      corretamente; o escopo restante do item D é extração de catálogo e
      geração de gráficos, não comprovante.
```

Troque `- [ ]` por `- [x]`. Adicione uma frase ao final da descrição (mesma linha de continuação, sem quebrar em novo bullet) registrando que a extração por visão migrou de `IngestionCostEvent` para `ai_usage_events` sem dual-write, por decisão do usuário — para que quem ler o histórico do roadmap entenda por que o card "Ingestão & Dados" do painel atual parou de crescer a partir desta mudança (isso é esperado, não um bug, e é exatamente o que o item E vai substituir).

- [ ] **Step 3: Commit**

```bash
git add docs/ROADMAP.md
git commit -m "docs: marca item D (origem Admin) do ledger de uso de IA como concluído"
```
