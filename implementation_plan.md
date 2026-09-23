# Suporte ao TypeSafe Jev no Roteador com Alternância no Admin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar o **TypeSafe Jev (via OpenRouter)** como opção configurável para o Roteador de Intenção e Domínios (Fase 1), permitindo alternância dinâmica em runtime entre o **Método Clássico** (Heurística + LLM Local Ollama) e o **TypeSafe Jev** (OpenRouter) através da página administrativa de parâmetros de execução, com fallback automático e telemetria transparente.

**Architecture:** O parâmetro `intent_router_provider` é gerenciado em memória no `app.state` do FastAPI via `RuntimeSettings` (`GET`/`PUT /api/admin/runtime-settings`). No fluxo do chat (`app/api/chat.py`), o provedor ativo é obtido do estado e injetado em `orchestrator.handle_message(...)`, que o repassa para `classifier.classify(...)`. No modo `jev_openrouter`, o classificador aciona o modelo `typesafe/jev-latest` (TypeSafe Jev, um modelo "System One" de decisão estruturada) através do **endpoint dedicado do OpenRouter `POST /api/v1/systemone`** — não o `/chat/completions` genérico usado pelo restante do `OpenRouterClient` — com um corpo `{model, state, questions}` (pergunta única do tipo `choice` cobrindo os 5 domínios) e resposta já tipada (`answers.dominio.choice`/`.confidence`), sem geração de texto livre nem parsing de JSON solto. Reaproveita a mesma chave (`EXTERNAL_MODEL_API_KEY`) e `base_url` já configurados para o modelo externo de chat. Em caso de falha de rede/API externa, o sistema degrada graciosamente para a heurística local sem interromper o atendimento. A decisão do roteador é registrada na telemetria SSE (`ChatDoneEventData`) e exibida no painel administrativo e no modal de chat. Decisão de arquitetura registrada em `docs/ARCHITECTURE.md` §5 (2026-09-23) e item correspondente em `docs/ROADMAP.md` ("Extra fora do MVP — Gerenciador de Modelos Locais (Ollama)").

> **Nota de verificação:** este plano foi revisado contra a API real do TypeSafe Jev via OpenRouter (`docs.typesafe.ai`, `openrouter.ai/~typesafe/jev-latest`, `openrouter.ai/docs/api/api-reference/systemone/submit-a-system-one-request.md`) — a versão anterior deste documento assumia incorretamente uma chamada `/chat/completions` com prompt em texto livre, que não funcionaria contra o modelo real (`output_modalities: ["decisions"]`, `has_text_output: false`). As assinaturas de função abaixo (`handle_message`, `RouterDecision`, etc.) refletem o estado do código em 2026-09-23 — **reconfirme contra o arquivo real antes de implementar cada task**, já que o código evolui entre o momento em que este plano foi escrito e sua execução.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, `httpx`, Next.js 14 (App Router), TypeScript, Tailwind CSS, Pytest.

---

## Global Constraints

- **Padrão Default Preservado:** O provedor padrão do roteador inicializa como `"heuristica_llm"`, garantindo total compatibilidade regressiva e independência de rede externa no boot padrão.
- **Desacoplamento de Camadas:** As funções em `app/router/` (`classifier.py`, `orchestrator.py`) permanecem puras e desacopladas do framework FastAPI — nenhuma função de domínio acessa `request.app.state` diretamente; dependências são sempre injetadas como parâmetros.
- **Resiliência e Fallback Gracioso:** Qualquer falha na chamada ao OpenRouter/Jev (timeout, HTTP 4xx/5xx, chave de API ausente ou payload malformado) degrada imediatamente para a heurística local de palavras-chave, emitindo warning no log estruturado e nunca derrubando a requisição do usuário com erro 500/503.
- **Modelo e Endpoint Oficiais do Jev:** Chamadas para o Jev usam o **endpoint dedicado do OpenRouter `POST {base_url}/systemone`** (não `/chat/completions`), identificador de modelo `typesafe/jev-latest` (configurável via `JEV_MODEL_NAME`), com uma única pergunta de escolha (`type: "choice"`) cobrindo exatamente os 5 domínios do sistema: `vendas`, `suporte`, `atendimento`, `agendamento` e `fora_escopo`. Resposta lida de `answers.dominio.choice`/`answers.dominio.confidence` — a API já devolve um resultado tipado, não texto para parsear.
- **Complexidade Local:** A avaliação de complexidade (`baixa` ou `alta`) continua utilizando o cálculo heurístico rápido local (`_heuristic_complexity`), garantindo resposta instantânea e sem requisições adicionais.
- **Telemetria de Ponta a Ponta:** O provedor utilizado (`heuristica_llm` ou `jev_openrouter`) deve ser propagado pelo `RouterDecision`, incluído no evento `done` (`ChatDoneEventData`) do stream SSE e disponibilizado na UI do chat.

