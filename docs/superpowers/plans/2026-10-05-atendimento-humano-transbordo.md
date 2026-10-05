# Atendimento Humano e Transbordo Dinâmico (Human-in-the-Loop) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar transbordo dinâmico (*Human-in-the-Loop*) de conversas do chat público para atendentes humanos no painel administrativo (`/admin/atendimento`), com fila de espera, locks atômicos contra conflito de atendimento, suspensão automática da IA durante o atendimento humano e visualização contextual completa do cliente.

**Architecture:** A tabela `conversas` recebe controle de ciclo de vida (`status`: `aberta`/`ia_ativa`, `aguardando_humano`, `em_atendimento_humano`, `encerrada`), identificador do operador (`atendente_id`/`atendente_nome`), motivo de escalonamento e prioridade. O orquestrador de chat (`/api/chat/messages`) suspende chamadas de LLM para conversas em fila ou atendimento humano, gravando mensagens do cliente e notificando via SSE. Uma nova API administrativa (`/api/admin/atendimento`) oferece fila com lock atômico condicional (`UPDATE ... WHERE status = 'aguardando_humano' AND atendente_id IS NULL`), envio de mensagens pelo operador e devolução/encerramento. No frontend, uma central administrativa de três colunas em `/admin/atendimento` permite aos operadores gerenciar a fila e responder em tempo real, enquanto o widget público exibe mensagens do atendente e status de conexão.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (async), PostgreSQL (asyncpg), Alembic, Pydantic v2, Next.js 14 (App Router), React, Tailwind CSS, TypeScript, Zustand, Vitest, Pytest.

**Spec:** `docs/superpowers/specs/2026-10-03-atendimento-humano-transbordo-design.md`

## Global Constraints

- Python 3.11+ assíncrono com SQLAlchemy 2.0 e asyncpg.
- Toda modificação estrutural de banco de dados deve ser versionada via Alembic migration (`0021_atendimento_humano_transbordo.py`).
- Autenticação obrigatória nos endpoints administrativos via dependência de segurança de admin.
- Suspensão estrita da IA quando `status in ("aguardando_humano", "em_atendimento_humano")`: nenhuma chamada externa ou local de LLM deve ser faturada ou disparada.
- Concorrência prevenida por lock atômico em nível de banco (`UPDATE ... WHERE status = 'aguardando_humano' AND atendente_id IS NULL`), retornando HTTP 409 em caso de colisão.
- Commits cirúrgicos, sem incluir arquivos de outros agentes ou unstaged changes alheias.

## Review Focus

1. **Race condition no claim simultâneo:** Dois atendentes clicando no mesmo chat da fila no mesmo milissegundo deve resultar em exatamente 1 atendente com sucesso (200 OK) e o outro com HTTP 409 Conflito, sem estado corrompido no banco.
2. **Pausa garantida de custos e tokens de IA:** Mensagens enviadas pelo cliente enquanto o chat está em atendimento humano não podem invocar nem Ollama nem OpenRouter, consumindo 0 tokens e gerando $0,00 de custo.
3. **Resiliência do widget de chat:** Mensagens recebidas do atendente humano (`papel = "atendente"`) devem ser renderizadas visualmente com destaque (verde/esmeralda com identificação de atendente humano) e salvas no histórico local.
4. **Devolução limpa para IA:** Ao devolver a conversa para a IA (`status = "aberta"`), a próxima mensagem do cliente deve voltar a ser atendida pelo bot com contexto prévio intacto.
5. **Encerramento sincronizado:** Quando o atendente encerra a conversa, o status passa para `"encerrada"`, com timestamp `encerrada_em` e motivo registrado, refletindo imediatamente nas métricas administrativas.

---

### Task 1: Migration 0021 & Modelos SQLAlchemy (`conversas` e `conversa_mensagens`)

**Files:**
- Create: `backend/migrations/versions/0021_atendimento_humano_transbordo.py`
- Modify: `backend/src/app/db/models.py`
- Test: `backend/tests/test_atendimento_humano_models.py`

**Interfaces:**
- Consumes: Modelos `Conversa` e `ConversaMensagem` de `app.db.models`.
- Produces: Colunas `atendente_id`, `atendente_nome`, `motivo_escalonamento`, `prioridade`, `escalado_em` em `Conversa`; coluna `atendente_nome` em `ConversaMensagem`; aceitação do papel `"atendente"`.

- [ ] **Step 1: Escrever teste de unidade que valida o schema dos modelos**

