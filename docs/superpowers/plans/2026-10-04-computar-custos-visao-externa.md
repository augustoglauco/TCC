# Plano de Implementação: Contabilização de Tokens e Custos da Visão Externa

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o cálculo e registro de consumo de tokens e custos financeiros de entrada e saída para chamadas ao modelo externo de visão computacional (`OpenRouterClient.describe_image`), propagando as métricas para a identificação de produtos, o fluxo de chat SSE e o painel `/admin/metricas`.

**Architecture:** O `OpenRouterClient.describe_image` extrai o objeto `usage` da resposta da API e calcula os custos segregados de prompt e completion baseado na precificação do modelo de visão; o `identify_product_by_image` propaga esses metadados no `ImageIdentificationResult`; o endpoint `/api/chat/messages` grava os tokens e custos no evento `done` e em `conversa_mensagens.metricas` com `backend_used="visao_externa"`; o agregador `/api/admin/metrics/tokens-and-costs` contabiliza `visao_externa` junto aos custos externos.

**Tech Stack:** Python 3.11/3.14, FastAPI, SQLAlchemy asyncpg / PostgreSQL, OpenRouter API, Pydantic v2, Pytest.

**Spec:** [`docs/superpowers/specs/2026-10-03-contabilizador-tokens-custos-design.md`](docs/superpowers/specs/2026-10-03-contabilizador-tokens-custos-design.md) (Seção 3.2).

## Global Constraints

- O retorno de `describe_image` deve continuar se comportando como `str` (via subclasse `VisionResult(str)`) para garantir 100% de retrocompatibilidade com chamadores existentes (`catalog_extractor`, parsers JSON, etc.).
- Se a resposta da API do OpenRouter não trouxer `usage` ou se o modelo for `:free`, os custos devem ser tratados graciosamente como `0.0` sem lançar exceções.
- Todas as propriedades financeiras devem ser em dólares (`USD`), com precisão de ponto flutuante compatível com os demais modelos externos.
- Todas as alterações devem ser cobertas por testes automatizados (`pytest`).

## Review Focus

1. Resposta da API do OpenRouter sem a chave `usage`: não deve falhar com `KeyError`, deve retornar string normal com tokens nulos e custos `0.0`.
2. Imagem não reconhecida pelo modelo (JSON de resposta inválido ou fora do portfólio): os custos da chamada de visão ainda devem ser contabilizados na mensagem, pois a inferência externa foi consumida e cobrada.
3. Compatibilidade retroativa de string: `isinstance(result, str)` e métodos de string (`result.strip()`, `json.loads(result)`) devem continuar funcionando transparentemente.
4. Preços customizados de visão: se definidos em configuração/runtime, devem prevalecer; se não definidos, deve utilizar a precificação padrão externa ou `0.0` se for modelo free.
5. Agregação em `/admin/metrics`: chamadas com `backend_used="visao_externa"` devem somar em `total_external_prompt_tokens`, `total_external_completion_tokens` e `total_cost_usd`.

---

### Task 1: `OpenRouterClient.describe_image` — Extração de Usage e Cálculo de Custos Segregados

**Files:**
- Modify: `backend/src/app/config.py`
- Modify: `backend/src/app/router/openrouter_client.py`
- Modify: `backend/src/app/main.py`
- Test: `backend/tests/test_openrouter_vision_cost.py`

**Interfaces:**
- Consumes: Configurações de preço `external_vision_model_price_per_1k_input_tokens` e `output_tokens`.
- Produces: `VisionResult(str)` em `OpenRouterClient.describe_image(...)` com atributos:
  - `content: str`
  - `prompt_tokens: int | None`
  - `completion_tokens: int | None`
  - `total_tokens: int | None`
  - `cost_prompt_usd: float`
  - `cost_completion_usd: float`
  - `estimated_cost_usd: float`
  - `model_name: str`

- [x] **Step 1: Escrever teste que falha em `backend/tests/test_openrouter_vision_cost.py`**

```python
import pytest
from unittest.mock import AsyncMock, patch
import httpx
from app.router.openrouter_client import OpenRouterClient, VisionResult

@pytest.mark.asyncio
async def test_describe_image_calculates_segregated_costs_and_usage():
    mock_response = httpx.Response(
        status_code=200,
        json={
            "choices": [{"message": {"content": '{"produto": "Câmera IP", "confianca": 0.9}'}}],
            "usage": {
                "prompt_tokens": 1200,
                "completion_tokens": 80,
                "total_tokens": 1280
            }
        },
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    )

    client = OpenRouterClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="mock-key",
        model="google/gemini-2.5-flash",
        vision_model="google/gemma-4-31b-it:free",
        price_per_1k_input_tokens=0.001,
        price_per_1k_output_tokens=0.002,
        price_per_1k_vision_input_tokens=0.005,
        price_per_1k_vision_output_tokens=0.015,
    )

    with patch.object(client._client, "post", AsyncMock(return_value=mock_response)):
        # PNG dummy 1x1
        dummy_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        res = await client.describe_image(dummy_png, "Identifique")

        assert isinstance(res, str)
        assert isinstance(res, VisionResult)
        assert '{"produto": "Câmera IP"' in res
        assert res.prompt_tokens == 1200
        assert res.completion_tokens == 80
        assert res.total_tokens == 1280
        assert pytest.approx(res.cost_prompt_usd, 0.00001) == (1200 / 1000.0) * 0.005 # 0.006
        assert pytest.approx(res.cost_completion_usd, 0.00001) == (80 / 1000.0) * 0.015 # 0.0012
        assert pytest.approx(res.estimated_cost_usd, 0.00001) == 0.0072
        assert res.model_name == "google/gemma-4-31b-it:free"
```