---

## Review Focus

1. **Injeção limpa de dependência:** Garantir que `intent_router_provider` seja extraído de `request.app.state` em `chat.py` e repassado explicitamente para `handle_message` e `classify`, sem acoplamento estático.
2. **Degradação graciosa em timeout/erro:** Simular falha de conexão HTTP na chamada ao Jev e assegurar que o classificador retorna o domínio heurístico sem levantar exceção não tratada.
3. **Persistência em memória no Admin:** Garantir que `PUT /api/admin/runtime-settings` atualiza `intent_router_provider` e reflete imediatamente no próximo `GET` e nas próximas mensagens de chat.
4. **Validação de payload inválido no PUT:** Garantir que strings fora de `["heuristica_llm", "jev_openrouter"]` resultem em HTTP 422 Unprocessable Entity.
5. **Telemetria completa no frontend:** Confirmar que o evento SSE `done` inclui `router_provider` sem quebrar clientes legados.

---

## File Structure

**Modificar (Backend):**
- `backend/src/app/models/runtime_settings.py`: Adiciona `intent_router_provider` a `RuntimeSettingsResponse` e `RuntimeSettingsUpdateRequest`.
- `backend/src/app/api/runtime_settings.py`: Gerencia `intent_router_provider` no `app.state` em `_build_response` e `update_runtime_settings`.
- `backend/src/app/config.py`: Adiciona `jev_model_name: str = "typesafe/jev-latest"` a `Settings` (env `JEV_MODEL_NAME`, já em `.env.example`).
- `backend/src/app/main.py`: Inicializa `app.state.intent_router_provider = "heuristica_llm"` e passa `jev_model=settings.jev_model_name` na construção de `app.state.external_client` (`OpenRouterClient(...)`, linha ~58 de `main.py`).
- `backend/src/app/router/openrouter_client.py`: Adiciona parâmetro de construtor `jev_model` e método `classify_intent_jev(...)`, que chama o endpoint dedicado `POST {base_url}/systemone` (distinto de `/chat/completions`).
- `backend/src/app/router/classifier.py`: Atualiza `classify(...)` e cria `_classify_with_jev(...)` com fallback gracioso.
- `backend/src/app/models/chat.py`: Adiciona `router_provider: str` a `ChatDoneEventData`.
- `backend/src/app/router/orchestrator.py`: Adiciona `router_provider: str` a `RouterDecision`, recebe `intent_router_provider` em `handle_message` e repassa para `classify`.
- `backend/src/app/api/chat.py`: Injeta `intent_router_provider` e preenche `ChatDoneEventData.router_provider`.

**Testes (Backend):**
- `backend/tests/test_runtime_settings_api.py`: Testa leitura e atualização de `intent_router_provider`.
- `backend/tests/test_openrouter_client.py`: Testa chamada formatada para `typesafe/jev-latest`.
- `backend/tests/test_classifier.py`: Testa classificação via Jev e fallback gracioso em erro.
- `backend/tests/test_orchestrator.py`: Testa fluxo completo com telemetria do roteador.
- `backend/tests/test_chat_api.py`: Testa evento SSE `done` contendo `router_provider`.

