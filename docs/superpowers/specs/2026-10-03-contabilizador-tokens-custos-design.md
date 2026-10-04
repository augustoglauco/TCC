# Contabilizador de Tokens Internos/Externos, Custos Segregados e Relatórios de Chats Encerrados

## 1. Visão Geral e Objetivos

Este documento especifica o subsistema de **contabilização de tokens** (modelos locais vs. externos), **segregação de custos de entrada (prompt) e saída (resposta)** para modelos externos (OpenRouter) e **relatório diário de chats encerrados**.

### 1.1. Motivação
Atualmente, o sistema registra telemetria básica por mensagem (tokens totais, latência e custo estimado simples). No entanto:
- Não há separação explícita entre custo dos tokens de entrada (pergunta/contexto) e saída (resposta gerada).
- Não há controle de ciclo de vida de encerramento da conversa (`aberta` vs. `encerrada`).
- Não existe uma visão consolidada por data de encerramento para acompanhar o custo financeiro diário e o consumo de tokens locais (GPU própria, custo US$ 0.00) vs. externos (OpenRouter).

### 1.2. Principais Funcionalidades
1. **Contabilidade de Entrada e Saída (Input vs. Output)**:
   - Registro de `prompt_tokens` e `completion_tokens` em todas as interações.
   - Cálculo de `cost_prompt_usd` e `cost_completion_usd` para modelos externos com base nos preços por 1k tokens.
2. **Ciclo de Vida de Chats e Encerramento Automático**:
   - Status da conversa (`aberta` ou `encerrada`) com marcação de `encerrada_em` e `motivo_encerramento` (`manual_usuario`, `manual_admin`, `inatividade`).
   - Botão no widget de chat para encerramento manual pelo visitante.
   - Worker assíncrono em segundo plano para encerramento automático após 30 minutos de inatividade.
3. **Dashboard de Métricas & Custos (`/admin/metricas`)**:
   - KPIs em tempo real de tokens locais, tokens remotos, custo financeiro acumulado de pergunta e resposta.
   - Tabela e gráfico de relatórios diários agrupados por data de encerramento dos chats (`date(encerrada_em)`).

---

## 2. Arquitetura e Modelo de Dados (PostgreSQL)

### 2.1. Alterações na Tabela `conversas`
A tabela `conversas` (migração Alembic `0018_conversas_status_custos.py`) ganha os seguintes campos:

```sql
ALTER TABLE conversas ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'aberta';
ALTER TABLE conversas ADD COLUMN encerrada_em TIMESTAMP WITH TIME ZONE NULL;
ALTER TABLE conversas ADD COLUMN motivo_encerramento VARCHAR(50) NULL;

CREATE INDEX idx_conversas_status ON conversas(status);
CREATE INDEX idx_conversas_encerrada_em ON conversas(encerrada_em);
```

### 2.2. Estrutura do JSON `conversa_mensagens.metricas`
Cada resposta gerada pelo assistente e gravada em `conversa_mensagens` passa a conter no campo `metricas`:

```json
{
  "domain": "vendas",
  "backend_used": "externo",
  "model_name": "google/gemini-2.5-flash:free",
  "prompt_tokens": 850,
  "completion_tokens": 120,
  "latency_ms": 1240.5,
  "ttft_ms": 320.0,
  "tps": 96.7,
  "cost_prompt_usd": 0.000085,
  "cost_completion_usd": 0.000036,
  "estimated_cost_usd": 0.000121,
  "router_provider": "heuristica_llm"
}
```

Para chamadas ao **modelo local (Ollama)**:
- `backend_used`: `"local"`
- `cost_prompt_usd`: `0.0`
- `cost_completion_usd`: `0.0`
- `estimated_cost_usd`: `0.0`

---

## 3. Motor de Cálculo de Custos & Clientes LLM

### 3.1. `OpenRouterClient` (`app/router/openrouter_client.py`)
Atualização da lógica de precificação para retornar o detalhamento segregado:

```python
def calcular_custos(
    self, prompt_tokens: int | None, completion_tokens: int | None
) -> tuple[float, float, float]:
    prompt_tokens = prompt_tokens or 0
    completion_tokens = completion_tokens or 0

    cost_prompt = (prompt_tokens / 1000.0) * self._price_in
    cost_completion = (completion_tokens / 1000.0) * self._price_out
    cost_total = cost_prompt + cost_completion

    return cost_prompt, cost_completion, cost_total
```

O schema `LLMResponse`, `LLMStreamChunk` e `ChatDoneEventData` ganham as propriedades:
- `cost_prompt_usd: float | None = 0.0`
- `cost_completion_usd: float | None = 0.0`