- [x] **Step 2: Executar teste e verificar que falha**

Run: `backend/.venv/bin/pytest backend/tests/test_openrouter_vision_cost.py`
Expected: FAIL (argumento inesperado ou `VisionResult` inexistente).

- [x] **Step 3: Implementar `VisionResult` e atualização em `OpenRouterClient` e `config.py`**

Adicionar em `app/config.py`:
- `external_vision_model_price_per_1k_input_tokens: float = 0.0`
- `external_vision_model_price_per_1k_output_tokens: float = 0.0`

Adicionar classe `VisionResult(str)` em `app/router/openrouter_client.py`:
```python
class VisionResult(str):
    content: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    cost_prompt_usd: float
    cost_completion_usd: float
    estimated_cost_usd: float
    model_name: str | None

    def __new__(
        cls,
        content: str,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        cost_prompt_usd: float = 0.0,
        cost_completion_usd: float = 0.0,
        estimated_cost_usd: float = 0.0,
        model_name: str | None = None,
    ):
        obj = super().__new__(cls, content)
        obj.content = content
        obj.prompt_tokens = prompt_tokens
        obj.completion_tokens = completion_tokens
        obj.total_tokens = total_tokens
        obj.cost_prompt_usd = cost_prompt_usd
        obj.cost_completion_usd = cost_completion_usd
        obj.estimated_cost_usd = estimated_cost_usd
        obj.model_name = model_name
        return obj
```

Em `OpenRouterClient.__init__`:
Adicionar parâmetros `price_per_1k_vision_input_tokens: float = 0.0` e `price_per_1k_vision_output_tokens: float = 0.0`.
Em `describe_image`:
Extrair `usage = data.get("usage", {})`, calcular custos e retornar `VisionResult(...)`.

- [x] **Step 4: Executar testes e validar aprovação**

Run: `backend/.venv/bin/pytest backend/tests/test_openrouter_vision_cost.py backend/tests/test_openrouter_client.py`
Expected: PASS.

- [x] **Step 5: Commit Task 1**

```bash
git add backend/src/app/config.py backend/src/app/router/openrouter_client.py backend/src/app/main.py backend/tests/test_openrouter_vision_cost.py
git commit -m "feat(router): compute token usage and segregated costs in OpenRouter describe_image"
```

---

### Task 2: Propagação de Métricas em `identify_product_by_image` (`image_identification.py`)

**Files:**
- Modify: `backend/src/app/rag/image_identification.py`
- Modify: `backend/tests/test_image_identification.py`

**Interfaces:**
- Consumes: `VisionResult` retornado por `vision_client.describe_image`.
- Produces: `ImageIdentificationResult` enriquecido com campos:
  - `prompt_tokens: int | None = None`
  - `completion_tokens: int | None = None`
  - `cost_prompt_usd: float | None = None`
  - `cost_completion_usd: float | None = None`
  - `estimated_cost_usd: float | None = None`
  - `model_name: str | None = None`

- [x] **Step 1: Escrever teste em `backend/tests/test_image_identification.py` verificando preenchimento dos custos**

Adicionar caso de teste onde `vision_client.describe_image` retorna um `VisionResult` com tokens e custos preenchidos, verificando que `identify_product_by_image` propaga esses valores em `resultado`.

- [x] **Step 2: Executar teste e verificar que falha**

Run: `backend/.venv/bin/pytest backend/tests/test_image_identification.py`
Expected: FAIL (campos ausentes em `ImageIdentificationResult`).

- [x] **Step 3: Atualizar `ImageIdentificationResult` e `identify_product_by_image`**

Em `app/rag/image_identification.py`:
Adicionar os campos em `ImageIdentificationResult`.
No bloco de fallback da visão externa:
```python
    raw = await vision_client.describe_image(image_bytes, _VISION_PROMPT)
    vision_prompt_tokens = getattr(raw, "prompt_tokens", None)
    vision_comp_tokens = getattr(raw, "completion_tokens", None)
    vision_cost_prompt = getattr(raw, "cost_prompt_usd", None)
    vision_cost_comp = getattr(raw, "cost_completion_usd", None)
    vision_cost_total = getattr(raw, "estimated_cost_usd", None)
    vision_model_name = getattr(raw, "model_name", None)
```
Propagar esses atributos tanto quando `status="encontrado_externo"` quanto quando `status="nao_identificado"` (caso a chamada externa tenha ocorrido).