**Modificar (Frontend):**
- `frontend/lib/types/runtimeSettings.ts`: Adiciona `intent_router_provider` na tipagem de `RuntimeSettings`.
- `frontend/lib/types/chat.ts`: Adiciona `router_provider?: string` em `ChatMetrics` e `ChatDoneEventData`.
- `frontend/components/admin/RuntimeSettingsForm.tsx`: Adiciona controle visual (radio buttons estilizados) para alternar o classificador de intenção.
- `frontend/components/chat/ChatModal.tsx`: Repassa `router_provider` para as métricas da mensagem.
- `frontend/components/chat/MessageBubble.tsx`: Exibe o provedor do roteador no painel expansível de métricas.

---

## Task 1: Parâmetros de Execução em Runtime — Schema e Endpoint

**Files:**
- Modify: `backend/src/app/models/runtime_settings.py`
- Modify: `backend/src/app/api/runtime_settings.py`
- Modify: `backend/src/app/main.py`
- Test: `backend/tests/test_runtime_settings_api.py`

**Interfaces:**
- Produces: `RuntimeSettingsResponse.intent_router_provider: Literal["heuristica_llm", "jev_openrouter"] = "heuristica_llm"`; `RuntimeSettingsUpdateRequest.intent_router_provider: Literal["heuristica_llm", "jev_openrouter"] | None = None`.

- [ ] **Step 1: Write failing tests in `test_runtime_settings_api.py`**

```python
# backend/tests/test_runtime_settings_api.py (adicionar ao final)
def test_get_retorna_intent_router_provider_default():
    app, *_ = _build_default_app()
    client = TestClient(app)

    response = client.get("/api/admin/runtime-settings")
    assert response.status_code == 200
    data = response.json()
    assert data["intent_router_provider"] == "heuristica_llm"


def test_put_atualiza_intent_router_provider():
    app, *_ = _build_default_app()
    client = TestClient(app)

    response = client.put(
        "/api/admin/runtime-settings",
        json={"intent_router_provider": "jev_openrouter"},
    )
    assert response.status_code == 200
    assert response.json()["intent_router_provider"] == "jev_openrouter"
    assert app.state.intent_router_provider == "jev_openrouter"

    # Confirma persistência em subsequente GET
    get_resp = client.get("/api/admin/runtime-settings")
    assert get_resp.json()["intent_router_provider"] == "jev_openrouter"


def test_put_rejeita_intent_router_provider_invalido():
    app, *_ = _build_default_app()
    client = TestClient(app)

    response = client.put(
        "/api/admin/runtime-settings",
        json={"intent_router_provider": "provedor_inexistente"},
    )
    assert response.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_runtime_settings_api.py -k "intent_router_provider" -v`
Expected: FAIL (campos ausentes no modelo e retorno da API).

- [ ] **Step 3: Implement changes in models, API and main**

Em `backend/src/app/models/runtime_settings.py`:
```python
from typing import Literal

IntentRouterProvider = Literal["heuristica_llm", "jev_openrouter"]

# Em RuntimeSettingsResponse:
    intent_router_provider: IntentRouterProvider = Field(
        default="heuristica_llm",
        description="Provedor ativo para classificação de intenção do roteador.",
    )

# Em RuntimeSettingsUpdateRequest:
    intent_router_provider: IntentRouterProvider | None = None
```

Em `backend/src/app/api/runtime_settings.py`:
```python
def _build_response(request: Request) -> RuntimeSettingsResponse:
    local_client, external_client, qdrant_client = _get_clients(request)
    intent_provider = getattr(request.app.state, "intent_router_provider", "heuristica_llm")
    return RuntimeSettingsResponse(
        ...
        intent_router_provider=intent_provider,
    )

# No update_runtime_settings:
    if "intent_router_provider" in campos:
        request.app.state.intent_router_provider = campos["intent_router_provider"]
```

Em `backend/src/app/main.py`:
```python
app.state.intent_router_provider = "heuristica_llm"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_runtime_settings_api.py -v`
Expected: PASS em todos os testes.

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/models/runtime_settings.py backend/src/app/api/runtime_settings.py backend/src/app/main.py backend/tests/test_runtime_settings_api.py
git commit -m "feat(runtime-settings): adiciona intent_router_provider para alternância de roteador"
```

---

## Task 2: Cliente OpenRouter para Chamadas do TypeSafe Jev (endpoint System One)

**Referência da API (verificada, 2026-09-23):**
`docs.typesafe.ai` + `openrouter.ai/docs/api/api-reference/systemone/submit-a-system-one-request.md`
— o Jev **não** é um modelo de chat comum: `output_modalities: ["decisions"]`,
`has_text_output: false`. É chamado por um endpoint próprio do OpenRouter,
`POST https://openrouter.ai/api/v1/systemone` (mesma auth Bearer/chave dos
demais clientes OpenRouter do projeto), com corpo estruturado:

