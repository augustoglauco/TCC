# Design — Gestão de Agendamentos (Fase 7 do Roadmap, R11)

> Spec resultante de sessão de brainstorming com o desenvolvedor em 2026-09-29.
> Implementa a seção completa de Agendamentos prevista na Fase 7 do roadmap, integrando o agendamento iniciado pelo visitante via Chat com a gestão administrativa, cancelamento pelo cliente e consulta direta à agenda corporativa no Google Calendar via MCP.

---

## 1. Visão Geral e Objetivos

1. **Agendamento pelo Cliente via Chat:**
   - O visitante/cliente solicita e confirma visitas técnicas ou comerciais diretamente através do Chat Inteligente (fluxo de agendamento R11).
   - Ao confirmar o agendamento, o sistema cria o evento na agenda corporativa via MCP Google Calendar e grava o registro correspondente no banco de dados Postgres (`agendamentos`), vinculado ao e-mail do usuário e à conversa.
2. **Visualização e Cancelamento pelo Usuário (`/agendamentos`):**
   - O usuário autenticado visualiza exclusivamente os seus agendamentos (ordenados cronologicamente, com status, horário e link do Google Calendar).
   - O usuário pode desmarcar/cancelar agendamentos confirmados. O cancelamento atualiza o status para `"cancelado"` no banco (preservando histórico para auditoria) e remove o evento da agenda do Google via MCP.
   - Novos agendamentos pelo usuário continuam centralizados no Chat (com CTA claro na tela).
3. **Gestão Administrativa (`/admin/agendamentos`):**
   - Acesso restrito a usuários com perfil `Admin`.
   - **Gestão por Usuário:** Visão de todos os agendamentos registrados no sistema com busca/filtros por e-mail, nome e status, e ação de desmarcar.
   - **Agendamento Manual pelo Admin:** Modal para agendar visitas diretamente em nome de qualquer cliente/e-mail, validando horários e sincronizando com o Google Calendar.
   - **Consulta Google Calendar:** Consulta em tempo real via MCP (`find_events`) para o administrador auditar e inspecionar diretamente os eventos presentes na agenda corporativa oficial do Google.

---

## 2. Decisão de Arquitetura: Híbrido Sincronizado

- **Postgres como Fonte de Verdade da Aplicação:** A tabela `agendamentos` mantém a integridade referencial com os clientes, conversas do chat e histórico de status (mesmo após cancelamento), permitindo auditoria comercial.
- **MCP Google Calendar como Barramento de Agenda Corporativa:** Gerencia a ocupação de horários oficiais, criação de eventos de calendário e envio automático de convites.
- **Cancelamento Bidirecional Gracioso:** O cancelamento no Postgres é imediato; em seguida, tenta-se remover o evento no Google Calendar via MCP. Caso o evento já tenha sido excluído lá ou o MCP esteja temporariamente indisponível, a operação no banco é mantida e um log de aviso é registrado sem quebrar a requisição do usuário.

---

## 3. Modelo de Dados (Postgres / SQLAlchemy)

### 3.1 Tabela `agendamentos` (Migração Alembic `0015`)

Em `backend/src/app/db/models.py`:

```python
class Agendamento(Base):
    __tablename__ = "agendamentos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_email: Mapped[str] = mapped_column(String, index=True)
    nome_cliente: Mapped[str] = mapped_column(String)
    telefone: Mapped[str | None] = mapped_column(String, nullable=True)
    data_hora_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    data_hora_fim: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="confirmado", index=True)  # "confirmado" | "cancelado" | "concluido"
    origem: Mapped[str] = mapped_column(String, default="chat")  # "chat" | "manual_admin"
    google_event_id: Mapped[str | None] = mapped_column(String, nullable=True)
    google_event_link: Mapped[str | None] = mapped_column(String, nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

---

## 4. Extensão do Cliente MCP Google Calendar

No arquivo `backend/src/app/mcp_client/google_calendar.py`:

1. **`create_event`:**
   - Retorna uma tupla `tuple[str, str]` com `(google_event_id, html_link)`.
   - Se o servidor MCP não retornar o ID, gera string vazia para fallback.
2. **`delete_event(event_id: str) -> bool`:**
   - Invoca a tool `delete_event` passando `calendar_id` e `event_id`.
   - Retorna `True` em caso de sucesso; ignora e loga se o evento não for encontrado (`404` do Google).
3. **`list_events(time_min: datetime, time_max: datetime) -> list[dict]`:**
   - Invoca a tool `find_events` com a janela informada.
   - Retorna a lista de eventos brutos contendo `id`, `summary`, `description`, `start_time`, `end_time`, `html_link`, `attendees`.

---

## 5. Integração com o Chat e Orquestrador

Em `backend/src/app/router/orchestrator.py` (`_handle_agendamento`):
- Ao confirmar o agendamento (`slots.awaiting_confirmation` e `extraction.confirmacao`):
  1. Chama `calendar_client.create_event(...)` obtendo `(google_event_id, google_event_link)`.
  2. Persiste o registro na tabela `agendamentos` do Postgres via sessão do banco da aplicação:
     - `user_email = slots.email`
     - `nome_cliente = slots.nome`
     - `telefone = slots.telefone`
     - `data_hora_inicio = slots.data_hora`
     - `data_hora_fim = slots.data_hora + DURACAO_VISITA`
     - `google_event_id = google_event_id`
     - `google_event_link = google_event_link`
     - `origem = "chat"`
     - `status = "confirmado"`
     - `conversation_id = conversation_id`
  3. Limpa os slots da conversa (`clear_booking_slots(conversation_id)`) e emite mensagem de sucesso com o link da agenda.

---

## 6. Endpoints da API REST (`/api/agendamentos`)

Em `backend/src/app/api/agendamentos.py`:

### 6.1 Endpoints do Cliente / Usuário
- `GET /api/agendamentos/meus?user_email={email}`
  - Retorna lista de agendamentos associados a `user_email`, ordenados por `data_hora_inicio DESC`.
  - Campos: `id`, `data_hora_inicio`, `data_hora_fim`, `nome_cliente`, `telefone`, `descricao`, `status`, `google_event_link`, `criado_em`.
- `POST /api/agendamentos/{id}/cancelar`
  - Parâmetros: `id: UUID`, `user_email: str`.
  - Verifica se o solicitante é dono do agendamento ou admin. Caso contrário, `403 Forbidden`.
  - Se `status == "cancelado"`, retorna `400 Bad Request`.
  - Atualiza `status = "cancelado"`.
  - Se houver `google_event_id`, dispara remoção no Google Calendar via `delete_event`.
  - Retorna o agendamento atualizado.

### 6.2 Endpoints Administrativos
- `GET /api/agendamentos/admin`
  - Permite filtros opcionais: `filtro_email`, `status`, `data_inicio`, `data_fim`.
  - Retorna lista completa com todos os dados de agendamentos do sistema.
- `POST /api/agendamentos/admin/manual`
  - Body: `AgendamentoManualCreate` (`user_email`, `nome_cliente`, `telefone`, `data_hora_inicio`, `data_hora_fim?`, `descricao?`, `forcar_sem_validacao?`).
  - Checa disponibilidade via `calendar_client.is_time_available`.
  - Cria no Google Calendar via `calendar_client.create_event`.
  - Grava no banco com `origem = "manual_admin"` e `status = "confirmado"`.
  - Retorna o agendamento cadastrado.
- `GET /api/agendamentos/admin/google-events`
  - Parâmetros: `time_min: datetime?`, `time_max: datetime?` (padrão: próximo mês).
  - Consulta direta no Google Calendar via `calendar_client.list_events`.
  - Retorna eventos da agenda corporativa para conferência em tempo real.

---

## 7. Frontend e Interface do Usuário

### 7.1 Página do Cliente (`frontend/app/agendamentos/page.tsx`)
- Se deslogado: card explicativo com botão para `/conta/login` e aviso de agendamento via Chat.
- Se logado:
  - Lista de cards com data/horário formatados em português, título, badge de status (`Confirmado` / `Cancelado`) e link para o Google Calendar.
  - Botão **"Desmarcar"** em agendamentos confirmados:
    - Diálogo de confirmação para evitar cliques acidentais.
    - Atualização otimista com feedback de sucesso via toast/alerta.
  - Banner explicativo de que novos agendamentos devem ser realizados pelo Chat, com botão que abre o widget (`useChatStore.getState().open()`).

### 7.2 Painel Administrativo (`frontend/app/admin/agendamentos/page.tsx`)
- Guardião de acesso: restrito a `user?.perfil === "Admin"`.
- Cabeçalho com métricas (Total, Confirmados, Cancelados) e botão **"+ Agendar Manualmente"**.
- Abas interativas:
  - **Aba 1: Agendamentos por Usuário (Sistema):**
    - Busca textual por nome/e-mail e filtro por status.
    - Tabela completa com cliente, horário, origem (Chat/Manual), status, link Google e ação de desmarcar.
  - **Aba 2: Consulta Google Calendar:**
    - Filtro de período de datas.
    - Listagem direta dos eventos da agenda Google via MCP com horário, convidados, resumo e link.
- **Modal de Agendamento Manual:**
  - Formulário com e-mail, nome, telefone, data/hora e descrição da visita.
  - Feedback em caso de conflito de agenda no Google.

### 7.3 Navegação
- Item no menu suspenso do administrador em [`AdminGearMenu.tsx`](file:///home/augusto/Projetos/TCC/frontend/components/layout/AdminGearMenu.tsx):
  `📅 Gestão de Agendamentos` -> `/admin/agendamentos`.
- Link principal no [`Header.tsx`](file:///home/augusto/Projetos/TCC/frontend/components/layout/Header.tsx): `/agendamentos` já existente no menu.

---

## 8. Estratégia de Testes

1. **Backend:**
   - Testes unitários do model e repositório `Agendamento` no Postgres em memória (`test_agendamentos_db.py`).
   - Testes da extensão do cliente MCP (`test_google_calendar_client.py`): `delete_event`, `list_events`, retorno de `(id, link)`.
   - Testes de integração da API (`test_agendamentos_api.py`):
     - Listagem de agendamentos por usuário;
     - Cancelamento por usuário e verificação de permissão (`403` para outros usuários);
     - Endpoints administrativos de listagem, agendamento manual e consulta de eventos do Google;
     - Persistência ao confirmar via Chat.
2. **Frontend:**
   - Testes de componentes com React Testing Library / Vitest:
     - `AgendamentosPage.test.tsx`: renderização deslogado vs logado, listagem de cards, ação de desmarcar;
     - `AdminAgendamentosPage.test.tsx`: bloqueio para não-admin, alternância de abas, submissão do modal de agendamento manual.