- [x] **Step 4: Executar testes e validar aprovação**

Run: `backend/.venv/bin/pytest backend/tests/test_image_identification.py`
Expected: PASS.

- [x] **Step 5: Commit Task 2**

```bash
git add backend/src/app/rag/image_identification.py backend/tests/test_image_identification.py
git commit -m "feat(rag): propagate vision token metrics and costs in ImageIdentificationResult"
```

---

### Task 3: Integração no Orquestrador SSE e Agregação em `/admin/metrics`

**Files:**
- Modify: `backend/src/app/api/chat.py`
- Modify: `backend/src/app/api/admin_metrics.py`
- Test: `backend/tests/test_chat_image_cost_accounting.py`

**Interfaces:**
- Consumes: `ImageIdentificationResult` com métricas preenchidas.
- Produces: `ChatDoneEventData` e `conversa_mensagens.metricas` com `backend_used="visao_externa"`, tokens e custos; agregação no dashboard `/admin/metricas`.

- [x] **Step 1: Escrever teste em `backend/tests/test_chat_image_cost_accounting.py`**

Testar que requisição com imagem ao endpoint `POST /api/chat/messages` que aciona a visão externa:
1. Emite evento SSE `done` com `backend_used="visao_externa"`, `prompt_tokens`, `completion_tokens`, `cost_prompt_usd`, `cost_completion_usd` e `estimated_cost_usd`.
2. Grava esses valores no JSON `metricas` de `conversa_mensagens`.
3. É acumulado como custo externo no endpoint `GET /api/admin/metrics/tokens-and-costs`.

- [x] **Step 2: Executar teste e verificar que falha**

Run: `backend/.venv/bin/pytest backend/tests/test_chat_image_cost_accounting.py`
Expected: FAIL.

- [x] **Step 3: Atualizar `chat.py` e `admin_metrics.py`**

Em `app/api/chat.py` (bloco `if is_identificacao_imagem:`):
```python
    has_vision_cost = (
        resultado.estimated_cost_usd is not None
        or resultado.prompt_tokens is not None
        or (resultado.fonte and "visao_externa" in resultado.fonte)
    )
    backend_used = "visao_externa" if has_vision_cost else "identificacao_imagem"
    total_tokens = None
    if resultado.prompt_tokens is not None or resultado.completion_tokens is not None:
        total_tokens = (resultado.prompt_tokens or 0) + (resultado.completion_tokens or 0)

    done_data = ChatDoneEventData(
        domain="vendas",
        backend_used=backend_used,
        escalation_reason="nenhum",
        prompt_tokens=resultado.prompt_tokens,
        completion_tokens=resultado.completion_tokens,
        total_tokens=total_tokens,
        cost_prompt_usd=resultado.cost_prompt_usd or 0.0 if has_vision_cost else None,
        cost_completion_usd=resultado.cost_completion_usd or 0.0 if has_vision_cost else None,
        estimated_cost_usd=resultado.estimated_cost_usd or 0.0 if has_vision_cost else None,
    )
```

Em `app/api/admin_metrics.py`:
```python
    if backend_used in ("externo", "visao_externa"):
        total_external_prompt += p_tok
        total_external_comp += c_tok
        total_cost_prompt += c_prompt
        total_cost_comp += c_comp
        total_cost += c_tot
        ...
```

- [x] **Step 4: Executar testes e validar aprovação**

Run: `backend/.venv/bin/pytest backend/tests/test_chat_image_cost_accounting.py backend/tests/test_admin_metrics_api.py`
Expected: PASS.

- [x] **Step 5: Commit Task 3**

```bash
git add backend/src/app/api/chat.py backend/src/app/api/admin_metrics.py backend/tests/test_chat_image_cost_accounting.py
git commit -m "feat(chat): record external vision tokens and costs in SSE done and admin metrics"
```

---

### Task 4: Verificação de Ponta a Ponta, Testes Gerais e Atualização de Documentação

**Files:**
- Modify: `docs/ROADMAP.md`

- [x] **Step 1: Executar suite completa do backend**

Run: `backend/.venv/bin/pytest`
Expected: 100% PASS (todos os 841+ testes).

- [x] **Step 2: Executar suite completa do frontend**

Run: `npm test` (no diretório `frontend`)
Expected: 100% PASS (todos os 369+ testes).

- [x] **Step 3: Atualizar documentação e roadmap**

Atualizar `docs/ROADMAP.md` registrando a conclusão formal da contabilização de custos e tokens de visão externa.

- [x] **Step 4: Commit e push final**

```bash
git add docs/ROADMAP.md
git commit -m "docs(roadmap): mark external vision model token and cost accounting as fully implemented"
git push origin master
```