```json
{
  "model": "typesafe/jev-latest",
  "state": "texto da mensagem + contexto recente",
  "questions": {
    "dominio": {
      "type": "choice",
      "instructions": "Classifique a mensagem do cliente em um dos domínios de atendimento.",
      "criteria": {
        "vendas": "Interesse em comprar, orçamento, preço ou catálogo de produtos.",
        "suporte": "Produto com defeito, erro ou problema técnico já adquirido.",
        "atendimento": "Nota fiscal, troca, devolução, cancelamento ou reclamação.",
        "agendamento": "Quer marcar, remarcar ou confirmar uma visita/horário.",
        "fora_escopo": "Não se encaixa claramente em nenhuma opção acima."
      }
    }
  }
}
```

E resposta já tipada (sem texto livre para parsear):

```json
{
  "answers": {
    "dominio": {
      "type": "choice",
      "choice": "vendas",
      "confidence": 0.95,
      "probabilities": {"vendas": 0.95, "suporte": 0.03, "...": "..."}
    }
  },
  "usage": {"input_tokens": 120, "output_tokens": 12, "cost": 0.000005}
}
```

**Files:**
- Modify: `backend/src/app/router/openrouter_client.py`
- Test: `backend/tests/test_openrouter_client.py`

**Interfaces:**
- `OpenRouterClient.__init__` ganha parâmetro `jev_model: str = ""`.
- Produces: `OpenRouterClient.classify_intent_jev(message: str, recent_messages: list[str] | None = None) -> tuple[str, float]`
  Retorna tupla `(dominio, confianca)`.

- [ ] **Step 1: Write failing tests in `test_openrouter_client.py`**

```python
# backend/tests/test_openrouter_client.py (adicionar ao arquivo existente)
import pytest
import httpx
from app.router.openrouter_client import OpenRouterClient

@pytest.mark.asyncio
async def test_classify_intent_jev_sucesso():
    captured_request: dict = {}

    def mock_handler(request: httpx.Request) -> httpx.Response:
        captured_request["url"] = str(request.url)
        captured_request["body"] = httpx.Request(request.method, request.url).read()
        data = {
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
        domain, confidence = await client.classify_intent_jev(
            message="quanto custa o produto?", recent_messages=[]
        )
        assert domain == "vendas"
        assert confidence == 0.95
        # Endpoint dedicado, distinto de /chat/completions
        assert captured_request["url"].endswith("/systemone")


@pytest.mark.asyncio
async def test_classify_intent_jev_choice_fora_do_enum_vira_fora_escopo():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        data = {"answers": {"dominio": {"type": "choice", "choice": "lixo", "confidence": 0.4}}}
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
        domain, _ = await client.classify_intent_jev(message="teste", recent_messages=[])
        assert domain == "fora_escopo"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_openrouter_client.py -k "classify_intent_jev" -v`
Expected: FAIL (`TypeError` no construtor — `jev_model` não existe — e/ou `AttributeError: 'OpenRouterClient' object has no attribute 'classify_intent_jev'`).

- [ ] **Step 3: Implement `classify_intent_jev` in `OpenRouterClient`**