Criar `backend/tests/test_atendimento_humano_models.py` testando a instanciação e persistência de conversas com os novos campos de atendimento humano e mensagem com `papel="atendente"`.

```python
import pytest
from datetime import datetime, UTC
from sqlalchemy import select
from app.db.models import Conversa, ConversaMensagem

@pytest.mark.asyncio
async def test_conversa_atendimento_humano_fields(db_session):
    now = datetime.now(UTC)
    conversa = Conversa(
        id="conv-transbordo-1",
        status="aguardando_humano",
        atendente_id="op_123",
        atendente_nome="Carlos Suporte",
        motivo_escalonamento="tom_frustrado",
        prioridade=5,
        escalado_em=now,
    )
    db_session.add(conversa)
    await db_session.flush()

    msg = ConversaMensagem(
        conversa_id="conv-transbordo-1",
        papel="atendente",
        atendente_nome="Carlos Suporte",
        texto="Olá! Sou o Carlos e assumi seu atendimento. Como posso ajudar?",
    )
    db_session.add(msg)
    await db_session.commit()

    saved_conv = await db_session.get(Conversa, "conv-transbordo-1")
    assert saved_conv.status == "aguardando_humano"
    assert saved_conv.atendente_id == "op_123"
    assert saved_conv.atendente_nome == "Carlos Suporte"
    assert saved_conv.motivo_escalonamento == "tom_frustrado"
    assert saved_conv.prioridade == 5
    assert saved_conv.escalado_em is not None

    stmt = select(ConversaMensagem).where(ConversaMensagem.conversa_id == "conv-transbordo-1")
    res = await db_session.execute(stmt)
    saved_msg = res.scalar_one()
    assert saved_msg.papel == "atendente"
    assert saved_msg.atendente_nome == "Carlos Suporte"
```

- [ ] **Step 2: Executar teste e verificar falha**

Run: `backend/.venv/bin/pytest backend/tests/test_atendimento_humano_models.py -v`
Expected: FAIL (AttributeError ou campos não reconhecidos no modelo).

- [ ] **Step 3: Criar migração Alembic 0021 e atualizar `models.py`**

Criar `backend/migrations/versions/0021_atendimento_humano_transbordo.py` aplicando `add_column` para:
- `conversas`: `atendente_id` (String 100, nullable=True), `atendente_nome` (String 100, nullable=True), `motivo_escalonamento` (String 100, nullable=True), `prioridade` (Integer, server_default="1", nullable=False), `escalado_em` (DateTime tz=True, nullable=True).
- `conversas`: criar índice em `(status, prioridade, escalado_em)`.
- `conversa_mensagens`: `atendente_nome` (String 100, nullable=True).

Atualizar `Conversa` e `ConversaMensagem` em `backend/src/app/db/models.py`.

- [ ] **Step 4: Aplicar migração e executar o teste**

Run:
```bash
PYTHONPATH=backend/src backend/.venv/bin/alembic -c backend/alembic.ini upgrade head
backend/.venv/bin/pytest backend/tests/test_atendimento_humano_models.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add backend/migrations/versions/0021_atendimento_humano_transbordo.py backend/src/app/db/models.py backend/tests/test_atendimento_humano_models.py
git commit -m "feat(atendimento): adiciona colunas de transbordo e atendimento humano em conversas e mensagens (migration 0021)"
```

---

### Task 2: Serviço de Atendimento Humano (`atendimento_service.py`) com Locks Atômicos

**Files:**
- Create: `backend/src/app/services/atendimento_service.py`
- Test: `backend/tests/test_atendimento_service.py`

**Interfaces:**
- Consumes: `Conversa`, `ConversaMensagem` e `AsyncSession`.
- Produces:
  - `escalar_para_humano(session, conversation_id, motivo, prioridade) -> Conversa`
  - `listar_fila_espera(session) -> list[dict]`
  - `listar_meus_chats(session, atendente_id) -> list[dict]`
  - `obter_detalhes_atendimento(session, conversation_id) -> dict | None`
  - `claim_conversa(session, conversation_id, atendente_id, atendente_nome) -> bool` (retorna True se assumiu com sucesso, False se colidiu/já assumida)
  - `enviar_mensagem_atendente(session, conversation_id, atendente_nome, texto) -> ConversaMensagem`
  - `finalizar_atendimento(session, conversation_id, motivo) -> Conversa`
  - `devolver_para_ia(session, conversation_id) -> Conversa`

- [ ] **Step 1: Escrever teste de unidade para regras de serviço e lock atômico**

