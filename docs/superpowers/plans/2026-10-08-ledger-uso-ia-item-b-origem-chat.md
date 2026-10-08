# Ledger de Uso de IA — Item B (Origem Chat) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Conectar os 10 pontos de uso de IA alcançáveis a partir de `app.api.chat`/`app.router.orchestrator` (origem `"chat"`) à função `registrar_uso_ia` (item A, já em produção).

**Architecture:** Cada ponto chama `spawn_background_task(registrar_uso_ia(...))` logo após obter a resposta do LLM/engine (local ou externo), nunca bloqueando o caminho de resposta ao usuário. Dois pontos (TypeSafe Jev) exigem alterar o retorno de `_perguntar_systemone_jev`/`classify_intent_jev`/`classify_tone_jev` para parar de descartar `model`/`usage`. Um ponto (`ComprovanteEvaluator`) exige dois parâmetros novos no construtor (`origem`, `llm_ambiente`) porque a classe é compartilhada por 4 call sites (chat = este item; B2B e Admin = itens C/D, fora de escopo, mas que também precisam de um valor correto e não "chat" por padrão).

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.0 async, pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-10-08-ledger-uso-ia-item-b-origem-chat-design.md`

## Global Constraints

- `origem` é sempre a constante `"chat"` nos 10 pontos deste item (exceto nos 3 call sites de `ComprovanteEvaluator` fora do fluxo de chat, que recebem `"b2b"`/`"admin"` — ver Task 6).
- `referencia_id` só é passado no ponto #1 (geração principal), como `conversation_id`. Os outros 9 pontos passam `None` (default).
- Toda chamada a `registrar_uso_ia` é disparada via `spawn_background_task(registrar_uso_ia(...))` (`app.background_tasks`) — nunca `await` direto.
- `modelo` nunca pode ser `None` (coluna `NOT NULL`): sempre `response.model_name or "desconhecido"` (ou equivalente para Jev/visão).
- `tokens_entrada`/`tokens_saida`/`custo_usd` usam os valores reais quando existirem; `None` quando o conceito não existe (ex.: tokens do CLIP) — nunca inventar um `0` para "não capturado" (`AiUsageEvent` já é nullable para esses 3 campos, decisão do item A).
- Nenhuma instrumentação nova pode propagar exceção: `registrar_uso_ia` já nunca lança (contrato do item A); o próprio ato de extrair campos (`getattr(obj, "campo", None)`) nunca deve usar acesso direto (`obj.campo`) que poderia levantar `AttributeError`.
- Quando a chamada de IA falhou (exceção propagada ou capturada antes de haver uma resposta), **não** chamar `registrar_uso_ia` — não houve uso real para registrar.

---

### Task 1: TypeSafe Jev — captura de metadados de uso (pontos #6, #7)

**Files:**
- Modify: `backend/src/app/router/openrouter_client.py:372-463` (`_perguntar_systemone_jev`, `classify_intent_jev`, `classify_tone_jev`)
- Modify: `backend/src/app/router/classifier.py:1-10` (imports), `:293-326` (`_classify_with_jev`)
- Modify: `backend/src/app/router/tone_monitor.py:1-14` (imports), `:154-186` (`_analyze_with_jev`)
- Test: `backend/tests/test_openrouter_client.py:265-431` (4 testes existentes de Jev)
- Test: `backend/tests/test_classifier.py:184-193`, `:294-297` (fake Jev client)
- Test: `backend/tests/test_tone_monitor.py:31-46` (fake Jev client)
- Test: `backend/tests/test_orchestrator.py:121-123` (fake `classify_intent_jev` em `_FakeLLMClientComJev`)
- Test: `backend/tests/test_chat_api.py:126-127` (fake `classify_intent_jev`)

**Interfaces:**
- Consumes: `registrar_uso_ia` (`app.services.ai_usage`, assinatura já existente — ver Global Constraints), `spawn_background_task` (`app.background_tasks`, assinatura já existente).
- Produces: `OpenRouterClient._perguntar_systemone_jev(...) -> tuple[dict, dict[str, Any] | None]`; `OpenRouterClient.classify_intent_jev(...) -> tuple[str, float, dict[str, Any] | None]`; `OpenRouterClient.classify_tone_jev(...) -> tuple[bool, float, dict[str, Any] | None]`. O terceiro elemento (`usage_info`) é `None` ou um dict com chaves `"model"`, `"input_tokens"`, `"output_tokens"`, `"cost"` (qualquer uma pode ser `None`). Tarefas 2+ não dependem deste formato — é consumido só dentro desta task.

- [ ] **Step 1: Escrever o teste que falha — `classify_intent_jev` passa a devolver `usage_info`**

Em `backend/tests/test_openrouter_client.py`, susbtitua o corpo de `test_classify_intent_jev_sucesso` (linhas 265-312) por:

```python
@pytest.mark.asyncio
async def test_classify_intent_jev_sucesso():
    captured_request: dict = {}

    def mock_handler(request: httpx.Request) -> httpx.Response:
        captured_request["url"] = str(request.url)
        captured_request["body"] = json.loads(request.content)
        data = {
            "model": "typesafe/jev-1.13-20260917",
            "answers": {
                "dominio": {
                    "type": "choice",
                    "choice": "vendas",
                    "confidence": 0.95,
                }
            },
            "usage": {"input_tokens": 42, "output_tokens": 5, "cost": 0.000002},
        }
        return httpx.Response(200, json=data)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as mock_client:
        client = OpenRouterClient(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
            model="meta-llama/llama-3",
            timeout_s=5.0,
            client=mock_client,
            jev_model="typesafe/jev-latest",
        )
        domain, confidence, usage_info = await client.classify_intent_jev(
            message="quanto custa o produto?", recent_messages=[]
        )
        assert domain == "vendas"
        assert confidence == 0.95
        assert usage_info == {
            "model": "typesafe/jev-1.13-20260917",
            "input_tokens": 42,
            "output_tokens": 5,
            "cost": 0.000002,
        }
        # Endpoint dedicado, distinto de /chat/completions
        assert captured_request["url"].endswith("/systemone")
        # Corpo da requisição segue o schema estruturado do System One
        # (model/state/questions.dominio), não o formato de chat.
        body = captured_request["body"]
        assert body["model"] == "typesafe/jev-latest"
        assert body["questions"]["dominio"]["type"] == "choice"
        assert set(body["questions"]["dominio"]["criteria"]) == {
            "vendas",
            "suporte",
            "atendimento",
            "agendamento",
            "fora_escopo",
        }
```

Em `test_classify_intent_jev_choice_fora_do_enum_vira_fora_escopo` (linhas 316-332), troque a linha
`domain, _ = await client.classify_intent_jev(message="teste", recent_messages=[])`
por
`domain, _, usage_info = await client.classify_intent_jev(message="teste", recent_messages=[])`
e adicione `assert usage_info is None` ao final (o mock desse teste não inclui `"usage"` no payload — cobre o caminho defensivo).

Em `test_classify_tone_jev_noul_alto_escala` (linhas 336-364), troque
`escalate, confidence = await client.classify_tone_jev(...)`
por
`escalate, confidence, usage_info = await client.classify_tone_jev(...)`
(sem novas asserções sobre `usage_info` aqui — o mock desse teste não tem `"usage"`; só não pode quebrar o unpacking).

Em `test_classify_tone_jev_noul_baixo_nao_escala` (linhas 368-387) e
`test_classify_tone_jev_resposta_sem_noul_usa_default_seguro` (linhas 391-411), mesma troca:
`escalate, confidence, usage_info = await client.classify_tone_jev(...)`.

`test_classify_tone_jev_falha_http_propaga_excecao` (linhas 415-430) não muda — a chamada levanta exceção antes de haver qualquer tupla para desempacotar.

- [ ] **Step 2: Rodar os testes e confirmar que falham por desempacotamento**

Run: `python -m pytest tests/test_openrouter_client.py -k jev -v`
Expected: FAIL — `ValueError: not enough values to unpack (expected 3, got 2)` nos testes editados (o código de produção ainda devolve 2-tuplas).

- [ ] **Step 3: Implementar a captura de `usage_info` em `openrouter_client.py`**

Substitua `_perguntar_systemone_jev` (linhas 372-401) por:

```python
    async def _perguntar_systemone_jev(
        self,
        message: str,
        recent_messages: list[str] | None,
        question_key: str,
        question: dict,
    ) -> tuple[dict, dict[str, Any] | None]:
        """Faz uma pergunta tipada via TypeSafe Jev, endpoint dedicado do
        OpenRouter (`/systemone`, não `/chat/completions`) — devolve a
        decisão tipada (`answers[question_key]`) e, junto, os metadados de
        uso da resposta (`model`/`usage.input_tokens`/`usage.output_tokens`/
        `usage.cost`, ou `None` quando a resposta não trouxer `usage` —
        achado de 2026-10-08: até aqui esses campos existiam na resposta
        real e eram descartados, zerando qualquer métrica de uso do Jev).
        Compartilhado por `classify_intent_jev` (pergunta `choice`) e
        `classify_tone_jev` (pergunta `noul`, R8) — acha review
        (2026-09-24): as duas duplicavam a mesma chamada HTTP.
        """
        if not self._jev_model:
            raise ValueError("jev_model não configurado (JEV_MODEL_NAME).")

        contexto = "\n".join(recent_messages) if recent_messages else "(nenhum)"
        response = await self._client.post(
            f"{self._base_url}/systemone",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self._jev_model,
                "state": f"Contexto prévio:\n{contexto}\n\nMensagem: {message}",
                "questions": {question_key: question},
            },
            timeout=self._jev_timeout_s,
        )
        response.raise_for_status()
        data = response.json()
        usage_raw = data.get("usage")
        usage_info = (
            {
                "model": data.get("model"),
                "input_tokens": usage_raw.get("input_tokens"),
                "output_tokens": usage_raw.get("output_tokens"),
                "cost": usage_raw.get("cost"),
            }
            if isinstance(usage_raw, dict)
            else None
        )
        return data["answers"][question_key], usage_info
