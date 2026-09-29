# Gestão de Agendamentos (Fase 7, R11) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o subsistema completo de agendamentos da Fase 7 do roadmap: persistência no Postgres vinculada ao cliente e conversa, expansão do cliente MCP Google Calendar (criação, cancelamento e consulta direta), API REST para usuário e administrador, tela do cliente (`/agendamentos`) para visualização e cancelamento, e painel administrativo (`/admin/agendamentos`) com gestão por usuário, agendamento manual e auditoria da agenda no Google.

**Architecture:** Híbrido Sincronizado — Postgres como fonte da aplicação para histórico, permissões e integridade com o Chat e Usuários; MCP Google Calendar como barramento de agenda corporativa e consulta ao vivo.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (async), Alembic, MCP Python SDK (Streamable HTTP), Next.js 16 (App Router), React 19, Tailwind CSS v4, Zustand, Vitest / Testing Library, Pytest.

**Spec:** [`docs/superpowers/specs/2026-09-29-gestao-agendamentos-design.md`](file:///home/augusto/Projetos/TCC/docs/superpowers/specs/2026-09-29-gestao-agendamentos-design.md)

## Global Constraints

- Backend: Python 3.14+, SQLAlchemy 2.0 async, timezone-aware Datetime (UTC).
- Banco de Dados: Postgres em produção; SQLite in-memory nos testes unitários com suporte a DateTime e UUIDs.
- MCP Client: falha graciosa (não derrubar requisição caso o servidor MCP do Google Calendar esteja offline ou o evento já tenha sido excluído).
- Frontend: Next.js App Router, Tailwind CSS, TypeScript estrito, responsivo mobile/desktop.
- Permissões: Clientes só enxergam e cancelam seus próprios agendamentos; Administradores (perfil `Admin`) têm acesso irrestrito, agendamento manual e consulta à agenda do Google.

## Review Focus

1. **Tentativa de cancelamento de agendamento alheio:** usuário comum tentando cancelar agendamento com e-mail divergente deve receber `403 Forbidden`.
2. **Cancelamento duplo ou de agendamento já cancelado:** chamada subsequente a `/cancelar` deve retornar `400 Bad Request` sem duplicar chamadas ao MCP.
3. **Instabilidade do MCP Google Calendar ao cancelar:** se o MCP retornar erro de conexão ou o evento já não existir no Google Calendar, o status no banco DEVE ser atualizado para `cancelado` sem falhar com erro 500 para o usuário.
4. **Agendamento manual com conflito de horário:** administrador tentando agendar em horário ocupado sem flag de override deve receber aviso de conflito `409 Conflict`.
5. **Acesso não autenticado ou não-admin:** `/admin/agendamentos` no frontend deve barrar usuários anônimos e clientes comuns, renderizando tela de acesso negado.

---

### Task 1: Modelo de Dados e Migração Alembic `Agendamento`

**Files:**
- Create: `backend/migrations/versions/0015_agendamentos.py`
- Modify: `backend/src/app/db/models.py`
- Test: `backend/tests/test_agendamentos_db.py`

**Interfaces:**
- Produces: `app.db.models.Agendamento` com campos `id (UUID)`, `user_email (str)`, `nome_cliente (str)`, `telefone (str | None)`, `data_hora_inicio (datetime)`, `data_hora_fim (datetime)`, `descricao (str | None)`, `status (str)`, `origem (str)`, `google_event_id (str | None)`, `google_event_link (str | None)`, `conversation_id (str | None)`, `criado_em (datetime)`, `atualizado_em (datetime)`.

- [ ] **Step 1: Escrever teste de banco de dados que falha (RED)**

Criar `backend/tests/test_agendamentos_db.py` testando a criação, indexação e persistência do modelo `Agendamento`:

```python
import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import select
from app.db.engine import create_db_engine, create_session_factory
from app.db.models import Base, Agendamento

@pytest.fixture
async def factory():
    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield create_session_factory(engine)
    await engine.dispose()

async def test_criar_e_consultar_agendamento(factory):
    agora = datetime.now(timezone.utc)
    agendamento_id = uuid.uuid4()
    async with factory() as session:
        ag = Agendamento(
            id=agendamento_id,
            user_email="cliente@teste.com",
            nome_cliente="Carlos Teste",
            telefone="11999998888",
            data_hora_inicio=agora,
            data_hora_fim=agora,
            descricao="Visita técnica de gerador",
            status="confirmado",
            origem="chat",
            google_event_id="evt_123",
            google_event_link="https://calendar.google.com/event/123",
            conversation_id="conv_abc",
        )
        session.add(ag)
        await session.commit()

    async with factory() as session:
        resultado = await session.execute(select(Agendamento).where(Agendamento.id == agendamento_id))
        recuperado = resultado.scalars().first()
        assert recuperado is not None
        assert recuperado.user_email == "cliente@teste.com"
        assert recuperado.status == "confirmado"
        assert recuperado.origem == "chat"
```

- [ ] **Step 2: Executar teste para verificar falha (RED)**

Run: `.venv/bin/pytest tests/test_agendamentos_db.py -v`
Expected: FAIL com `ImportError: cannot import name 'Agendamento' from 'app.db.models'`

- [ ] **Step 3: Implementar o modelo `Agendamento` e migração Alembic (GREEN)**

1. Adicionar `Agendamento` em `backend/src/app/db/models.py`.
2. Criar migração `backend/migrations/versions/0015_agendamentos.py` com upgrade/downgrade para a tabela `agendamentos`.

- [ ] **Step 4: Executar teste para verificar aprovação (GREEN)**

Run: `.venv/bin/pytest tests/test_agendamentos_db.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/db/models.py backend/migrations/versions/0015_agendamentos.py backend/tests/test_agendamentos_db.py
git commit -m "feat(db): adiciona model e migracao 0015 da tabela agendamentos"
```

---

### Task 2: Extensão do Cliente MCP do Google Calendar

**Files:**
- Modify: `backend/src/app/mcp_client/google_calendar.py`
- Modify: `backend/tests/test_google_calendar_client.py`

**Interfaces:**
- Modifies: `GoogleCalendarMCPClient.create_event(...) -> tuple[str, str]` (retorna `(google_event_id, html_link)`).
- Produces: `GoogleCalendarMCPClient.delete_event(event_id: str) -> bool`.
- Produces: `GoogleCalendarMCPClient.list_events(time_min: datetime, time_max: datetime) -> list[dict]`.

- [ ] **Step 1: Escrever testes unitários que falham para as novas funções do MCP (RED)**

Em `backend/tests/test_google_calendar_client.py`, adicionar testes:
1. `test_create_event_retorna_id_e_link_do_evento`: valida retorno de tupla `("evt1", "https://calendar.google.com/evt1")`.
2. `test_delete_event_chama_tool_delete_event_com_sucesso`: valida chamada à tool `delete_event`.
3. `test_list_events_retorna_lista_de_eventos`: valida chamada a `find_events` e retorno da lista de eventos brutos.

- [ ] **Step 2: Executar testes para verificar falha (RED)**

Run: `.venv/bin/pytest tests/test_google_calendar_client.py -k "delete_event or list_events" -v`
Expected: FAIL com `AttributeError: 'GoogleCalendarMCPClient' object has no attribute 'delete_event'`

- [ ] **Step 3: Implementar métodos no `GoogleCalendarMCPClient` (GREEN)**

Em `backend/src/app/mcp_client/google_calendar.py`:
1. Atualizar assinatura do Protocol `CalendarClient`.
2. Em `create_event`, extrair `evento.get("id", "")` e `evento.get("html_link", "")`, retornando a tupla `(id, link)`.
3. Implementar `async def delete_event(self, event_id: str) -> bool`:
   - Chama `_call_tool("delete_event", {"calendar_id": self._calendar_id, "event_id": event_id})`.
   - Retorna `True`. Em caso de erro contendo "not found" ou similar, retorna `False`.
4. Implementar `async def list_events(self, time_min: datetime, time_max: datetime) -> list[dict]`:
   - Chama `_call_tool("find_events", {"calendar_id": self._calendar_id, "time_min": time_min.isoformat(), "time_max": time_max.isoformat()})`.
   - Retorna `resultado.get("events", [])`.

- [ ] **Step 4: Executar testes do cliente Google Calendar (GREEN)**

Run: `.venv/bin/pytest tests/test_google_calendar_client.py -v`
Expected: PASS (todos os testes passando)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/mcp_client/google_calendar.py backend/tests/test_google_calendar_client.py
git commit -m "feat(mcp): expande cliente Google Calendar com delete_event, list_events e retorno de id"
```

---

### Task 3: Integração do Agendamento pelo Chat com Persistência no Banco

**Files:**
- Modify: `backend/src/app/router/orchestrator.py`
- Modify: `backend/src/app/api/chat.py`
- Modify: `backend/tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `app.db.models.Agendamento`, `CalendarClient.create_event`.
- Produces: Registro de `Agendamento` no Postgres ao confirmar no fluxo de agendamento do chat.

- [ ] **Step 1: Escrever teste em `test_orchestrator.py` para persistência ao confirmar agendamento (RED)**

Adicionar teste `test_handle_agendamento_persiste_registro_no_banco_ao_confirmar`:
- Configura `_FakeCalendarClient` com retorno de tupla `("evt-chat-1", "https://calendar.google.com/evt-chat-1")`.
- Executa confirmação de agendamento em `handle_message`.
- Valida que `db_sessionmaker` grava `Agendamento` com `origem="chat"` e `status="confirmado"`.

- [ ] **Step 2: Executar teste para verificar falha (RED)**

Run: `.venv/bin/pytest tests/test_orchestrator.py -k "test_handle_agendamento_persiste_registro_no_banco_ao_confirmar" -v`
Expected: FAIL

- [ ] **Step 3: Implementar persistência de agendamento no orquestrador e injeção do sessionmaker (GREEN)**

1. Em `_handle_agendamento` e `handle_message`, receber `db_sessionmaker: async_sessionmaker[AsyncSession] | None = None`.
2. Ao confirmar agendamento e obter o `(google_event_id, google_event_link)`, se `db_sessionmaker` estiver presente, salvar o novo `Agendamento` com `origem="chat"`.
3. Em `chat.py`, repassar `request.app.state.db_sessionmaker` para `handle_message`.

- [ ] **Step 4: Executar testes de orquestrador (GREEN)**

Run: `.venv/bin/pytest tests/test_orchestrator.py -k "agendamento" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/router/orchestrator.py backend/src/app/api/chat.py backend/tests/test_orchestrator.py
git commit -m "feat(chat): persiste agendamento no banco ao confirmar visita no chat"
```

---

### Task 4: Endpoints da API REST de Agendamentos

**Files:**
- Create: `backend/src/app/api/agendamentos.py`
- Modify: `backend/src/app/main.py`
- Create: `backend/tests/test_agendamentos_api.py`

**Interfaces:**
- Produces:
  - `GET /api/agendamentos/meus?user_email={email}`
  - `POST /api/agendamentos/{id}/cancelar?user_email={email}`
  - `GET /api/agendamentos/admin`
  - `POST /api/agendamentos/admin/manual`
  - `GET /api/agendamentos/admin/google-events`

- [ ] **Step 1: Escrever testes da API de Agendamentos (RED)**

Em `backend/tests/test_agendamentos_api.py`, cobrir:
1. `test_listar_meus_agendamentos_filtra_por_usuario`: cliente só vê os seus.
2. `test_cancelar_agendamento_proprio_com_sucesso`: atualiza status para cancelado e remove do MCP Calendar.
3. `test_cancelar_agendamento_de_outro_usuario_retorna_403`: valida Review Focus 1.
4. `test_cancelar_agendamento_ja_cancelado_retorna_400`: valida Review Focus 2.
5. `test_admin_listar_todos_agendamentos`: retorna todos com filtros.
6. `test_admin_criar_agendamento_manual`: cadastra com `origem="manual_admin"` e cria no Google.
7. `test_admin_consultar_eventos_google`: retorna eventos reais do MCP.

- [ ] **Step 2: Executar testes para verificar falha (RED)**

Run: `.venv/bin/pytest tests/test_agendamentos_api.py -v`
Expected: FAIL (404 Not Found para rotas de agendamentos)

- [ ] **Step 3: Implementar `backend/src/app/api/agendamentos.py` e registrar no `main.py` (GREEN)**

1. Criar schemas Pydantic: `AgendamentoOut`, `AgendamentoAdminOut`, `AgendamentoManualCreate`, `GoogleCalendarEventOut`.
2. Implementar endpoints com injeção de `db_sessionmaker` e `calendar_client`.
3. Registrar roteador no `app/main.py` com `app.include_router(agendamentos.router)`.

- [ ] **Step 4: Executar testes da API (GREEN)**

Run: `.venv/bin/pytest tests/test_agendamentos_api.py -v`
Expected: PASS (todos os 7 testes passando)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/api/agendamentos.py backend/src/app/main.py backend/tests/test_agendamentos_api.py
git commit -m "feat(api): adiciona endpoints REST para gestao e cancelamento de agendamentos"
```

---

### Task 5: Tipos TypeScript e Cliente de API no Frontend

**Files:**
- Create: `frontend/lib/types/agendamentos.ts`
- Create: `frontend/lib/api/agendamentos.ts`
- Create: `frontend/tests/lib/api/agendamentos.test.ts`

**Interfaces:**
- Produces: `fetchMeusAgendamentos(email)`, `cancelarAgendamento(id, email)`, `fetchAdminAgendamentos(filters)`, `criarAgendamentoManual(payload)`, `fetchGoogleCalendarEvents(params)`.

- [ ] **Step 1: Escrever testes unitários do cliente de API frontend (RED)**

Criar `frontend/tests/lib/api/agendamentos.test.ts` mockando `fetch` e validando URLs e payloads para cada função.

- [ ] **Step 2: Executar testes para verificar falha (RED)**

Run: `npx vitest run tests/lib/api/agendamentos.test.ts`
Expected: FAIL com módulo não encontrado

- [ ] **Step 3: Implementar tipos e funções de API (GREEN)**

1. `frontend/lib/types/agendamentos.ts`: interfaces `Agendamento`, `AgendamentoAdmin`, `AgendamentoManualInput`, `GoogleCalendarEvent`.
2. `frontend/lib/api/agendamentos.ts`: métodos usando `API_BASE_URL` com tratamento de erros.

- [ ] **Step 4: Executar testes do cliente de API (GREEN)**

Run: `npx vitest run tests/lib/api/agendamentos.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/types/agendamentos.ts frontend/lib/api/agendamentos.ts frontend/tests/lib/api/agendamentos.test.ts
git commit -m "feat(frontend): adiciona tipos e cliente de API para agendamentos"
```

---

### Task 6: Página do Cliente de Agendamentos (`/agendamentos`)

**Files:**
- Modify: `frontend/app/agendamentos/page.tsx`
- Create: `frontend/tests/components/AgendamentosPage.test.tsx`

**Interfaces:**
- Consumes: `useAuthStore`, `useChatStore`, `fetchMeusAgendamentos`, `cancelarAgendamento`.
- Produces: Página interativa do cliente com listagem, modal de confirmação para desmarcar e banner de novo agendamento via Chat.

- [ ] **Step 1: Escrever testes do componente de página do cliente (RED)**

Em `frontend/tests/components/AgendamentosPage.test.tsx`:
1. Renderiza mensagem de login quando deslogado.
2. Quando logado, renderiza cards de agendamentos confirmados e cancelados.
3. Ao clicar em "Desmarcar Visita", abre diálogo de confirmação e, ao confirmar, chama `cancelarAgendamento`.
4. Ao clicar no CTA de novo agendamento, chama `useChatStore.getState().open()`.

- [ ] **Step 2: Executar testes para verificar falha (RED)**

Run: `npx vitest run tests/components/AgendamentosPage.test.tsx`
Expected: FAIL

- [ ] **Step 3: Implementar `frontend/app/agendamentos/page.tsx` (GREEN)**

Construir a interface completa com:
- Header com ícone e descrição.
- Seletor de estado (deslogado / sem agendamentos / lista de agendamentos).
- Cards com formatação de data brasileira, badges com cores semânticas e link para o Google Calendar.
- Diálogo de confirmação para desmarcar.
- Banner de novo agendamento acionando o Chat.

- [ ] **Step 4: Executar testes da página de agendamentos (GREEN)**

Run: `npx vitest run tests/components/AgendamentosPage.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/app/agendamentos/page.tsx frontend/tests/components/AgendamentosPage.test.tsx
git commit -m "feat(frontend): implementa pagina de agendamentos do cliente com cancelamento"
```

---

### Task 7: Painel Administrativo de Agendamentos (`/admin/agendamentos`) e Navegação

**Files:**
- Create: `frontend/app/admin/agendamentos/page.tsx`
- Modify: `frontend/components/layout/AdminGearMenu.tsx`
- Create: `frontend/tests/components/AdminAgendamentosPage.test.tsx`

**Interfaces:**
- Consumes: `fetchAdminAgendamentos`, `criarAgendamentoManual`, `fetchGoogleCalendarEvents`, `cancelarAgendamento`, `useAuthStore`.
- Produces: Rota `/admin/agendamentos` com Abas (Sistema por Usuário vs Google Calendar) e Modal de Agendamento Manual.

- [ ] **Step 1: Escrever testes do painel administrativo (RED)**

Em `frontend/tests/components/AdminAgendamentosPage.test.tsx`:
1. Bloqueia acesso quando usuário não for Admin (Review Focus 5).
2. Para Admin, renderiza métricas e lista de agendamentos na Aba 1.
3. Permite alternar para a Aba 2 e exibe eventos do Google Calendar.
4. Abre modal "+ Agendar Manualmente", preenche formulário e envia com sucesso.

- [ ] **Step 2: Executar testes para verificar falha (RED)**

Run: `npx vitest run tests/components/AdminAgendamentosPage.test.tsx`
Expected: FAIL

- [ ] **Step 3: Implementar `frontend/app/admin/agendamentos/page.tsx` e link no `AdminGearMenu` (GREEN)**

1. Construir a página administrativa com as duas abas interativas, tabela com busca/filtros e modal de agendamento manual.
2. Adicionar o item `📅 Gestão de Agendamentos` no menu suspenso de [`AdminGearMenu.tsx`](file:///home/augusto/Projetos/TCC/frontend/components/layout/AdminGearMenu.tsx).

- [ ] **Step 4: Executar testes do painel admin (GREEN)**

Run: `npx vitest run tests/components/AdminAgendamentosPage.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/app/admin/agendamentos/page.tsx frontend/components/layout/AdminGearMenu.tsx frontend/tests/components/AdminAgendamentosPage.test.tsx
git commit -m "feat(admin): implementa painel administrativo de agendamentos e integracao com Google Calendar"
```

---

### Task 8: Verificação Completa e Atualização de Documentação

**Files:**
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/FRONTEND.md`
- Modify: `docs/ROADMAP.md`

- [ ] **Step 1: Executar suíte completa de testes no Backend**

Run: `cd backend && .venv/bin/pytest`
Expected: 100% dos testes passando (sem falhas ou regressões).

- [ ] **Step 2: Executar suíte completa de testes no Frontend**

Run: `cd frontend && npx vitest run`
Expected: 100% dos testes passando.

- [ ] **Step 3: Executar build de produção do Frontend**

Run: `cd frontend && npm run build`
Expected: Exit code 0, rotas `/agendamentos` e `/admin/agendamentos` compiladas com sucesso.

- [ ] **Step 4: Atualizar documentação técnica e roadmap**

1. Marcar item correspondente da Fase 7 em `docs/ROADMAP.md` como concluído (`[x]`).
2. Atualizar seções correspondentes de arquitetura em `docs/ARCHITECTURE.md` e `docs/FRONTEND.md`.

- [ ] **Step 5: Commit final**

```bash
git add docs/ROADMAP.md docs/ARCHITECTURE.md docs/FRONTEND.md
git commit -m "docs(agendamentos): conclui item da Fase 7 de agendamentos no roadmap e documentacao"
```
