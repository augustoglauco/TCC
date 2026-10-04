# Plano de Implementação: Agente Analítico de Gráficos Dinâmicos com LLM

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar o gerador de gráficos do chat em um agente analítico dinâmico orientado a LLM, capaz de gerar gráficos sob demanda a partir de dados digitados no prompt, consultas Text-to-SQL seguras no banco de dados relacional e busca vetorial RAG.

**Architecture:** Um motor de validação e execução SQL segura (`safe_sql.py`) executa consultas somente-leitura nas tabelas do sistema com limite de linhas e timeout; o `AnalyticsAgent` coordena a extração de dados (do texto digitado, do BD ou do RAG) e solicita ao LLM a estruturação da visualização (`CardGrafico`); o orquestrador do chat transmite a resposta e o gráfico em tempo real para persistência e exibição no `/admin/dashboards`.

**Tech Stack:** FastAPI, SQLAlchemy assíncrono (PostgreSQL asyncpg), Ollama/OpenRouter LLM, Qdrant RAG, React, Next.js 16, Recharts, Zustand, Vitest, Pytest.

**Spec:** [spec_dynamic_charts_agent.md](file:///home/augusto/.gemini/antigravity-cli/brain/a6bfd4d6-07f6-41ee-b256-a8d4952cb6b1/spec_dynamic_charts_agent.md)

## Global Constraints

- Apenas usuários com perfil Admin autenticado podem gerar gráficos analíticos.
- Consultas dinâmicas ao banco de dados DEVEM ser estritamente `SELECT` somente-leitura, sem comandos DDL/DML e sem consultas múltiplas.
- Resultados de banco de dados são limitados a no máximo 50 linhas para preservar performance e contexto do LLM.
- Todos os gráficos gerados devem ser persistidos na tabela `admin_charts` e notificar a interface em tempo real via evento `refresh_admin_charts`.

## Review Focus

1. Tentativa de injeção de SQL ou comando de escrita (ex: `DROP TABLE`, `UPDATE`, `INSERT`, `;`) — deve ser terminantemente rejeitada com erro seguro.
2. Prompt com dados digitados livremente (ex: `"Jan 100, Fev 200"`) — deve ser estruturado sem tentar consultar o banco de dados.
3. Prompt de dados de vendas (ex: `"venda de produtos x quantidade"`) — deve consultar as tabelas reais de vendas e produzir gráfico numérico de unidades.
4. Consulta retornando zero registros — deve produzir um gráfico com dados vazios/amigáveis sem quebrar o orquestrador.
5. Recálculo no dashboard (refresh) — deve atualizar os dados do gráfico dinâmico reexecutando a consulta segura correspondente.

---

### Task 1: Motor de Validação e Execução SQL Seguro (`safe_sql.py`)

**Files:**
- Create: `backend/src/app/services/safe_sql.py`
- Create: `backend/tests/test_safe_sql.py`

- [ ] **Step 1:** Escrever testes unitários em `backend/tests/test_safe_sql.py` cobrindo validação de SELECT, rejeição de queries destrutivas (`INSERT`, `UPDATE`, `DELETE`, `DROP`), rejeição de múltiplos comandos (`;`), aplicação forçada de `LIMIT 50` e geração do esquema de tabelas para o prompt.
- [ ] **Step 2:** Executar `pytest tests/test_safe_sql.py` e confirmar que os testes falham.
- [ ] **Step 3:** Implementar `backend/src/app/services/safe_sql.py` com `validate_readonly_sql(sql)`, `execute_readonly_sql(session, sql)` e `get_catalog_schema_prompt()`.
- [ ] **Step 4:** Executar `pytest tests/test_safe_sql.py` e garantir 100% de aprovação.
- [ ] **Step 5:** Commit Task 1.

---

### Task 2: Agente Analítico de Gráficos (`analytics_agent.py`)

**Files:**
- Create: `backend/src/app/services/analytics_agent.py`
- Create: `backend/tests/test_analytics_agent.py`

- [ ] **Step 1:** Escrever testes em `backend/tests/test_analytics_agent.py` cobrindo:
  - Extração de dados digitados diretamente no prompt (chave-valor, listas, CSV).
  - Geração de especificação estruturada com LLM mockado.
  - Fallback resiliente para prompts com dados insuficientes.
- [ ] **Step 2:** Executar `pytest tests/test_analytics_agent.py` e confirmar que falham.
- [ ] **Step 3:** Implementar `backend/src/app/services/analytics_agent.py`:
  - `extract_prompt_inline_data(prompt)` para capturar dados explícitos do usuário.
  - `generate_dynamic_chart(...)` integrando com o LLM para Text-to-SQL ou estruturação direta.
  - Persistência em `AdminChart` com `fixado=True`.
- [ ] **Step 4:** Executar `pytest tests/test_analytics_agent.py` e validar aprovação.
- [ ] **Step 5:** Commit Task 2.

---

### Task 3: Integração no Orquestrador do Chat e SSE (`orchestrator.py`)

**Files:**
- Modify: `backend/src/app/router/orchestrator.py`
- Modify: `backend/tests/test_chat_chart_card.py`

- [ ] **Step 1:** Atualizar teste em `backend/tests/test_chat_chart_card.py` para verificar que o orquestrador aciona o agente analítico dinâmico quando o usuário admin solicita gráficos.
- [ ] **Step 2:** Executar teste e verificar que falha antes da alteração.
- [ ] **Step 3:** Atualizar `backend/src/app/router/orchestrator.py` substituindo as chamadas de agregações estáticas pelo `AnalyticsAgent`.
- [ ] **Step 4:** Executar `pytest tests/test_chat_chart_card.py` e confirmar aprovação.
- [ ] **Step 5:** Commit Task 3.

---

### Task 4: Atualização Dinâmica no Endpoint de Refresh (`/api/admin/charts/{id}/refresh`)

**Files:**
- Modify: `backend/src/app/api/admin_charts.py`
- Modify: `backend/tests/test_admin_charts_api.py`

- [ ] **Step 1:** Adicionar casos de teste em `backend/tests/test_admin_charts_api.py` testando o refresh de gráficos com `dynamic_sql: SELECT ...` e com `dynamic_user_data`.
- [ ] **Step 2:** Executar teste e verificar falha.
- [ ] **Step 3:** Atualizar `backend/src/app/api/admin_charts.py` para suportar queries que iniciam com `dynamic_sql:` executando via `safe_sql`.
- [ ] **Step 4:** Executar `pytest tests/test_admin_charts_api.py` e validar aprovação.
- [ ] **Step 5:** Commit Task 4.

---

### Task 5: Modal de Criação Manual no Painel de Dashboards (`/admin/dashboards`)

**Files:**
- Create: `frontend/components/admin/CreateChartModal.tsx`
- Modify: `frontend/app/admin/dashboards/page.tsx`
- Create: `frontend/tests/components/CreateChartModal.test.tsx`
- Modify: `frontend/tests/components/AdminDashboardsPage.test.tsx`

- [ ] **Step 1:** Escrever teste em `frontend/tests/components/CreateChartModal.test.tsx` cobrindo inserção de título, tipo de gráfico, formato e adição de linhas personalizadas de dados.
- [ ] **Step 2:** Executar `npm test -- tests/components/CreateChartModal.test.tsx` e confirmar falha.
- [ ] **Step 3:** Criar componente `CreateChartModal.tsx` com formulário intuitivo e botão de adicionar/remover categorias e valores.
- [ ] **Step 4:** Adicionar botão "+ Criar Gráfico" no cabeçalho de `frontend/app/admin/dashboards/page.tsx` abrindo o modal.
- [ ] **Step 5:** Executar os testes do frontend e validar aprovação.
- [ ] **Step 6:** Commit Task 5.

---

### Task 6: Verificação de Ponta a Ponta, Testes Gerais e Roadmap

**Files:**
- Modify: `docs/ROADMAP.md`

- [ ] **Step 1:** Executar suite completa do pytest no backend: `.venv/bin/pytest`.
- [ ] **Step 2:** Executar suite completa do vitest no frontend: `npm test`.
- [ ] **Step 3:** Executar build de produção do frontend: `npm run build`.
- [ ] **Step 4:** Atualizar `docs/ROADMAP.md` documentando a funcionalidade de geração de gráficos dinâmicos com IA e criação manual no dashboard.
- [ ] **Step 5:** Commit e push para o repositório remoto.