```

Substitua `classify_intent_jev` (linhas 403-423) por:

```python
    async def classify_intent_jev(
        self, message: str, recent_messages: list[str] | None = None
    ) -> tuple[str, float, dict[str, Any] | None]:
        """Classifica o domínio via TypeSafe Jev — ver `_perguntar_systemone_jev`."""
        answer, usage_info = await self._perguntar_systemone_jev(
            message,
            recent_messages,
            "dominio",
            {
                "type": "choice",
                "instructions": (
                    "Classifique a mensagem do cliente em um dos domínios de atendimento."
                ),
                "criteria": DOMAIN_CRITERIA,
            },
        )
        choice = str(answer.get("choice", "fora_escopo")).lower().strip()
        confidence = float(answer.get("confidence", 0.5))
        if choice not in _VALID_DOMAINS:
            choice = "fora_escopo"
        return choice, confidence, usage_info
```

Substitua `classify_tone_jev` (linhas 425-463) por:

```python
    async def classify_tone_jev(
        self, message: str, recent_messages: list[str] | None = None
    ) -> tuple[bool, float, dict[str, Any] | None]:
        """Avalia urgência/insatisfação via TypeSafe Jev (R8, Fase 4B) —
        mesmo endpoint dedicado de `classify_intent_jev` (`/systemone`), mas
        com uma pergunta do tipo `noul` (sim/não com probabilidade
        calibrada) em vez de `choice` — ver
        docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md §3.2.
        """
        answer, usage_info = await self._perguntar_systemone_jev(
            message,
            recent_messages,
            "escalar",
            {
                "type": "noul",
                "instructions": (
                    "O cliente está demonstrando urgência ou insatisfação forte "
                    "que justifique transferência para atendimento humano?"
                ),
                "criteria": {
                    "true": (
                        "Mensagem com tom de urgência, raiva, ameaça de "
                        "cancelamento/processo, ou insatisfação explícita e forte."
                    ),
                    "false": (
                        "Tom neutro ou normal de atendimento, mesmo com dúvida ou reclamação leve."
                    ),
                },
            },
        )
        # Achado no code-review (2026-09-24): sem `.get()` defensivo (ao
        # contrário do irmão `classify_intent_jev` acima), uma resposta sem
        # a chave "noul" levantava KeyError cru em vez de degradar — o
        # chamador (`tone_monitor._analyze_with_jev`) captura qualquer
        # exceção e já degrada com segurança, mas o default aqui evita
        # depender só disso. Default `0.0` (não escala) é o lado seguro,
        # mesmo espírito de `_classify_heuristic_fallback`.
        noul = float(answer.get("noul", 0.0))
        return noul >= 0.5, noul, usage_info
```

Confirme que `Any` já está importado em `openrouter_client.py` (`from typing import Any` ou equivalente); se não estiver, adicione.

- [ ] **Step 4: Atualizar os fakes de teste que chamam `classify_intent_jev`/`classify_tone_jev`**

Em `backend/tests/test_classifier.py`, `_FakeOpenRouterJevClient.classify_intent_jev` (linhas 184-193):

```python
class _FakeOpenRouterJevClient:
    def __init__(
        self,
        domain: str = "vendas",
        confidence: float = 0.9,
        fail: bool = False,
        usage_info: dict | None = None,
    ):
        self.domain = domain
        self.confidence = confidence
        self.fail = fail
        self.usage_info = usage_info

    async def classify_intent_jev(self, message: str, recent_messages: list[str] | None = None):
        if self.fail:
            raise RuntimeError("Conexão com OpenRouter falhou")
        return self.domain, self.confidence, self.usage_info
```

Em `backend/tests/test_tone_monitor.py`, `_FakeJevClient.classify_tone_jev` (linhas 31-46):

```python
class _FakeJevClient:
    def __init__(
        self,
        escalate: bool = False,
        confidence: float = 0.0,
        exception: Exception | None = None,
        usage_info: dict | None = None,
    ) -> None:
        self._escalate = escalate
        self._confidence = confidence
        self._exception = exception
        self.usage_info = usage_info

    async def classify_tone_jev(self, message: str, recent_messages: list[str] | None = None):
        if self._exception is not None:
            raise self._exception
        return self._escalate, self._confidence, self.usage_info