Criar `backend/tests/test_atendimento_service.py` testando:
1. `escalar_para_humano` atualizando status para `aguardando_humano`.
2. `claim_conversa` retornando `True` no primeiro claim e `False` (sem corromper) no segundo claim concorrente.
3. `enviar_mensagem_atendente` gravando mensagem com papel `"atendente"`.
4. `devolver_para_ia` resetando status para `"aberta"` e limpando `atendente_id`.

- [ ] **Step 2: Executar teste e verificar falha**

Run: `backend/.venv/bin/pytest backend/tests/test_atendimento_service.py -v`
Expected: FAIL (módulo `atendimento_service` não encontrado).

- [ ] **Step 3: Implementar `backend/src/app/services/atendimento_service.py`**

Implementar todas as operações assíncronas com tratamento rigoroso de integridade, incluindo a cláusula atômica:
```python
stmt = (
    update(Conversa)
    .where(
        Conversa.id == conversation_id,
        Conversa.status == "aguardando_humano",
        Conversa.atendente_id.is_(None),
    )
    .values(
        status="em_atendimento_humano",
        atendente_id=atendente_id,
        atendente_nome=atendente_nome,
    )
)
result = await session.execute(stmt)
return result.rowcount > 0
```

- [ ] **Step 4: Executar testes e verificar aprovação**

Run: `backend/.venv/bin/pytest backend/tests/test_atendimento_service.py -v`
Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add backend/src/app/services/atendimento_service.py backend/tests/test_atendimento_service.py
git commit -m "feat(atendimento): cria servico de atendimento humano com claim atomico e gestao de ciclo de vida"
```

---

### Task 3: Integração no Orquestrador e Chat SSE (`chat.py`) com Pausa da IA e Gatilhos

**Files:**
- Modify: `backend/src/app/api/chat.py`
- Modify: `backend/src/app/router/orchestrator.py`
- Create: `backend/tests/test_chat_transbordo_pausa.py`

**Interfaces:**
- Consumes: `app.services.atendimento_service.escalar_para_humano`, status da conversa.
- Produces: Pausa do LLM quando conversa estiver em atendimento humano, emissão de SSE `status` e endpoint de solicitação direta de atendente (`POST /api/chat/conversations/{id}/transbordo`).

- [ ] **Step 1: Escrever teste de unidade que valida a pausa da IA e gatilho de transbordo**

Criar `backend/tests/test_chat_transbordo_pausa.py`:
1. Testar que quando `conversa.status == "aguardando_humano"`, enviar mensagem grava a mensagem do cliente, NÃO chama LLM (0 tokens faturados) e emite SSE informando espera por atendente.
2. Testar que quando `conversa.status == "em_atendimento_humano"`, a mensagem do cliente é entregue sem disparar LLM.
3. Testar endpoint `POST /api/chat/conversations/{id}/transbordo` que coloca a conversa em `aguardando_humano` sob demanda.
4. Testar que quando o monitor de tom dispara `EscalonamentoEvent(motivo="tom_frustrado")`, a conversa é persistida como `aguardando_humano` com `prioridade=5`.

- [ ] **Step 2: Executar teste e verificar falha**

Run: `backend/.venv/bin/pytest backend/tests/test_chat_transbordo_pausa.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar a lógica no `chat.py`**

1. Em `send_message` (`POST /api/chat/messages`):
   Verificar o status atual da conversa no Postgres:
   ```python
   if conversa_db and conversa_db.status in ("aguardando_humano", "em_atendimento_humano"):
       # Grava mensagem do cliente
       await _gravar_mensagem_cliente_direta(request.app.state, conversation_id, effective_message)
       # Emite evento de status no SSE e encerra sem LLM
       yield _sse("status", {"status": conversa_db.status, "atendente_nome": conversa_db.atendente_nome})
       msg_info = (
           "Sua mensagem foi recebida. Um atendente humano responderá em breve."
           if conversa_db.status == "aguardando_humano"
           else f"Mensagem enviada para {conversa_db.atendente_nome}."
       )
       yield _sse("token", {"text": msg_info})
       yield _sse("done", ChatDoneEventData(conversa_status=conversa_db.status).model_dump(mode="json"))
       return
   ```
2. Ao receber `EscalonamentoEvent` no stream: além de emitir SSE, atualizar a conversa no banco para `status = "aguardando_humano"`, `motivo_escalonamento = "tom_frustrado"`, `prioridade = 5`, `escalado_em = func.now()`.
3. Adicionar rota `POST /api/chat/conversations/{conversation_id}/transbordo` para solicitação direta via botão do widget.

- [ ] **Step 4: Executar testes e verificar aprovação**