```python
# backend/src/app/router/openrouter_client.py
_VALID_DOMAINS = {"vendas", "suporte", "atendimento", "agendamento", "fora_escopo"}

_DOMAIN_CRITERIA = {
    "vendas": "Interesse em comprar, orçamento, preço ou catálogo de produtos.",
    "suporte": "Produto com defeito, erro ou problema técnico já adquirido.",
    "atendimento": "Nota fiscal, troca, devolução, cancelamento ou reclamação.",
    "agendamento": "Quer marcar, remarcar ou confirmar uma visita/horário.",
    "fora_escopo": "Não se encaixa claramente em nenhuma opção acima.",
}

class OpenRouterClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_s: float,
        price_per_1k_input_tokens: float = 0.0,
        price_per_1k_output_tokens: float = 0.0,
        client: httpx.AsyncClient | None = None,
        vision_model: str = "",
        jev_model: str = "",
    ) -> None:
        ...
        # Modelo do classificador estruturado TypeSafe Jev (R3, Fase 1,
        # além do MVP — ver docs/ARCHITECTURE.md §5).
        # MVP: nome do modelo só configurável via env/restart (JEV_MODEL_NAME),
        # diferente de `vision_model` acima, que é editável em runtime pelo
        # admin — não há caso de uso que justifique trocar o modelo do Jev
        # sem redeploy. Vazio = provedor "jev_openrouter" no admin fica sem
        # efeito prático (classify_intent_jev levanta erro, capturado pelo
        # fallback gracioso do classificador).
        self._jev_model = jev_model

    async def classify_intent_jev(
        self, message: str, recent_messages: list[str] | None = None
    ) -> tuple[str, float]:
        """Classifica o domínio via TypeSafe Jev, endpoint dedicado do
        OpenRouter (`/systemone`, não `/chat/completions`) — o modelo devolve
        uma decisão tipada (`answers.dominio.choice`/`.confidence`), sem
        geração de texto livre nem parsing de JSON solto.
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
                "questions": {
                    "dominio": {
                        "type": "choice",
                        "instructions": (
                            "Classifique a mensagem do cliente em um dos "
                            "domínios de atendimento."
                        ),
                        "criteria": _DOMAIN_CRITERIA,
                    }
                },
            },
            timeout=self._timeout_s,
        )
        response.raise_for_status()
        answer = response.json()["answers"]["dominio"]
        choice = str(answer.get("choice", "fora_escopo")).lower().strip()
        confidence = float(answer.get("confidence", 0.5))
        if choice not in _VALID_DOMAINS:
            choice = "fora_escopo"
        return choice, confidence
```

Em `backend/src/app/config.py`:
```python
    # Provedor alternativo do classificador de intenção (além do MVP, ver
    # docs/ARCHITECTURE.md §5, decisão 2026-09-23). Reaproveita
    # external_model_api_key/external_model_base_url (mesma conta OpenRouter).
    jev_model_name: str = "typesafe/jev-latest"
```

Em `backend/src/app/main.py` (dentro da construção de `app.state.external_client`):
```python
    app.state.external_client = OpenRouterClient(
        base_url=settings.external_model_base_url,
        api_key=settings.external_model_api_key,
        model=settings.external_model_name,
        timeout_s=settings.external_llm_timeout_s,
        price_per_1k_input_tokens=settings.external_model_price_per_1k_input_tokens,
        price_per_1k_output_tokens=settings.external_model_price_per_1k_output_tokens,
        vision_model=settings.external_vision_model_name,
        jev_model=settings.jev_model_name,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_openrouter_client.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/router/openrouter_client.py backend/src/app/config.py backend/src/app/main.py backend/tests/test_openrouter_client.py
git commit -m "feat(openrouter): implementa classify_intent_jev via endpoint /systemone"
```

---

## Task 3: Classificador de Intenção com Suporte ao Jev e Fallback Gracioso

**Files:**
- Modify: `backend/src/app/router/classifier.py`
- Test: `backend/tests/test_classifier.py`

**Interfaces:**
- Consumes: `OpenRouterClient.classify_intent_jev`
- Produces: `classify(message, recent_messages, strategy, llm_client, provider="heuristica_llm", external_client=None) -> ClassificationResult`

- [ ] **Step 1: Write failing tests in `test_classifier.py`**