```

- [ ] **Step 4b: Atualizar os demais fakes de `classify_intent_jev` que ainda devolvem 2-tuplas**

Run: `grep -rn "def classify_intent_jev\|def classify_tone_jev" backend/tests/*.py` para confirmar a lista completa antes de editar (pode haver mais algum fora dos 4 arquivos já identificados nesta task).

Em `backend/tests/test_orchestrator.py`, `_FakeLLMClientComJev.classify_intent_jev` (linhas 121-123):

```python
    async def classify_intent_jev(self, message: str, recent_messages: list[str] | None = None):
        if self._jev_fail:
            raise RuntimeError("Conexão com OpenRouter falhou")
        return self._jev_domain, self._jev_confidence, None
```

Em `backend/tests/test_chat_api.py`, o fake equivalente (linhas 126-127):

```python
    async def classify_intent_jev(self, message: str, recent_messages: list[str] | None = None):
        return self._jev_domain, self._jev_confidence, None
```

(Ambos devolvem `None` como terceiro elemento — nenhum desses testes verifica telemetria de Jev, então `usage_info=None` é suficiente; não precisam do parâmetro extra que `_FakeOpenRouterJevClient`/`_FakeJevClient` ganharam no Step 4, só o retorno de 3 elementos para não quebrar o desempacotamento em `_classify_with_jev`.)

Run: `python -m pytest tests/test_orchestrator.py tests/test_chat_api.py -v`
Expected: PASS em todos (nenhum desses testes é novo — são os já existentes, só não podem quebrar por causa da mudança de assinatura).

- [ ] **Step 5: Rodar os testes de Jev de novo e confirmar que passam**

Run: `python -m pytest tests/test_openrouter_client.py tests/test_classifier.py tests/test_tone_monitor.py -v`
Expected: PASS em todos (os testes de `classifier`/`tone_monitor` ainda não fazem asserção sobre instrumentação — isso é o Step 6/7 abaixo).

- [ ] **Step 6: Escrever o teste que falha — `_classify_with_jev` registra uso de IA**

Em `backend/tests/test_classifier.py`, adicione (perto de `test_classify_com_jev_sucesso`):

```python
async def test_classify_com_jev_sucesso_registra_uso_ia(monkeypatch):
    import app.router.classifier as classifier_module

    captured: dict = {}

    async def fake_registrar_uso_ia(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(classifier_module, "registrar_uso_ia", fake_registrar_uso_ia)

    fake_client = _FakeOpenRouterJevClient(
        domain="vendas",
        confidence=0.92,
        usage_info={
            "model": "typesafe/jev-1.13-20260917",
            "input_tokens": 401,
            "output_tokens": 63,
            "cost": 1.6842e-05,
        },
    )
    await classify(
        message="Quero saber o valor do plano",
        provider="jev_openrouter",
        external_client=fake_client,
    )
    await asyncio.sleep(0)

    assert captured == {
        "origem": "chat",
        "ambiente": "externo",
        "modelo": "typesafe/jev-1.13-20260917",
        "operacao": "classificacao_jev",
        "tokens_entrada": 401,
        "tokens_saida": 63,
        "custo_usd": 1.6842e-05,
        "referencia_id": None,
        "session": None,
        "session_factory": None,
        "commit": False,
    }
```

Adicione `import asyncio` no topo de `test_classifier.py` se ainda não estiver importado.

Também adicione um teste cobrindo `usage_info is None` (resposta do Jev sem `usage`):

```python
async def test_classify_com_jev_sem_usage_info_registra_uso_ia_com_none(monkeypatch):
    import app.router.classifier as classifier_module

    captured: dict = {}

    async def fake_registrar_uso_ia(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(classifier_module, "registrar_uso_ia", fake_registrar_uso_ia)

    fake_client = _FakeOpenRouterJevClient(domain="vendas", confidence=0.92, usage_info=None)
    await classify(
        message="Quero saber o valor do plano",
        provider="jev_openrouter",
        external_client=fake_client,
    )
    await asyncio.sleep(0)

    assert captured["modelo"] == "jev"
    assert captured["tokens_entrada"] is None
    assert captured["tokens_saida"] is None
    assert captured["custo_usd"] is None
```

E um teste confirmando que uma falha do Jev (degradação para heurística) **não** chama `registrar_uso_ia` nenhuma vez:

```python
async def test_classify_jev_falha_nao_registra_uso_ia(monkeypatch):
    import app.router.classifier as classifier_module

    calls: list[dict] = []

    async def fake_registrar_uso_ia(**kwargs):
        calls.append(kwargs)
        return None

    monkeypatch.setattr(classifier_module, "registrar_uso_ia", fake_registrar_uso_ia)

    fake_client = _FakeOpenRouterJevClient(fail=True)
    await classify(
        message="Quero saber o valor do plano",
        provider="jev_openrouter",
        external_client=fake_client,
    )
    await asyncio.sleep(0)

    assert calls == []
```

- [ ] **Step 7: Rodar e confirmar que falham**

Run: `python -m pytest tests/test_classifier.py -k registra_uso_ia -v`
Expected: FAIL — `AttributeError: <module 'app.router.classifier'> does not have the attribute 'registrar_uso_ia'` (ainda não foi importado em `classifier.py`).

- [ ] **Step 8: Instrumentar `_classify_with_jev` em `classifier.py`**

No topo de `backend/src/app/router/classifier.py`, depois do bloco de imports existente (linha 9-10), adicione:

```python
from app.background_tasks import spawn_background_task
from app.services.ai_usage import registrar_uso_ia
```

Substitua `_classify_with_jev` (linhas 293-326) por:

```python
async def _classify_with_jev(
    message: str,
    recent_messages: list[str],
    external_client: IntentClassifierClient | None,
    ultima_resposta: str | None = None,
) -> ClassificationResult:
    try:
        if external_client is None or not hasattr(external_client, "classify_intent_jev"):
            raise ValueError("external_client inválido para Jev")
        domain, confidence, usage_info = await external_client.classify_intent_jev(
            message, _contexto_com_ultima_resposta(recent_messages, ultima_resposta)
        )
        usage_info = usage_info or {}
        spawn_background_task(
            registrar_uso_ia(
                origem="chat",
                ambiente="externo",
                modelo=usage_info.get("model") or "jev",
                operacao="classificacao_jev",
                tokens_entrada=usage_info.get("input_tokens"),
                tokens_saida=usage_info.get("output_tokens"),
                custo_usd=usage_info.get("cost"),
            )
        )
        return ClassificationResult(
            domain=domain,
            complexity=_heuristic_complexity(message),
            confidence=confidence,
            provider_efetivo="jev_openrouter",
        )
    except Exception as exc:
        # MVP: qualquer falha do provedor Jev (timeout, cliente ausente,
        # resposta malformada) degrada silenciosamente para a heurística
        # local — nunca deve derrubar a requisição de chat.
        logger.warning(
            "jev_classificacao_falhou_fallback_heuristica",
            extra={
                "router": {
                    "event": "jev_falha_fallback",
                    "erro": str(exc),
                }
            },
        )
        return _classify_heuristic_fallback(
            message, recent_messages, provider_efetivo="heuristica_llm"
        )
```

- [ ] **Step 9: Rodar os testes de `classifier.py` e confirmar que passam**

Run: `python -m pytest tests/test_classifier.py -v`
Expected: PASS em todos, incluindo os 3 novos.

- [ ] **Step 10: Repetir Steps 6-9 para `tone_monitor.py` (`_analyze_with_jev`)**

Em `backend/tests/test_tone_monitor.py`, adicione (padrão idêntico ao de `classifier.py`, adaptado):

```python
async def test_analyze_tone_jev_sucesso_registra_uso_ia(monkeypatch):
    import app.router.tone_monitor as tone_monitor_module

    captured: dict = {}

    async def fake_registrar_uso_ia(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(tone_monitor_module, "registrar_uso_ia", fake_registrar_uso_ia)

    jev = _FakeJevClient(
        escalate=True,
        confidence=0.9,
        usage_info={
            "model": "typesafe/jev-1.13-20260917",
            "input_tokens": 300,
            "output_tokens": 10,
            "cost": 5e-06,
        },
    )
    await analyze_tone(
        message="Será que vocês poderiam me ajudar com uma dúvida sobre o pedido",
        recent_messages=[],
        strategy_provider="jev_openrouter",
        llm_client=_FakeLLMClient(),
        external_client=jev,
    )
    await asyncio.sleep(0)

    assert captured == {
        "origem": "chat",
        "ambiente": "externo",
        "modelo": "typesafe/jev-1.13-20260917",
        "operacao": "monitor_tom_jev",
        "tokens_entrada": 300,
        "tokens_saida": 10,
        "custo_usd": 5e-06,
        "referencia_id": None,
        "session": None,
        "session_factory": None,
        "commit": False,
    }


async def test_analyze_tone_jev_falha_nao_registra_uso_ia(monkeypatch):
    import app.router.tone_monitor as tone_monitor_module

    calls: list[dict] = []

    async def fake_registrar_uso_ia(**kwargs):
        calls.append(kwargs)
        return None

    monkeypatch.setattr(tone_monitor_module, "registrar_uso_ia", fake_registrar_uso_ia)

    jev = _FakeJevClient(exception=RuntimeError("timeout"))
    await analyze_tone(
        message="Será que vocês poderiam me ajudar com uma dúvida sobre o pedido",
        recent_messages=[],
        strategy_provider="jev_openrouter",
        llm_client=_FakeLLMClient(),
        external_client=jev,
    )
    await asyncio.sleep(0)

    assert calls == []
```

Adicione `import asyncio` no topo de `test_tone_monitor.py` se ainda não estiver.

Run: `python -m pytest tests/test_tone_monitor.py -k registra_uso_ia -v`
Expected: FAIL (mesma causa do Step 7).

No topo de `backend/src/app/router/tone_monitor.py`, depois do bloco de imports existente (linha 12), adicione:

```python
from app.background_tasks import spawn_background_task
from app.services.ai_usage import registrar_uso_ia
```

Substitua `_analyze_with_jev` (linhas 154-186) por:

```python
async def _analyze_with_jev(
    message: str, recent_messages: list[str], external_client: Any
) -> ToneResult:
    try:
        if external_client is None or not hasattr(external_client, "classify_tone_jev"):
            raise ValueError("external_client inválido para Jev")
        escalate, confidence, usage_info = await external_client.classify_tone_jev(
            message, recent_messages
        )
        usage_info = usage_info or {}
        spawn_background_task(
            registrar_uso_ia(
                origem="chat",
                ambiente="externo",
                modelo=usage_info.get("model") or "jev",
                operacao="monitor_tom_jev",
                tokens_entrada=usage_info.get("input_tokens"),
                tokens_saida=usage_info.get("output_tokens"),
                custo_usd=usage_info.get("cost"),
            )
        )
        # Jev responde com uma única pergunta noul (sim/não) — não distingue
        # motivo. "insatisfacao" é um rótulo genérico quando escala; refinar
        # com duas perguntas noul separadas fica para uma iteração futura.
        return ToneResult(
            escalate=escalate,
            motivo="insatisfacao" if escalate else None,
            confidence=confidence,
            provider_efetivo="jev_openrouter",
        )
    except Exception as exc:
        logger.warning(
            "jev_tom_falhou_fallback_heuristica",
            extra={
                "router": {
                    "event": "jev_tom_falha_fallback",
                    "tipo": type(exc).__name__,
                    "erro": str(exc),
                }
            },
        )
        return ToneResult(
            escalate=False,
            motivo=None,
            confidence=0.0,
            provider_efetivo=DEFAULT_TONE_MONITOR_PROVIDER,
        )
```

Run: `python -m pytest tests/test_tone_monitor.py -v`
Expected: PASS em todos.

- [ ] **Step 11: Commit**

```bash
git add backend/src/app/router/openrouter_client.py backend/src/app/router/classifier.py backend/src/app/router/tone_monitor.py backend/tests/test_openrouter_client.py backend/tests/test_classifier.py backend/tests/test_tone_monitor.py
git commit -m "feat(telemetria): instrumenta classificador/monitor de tom via Jev no ledger de uso de IA (item B, pontos 6-7)"
```

---

### Task 2: Classificador e monitor de tom — caminho heurística+LLM local (pontos #4, #5)

**Files:**
- Modify: `backend/src/app/router/classifier.py:263-290` (`_classify_with_llm`)
- Modify: `backend/src/app/router/tone_monitor.py:104-151` (`_analyze_with_llm`)
- Test: `backend/tests/test_classifier.py`
- Test: `backend/tests/test_tone_monitor.py`

**Interfaces:**
- Consumes: `registrar_uso_ia`/`spawn_background_task` já importados em ambos os módulos pela Task 1.
- Produces: nenhuma interface nova — só instrumentação interna.

- [ ] **Step 1: Escrever o teste que falha — `_classify_with_llm` registra uso de IA**

Em `backend/tests/test_classifier.py`, adicione:

```python
async def test_classify_com_llm_local_registra_uso_ia(monkeypatch):
    import app.router.classifier as classifier_module

    captured: dict = {}

    async def fake_registrar_uso_ia(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(classifier_module, "registrar_uso_ia", fake_registrar_uso_ia)

    class _FakeLLMClientComModelo(_FakeLLMClient):
        async def generate(self, prompt: str) -> LLMResponse:
            self.calls += 1
            self.last_prompt = prompt
            return LLMResponse(
                text=self._text,
                total_duration_ms=10.0,
                model_name="gemma4:12b-it-q4_K_M",
                prompt_tokens=120,
                completion_tokens=15,
                estimated_cost_usd=0.0,
            )

    await classify(
        message="Quero saber o valor do plano",
        strategy="llm",
        llm_client=_FakeLLMClientComModelo(
            '{"domain": "vendas", "complexity": "baixa", "confidence": 0.8}'
        ),
        provider="heuristica_llm",
    )
    await asyncio.sleep(0)

    assert captured == {
        "origem": "chat",
        "ambiente": "interno",
        "modelo": "gemma4:12b-it-q4_K_M",
        "operacao": "classificacao_heuristica_llm",
        "tokens_entrada": 120,
        "tokens_saida": 15,
        "custo_usd": 0.0,
        "referencia_id": None,
        "session": None,
        "session_factory": None,
        "commit": False,
    }
```

Verifique que a mensagem usada (`"Quero saber o valor do plano"`) não casa com nenhuma palavra-chave de `_match_domain_by_keywords` — se casar, `classify()` nunca chega a chamar `_classify_with_llm` e o teste falha por `captured == {}`. Se precisar trocar a mensagem, use algo deliberadamente ambíguo (ex.: `"Isso realmente funciona bem?"`).

Adicione `import asyncio` no topo do arquivo se ainda não estiver.

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest tests/test_classifier.py -k registra_uso_ia_llm_local -v` (ajuste o `-k` para o nome real do teste)
Expected: FAIL — `captured == {}` (nenhuma chamada registrada ainda).

- [ ] **Step 3: Instrumentar `_classify_with_llm`**

Substitua `_classify_with_llm` (linhas 263-290 de `classifier.py`) por:

```python
async def _classify_with_llm(
    message: str,
    recent_messages: list[str],
    llm_client: LLMClient,
    ultima_resposta: str | None = None,
    provider_efetivo: str = "heuristica_llm",
) -> ClassificationResult:
    contexto_llm = _contexto_com_ultima_resposta(recent_messages, ultima_resposta)
    contexto = "\n".join(contexto_llm) if contexto_llm else "(nenhum)"
    prompt = _CLASSIFIER_PROMPT_TEMPLATE.format(
        dominios=_DOMINIOS_FORMATADOS, contexto=contexto, mensagem=message
    )

    # A chamada de rede fica FORA do try/except abaixo de propósito: qualquer
    # exceção dela é falha de infraestrutura do backend local (inclusive o
    # ValidationError que o OllamaClient levanta com payload malformado) e
    # deve propagar para o orchestrator virar LocalBackendIndisponivelError,
    # nunca degradar em silêncio para a heurística (spec §2.4).
    response = await llm_client.generate(prompt)
    spawn_background_task(
        registrar_uso_ia(
            origem="chat",
            ambiente="interno",
            modelo=response.model_name or "desconhecido",
            operacao="classificacao_heuristica_llm",
            tokens_entrada=response.prompt_tokens,
            tokens_saida=response.completion_tokens,
            custo_usd=response.estimated_cost_usd,
        )
    )

    try:
        return _parse_llm_classification(response.text, provider_efetivo=provider_efetivo)
    except (json.JSONDecodeError, ValidationError, TypeError):  # fmt: skip
        # O LLM respondeu, mas o conteúdo não é JSON de classificação válido:
        # aí sim cai para a heurística só nesta requisição (spec §2.2).
        return _classify_heuristic_fallback(
            message, recent_messages, provider_efetivo=provider_efetivo
        )
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest tests/test_classifier.py -v`
Expected: PASS em todos.

- [ ] **Step 5: Repetir Steps 1-4 para `tone_monitor._analyze_with_llm`**

Em `backend/tests/test_tone_monitor.py`:

```python
async def test_analyze_tone_llm_local_registra_uso_ia(monkeypatch):
    import app.router.tone_monitor as tone_monitor_module

    captured: dict = {}

    async def fake_registrar_uso_ia(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(tone_monitor_module, "registrar_uso_ia", fake_registrar_uso_ia)

    response = LLMResponse(
        text='{"escalar": false, "motivo": null, "confianca": 0.1}',
        total_duration_ms=10.0,
        model_name="gemma4:12b-it-q4_K_M",
        prompt_tokens=80,
        completion_tokens=12,
        estimated_cost_usd=0.0,
    )
    llm = _FakeLLMClient(response=response)
    await analyze_tone(
        message="Só queria saber o horário de funcionamento da loja hoje",
        recent_messages=[],
        strategy_provider="heuristica_llm",
        llm_client=llm,
        external_client=None,
    )
    await asyncio.sleep(0)

    assert captured == {
        "origem": "chat",
        "ambiente": "interno",
        "modelo": "gemma4:12b-it-q4_K_M",
        "operacao": "monitor_tom_heuristica_llm",
        "tokens_entrada": 80,
        "tokens_saida": 12,
        "custo_usd": 0.0,
        "referencia_id": None,
        "session": None,
        "session_factory": None,
        "commit": False,
    }
```

Confira que a mensagem de teste não casa com `_match_heuristic_signal` (nem urgência, nem insatisfação, nem maiúsculas/exclamação) — senão `analyze_tone` resolve pela heurística e nunca chama `_analyze_with_llm`.

Run: `python -m pytest tests/test_tone_monitor.py -k registra_uso_ia_llm_local -v`
Expected: FAIL (ainda não instrumentado).

Substitua o corpo de `_analyze_with_llm` (linhas 104-151 de `tone_monitor.py`), só a parte dentro do `try`, inserindo a chamada logo após obter `response`:

```python
async def _analyze_with_llm(
    message: str, recent_messages: list[str], llm_client: LLMClient
) -> ToneResult:
    contexto = "\n".join(recent_messages) if recent_messages else "(nenhum)"
    prompt = _TONE_PROMPT_TEMPLATE.format(contexto=contexto, mensagem=message)
    try:
        response = await llm_client.generate(prompt)
        spawn_background_task(
            registrar_uso_ia(
                origem="chat",
                ambiente="interno",
                modelo=response.model_name or "desconhecido",
                operacao="monitor_tom_heuristica_llm",
                tokens_entrada=response.prompt_tokens,
                tokens_saida=response.completion_tokens,
                custo_usd=response.estimated_cost_usd,
            )
        )
        parsed = json.loads(strip_code_fence(response.text))
        escalate = bool(parsed.get("escalar", False))
        motivo = parsed.get("motivo") if escalate else None
        confidence = float(parsed.get("confianca", 0.0))
        return ToneResult(
            escalate=escalate,
            motivo=motivo,
            confidence=confidence,
            provider_efetivo=DEFAULT_TONE_MONITOR_PROVIDER,
        )
    except Exception as exc:
        logger.warning(
            "llm_tom_falhou_fallback_degradado",
            extra={
                "router": {
                    "event": "llm_tom_falha_fallback",
                    "tipo": type(exc).__name__,
                    "erro": str(exc),
                }
            },
        )
        return ToneResult(
            escalate=False,
            motivo=None,
            confidence=0.0,
            provider_efetivo=DEFAULT_TONE_MONITOR_PROVIDER,
        )
```

Não altere o resto da função (comentários extensos acima do `except`, já existentes, continuam exatamente iguais).

Run: `python -m pytest tests/test_tone_monitor.py -v`
Expected: PASS em todos.

- [ ] **Step 6: Commit**

```bash
git add backend/src/app/router/classifier.py backend/src/app/router/tone_monitor.py backend/tests/test_classifier.py backend/tests/test_tone_monitor.py
git commit -m "feat(telemetria): instrumenta classificador/monitor de tom local no ledger de uso de IA (item B, pontos 4-5)"
```

---

### Task 3: Extração de slots — Vendas e Agendamento (pontos #2, #3)

**Files:**
- Modify: `backend/src/app/router/sales_catalog.py:1-20` (imports), `:381-418` (`extract_sales_slots`)
- Modify: `backend/src/app/router/scheduling.py:1-24` (imports), `:159-191` (`extract_booking_slots`)
- Test: `backend/tests/test_sales_catalog.py`
- Test: `backend/tests/test_scheduling.py`

**Interfaces:**
- Consumes: `registrar_uso_ia`/`spawn_background_task`.
- Produces: nenhuma interface nova.

- [ ] **Step 1: Escrever o teste que falha — `extract_sales_slots` registra uso de IA**

Verifique em `backend/tests/test_sales_catalog.py` (linhas ~217-225) a classe `_FakeLLMClient` existente — ela já devolve `LLMResponse(text=self._text, total_duration_ms=10.0)`. Adicione um teste novo:

```python
async def test_extract_sales_slots_registra_uso_ia(monkeypatch):
    import app.router.sales_catalog as sales_catalog_module

    captured: dict = {}

    async def fake_registrar_uso_ia(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(sales_catalog_module, "registrar_uso_ia", fake_registrar_uso_ia)

    class _FakeLLMClientComMetricas(_FakeLLMClient):
        async def generate(self, prompt: str) -> LLMResponse:
            self.last_prompt = prompt
            return LLMResponse(
                text=self._text,
                total_duration_ms=10.0,
                model_name="gemma4:12b-it-q4_K_M",
                prompt_tokens=200,
                completion_tokens=30,
                estimated_cost_usd=0.0,
            )

    client = _FakeLLMClientComMetricas('{"produto_id": null, "categoria": null}')
    await extract_sales_slots(
        message="quais produtos vocês têm?",
        recent_messages=[],
        candidatos=[],
        llm_client=client,
        categorias_disponiveis=[],
    )
    await asyncio.sleep(0)

    assert captured == {
        "origem": "chat",
        "ambiente": "interno",
        "modelo": "gemma4:12b-it-q4_K_M",
        "operacao": "extracao_slots_vendas",
        "tokens_entrada": 200,
        "tokens_saida": 30,
        "custo_usd": 0.0,
        "referencia_id": None,
        "session": None,
        "session_factory": None,
        "commit": False,
    }
```

Adicione `import asyncio` no topo do arquivo se ainda não estiver. Ajuste o payload JSON de `_text` caso a classe real `VendaSlots`/`_parse_extraction` exija outros campos (confira a definição de `VendaSlots` em `sales_catalog.py` antes de finalizar o texto).

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest tests/test_sales_catalog.py -k registra_uso_ia -v`
Expected: FAIL — `captured == {}`.

- [ ] **Step 3: Instrumentar `extract_sales_slots`**

No topo de `backend/src/app/router/sales_catalog.py`, junto aos imports existentes (depois da linha 17-18 `import json` / `import re`), adicione:

```python
from app.background_tasks import spawn_background_task
from app.services.ai_usage import registrar_uso_ia
```

Em `extract_sales_slots` (linha 413), insira a chamada logo após `response = await llm_client.generate(prompt)` e antes do `try: slots = _parse_extraction(...)`:

```python
    response = await llm_client.generate(prompt)
    spawn_background_task(
        registrar_uso_ia(
            origem="chat",
            ambiente="interno",
            modelo=response.model_name or "desconhecido",
            operacao="extracao_slots_vendas",
            tokens_entrada=response.prompt_tokens,
            tokens_saida=response.completion_tokens,
            custo_usd=response.estimated_cost_usd,
        )
    )
    try:
        slots = _parse_extraction(response.text)
    except json.JSONDecodeError, ValidationError, TypeError:
        return VendaSlots()
```

(A linha `except json.JSONDecodeError, ValidationError, TypeError:` já existe no arquivo tal como está — Python 3.14 aceita múltiplos tipos separados por vírgula sem parênteses em `except`, sintaxe nova desta versão; não normalize para `except (A, B, C):`, mantenha como já estava.)

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest tests/test_sales_catalog.py -v`
Expected: PASS em todos.

- [ ] **Step 5: Repetir Steps 1-4 para `extract_booking_slots` em `scheduling.py`**

Em `backend/tests/test_scheduling.py`:

```python
async def test_extract_booking_slots_registra_uso_ia(monkeypatch):
    import app.router.scheduling as scheduling_module

    captured: dict = {}

    async def fake_registrar_uso_ia(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(scheduling_module, "registrar_uso_ia", fake_registrar_uso_ia)

    response = LLMResponse(
        text="{}",
        total_duration_ms=10.0,
        model_name="gemma4:12b-it-q4_K_M",
        prompt_tokens=150,
        completion_tokens=20,
        estimated_cost_usd=0.0,
    )

    class _FakeLLMClientComMetricas(_FakeLLMClient):
        async def generate(self, prompt: str) -> LLMResponse:
            return response

    client = _FakeLLMClientComMetricas("{}")
    await extract_booking_slots(
        message="quero agendar para quarta",
        recent_messages=[],
        current_slots=BookingSlots(),
        llm_client=client,
        timezone="America/Sao_Paulo",
    )
    await asyncio.sleep(0)

    assert captured == {
        "origem": "chat",
        "ambiente": "interno",
        "modelo": "gemma4:12b-it-q4_K_M",
        "operacao": "extracao_slots_agendamento",
        "tokens_entrada": 150,
        "tokens_saida": 20,
        "custo_usd": 0.0,
        "referencia_id": None,
        "session": None,
        "session_factory": None,
        "commit": False,
    }
```

Adicione `import asyncio` no topo se necessário. Confirme a assinatura exata de `_FakeLLMClient` em `test_scheduling.py` (linhas ~73-80) antes de herdar dela.

Run: `python -m pytest tests/test_scheduling.py -k registra_uso_ia -v`
Expected: FAIL.

No topo de `backend/src/app/router/scheduling.py`, junto aos imports existentes (depois de `import json`/`import re`, linhas 15-16), adicione:

```python
from app.background_tasks import spawn_background_task
from app.services.ai_usage import registrar_uso_ia
```

Em `extract_booking_slots` (linha 182), insira a chamada logo após `response = await llm_client.generate(prompt)`:

```python
    response = await llm_client.generate(prompt)
    spawn_background_task(
        registrar_uso_ia(
            origem="chat",
            ambiente="interno",
            modelo=response.model_name or "desconhecido",
            operacao="extracao_slots_agendamento",
            tokens_entrada=response.prompt_tokens,
            tokens_saida=response.completion_tokens,
            custo_usd=response.estimated_cost_usd,
        )
    )
    try:
        return _parse_extraction(response.text)
    except (json.JSONDecodeError, ValidationError, TypeError):  # fmt: skip
        return SlotExtractionResult()
```

Run: `python -m pytest tests/test_scheduling.py -v`
Expected: PASS em todos.

- [ ] **Step 6: Commit**

```bash
git add backend/src/app/router/sales_catalog.py backend/src/app/router/scheduling.py backend/tests/test_sales_catalog.py backend/tests/test_scheduling.py
git commit -m "feat(telemetria): instrumenta extração de slots de vendas e agendamento no ledger de uso de IA (item B, pontos 2-3)"
```

---

### Task 4: Geração de resposta principal (ponto #1)

**Files:**
- Modify: `backend/src/app/router/orchestrator.py:1-10` (imports), `:1660-1668` (fim de `handle_message`)
- Test: `backend/tests/test_orchestrator.py` (já tem a infraestrutura de teste pronta: `_FakeLLMClient`, `_resposta_local()`, `_resposta_externa()`, `_coletar_eventos()`, `_FakeRAGClient` — ver linhas 42-160)

**Interfaces:**
- Consumes: `registrar_uso_ia`/`spawn_background_task`; variáveis já em escopo em `handle_message`: `conversation_id`, `backend_escolhido`, `decisao` (`RouterDecision`, campos `modelo_usado`, `tokens_entrada`, `tokens_saida`, `custo_estimado_usd`).
- Produces: nenhuma interface nova.

- [ ] **Step 1: Escrever o teste que falha — geração principal registra uso de IA (backend local)**

Em `backend/tests/test_orchestrator.py`, usando o mesmo padrão de `test_fora_escopo_baixa_complexidade_usa_modelo_local` (linhas 862-883), adicione:

```python
async def test_handle_message_registra_uso_ia_geracao_principal_local(monkeypatch):
    import app.router.orchestrator as orchestrator_module

    captured: dict = {}

    async def fake_registrar_uso_ia(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(orchestrator_module, "registrar_uso_ia", fake_registrar_uso_ia)

    resposta = LLMResponse(
        text="resposta local",
        total_duration_ms=100.0,
        model_name="gemma4:12b-it-q4_K_M",
        prompt_tokens=500,
        completion_tokens=80,
        estimated_cost_usd=0.0,
    )
    local_client = _FakeLLMClient(response=resposta)
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(exception=RAGConnectionError("não deveria ser chamado"))

    await _coletar_eventos(
        "Olá, boa noite",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
        tone_monitor_enabled=False,
        conversation_id="conv-123",
    )
    await asyncio.sleep(0)

    assert captured == {
        "origem": "chat",
        "ambiente": "interno",
        "modelo": "gemma4:12b-it-q4_K_M",
        "operacao": "geracao_resposta",
        "tokens_entrada": 500,
        "tokens_saida": 80,
        "custo_usd": 0.0,
        "referencia_id": "conv-123",
        "session": None,
        "session_factory": None,
        "commit": False,
    }
```

Adicione `import asyncio` no topo de `test_orchestrator.py` se ainda não estiver.

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest tests/test_orchestrator.py -k registra_uso_ia_geracao_principal_local -v`
Expected: FAIL — `captured == {}`.

- [ ] **Step 3: Instrumentar o fim de `handle_message`**

No topo de `backend/src/app/router/orchestrator.py`, junto aos imports existentes de `app.router.*` (perto da linha 31-33), adicione:

```python
from app.background_tasks import spawn_background_task
from app.services.ai_usage import registrar_uso_ia
```

Logo antes de `yield decisao` (linha 1668, imediatamente após o bloco `logger.info("router_decision", ...)` que termina na linha 1667), insira:

```python
    spawn_background_task(
        registrar_uso_ia(
            origem="chat",
            ambiente="interno" if backend_escolhido == "local" else "externo",
            modelo=decisao.modelo_usado or "desconhecido",
            operacao="geracao_resposta",
            tokens_entrada=decisao.tokens_entrada,
            tokens_saida=decisao.tokens_saida,
            custo_usd=decisao.custo_estimado_usd,
            referencia_id=conversation_id or None,
        )
    )
    yield decisao
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: PASS em todos (o teste novo e todos os já existentes nesse arquivo — a instrumentação é fire-and-forget e não deve alterar nenhum `RouterDecision` já verificado pelos testes antigos).

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/router/orchestrator.py backend/tests/test_orchestrator.py
git commit -m "feat(telemetria): instrumenta geração de resposta principal no ledger de uso de IA (item B, ponto 1)"
```

---

### Task 5: Identificação de produto por imagem (pontos #8a, #8b)

**Files:**
- Modify: `backend/src/app/rag/image_identification.py:1-42` (imports), `:143-218` (`identify_product_by_image`)
- Test: `backend/tests/test_image_identification.py`

**Interfaces:**
- Consumes: `registrar_uso_ia`/`spawn_background_task`.
- Produces: nenhuma interface nova.

- [ ] **Step 1: Escrever o teste que falha — branch CLIP registra uso de IA**

Em `backend/tests/test_image_identification.py`, adicione:

```python
async def test_identify_product_clip_registra_uso_ia(monkeypatch):
    import app.rag.image_identification as image_identification_module

    captured: dict = {}

    async def fake_registrar_uso_ia(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(image_identification_module, "registrar_uso_ia", fake_registrar_uso_ia)

    clip_store = _FakeClipStore(results=[_clip_hit(0.95)])
    resultado = await identify_product_by_image(
        _IMG,
        clip_store=clip_store,
        clip_embedder=None,
        vision_client=_FakeVisionClient(),
        rag_client=_FakeRAGClient(),
        internal_confidence=0.8,
        external_confidence=0.6,
    )
    await asyncio.sleep(0)

    assert resultado.status == "encontrado_interno"
    assert captured == {
        "origem": "chat",
        "ambiente": "interno",
        "modelo": "clip",
        "operacao": "identificacao_imagem_clip",
        "tokens_entrada": None,
        "tokens_saida": None,
        "custo_usd": 0.0,
        "referencia_id": None,
        "session": None,
        "session_factory": None,
        "commit": False,
    }
```

Adicione `import asyncio` no topo do arquivo se ainda não estiver.

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest tests/test_image_identification.py -k clip_registra_uso_ia -v`
Expected: FAIL.

- [ ] **Step 3: Instrumentar a branch CLIP**

No topo de `backend/src/app/rag/image_identification.py`, junto aos imports existentes de `app.*` (linhas 32-40), adicione:

```python
from app.background_tasks import spawn_background_task
from app.services.ai_usage import registrar_uso_ia
```

No bloco "1) Catálogo interno (CLIP)" (linhas 143-164), insira a chamada logo antes do `return ImageIdentificationResult(status="encontrado_interno", ...)`:

```python
    # 1) Catálogo interno (CLIP).
    internos = await clip_store.search_by_image(clip_embedder, image_bytes, domain=_RAG_DOMAIN)
    if internos and internos[0].score >= internal_confidence:
        melhor = internos[0]
        produto_id = melhor.produto_id
        ficha = await _ficha_do_banco(sales_catalog_client, melhor.filename, produto_id)
        if ficha is not None:
            produto_id, nome, detalhes = ficha
        else:
            nome = melhor.filename
            detalhes = await _buscar_detalhes(
                rag_client, melhor.filename, recent_messages, produto_id=melhor.produto_id
            )
        spawn_background_task(
            registrar_uso_ia(
                origem="chat",
                ambiente="interno",
                modelo="clip",
                operacao="identificacao_imagem_clip",
                custo_usd=0.0,
            )
        )
        return ImageIdentificationResult(
            status="encontrado_interno",
            produto=nome,
            produto_id=produto_id,
            imagem_url=melhor.imagem_url,
            fonte="catalogo_imagens",
            detalhes=detalhes,
            confianca_interna=melhor.score,
        )
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest tests/test_image_identification.py -v`
Expected: PASS em todos.

- [ ] **Step 5: Escrever o teste que falha — branch visão externa registra uso de IA**

Primeiro, dê ao `_FakeVisionClient` (linhas ~25-33 de `test_image_identification.py`) a opção de devolver um `VisionResult` real (classe já existente em produção, `app.router.openrouter_client`) em vez de uma string pura, sem mudar o comportamento default dos testes já existentes:

```python
from app.router.openrouter_client import VisionModelIndisponivelError, VisionResult


class _FakeVisionClient:
    def __init__(
        self,
        answer: dict | None = None,
        raise_exc: Exception | None = None,
        usage: dict | None = None,
    ) -> None:
        self._answer = answer
        self._raise = raise_exc
        self._usage = usage
        self.called = False

    async def describe_image(self, image_bytes: bytes, prompt: str) -> str:
        self.called = True
        if self._raise is not None:
            raise self._raise
        content = json.dumps(self._answer)
        if self._usage is None:
            return content
        return VisionResult(
            content=content,
            prompt_tokens=self._usage.get("prompt_tokens"),
            completion_tokens=self._usage.get("completion_tokens"),
            total_tokens=self._usage.get("total_tokens"),
            cost_prompt_usd=self._usage.get("cost_prompt_usd", 0.0),
            cost_completion_usd=self._usage.get("cost_completion_usd", 0.0),
            estimated_cost_usd=self._usage.get("estimated_cost_usd", 0.0),
            model_name=self._usage.get("model_name"),
        )
```

(O import de `VisionModelIndisponivelError` já existe no arquivo — só adicione `VisionResult` ao `from app.router.openrouter_client import ...` já existente, não duplique a linha de import.)

Depois, adicione o teste:

```python
async def test_identify_product_visao_externa_registra_uso_ia(monkeypatch):
    import app.rag.image_identification as image_identification_module

    captured: dict = {}

    async def fake_registrar_uso_ia(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(image_identification_module, "registrar_uso_ia", fake_registrar_uso_ia)

    clip_store = _FakeClipStore(results=[])
    vision_client = _FakeVisionClient(
        answer={"produto": "Câmera XPTO", "e_do_portfolio": True, "confianca": 0.9},
        usage={
            "prompt_tokens": 1200,
            "completion_tokens": 40,
            "total_tokens": 1240,
            "cost_prompt_usd": 0.0008,
            "cost_completion_usd": 0.0002,
            "estimated_cost_usd": 0.001,
            "model_name": "openai/gpt-4o-mini",
        },
    )
    resultado = await identify_product_by_image(
        _IMG,
        clip_store=clip_store,
        clip_embedder=None,
        vision_client=vision_client,
        rag_client=_FakeRAGClient(),
        internal_confidence=0.8,
        external_confidence=0.6,
    )
    await asyncio.sleep(0)

    assert resultado.status == "encontrado_externo"
    assert captured == {
        "origem": "chat",
        "ambiente": "externo",
        "modelo": "openai/gpt-4o-mini",
        "operacao": "identificacao_imagem_visao_externa",
        "tokens_entrada": 1200,
        "tokens_saida": 40,
        "custo_usd": 0.001,
        "referencia_id": None,
        "session": None,
        "session_factory": None,
        "commit": False,
    }
```

- [ ] **Step 6: Rodar e confirmar que falha**

Run: `python -m pytest tests/test_image_identification.py -k visao_externa_registra_uso_ia -v`
Expected: FAIL.

- [ ] **Step 7: Instrumentar a branch de visão externa**

No bloco "2) Visão externa (fallback)" (linhas 166-181), insira a chamada depois de extrair as variáveis `v_*` e antes de `answer = _parse_vision_answer(raw)`:

```python
    # 2) Visão externa (fallback).
    try:
        raw = await vision_client.describe_image(image_bytes, _VISION_PROMPT)
    except VisionModelIndisponivelError:
        logger.info("identify_image vision_indisponivel -> nao_identificado")
        return ImageIdentificationResult(status="nao_identificado", mensagem=_NAO_IDENTIFICADO_MSG)

    v_prompt_tokens = getattr(raw, "prompt_tokens", None)
    v_comp_tokens = getattr(raw, "completion_tokens", None)
    v_total_tokens = getattr(raw, "total_tokens", None)
    v_cost_prompt = getattr(raw, "cost_prompt_usd", None)
    v_cost_comp = getattr(raw, "cost_completion_usd", None)
    v_cost_total = getattr(raw, "estimated_cost_usd", None)
    v_model_name = getattr(raw, "model_name", None)

    spawn_background_task(
        registrar_uso_ia(
            origem="chat",
            ambiente="externo",
            modelo=v_model_name or "desconhecido",
            operacao="identificacao_imagem_visao_externa",
            tokens_entrada=v_prompt_tokens,
            tokens_saida=v_comp_tokens,
            custo_usd=v_cost_total,
        )
    )

    answer = _parse_vision_answer(raw)
```

(O resto da função, abaixo desta linha, continua idêntico — não precisa ser reescrito.)

- [ ] **Step 8: Rodar e confirmar que passa**

Run: `python -m pytest tests/test_image_identification.py -v`
Expected: PASS em todos.

- [ ] **Step 9: Commit**

```bash
git add backend/src/app/rag/image_identification.py backend/tests/test_image_identification.py
git commit -m "feat(telemetria): instrumenta identificação de produto por imagem (CLIP e visão externa) no ledger de uso de IA (item B, pontos 8a-8b)"
```

---

### Task 6: ComprovanteEvaluator — julgamento por LLM e visão (pontos #9, #10a, #10b)

**Files:**
- Modify: `backend/src/app/services/comprovante_evaluator.py:1-16` (imports), `:63-78` (`__init__`), `:196-271` (`avaliar_texto`), `:273-345` (`avaliar_documento`)
- Modify: `backend/src/app/router/sales_catalog.py:552-578` (`processar_conversao_comprovante`)
- Modify: `backend/src/app/router/orchestrator.py:1288-1297`, `:1307-1316` (os dois call sites de `processar_conversao_comprovante`)
- Modify: `backend/src/app/mcp_server/b2b.py:591-596` (construção do `ComprovanteEvaluator` no MCP B2B)
- Modify: `backend/src/app/api/admin_pedidos_conversao.py:202-208`, `:288-294` (as duas construções do `ComprovanteEvaluator` no admin)
- Test: `backend/tests/test_comprovante_evaluator.py` (13 call sites de `ComprovanteEvaluator(...)` precisam do novo parâmetro — ver Step 7)
- Test: `backend/tests/test_sales_catalog.py`, `backend/tests/test_chat_conversao_reserva.py` (verifique com `grep -rln "processar_conversao_comprovante(" backend/tests/*.py` quais outros arquivos chamam essa função)
- Test: `backend/tests/test_mcp_b2b.py` (ou equivalente — `grep -rln "ComprovanteEvaluator\|converter_reserva_venda" backend/tests/*.py`)
- Test: `backend/tests/test_admin_pedidos_conversao.py` (ou equivalente)

**Interfaces:**
- Consumes: `registrar_uso_ia`/`spawn_background_task`.
- Produces: `ComprovanteEvaluator.__init__(self, llm_client=None, vision_client=None, local_vision_client=None, *, origem: str, llm_ambiente: str)` — `origem`/`llm_ambiente` passam a ser **obrigatórios** (keyword-only, sem default). `processar_conversao_comprovante(..., *, origem: str, llm_ambiente: str)` — mesma obrigatoriedade.

**Por que `origem`/`llm_ambiente` são obrigatórios:** `ComprovanteEvaluator` é construída em 4 lugares — `sales_catalog.py` (chat, este item), `mcp_server/b2b.py` (item C) e `admin_pedidos_conversao.py` ×2 (item D). Um default `"chat"` rotularia incorretamente as chamadas de B2B/Admin no ledger assim que este item for implantado. Tornar os parâmetros obrigatórios (decisão do usuário, 2026-10-08) força os 4 call sites a declarar o valor certo agora — sem adicionar nenhuma lógica de instrumentação nova para B2B/Admin além do literal correto.

- [ ] **Step 1: Escrever o teste que falha — `avaliar_texto` registra uso de IA (ambiente interno)**

Em `backend/tests/test_comprovante_evaluator.py`, veja a classe de mock LLM já usada no arquivo (procure por `mock_llm` nas linhas ~60-96) antes de escrever o teste — provavelmente um `Mock`/`AsyncMock` configurado inline. Adicione:

```python
async def test_avaliar_texto_llm_interno_registra_uso_ia(monkeypatch):
    import app.services.comprovante_evaluator as comprovante_evaluator_module

    captured: dict = {}

    async def fake_registrar_uso_ia(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(comprovante_evaluator_module, "registrar_uso_ia", fake_registrar_uso_ia)

    mock_llm = AsyncMock()
    mock_llm.generate.return_value = LLMResponse(
        text='{"comprovante_valido": true, "valor_pago": 100.0, '
        '"codigo_transacao": "E123", "justificativa": "ok"}',
        total_duration_ms=10.0,
        model_name="gemma4:12b-it-q4_K_M",
        prompt_tokens=300,
        completion_tokens=40,
        estimated_cost_usd=0.0,
    )
    evaluator = ComprovanteEvaluator(
        llm_client=mock_llm, origem="chat", llm_ambiente="interno"
    )

    await evaluator.avaliar_texto(
        texto="Comprovante PIX de pagamento, valor R$ 100,00", valor_devido=Decimal("100.00")
    )
    await asyncio.sleep(0)

    assert captured == {
        "origem": "chat",
        "ambiente": "interno",
        "modelo": "gemma4:12b-it-q4_K_M",
        "operacao": "comprovante_texto_llm",
        "tokens_entrada": 300,
        "tokens_saida": 40,
        "custo_usd": 0.0,
        "referencia_id": None,
        "session": None,
        "session_factory": None,
        "commit": False,
    }
```

Confira os imports já existentes no topo de `test_comprovante_evaluator.py` (`Decimal`, `AsyncMock`/`Mock`, `LLMResponse`) e adicione os que faltarem, incluindo `import asyncio`.

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest tests/test_comprovante_evaluator.py -k avaliar_texto_llm_interno_registra_uso_ia -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'origem'` (o construtor ainda não aceita esses parâmetros).

- [ ] **Step 3: Adicionar `origem`/`llm_ambiente` ao construtor e instrumentar `avaliar_texto`**

No topo de `backend/src/app/services/comprovante_evaluator.py`, junto aos imports existentes (depois da linha 14, `from app.router.prompt_safety import wrap_untrusted`), adicione:

```python
from app.background_tasks import spawn_background_task
from app.services.ai_usage import registrar_uso_ia
```

Substitua `__init__` (linhas 63-78) por:

```python
    def __init__(
        self,
        llm_client: Any = None,
        vision_client: Any = None,
        local_vision_client: Any = None,
        *,
        origem: str,
        llm_ambiente: str,
    ):
        self.llm_client = llm_client
        # `vision_client`: visão externa (OpenRouter), último recurso.
        # `local_vision_client`: visão local (Ollama, `describe_image`),
        # tentada antes — decisão de custo mínimo registrada em
        # docs/ARCHITECTURE.md §4 (2026-10-06).
        self.vision_client = vision_client
        self.local_vision_client = local_vision_client
        # `origem`/`llm_ambiente`: dimensões do ledger de uso de IA
        # (docs/superpowers/specs/2026-10-08-ledger-uso-ia-item-b-origem-chat-design.md
        # §4.3) — obrigatórios porque esta classe é compartilhada por chat
        # (item B), MCP B2B (item C) e admin (item D); um default
        # mascararia a origem real de quem chama.
        self.origem = origem
        self.llm_ambiente = llm_ambiente
```

Em `avaliar_texto` (linhas 236-265), insira a chamada logo após obter `raw_text`:

```python
            try:
                res = None
                if hasattr(self.llm_client, "generate"):
                    res = await self.llm_client.generate(prompt)
                elif hasattr(self.llm_client, "chat"):
                    res = await self.llm_client.chat(prompt)

                raw_text = res.text if hasattr(res, "text") else str(res)
                spawn_background_task(
                    registrar_uso_ia(
                        origem=self.origem,
                        ambiente=self.llm_ambiente,
                        modelo=getattr(res, "model_name", None) or "desconhecido",
                        operacao="comprovante_texto_llm",
                        tokens_entrada=getattr(res, "prompt_tokens", None),
                        tokens_saida=getattr(res, "completion_tokens", None),
                        custo_usd=getattr(res, "estimated_cost_usd", None),
                    )
                )
                # Remove cercas de markdown
                cleaned = re.sub(r"^```(?:json)?\s*", "", raw_text.strip(), flags=re.MULTILINE)
                cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()

                parsed = json.loads(cleaned)
                valor_pago = Decimal(str(parsed.get("valor_pago", 0.0)))
                codigo_transacao = parsed.get("codigo_transacao")
                divergencia = valor_pago - valor_devido
                valido = bool(parsed.get("comprovante_valido")) and (
                    abs(divergencia) <= Decimal("0.01")
                )

                return ParecerComprovante(
                    valido=valido,
                    valor_pago=valor_pago,
                    divergencia=divergencia,
                    justificativa=parsed.get("justificativa", ""),
                    codigo_transacao=codigo_transacao,
                    raw_json=parsed,
                    prompt_tokens=getattr(res, "prompt_tokens", None),
                    completion_tokens=getattr(res, "completion_tokens", None),
                )
            except Exception as exc:
                logger.warning(
                    "Falha na interpretação via LLM (%s), acionando fallback heurístico.", exc
                )
```

- [ ] **Step 4: Atualizar os 13 call sites de `ComprovanteEvaluator(...)` em `test_comprovante_evaluator.py`**

Run: `grep -n "ComprovanteEvaluator(" tests/test_comprovante_evaluator.py`

Para cada ocorrência (as 13 já listadas na investigação desta task — linhas aproximadas 21, 37, 52, 70, 96, 106, 116, 140, 172, 203, 236, 249, 269 — confirme os números reais com o grep acima, podem ter mudado com o Step 1), adicione `, origem="chat", llm_ambiente="interno"` aos argumentos — exceto o teste escrito no Step 1, que já os tem. Exemplo de transformação:

```python
# Antes:
evaluator = ComprovanteEvaluator()
# Depois:
evaluator = ComprovanteEvaluator(origem="chat", llm_ambiente="interno")

# Antes:
evaluator = ComprovanteEvaluator(llm_client=mock_llm)
# Depois:
evaluator = ComprovanteEvaluator(llm_client=mock_llm, origem="chat", llm_ambiente="interno")
```

Para as 3 ocorrências com múltiplos argumentos já quebrados em várias linhas (aprox. linhas 140, 172, 203 pelo grep original), adicione as duas novas linhas de keyword-arg dentro dos parênteses já existentes, mantendo a formatação.

- [ ] **Step 5: Rodar e confirmar que passa**

Run: `python -m pytest tests/test_comprovante_evaluator.py -v`
Expected: PASS em todos (os 13 testes antigos + o novo do Step 1).

- [ ] **Step 6: Escrever o teste que falha — `avaliar_texto` com `llm_ambiente="externo"`**

```python
async def test_avaliar_texto_llm_externo_registra_uso_ia(monkeypatch):
    import app.services.comprovante_evaluator as comprovante_evaluator_module

    captured: dict = {}

    async def fake_registrar_uso_ia(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(comprovante_evaluator_module, "registrar_uso_ia", fake_registrar_uso_ia)

    mock_llm = AsyncMock()
    mock_llm.generate.return_value = LLMResponse(
        text='{"comprovante_valido": true, "valor_pago": 100.0, '
        '"codigo_transacao": "E123", "justificativa": "ok"}',
        total_duration_ms=10.0,
        model_name="meta-llama/llama-3",
        prompt_tokens=300,
        completion_tokens=40,
        estimated_cost_usd=0.002,
    )
    evaluator = ComprovanteEvaluator(
        llm_client=mock_llm, origem="chat", llm_ambiente="externo"
    )

    await evaluator.avaliar_texto(
        texto="Comprovante PIX de pagamento, valor R$ 100,00", valor_devido=Decimal("100.00")
    )
    await asyncio.sleep(0)

    assert captured["ambiente"] == "externo"
    assert captured["custo_usd"] == 0.002
```

Esse teste já passa sem mudança de código (o `self.llm_ambiente` já é repassado como veio) — é só uma confirmação de que a inferência de ambiente é responsabilidade exclusiva do chamador, não do evaluator. Rode para confirmar:

Run: `python -m pytest tests/test_comprovante_evaluator.py -k avaliar_texto_llm_externo -v`
Expected: PASS direto (sem precisar editar produção de novo).

- [ ] **Step 7: Escrever o teste que falha — `avaliar_documento` registra uso de IA (visão local e externa)**

```python
async def test_avaliar_documento_visao_local_registra_uso_ia(monkeypatch):
    import app.services.comprovante_evaluator as comprovante_evaluator_module

    captured: dict = {}

    async def fake_registrar_uso_ia(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(comprovante_evaluator_module, "registrar_uso_ia", fake_registrar_uso_ia)

    local_vision = AsyncMock()
    local_vision.describe_image.return_value = LocalVisionResult(
        content='{"comprovante_valido": true, "valor_pago": 100.0, '
        '"codigo_transacao": "E123", "justificativa": "ok"}',
        prompt_tokens=500,
        completion_tokens=60,
        model_name="gemma4:12b-it-q4_K_M-vision",
    )
    evaluator = ComprovanteEvaluator(
        local_vision_client=local_vision, origem="chat", llm_ambiente="interno"
    )

    await evaluator.avaliar_documento(
        conteudo=b"fake-image-bytes",
        nome_arquivo_ou_extensao="comprovante.png",
        valor_devido=Decimal("100.00"),
    )
    await asyncio.sleep(0)

    assert captured == {
        "origem": "chat",
        "ambiente": "interno",
        "modelo": "gemma4:12b-it-q4_K_M-vision",
        "operacao": "comprovante_visao_interna",
        "tokens_entrada": 500,
        "tokens_saida": 60,
        "custo_usd": 0.0,
        "referencia_id": None,
        "session": None,
        "session_factory": None,
        "commit": False,
    }


async def test_avaliar_documento_visao_externa_registra_uso_ia(monkeypatch):
    import app.services.comprovante_evaluator as comprovante_evaluator_module

    captured: dict = {}

    async def fake_registrar_uso_ia(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(comprovante_evaluator_module, "registrar_uso_ia", fake_registrar_uso_ia)

    external_vision = AsyncMock()
    external_vision.describe_image.return_value = VisionResult(
        content='{"comprovante_valido": true, "valor_pago": 100.0, '
        '"codigo_transacao": "E123", "justificativa": "ok"}',
        prompt_tokens=800,
        completion_tokens=70,
        total_tokens=870,
        cost_prompt_usd=0.001,
        cost_completion_usd=0.0005,
        estimated_cost_usd=0.0015,
        model_name="openai/gpt-4o-mini",
    )
    evaluator = ComprovanteEvaluator(
        vision_client=external_vision, origem="chat", llm_ambiente="interno"
    )

    await evaluator.avaliar_documento(
        conteudo=b"fake-image-bytes",
        nome_arquivo_ou_extensao="comprovante.png",
        valor_devido=Decimal("100.00"),
    )
    await asyncio.sleep(0)

    assert captured == {
        "origem": "chat",
        "ambiente": "externo",
        "modelo": "openai/gpt-4o-mini",
        "operacao": "comprovante_visao_externa",
        "tokens_entrada": 800,
        "tokens_saida": 70,
        "custo_usd": 0.0015,
        "referencia_id": None,
        "session": None,
        "session_factory": None,
        "commit": False,
    }
```

Adicione `from app.router.ollama_client import LocalVisionResult` e `from app.router.openrouter_client import VisionResult` aos imports de `test_comprovante_evaluator.py` (verifique se já não existem antes de duplicar).

- [ ] **Step 8: Rodar e confirmar que falham**

Run: `python -m pytest tests/test_comprovante_evaluator.py -k "visao_local_registra_uso_ia or visao_externa_registra_uso_ia" -v`
Expected: FAIL — `captured == {}` em ambos (vision loop ainda não instrumentado).

- [ ] **Step 9: Instrumentar o loop de visão em `avaliar_documento`**

Substitua o loop `for vision_client in (self.local_vision_client, self.vision_client):` (linhas 307-335) por:

```python
            for vision_client in (self.local_vision_client, self.vision_client):
                if not vision_client:
                    continue
                try:
                    raw_vision = await vision_client.describe_image(conteudo, prompt_vision)
                    ambiente_vision = (
                        "interno" if vision_client is self.local_vision_client else "externo"
                    )
                    spawn_background_task(
                        registrar_uso_ia(
                            origem=self.origem,
                            ambiente=ambiente_vision,
                            modelo=getattr(raw_vision, "model_name", None) or "desconhecido",
                            operacao=(
                                "comprovante_visao_interna"
                                if ambiente_vision == "interno"
                                else "comprovante_visao_externa"
                            ),
                            tokens_entrada=getattr(raw_vision, "prompt_tokens", None),
                            tokens_saida=getattr(raw_vision, "completion_tokens", None),
                            custo_usd=(
                                getattr(raw_vision, "cost_prompt_usd", 0.0)
                                + getattr(raw_vision, "cost_completion_usd", 0.0)
                            ),
                        )
                    )
                    cleaned = re.sub(
                        r"^```(?:json)?\s*", "", raw_vision.strip(), flags=re.MULTILINE
                    )
                    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()
                    parsed = json.loads(cleaned)
                    valor_pago = Decimal(str(parsed.get("valor_pago", 0.0)))
                    codigo = parsed.get("codigo_transacao")
                    divergencia = valor_pago - valor_devido
                    valido = bool(parsed.get("comprovante_valido")) and (
                        abs(divergencia) <= Decimal("0.01")
                    )

                    return ParecerComprovante(
                        valido=valido,
                        valor_pago=valor_pago,
                        divergencia=divergencia,
                        justificativa=parsed.get("justificativa", ""),
                        codigo_transacao=codigo,
                        raw_json=parsed,
                        prompt_tokens=getattr(raw_vision, "prompt_tokens", None),
                        completion_tokens=getattr(raw_vision, "completion_tokens", None),
                    )
                except Exception as exc:
                    logger.warning("Falha na visão (%s), tentando próximo nível do fallback.", exc)
```

Note que `custo_usd` usa `getattr(raw_vision, "cost_prompt_usd", 0.0)` com fallback `0.0` (não `None`) — diferente dos outros pontos — porque `LocalVisionResult` genuinamente não tem esses atributos (visão local é sempre grátis, um "não existe" que já sabemos valer zero), enquanto nos outros pontos um atributo ausente significa "não foi possível capturar" (`None`). Essa distinção é intencional, não inconsistência.

- [ ] **Step 10: Rodar e confirmar que passam**

Run: `python -m pytest tests/test_comprovante_evaluator.py -v`
Expected: PASS em todos.

- [ ] **Step 11: Atualizar os 4 call sites de produção**

Em `backend/src/app/router/sales_catalog.py`, `processar_conversao_comprovante` (linhas 552-578):

```python
async def processar_conversao_comprovante(
    session: AsyncSession,
    pedido: Pedido,
    texto_comprovante: str,
    llm_client: Any = None,
    comprovante_bytes: bytes | None = None,
    nome_arquivo: str | None = None,
    vision_client: Any = None,
    local_vision_client: Any = None,
    *,
    origem: str,
    llm_ambiente: str,
) -> tuple[bool, str, ParecerComprovante]:
    """Avalia o comprovante de pagamento via ComprovanteEvaluator e converte o status do pedido.

    `local_vision_client`/`vision_client` (achado de 2026-10-06, religado
    aqui — antes só o fluxo administrativo passava visão): sem eles, uma
    foto de comprovante malfeita (ângulo/luz, comum vindo do celular do
    cliente) que o OCR não consegue ler nunca tinha nenhuma tentativa de
    visão no chat.

    `origem`/`llm_ambiente` são obrigatórios e repassados direto ao
    `ComprovanteEvaluator` — ver docs/superpowers/specs/
    2026-10-08-ledger-uso-ia-item-b-origem-chat-design.md §4.3.
    """
    valor_devido = sum(
        (item.preco_unitario * item.quantidade for item in pedido.itens),
        Decimal("0.00"),
    )
    evaluator = ComprovanteEvaluator(
        llm_client=llm_client,
        vision_client=vision_client,
        local_vision_client=local_vision_client,
        origem=origem,
        llm_ambiente=llm_ambiente,
    )
```

(O resto da função, abaixo dessa construção, continua idêntico.)

Em `backend/src/app/router/orchestrator.py`, nos dois call sites de `processar_conversao_comprovante` (linhas 1288-1297 e 1307-1316), adicione os dois novos argumentos em ambos usando a mesma inferência de `llm_to_use` já calculada na linha 1275:

```python
                        sucesso, texto_resp, parecer_res = await processar_conversao_comprovante(
                            session=session,
                            pedido=pedido,
                            texto_comprovante=message,
                            llm_client=llm_to_use,
                            comprovante_bytes=comprovante_bytes,
                            nome_arquivo=comprovante_filename,
                            vision_client=external_client,
                            local_vision_client=local_client,
                            origem="chat",
                            llm_ambiente="interno" if llm_to_use is local_client else "externo",
                        )
```

(Aplique a mesma adição de `origem="chat", llm_ambiente=...` ao segundo call site, linha ~1307, que usa `session=session_ctx` em vez de `session=session`.)

Em `backend/src/app/mcp_server/b2b.py` (linhas 591-596):

```python
                llm_client = local_client if local_client is not None else external_client
                evaluator = ComprovanteEvaluator(
                    llm_client=llm_client,
                    vision_client=external_client,
                    local_vision_client=local_client,
                    origem="b2b",
                    llm_ambiente="interno" if llm_client is local_client else "externo",
                )
```

Em `backend/src/app/api/admin_pedidos_conversao.py`, nas duas ocorrências (linhas ~202-208 e ~288-294), substitua:

```python
    llm_client = getattr(request.app.state, "local_client", None) or getattr(
        request.app.state, "external_client", None
    )
    vision_client = getattr(request.app.state, "external_client", None)
    local_vision_client = getattr(request.app.state, "local_client", None)
    evaluator = ComprovanteEvaluator(
        llm_client=llm_client, vision_client=vision_client, local_vision_client=local_vision_client
    )
```

por:

```python
    local_client = getattr(request.app.state, "local_client", None)
    external_client = getattr(request.app.state, "external_client", None)
    llm_client = local_client if local_client is not None else external_client
    evaluator = ComprovanteEvaluator(
        llm_client=llm_client,
        vision_client=external_client,
        local_vision_client=local_client,
        origem="admin",
        llm_ambiente="interno" if llm_client is local_client else "externo",
    )
```

(Isso é um refatoro que preserva o comportamento exato — `X or Y` e `X if X is not None else Y` são equivalentes aqui porque `local_client`/`external_client` só valem `None` ou uma instância de cliente, nunca um valor falsy diferente de `None`. A mudança de nome de variável — de inline `getattr(...)` para `local_client`/`external_client` nomeados — é só para poder fazer a comparação de identidade do `llm_ambiente`.)

- [ ] **Step 12: Atualizar os testes que chamam `processar_conversao_comprovante` e os dos outros 3 call sites**

Run: `grep -rln "processar_conversao_comprovante(" backend/tests/*.py`

Em cada chamada encontrada, adicione `origem="chat", llm_ambiente="interno"` (ou `"externo"`, se o teste especificamente exercitar o backend externo — confira o que o teste já configura como `llm_client` antes de decidir).

Run: `grep -rln "ComprovanteEvaluator(" backend/tests/*.py` (deve retornar só `test_comprovante_evaluator.py`, já tratado no Step 4 — se aparecer outro arquivo, ele também precisa da mesma atualização).

Run: `grep -rln "converter_reserva_venda\|post_converter_auto_admin\|post_converter_etapa1" backend/tests/*.py` para achar os testes do MCP B2B e do admin — eles não constroem `ComprovanteEvaluator` diretamente, então não precisam de mudança de código, mas rode-os para confirmar que a mudança de assinatura não quebrou nada por outro caminho.

- [ ] **Step 13: Rodar a suíte completa do backend**

Run: `cd backend && python -m pytest -x -q`
Expected: PASS em todos os testes (não só os arquivos tocados por esta task — a mudança de assinatura de `ComprovanteEvaluator`/`processar_conversao_comprovante` é cross-cutting).

- [ ] **Step 14: Commit**

```bash
git add backend/src/app/services/comprovante_evaluator.py backend/src/app/router/sales_catalog.py backend/src/app/router/orchestrator.py backend/src/app/mcp_server/b2b.py backend/src/app/api/admin_pedidos_conversao.py backend/tests/test_comprovante_evaluator.py
git add -u backend/tests/
git commit -m "feat(telemetria): instrumenta julgamento de comprovante por LLM e visão no ledger de uso de IA (item B, pontos 9-10); exige origem/llm_ambiente explícitos em todos os 4 call sites de ComprovanteEvaluator"
```

---

### Task 7: Documentação final

**Files:**
- Modify: `docs/ROADMAP.md` (marcar item B como `[x]`)
- Modify: `docs/ARCHITECTURE.md` (seção de telemetria/ledger de uso de IA, se existir uma após o item A — verifique com `grep -n "ledger\|AiUsageEvent\|registrar_uso_ia" docs/ARCHITECTURE.md`)
- Verify: `docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md`

- [ ] **Step 1: Verificar se algum prompt mapeado mudou**

A mudança em `_perguntar_systemone_jev` (Task 1) só adiciona captura de metadados da resposta (`model`/`usage`) — não altera o `json={...}` enviado na requisição. Confirme lendo o diff final da Task 1 (`git show <hash-da-task-1> -- backend/src/app/router/openrouter_client.py`) que o payload de request (chave `"questions"`) é idêntico ao anterior. Se for, nenhuma entrada de `docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md` precisa mudar — registre isso no commit desta task em vez de editar o arquivo.

- [ ] **Step 2: Marcar item B como concluído em `docs/ROADMAP.md`**

Localize a linha (texto exato, já registrado no roadmap pelo item A):

```
- [ ] **B — Origem Chat.** Conecta todos os pontos de uso de IA que
      passam por `app.api.chat`/`app.router.orchestrator` à função de A:
      geração de texto local/externo, identificação de produto por imagem
      (CLIP interno x visão externa), comprovante por chat (OCR + visão +
      julgamento), e o classificador/monitor de tom via TypeSafe Jev
      (`classify_intent_jev`/`classify_tone_jev` — hoje sem nenhuma
      métrica capturada).
```

Troque `- [ ]` por `- [x]` nessa linha (só o checkbox — o texto descritivo permanece, já está correto).

- [ ] **Step 3: Registrar a decisão de `origem`/`llm_ambiente` obrigatórios em `docs/ARCHITECTURE.md`**

Se existir uma seção de telemetria/ledger criada pelo item A (busque com o grep do Step 1), adicione um parágrafo curto registrando: `ComprovanteEvaluator` agora exige `origem`/`llm_ambiente` no construtor porque é compartilhada por chat (B), B2B (C) e admin (D) — decisão tomada durante a implementação do item B para evitar rotulagem incorreta no ledger antes dos itens C/D serem desenhados. Se a seção não existir ainda (o item A pode não ter criado uma seção dedicada), não crie uma nova seção agora — essa decisão de documentação pertence ao item E (painel), quando o ledger como um todo for documentado em `ARCHITECTURE.md`; registre só a nota no `ROADMAP.md` do Step 2 e deixe uma frase no corpo do commit desta task explicando a omissão.

- [ ] **Step 4: Commit**

```bash
git add docs/ROADMAP.md docs/ARCHITECTURE.md
git commit -m "docs: marca item B (origem Chat) do ledger de uso de IA como concluído"
```