Run: `backend/.venv/bin/pytest backend/tests/test_chat_transbordo_pausa.py -v`
Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add backend/src/app/api/chat.py backend/src/app/router/orchestrator.py backend/tests/test_chat_transbordo_pausa.py
git commit -m "feat(chat): integra transbordo dinamico e pausa automatica do LLM durante atendimento humano"
```

---

### Task 4: Endpoints REST Administrativos (`/api/admin/atendimento`)

**Files:**
- Create: `backend/src/app/api/admin_atendimento.py`
- Modify: `backend/src/app/main.py`
- Test: `backend/tests/test_admin_atendimento_api.py`

**Interfaces:**
- Consumes: `app.services.atendimento_service`, `app.api.admin_auth.require_admin`.
- Produces: Router `/api/admin/atendimento` com rotas para fila, claim (com 409 em conflito), histórico, mensagens de operador e encerramento/devolução.

- [ ] **Step 1: Escrever testes unitários da API administrativa**

Criar `backend/tests/test_admin_atendimento_api.py`:
- `GET /api/admin/atendimento/fila`: exige token admin e retorna itens ordenados por prioridade desc.
- `POST /api/admin/atendimento/{id}/claim`: retorna 200 ao assumir; retorna 409 Conflict se tentar assumir conversa já reivindicada.
- `POST /api/admin/atendimento/{id}/mensagem`: grava mensagem de atendente com nome autenticado.
- `POST /api/admin/atendimento/{id}/close`:
  - com `{"acao": "finalizar"}` -> fecha conversa.
  - com `{"acao": "devolver_ia"}` -> retorna conversa para `aberta`.

- [ ] **Step 2: Executar testes e verificar falha**

Run: `backend/.venv/bin/pytest backend/tests/test_admin_atendimento_api.py -v`
Expected: FAIL (404 Not Found para rotas de `/api/admin/atendimento`).

- [ ] **Step 3: Implementar `backend/src/app/api/admin_atendimento.py` e registrar em `main.py`**

Criar endpoints autenticados usando `require_admin` e conectando diretamente ao `atendimento_service`.

- [ ] **Step 4: Executar testes e verificar aprovação**

Run: `backend/.venv/bin/pytest backend/tests/test_admin_atendimento_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add backend/src/app/api/admin_atendimento.py backend/src/app/main.py backend/tests/test_admin_atendimento_api.py
git commit -m "feat(api): adiciona endpoints administrativos para gestao de fila de atendimento humano"
```

---

### Task 5: Cliente Frontend e Suporte no Chat Widget

**Files:**
- Create: `frontend/lib/api/adminAtendimento.ts`
- Modify: `frontend/lib/types/chat.ts`
- Modify: `frontend/components/chat/MessageBubble.tsx`
- Modify: `frontend/components/chat/ChatWidget.tsx` (ou hooks associados)
- Test: `frontend/tests/components/ChatWidgetTransbordo.test.tsx`

**Interfaces:**
- Consumes: `/api/admin/atendimento` e `/api/chat/conversations/{id}/transbordo`.
- Produces: Exibição de balões verdes para atendentes humanos, indicador de fila no chat e botão "Falar com atendente humano".

- [ ] **Step 1: Escrever teste de unidade no frontend para renderização de atendente humano**

Criar `frontend/tests/components/ChatWidgetTransbordo.test.tsx`:
- Renderizar mensagem com `papel: "atendente"` com badge verde "Atendente Humano" e nome do operador.
- Testar botão de solicitação de atendente humano disparando API de transbordo.

- [ ] **Step 2: Executar teste e verificar falha**

Run: `npm --prefix frontend test -- tests/components/ChatWidgetTransbordo.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implementar atualizações no frontend**

1. `frontend/lib/types/chat.ts`: adicionar `"atendente"` aos papéis válidos e campo `atendente_nome?: string`.
2. `frontend/components/chat/MessageBubble.tsx`: adicionar estilo para balão de atendente humano (borda verde/esmeralda, badge discreto com nome do atendente).
3. `frontend/lib/api/adminAtendimento.ts`: criar funções tipadas para `fetchFilaEspera`, `claimConversa`, `enviarMensagemAtendente`, `fecharAtendimento`, `solicitarTransbordo`.

- [ ] **Step 4: Executar testes e validar aprovação**