```python
# backend/tests/test_classifier.py
import pytest
from app.router.classifier import classify

class _FakeOpenRouterJevClient:
    def __init__(self, domain: str = "vendas", confidence: float = 0.9, fail: bool = False):
        self.domain = domain
        self.confidence = confidence
        self.fail = fail

    async def classify_intent_jev(self, message: str, recent_messages: list[str] | None = None):
        if self.fail:
            raise RuntimeError("Conexão com OpenRouter falhou")
        return self.domain, self.confidence

@pytest.mark.asyncio
async def test_classify_com_jev_sucesso():
    fake_client = _FakeOpenRouterJevClient(domain="vendas", confidence=0.92)
    result = await classify(
        message="Quero saber o valor do plano",
        provider="jev_openrouter",
        external_client=fake_client,
    )
    assert result.domain == "vendas"
    assert result.confidence == 0.92
    assert result.complexity == "baixa"

@pytest.mark.asyncio
async def test_classify_com_jev_fallback_em_falha():
    fake_client = _FakeOpenRouterJevClient(fail=True)
    # Deve degradar para a heurística sem estourar exceção
    result = await classify(
        message="Qual o preço desse produto?",
        provider="jev_openrouter",
        external_client=fake_client,
    )
    # Heurística reconhece "preço" como vendas. Confidence fixo em 0.3: o
    # fallback do Jev cai em `_classify_heuristic_fallback` (não no
    # short-circuit de match direto de `classify()`, que usaria 0.6) —
    # conferir contra `classifier.py` real antes de implementar, esse valor
    # é fixo na função (`ClassificationResult(..., confidence=0.3)`).
    assert result.domain == "vendas"
    assert result.confidence == 0.3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_classifier.py -k "jev" -v`
Expected: FAIL (parâmetros não aceitos em `classify`).

- [ ] **Step 3: Implement Jev routing and graceful fallback in `classifier.py`**

```python
# backend/src/app/router/classifier.py
import logging
from typing import Any

logger = logging.getLogger(__name__)

async def _classify_with_jev(
    message: str,
    recent_messages: list[str],
    external_client: Any,
) -> ClassificationResult:
    try:
        if external_client is None or not hasattr(external_client, "classify_intent_jev"):
            raise ValueError("external_client inválido para Jev")
        domain, confidence = await external_client.classify_intent_jev(message, recent_messages)
        return ClassificationResult(
            domain=domain,
            complexity=_heuristic_complexity(message),
            confidence=confidence,
        )
    except Exception as exc:
        logger.warning(
            "jev_classificacao_falhou_fallback_heuristica",
            extra={
                "router": {
                    "event": "jev_falha_fallback",
                    "erro": str(exc),
                }
            },
        )
        return _classify_heuristic_fallback(message, recent_messages)

async def classify(
    message: str,
    recent_messages: list[str] | None = None,
    strategy: str = "heuristic",
    llm_client: LLMClient | None = None,
    provider: str = "heuristica_llm",
    external_client: Any = None,
) -> ClassificationResult:
    recent_messages = recent_messages or []

    if provider == "jev_openrouter":
        return await _classify_with_jev(message, recent_messages, external_client)

    # Fluxo clássico (heurística de palavras-chave + fallback Ollama)
    domain = _match_domain_by_keywords(message)
    if domain is not None:
        return ClassificationResult(
            domain=domain, complexity=_heuristic_complexity(message), confidence=0.6
        )

    if strategy == "heuristic":
        return _classify_heuristic_fallback(message, recent_messages)

    if llm_client is None:
        raise ValueError("llm_client é obrigatório quando strategy='llm'")

    return await _classify_with_llm(message, recent_messages, llm_client)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_classifier.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/router/classifier.py backend/tests/test_classifier.py
git commit -m "feat(classifier): suporte ao TypeSafe Jev com fallback gracioso para heurística"
```

---

## Task 4: Injeção no Orquestrador e Telemetria no Endpoint de Chat

**Files:**
- Modify: `backend/src/app/router/orchestrator.py`
- Modify: `backend/src/app/models/chat.py`
- Modify: `backend/src/app/api/chat.py`
- Test: `backend/tests/test_orchestrator.py`
- Test: `backend/tests/test_chat_api.py`

**Interfaces:**
- Produces: `RouterDecision.router_provider: str = "heuristica_llm"`; `ChatDoneEventData.router_provider: str | None`.

- [ ] **Step 1: Write failing tests in `test_orchestrator.py` and `test_chat_api.py`**