### 3.2. Contabilização do Modelo de Visão Computacional Externo (`describe_image`)
Quando uma mensagem do usuário contém uma imagem enviada para o fluxo de identificação de produto ou visão externa (R6), a chamada multimodal realizada por `OpenRouterClient.describe_image` também gera consumo de tokens e custos no OpenRouter:
- **Extração de `usage`**: O método `describe_image` extrai `prompt_tokens` e `completion_tokens` da chave `usage` contida na resposta da API do OpenRouter.
- **Cálculo de Custos do Modelo de Visão**: O custo de entrada e saída da chamada de visão é calculado utilizando a precificação por 1k tokens do `external_vision_model_name` (lido do cache de `model_characteristics` ou `app_settings`).
- **Agregação na Mensagem**: O Orquestrador acumula os tokens e custos da chamada de visão com os tokens/custos do LLM de texto, registrando o total combinado no evento SSE `done` e no JSON `conversa_mensagens.metricas` da resposta.

### 3.3. Fonte dos Preços de Modelos Externos
1. **Cache Automático**: `OpenRouterClient` lê a precificação atualizada a partir do modelo ativo em `model_characteristics` (`pricing_prompt_per_1k` e `pricing_completion_per_1k`), tanto para o modelo de texto quanto para o modelo de visão.
2. **Override Administrativo**: Caso haja ajuste manual no painel `/admin/modelos`, os valores sobrepostos salvos em `app_settings` têm precedência.

---

## 4. Ciclo de Vida da Conversa & Encerramento Automático

### 4.1. Encerramento Manual (`POST /api/chat/conversations/{id}/close`)
- Endpoint que recebe a solicitação de fechamento da conversa.
- Atualiza a linha na tabela `conversas`:
  - `status = 'encerrada'`
  - `encerrada_em = datetime.now(UTC)`
  - `motivo_encerramento = 'manual_usuario'` (ou `'manual_admin'`).

### 4.2. Worker de Inatividade em Segundo Plano (`app/services/chat_closure_service.py`)
- Serviço executado periodicamente (disparado via `lifespan` do FastAPI a cada 5 minutos):
```sql
UPDATE conversas
SET status = 'encerrada',
    encerrada_em = NOW(),
    motivo_encerramento = 'inatividade'
WHERE status = 'aberta'
  AND atualizada_em < NOW() - INTERVAL '30 minutes';
```

---

## 5. Endpoints Analíticos & Dashboard (`/admin/metricas`)

### 5.1. Endpoint Backend (`GET /api/admin/metrics/tokens-and-costs`)
**Parâmetros de Query**:
- `start_date` (opcional): Data inicial ISO (ex: `2026-10-01`).
- `end_date` (opcional): Data final ISO (ex: `2026-10-03`).
- `period` (opcional): `"today"`, `"7d"`, `"30d"`, `"all"` (padrão `"7d"`).

**Resposta JSON (`TokenCostMetricsResponse`)**:
```json
{
  "period": "7d",
  "summary": {
    "total_closed_chats": 42,
    "total_internal_prompt_tokens": 125000,
    "total_internal_completion_tokens": 48000,
    "total_external_prompt_tokens": 35000,
    "total_external_completion_tokens": 12000,
    "total_cost_prompt_usd": 0.0452,
    "total_cost_completion_usd": 0.0384,
    "total_cost_usd": 0.0836
  },
  "daily_breakdown": [
    {
      "date": "2026-10-03",
      "closed_chats_count": 15,
      "internal_prompt_tokens": 45000,
      "internal_completion_tokens": 18000,
      "external_prompt_tokens": 12000,
      "external_completion_tokens": 4000,
      "cost_prompt_usd": 0.0156,
      "cost_completion_usd": 0.0128,
      "total_cost_usd": 0.0284
    }
  ]
}
```

### 5.2. Interface Frontend (`/admin/metricas`)
- **Cards de Resumo no Topo**:
  - `Tokens Internos (GPU Local)`: Total Prompt + Total Completion (Custo R$ 0,00).
  - `Tokens Externos (OpenRouter)`: Total Prompt + Total Completion.
  - `Custo de Entrada (Prompt USD)`: Valor gasto no envio de contexto para a nuvem.
  - `Custo de Saída (Resposta USD)`: Valor gasto na geração de resposta pela nuvem.
  - `Custo Total Acumulado (USD)`: Custo combinado.
  - `Chats Encerrados no Período`: Quantidade de sessões finalizadas.
- **Tabela de Detalhamento Diário**:
  - Colunas: Data, Chats Encerrados, Tokens Internos (Entrada/Saída), Tokens Externos (Entrada/Saída), Custo Entrada ($), Custo Saída ($), Custo Total ($).

---

## 6. Estratégia de Testes e Validação

1. **Testes Unitários (Backend)**:
   - `test_openrouter_token_cost_calculation`: Valida a matemática de segregação de custo de entrada vs. saída.
   - `test_chat_closure_manual_and_inactivity`: Valida transição de status para `encerrada` e o worker de inatividade de 30 min.
   - `test_token_and_cost_metrics_api`: Valida agregação SQL por `date(encerrada_em)`.
2. **Testes de Integração Frontend**:
   - Valida renderização da aba `/admin/metricas` e botão de encerramento no `ChatModal.tsx`.