Run: `npm --prefix frontend test -- tests/components/ChatWidgetTransbordo.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit Task 5**

```bash
git add frontend/lib/api/adminAtendimento.ts frontend/lib/types/chat.ts frontend/components/chat/MessageBubble.tsx frontend/tests/components/ChatWidgetTransbordo.test.tsx
git commit -m "feat(frontend): adiciona suporte a mensagens e transbordo para atendente humano no widget de chat"
```

---

### Task 6: Interface da Central de Atendimento Humano (`/admin/atendimento`)

**Files:**
- Create: `frontend/app/admin/atendimento/page.tsx`
- Create: `frontend/components/admin/atendimento/FilaEsperaPanel.tsx`
- Create: `frontend/components/admin/atendimento/MeusChatsTabs.tsx`
- Create: `frontend/components/admin/atendimento/ContextoClientePanel.tsx`
- Modify: `frontend/components/layout/AdminGearMenu.tsx`
- Test: `frontend/tests/components/AdminAtendimentoPage.test.tsx`

**Interfaces:**
- Consumes: `adminAtendimento.ts`, `useAuthStore`.
- Produces: Tela `/admin/atendimento` de três colunas: Fila de Espera, Chat Ativo com histórico unificado e Painel de Contexto do Cliente com dados cadastrais e compras.

- [ ] **Step 1: Escrever teste de unidade para a página `/admin/atendimento`**

Criar `frontend/tests/components/AdminAtendimentoPage.test.tsx`:
- Renderizar aviso de restrição se não for admin.
- Exibir conversas da fila de espera com motivo de escalonamento.
- Clicar em "Assumir Atendimento" e abrir a aba de chat do operador.
- Enviar mensagem de atendente e exibir no histórico.
- Exibir feedback de erro amigável se a conversa já foi assumida (409 Conflict).
- Concluir atendimento com devolução para IA ou encerramento final.

- [ ] **Step 2: Executar teste e verificar falha**

Run: `npm --prefix frontend test -- tests/components/AdminAtendimentoPage.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implementar componentes e página `/admin/atendimento`**

1. Implementar `FilaEsperaPanel.tsx` com badges, timers e botão "Assumir".
2. Implementar `MeusChatsTabs.tsx` com histórico de mensagens, identificação de papéis e caixa de digitação rápida.
3. Implementar `ContextoClientePanel.tsx` com dados cadastrais, e-mail, telefone, histórico de compras e motivo do transbordo.
4. Montar `frontend/app/admin/atendimento/page.tsx`.
5. Adicionar link no menu `AdminGearMenu.tsx`.

- [ ] **Step 4: Executar testes e verificar aprovação**

Run:
```bash
npm --prefix frontend test -- tests/components/AdminAtendimentoPage.test.tsx
./frontend/node_modules/.bin/tsc --project frontend/tsconfig.json --noEmit
```
Expected: PASS.

- [ ] **Step 5: Commit Task 6**

```bash
git add frontend/app/admin/atendimento/page.tsx frontend/components/admin/atendimento/ frontend/components/layout/AdminGearMenu.tsx frontend/tests/components/AdminAtendimentoPage.test.tsx
git commit -m "feat(admin): implementa Central de Atendimento Humano em /admin/atendimento com gestao de fila e contexto de cliente"
```

---

### Task 7: Verificação Integrada, Testes Gerais e Roadmap

**Files:**
- Modify: `docs/ROADMAP.md`
- Modify: `docs/ARCHITECTURE.md`

- [ ] **Step 1: Executar suite completa do backend**

Run: `backend/.venv/bin/pytest backend/tests/test_atendimento_humano_models.py backend/tests/test_atendimento_service.py backend/tests/test_chat_transbordo_pausa.py backend/tests/test_admin_atendimento_api.py -v`
Expected: Todos os testes passando sem erros nem warnings críticos.

- [ ] **Step 2: Executar suite do frontend**

Run: `npm --prefix frontend test -- tests/components/AdminAtendimentoPage.test.tsx tests/components/ChatWidgetTransbordo.test.tsx`
Expected: Todos os testes passando.

- [ ] **Step 3: Validação de tipagem do frontend**

Run: `./frontend/node_modules/.bin/tsc --project frontend/tsconfig.json --noEmit`
Expected: 0 erros.

- [ ] **Step 4: Atualizar documentação e roadmap**

Atualizar `docs/ROADMAP.md` marcando a funcionalidade de transbordo e atendimento humano como concluída e documentar o fluxo em `docs/ARCHITECTURE.md`.

- [ ] **Step 5: Commit Task 7**

```bash
git add docs/ROADMAP.md docs/ARCHITECTURE.md
git commit -m "docs: documenta funcionalidade de transbordo e atendimento humano (Human-in-the-Loop) no roadmap e arquitetura"
```