Em `backend/tests/test_orchestrator.py`:
```python
@pytest.mark.asyncio
async def test_handle_message_propaga_router_provider_jev():
    # Verifica que RouterDecision recebe router_provider="jev_openrouter"
    decision = None
    async for event in handle_message(
        message="Quero orçamento",
        recent_messages=[],
        local_client=_FakeLLMClient(LLMResponse(text="resposta")),
        external_client=_FakeLLMClient(LLMResponse(text="resposta")),
        rag_client=_FakeRAGClient([]),
        complexity_strategy="heuristic",
        intent_router_provider="jev_openrouter",
    ):
        if isinstance(event, RouterDecision):
            decision = event
    assert decision is not None
    assert decision.router_provider == "jev_openrouter"
```

Em `backend/tests/test_chat_api.py`:
```python
def test_chat_stream_emite_router_provider_no_done():
    # Verifica que o evento 'done' do stream SSE contém o campo 'router_provider'
    app = _build_test_app()
    app.state.intent_router_provider = "jev_openrouter"
    client = TestClient(app)

    response = client.post("/api/chat/messages", json={"message": "olá"})
    eventos = _parse_sse(response.text)
    done_data = _find(eventos, "done")
    assert done_data["router_provider"] == "jev_openrouter"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_orchestrator.py backend/tests/test_chat_api.py -k "router_provider" -v`
Expected: FAIL.

- [ ] **Step 3: Implement orchestrator and chat endpoint changes**

Em `backend/src/app/router/orchestrator.py`:
```python
class RouterDecision(BaseModel):
    ...
    router_provider: str = "heuristica_llm"

async def handle_message(
    message: str,
    recent_messages: list[str],
    local_client: LLMClient,
    external_client: LLMClient,
    rag_client: RAGClient,
    complexity_strategy: str,
    intent_router_provider: str = "heuristica_llm",
) -> AsyncIterator[StatusEvent | TokenEvent | RouterDecision]:
    ...
    # Ajusta emissão de cold-start: só quando for Ollama local
    if intent_router_provider == "heuristica_llm" and complexity_strategy == "llm" and not await local_client.is_model_ready():
        yield StatusEvent(status="carregando_modelo")

    classification = await classify(
        message=message,
        recent_messages=recent_messages,
        strategy=complexity_strategy,
        llm_client=local_client,
        provider=intent_router_provider,
        external_client=external_client,
    )
    ...
    # Ao criar RouterDecision:
    yield RouterDecision(
        ...
        router_provider=intent_router_provider,
    )
```

Em `backend/src/app/models/chat.py`:
```python
class ChatDoneEventData(BaseModel):
    ...
    router_provider: str | None = Field(
        default="heuristica_llm",
        description='Provedor de roteamento utilizado ("heuristica_llm" ou "jev_openrouter").',
    )
```

Em `backend/src/app/api/chat.py`:
```python
def get_intent_router_provider(request: Request) -> str:
    return getattr(request.app.state, "intent_router_provider", "heuristica_llm")

# No endpoint send_message:
    intent_router_provider: str = Depends(get_intent_router_provider),
    ...
    async for event in handle_message(
        ...
        intent_router_provider=intent_router_provider,
    ):
        ...
        elif isinstance(event, RouterDecision):
            done_data = ChatDoneEventData(
                ...
                router_provider=event.router_provider,
            )
            yield _sse("done", done_data.model_dump())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_orchestrator.py backend/tests/test_chat_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/router/orchestrator.py backend/src/app/models/chat.py backend/src/app/api/chat.py backend/tests/test_orchestrator.py backend/tests/test_chat_api.py
git commit -m "feat(router): propaga intent_router_provider no orquestrador e telemetria do chat"
```

---

## Task 5: Frontend — Tipagem, Exibição de Telemetria e Seletor no Admin

**Files:**
- Modify: `frontend/lib/types/runtimeSettings.ts`
- Modify: `frontend/lib/types/chat.ts`
- Modify: `frontend/components/admin/RuntimeSettingsForm.tsx`
- Modify: `frontend/components/chat/ChatModal.tsx`
- Modify: `frontend/components/chat/MessageBubble.tsx`

**Interfaces:**
- `RuntimeSettings.intent_router_provider: "heuristica_llm" | "jev_openrouter"`
- `ChatMetrics.routerProvider?: string`

- [ ] **Step 1: Update TypeScript types**

Em `frontend/lib/types/runtimeSettings.ts`:
```typescript
export interface RuntimeSettings {
  local_llm_temperature: number | null;
  local_llm_timeout_s: number;
  external_llm_timeout_s: number;
  rag_search_domain_fallback: boolean;
  crawler_max_pages_default: number;
  crawler_confidence_threshold: number;
  intent_router_provider?: "heuristica_llm" | "jev_openrouter";
}
```

Em `frontend/lib/types/chat.ts`:
```typescript
export interface ChatMetrics {
  ...
  routerProvider?: string;
}

export interface ChatDoneEventData {
  ...
  router_provider?: string | null;
}
```

- [ ] **Step 2: Add router provider control in `RuntimeSettingsForm.tsx`**

No componente `RuntimeSettingsForm.tsx`:
1. Adicionar estado `const [routerProvider, setRouterProvider] = useState<"heuristica_llm" | "jev_openrouter">("heuristica_llm");`.
2. No `carregar()`, inicializar `setRouterProvider(atual.intent_router_provider ?? "heuristica_llm");`.
3. No `handleSubmit()`, incluir `intent_router_provider: routerProvider` no payload de `updateRuntimeSettings`.
4. Renderizar o campo na UI com radio buttons elegantes e descritivos:
   - Opção 1: **Heurística + LLM Local (Ollama)** — *Padrão: palavras-chave locais e fallback para modelo Ollama configurado.*
   - Opção 2: **TypeSafe Jev (OpenRouter)** — *Modelo System One de decisão estruturada de alta velocidade e baixo custo.*

- [ ] **Step 3: Update `ChatModal.tsx` and `MessageBubble.tsx` for telemetry display**

Em `frontend/components/chat/ChatModal.tsx`:
Mapear `routerProvider: data.router_provider ?? undefined` no callback `onDone`.

Em `frontend/components/chat/MessageBubble.tsx`:
No painel expansível de detalhes técnicos/métricas, exibir:
```tsx
{metrics?.routerProvider && (
  <div className="flex justify-between">
    <span className="text-gray-500">Roteador de Intenção:</span>
    <span className="font-mono text-gray-800">
      {metrics.routerProvider === "jev_openrouter" ? "TypeSafe Jev (OpenRouter)" : "Heurística + LLM Local"}
    </span>
  </div>
)}
```

- [ ] **Step 4: Verify typecheck and frontend build**

Run: `cd frontend && npm run build` (ou `npx tsc --noEmit`)
Expected: Sucesso sem erros de tipagem.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/types/runtimeSettings.ts frontend/lib/types/chat.ts frontend/components/admin/RuntimeSettingsForm.tsx frontend/components/chat/ChatModal.tsx frontend/components/chat/MessageBubble.tsx
git commit -m "feat(frontend): adiciona seletor de roteador no admin e indicador de telemetria no chat"
```

---

## Task 6: Verificação de Ponta a Ponta

- [ ] **Step 1: Rodar suíte completa de testes no backend**
Run: `cd backend && pytest -v`
Expected: Todos os testes passando sem quebras ou regressões.

- [ ] **Step 2: Teste manual no Painel Admin**
1. Iniciar os serviços locais (`backend` e `frontend`).
2. Acessar `http://localhost:3000/admin/modelos`.
3. Localizar a seção **Parâmetros de execução** e verificar o seletor do Roteador de Intenção.
4. Selecionar **TypeSafe Jev (OpenRouter)** e clicar em **Salvar parâmetros**.
5. Recarregar a página para confirmar que a opção permanece selecionada.

- [ ] **Step 3: Teste de ponta a ponta no Chat**
1. Abrir o widget do chat.
2. Enviar uma pergunta (ex.: *"Quanto custa o serviço?"*).
3. Abrir os detalhes da mensagem e verificar no painel de telemetria o campo **Roteador de Intenção: TypeSafe Jev (OpenRouter)**.
4. Voltar ao admin, alternar para **Heurística + LLM Local (Ollama)**, salvar e repetir o teste no chat, verificando a alteração imediata da telemetria.
