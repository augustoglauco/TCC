# Chat Admin com ferramentas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O Admin consulta o banco (SELECT), cria/edita produto, dá baixa em estoque e muda o status de uma venda (inclusive cancelar devolvendo ao estoque) pelo chat, sempre com prévia e confirmação, e tudo auditado.

**Architecture:** O LLM local só devolve uma *proposta* JSON (ferramenta + argumentos). Um módulo novo `app.admin_tools` valida, resolve produto/pedido, monta a prévia e grava a proposta em `chat_admin_acoes`. O chat mostra um card com Confirmar/Cancelar; o botão chama `POST /api/admin/chat/acoes/{id}/confirmar`, que revalida e executa dentro de uma transação. Leitura (`consultar`) executa direto via `safe_sql`. Não existe SQL de escrita em nenhum ponto.

**Tech Stack:** FastAPI, SQLAlchemy async (SQLite nos testes, Postgres em produção), Alembic, Pydantic v2, Next.js 16 + React, vitest.

**Spec:** `docs/superpowers/specs/2026-11-01-chat-admin-ferramentas-design.md`

## Global Constraints

- Só perfil Admin usa as ferramentas: `is_admin` no orquestrador; `require_admin` nos endpoints. Não-admin nunca vê prévia nem resultado.
- Toda escrita pede confirmação; a gravação só acontece no endpoint de confirmação, nunca a partir do texto da conversa.
- Sem SQL de escrita em lugar nenhum; `consultar` usa `app.services.safe_sql` (só SELECT, tabelas permitidas, `LIMIT 50`).
- Proposta expira em 10 minutos (`PROPOSTA_TTL = timedelta(minutes=10)`); proposta já executada/cancelada/expirada não executa de novo.
- Status de venda: `reservado`, `venda_concluida`, `pagamento_divergente`, e o novo `cancelada` (terminal). Transições só pela tabela da Task 5.
- Estoque: sempre `UPDATE … SET quantidade = quantidade ± n [WHERE quantidade >= n]` em uma instrução.
- Estilo: Python 3.14, ruff `line-length = 100`, CCN ≤ 9 e ≤ ~50 linhas por função, comentários `# MVP:` para simplificações, textos ao usuário em pt-BR.
- Cada tarefa atualiza `docs/ROADMAP.md`; ao final, ARCHITECTURE, FRONTEND, `docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md` e `docs/Manuais/HOWTO_ADMINISTRADOR.md` (regras 5, 6, 9 e 11 do CLAUDE.md).
- Antes de cada commit: ruff check, ruff format, pytest dos arquivos tocados (a suíte inteira pode estourar o timeout do `nvidia-smi`), e no frontend tsc, eslint e vitest.
- Commits terminam com `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` e `Claude-Session: https://claude.ai/code/session_01LWHU93RFKRBtczFPDwwTgx`. Push só quando o usuário pedir.

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `backend/src/app/admin_tools/__init__.py` | pacote |
| `backend/src/app/admin_tools/consulta.py` | `executar_consulta` (SELECT com tempo máximo) e `gerar_sql` (NL → SQL via LLM) |
| `backend/src/app/admin_tools/intencao.py` | `detectar_consulta`, `detectar_escrita`: classificador por palavras-chave |
| `backend/src/app/admin_tools/ferramentas.py` | registro das ferramentas de escrita: esquema de argumentos, `preparar` (prévia) e `executar` |
| `backend/src/app/admin_tools/propostas.py` | ciclo de vida: `criar_proposta`, `confirmar`, `cancelar` |
| `backend/src/app/admin_tools/handler.py` | `processar_pedido_admin`: gerador de eventos usado pelo orquestrador |
| `backend/src/app/api/admin_chat_acoes.py` | endpoints de confirmar/cancelar |
| `backend/src/app/db/models.py` | `ChatAdminAcao` |
| `backend/migrations/versions/0031_chat_admin_acoes.py` | tabela nova |
| `backend/src/app/models/chat.py` | `CardTabela`, `CardAcaoProposta` |
| `backend/src/app/router/orchestrator.py` | ligar o handler antes do gráfico |
| `backend/src/app/services/safe_sql.py` | nota semântica do status `cancelada` |
| `frontend/lib/types/chat.ts`, `lib/api/adminChatAcoes.ts` | tipos e cliente |
| `frontend/components/chat/cards/TabelaCard.tsx`, `AcaoPropostaCard.tsx`, `ChatCard.tsx` | cards |

---

### Task 1: `consultar(sql)` no chat Admin

**Files:**
- Create: `backend/src/app/admin_tools/__init__.py`, `consulta.py`, `intencao.py`, `handler.py`
- Modify: `backend/src/app/models/chat.py`, `backend/src/app/router/orchestrator.py`
- Test: `backend/tests/test_admin_tools_consulta.py`, `backend/tests/test_admin_tools_handler.py`
- Frontend: `frontend/lib/types/chat.ts`, `frontend/components/chat/cards/TabelaCard.tsx`, `ChatCard.tsx`, `frontend/tests/components/TabelaCard.test.tsx`

**Interfaces:**
- Produces: `executar_consulta(session: AsyncSession, sql: str) -> list[dict[str, Any]]`; `async gerar_sql(llm_client, pergunta: str, schema: str) -> str | None`; `detectar_consulta(message: str) -> bool`; `CardTabela(tipo="tabela", titulo: str, colunas: list[str], linhas: list[list[Any]], truncado: bool)`; `async processar_pedido_admin(message, *, is_admin, local_client, db_sessionmaker, intent_router_provider) -> AsyncIterator[TokenEvent | RouterDecision]` (não emite nada se não for pedido de ferramenta).

- [ ] **Step 1: Write the failing tests (consulta)**

```python
# backend/tests/test_admin_tools_consulta.py
import pytest

from app.admin_tools.consulta import executar_consulta, gerar_sql
from app.services.safe_sql import SQLSecurityError


@pytest.mark.asyncio
async def test_executar_consulta_devolve_linhas(db_session):
    linhas = await executar_consulta(db_session, "SELECT 1 AS um")
    assert linhas == [{"um": 1}]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM produtos",
        "SELECT * FROM produtos; DROP TABLE produtos",
        "SELECT * FROM usuarios_secretos",
        "UPDATE produtos SET preco = 0",
    ],
)
async def test_executar_consulta_bloqueia_escrita_e_tabela_fora_da_lista(db_session, sql):
    with pytest.raises(SQLSecurityError):
        await executar_consulta(db_session, sql)


class _LLM:
    def __init__(self, texto):
        self._texto = texto

    async def generate(self, prompt):
        class _R:
            response = self._texto
            text = self._texto

        return _R()


@pytest.mark.asyncio
async def test_gerar_sql_extrai_o_sql_do_json_do_modelo():
    llm = _LLM('{"sql": "SELECT nome FROM produtos"}')
    assert await gerar_sql(llm, "liste os produtos", "esquema") == "SELECT nome FROM produtos"


@pytest.mark.asyncio
async def test_gerar_sql_devolve_none_se_o_modelo_nao_responde_json():
    assert await gerar_sql(_LLM("não sei"), "x", "esquema") is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_tools_consulta.py -v`
Expected: FAIL (`ModuleNotFoundError: app.admin_tools`).

- [ ] **Step 3: Implement `consulta.py`**

```python
# backend/src/app/admin_tools/__init__.py  (arquivo vazio)
```

```python
# backend/src/app/admin_tools/consulta.py
"""Consulta SELECT pedida pelo Admin no chat (leitura, sem confirmação)."""

import json
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.safe_sql import execute_readonly_sql

TEMPO_MAX_MS = 5000

_PROMPT = """Você é um analista de dados PostgreSQL. O administrador perguntou: "{pergunta}".

{schema}

Responda APENAS com JSON válido: {{"sql": "SELECT ..."}}. Só SELECT; sem texto fora do JSON.
"""


async def executar_consulta(session: AsyncSession, sql: str) -> list[dict[str, Any]]:
    """Valida (safe_sql) e executa o SELECT com tempo máximo no Postgres.

    # MVP: o limite de tempo só existe no Postgres (`SET LOCAL statement_timeout`);
    # nos testes com SQLite a consulta roda sem ele.
    """
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        await session.execute(text(f"SET LOCAL statement_timeout = {TEMPO_MAX_MS}"))
    return await execute_readonly_sql(session, sql)


async def gerar_sql(llm_client: Any, pergunta: str, schema: str) -> str | None:
    """Pede ao LLM o SELECT que responde `pergunta`; None se a resposta não for o JSON esperado."""
    resposta = await llm_client.generate(_PROMPT.format(pergunta=pergunta, schema=schema))
    bruto = getattr(resposta, "response", getattr(resposta, "text", str(resposta)))
    achado = re.search(r"\{.*\}", bruto, re.DOTALL)
    if not achado:
        return None
    try:
        sql = json.loads(achado.group(0)).get("sql")
    except json.JSONDecodeError:
        return None
    return sql.strip() if isinstance(sql, str) and sql.strip() else None
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_tools_consulta.py -v`
Expected: PASS (7 testes).

- [ ] **Step 5: Write the failing tests (intenção + handler + card)**

```python
# backend/tests/test_admin_tools_handler.py
import pytest

from app.admin_tools.handler import processar_pedido_admin
from app.admin_tools.intencao import detectar_consulta
from app.router.orchestrator import RouterDecision, TokenEvent


@pytest.mark.parametrize(
    ("mensagem", "esperado"),
    [
        ("consulte quantos pedidos foram cancelados", True),
        ("liste os produtos da categoria CFTV", True),
        ("mostre o estoque do iDFace", True),
        ("qual o horário de atendimento?", False),
        ("gere um gráfico de vendas", False),
    ],
)
def test_detectar_consulta(mensagem, esperado):
    assert detectar_consulta(mensagem) is esperado


class _LLM:
    async def generate(self, prompt):
        class _R:
            response = text = '{"sql": "SELECT 1 AS um"}'

        return _R()


async def _coletar(gerador):
    return [e async for e in gerador]


@pytest.mark.asyncio
async def test_nao_admin_nao_executa_consulta(db_session):
    eventos = await _coletar(
        processar_pedido_admin(
            "liste os produtos",
            is_admin=False,
            local_client=_LLM(),
            db_sessionmaker=lambda: db_session,
            intent_router_provider="heuristica_llm",
        )
    )
    assert eventos == []


@pytest.mark.asyncio
async def test_admin_recebe_card_tabela_com_o_resultado(db_session, monkeypatch):
    class _Maker:
        def __call__(self):
            return self

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *a):
            return False

    eventos = await _coletar(
        processar_pedido_admin(
            "liste os produtos",
            is_admin=True,
            local_client=_LLM(),
            db_sessionmaker=_Maker(),
            intent_router_provider="heuristica_llm",
        )
    )
    decisao = next(e for e in eventos if isinstance(e, RouterDecision))
    assert decisao.card.tipo == "tabela"
    assert decisao.card.colunas == ["um"]
    assert decisao.card.linhas == [[1]]
    assert any(isinstance(e, TokenEvent) for e in eventos)
```

```tsx
// frontend/tests/components/TabelaCard.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import TabelaCard from "@/components/chat/cards/TabelaCard";

describe("TabelaCard", () => {
  it("mostra colunas e linhas e avisa quando o resultado foi truncado", () => {
    render(
      <TabelaCard
        card={{
          tipo: "tabela",
          titulo: "Produtos",
          colunas: ["nome", "preco"],
          linhas: [["iDFace", 1356.3]],
          truncado: true,
        }}
      />,
    );
    expect(screen.getByRole("columnheader", { name: "nome" })).toBeInTheDocument();
    expect(screen.getByText("iDFace")).toBeInTheDocument();
    expect(screen.getByText(/primeiras 50 linhas/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 6: Run to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_tools_handler.py -v` and `cd frontend && npx vitest run tests/components/TabelaCard.test.tsx`
Expected: FAIL (módulos inexistentes).

- [ ] **Step 7: Implement**

`backend/src/app/models/chat.py`: adicionar antes de `ChatCard`:

```python
class CardTabela(BaseModel):
    """Resultado de uma consulta SELECT do Admin no chat (`app.admin_tools`)."""

    tipo: Literal["tabela"] = "tabela"
    titulo: str
    colunas: list[str]
    linhas: list[list[Any]]
    truncado: bool = False
```

e incluir `CardTabela` na união `ChatCard` (importar `Any` de `typing`).

```python
# backend/src/app/admin_tools/intencao.py
"""Classificador por palavras-chave: separa pedido de consulta de conversa comum."""

import re

_CONSULTA_RE = re.compile(
    r"\b(consult[ea]\w*|list[ea]\w*|mostr[ea]\w*|quant[oa]s?|qual(?:is)?\s+(?:o|a|os|as)\s+\w+"
    r"\s+(?:de|do|da|dos|das))\b",
    re.IGNORECASE,
)
_DADOS_RE = re.compile(
    r"\b(produtos?|pedidos?|vendas?|estoque|clientes?|agendamentos?|mensagens?)\b",
    re.IGNORECASE,
)


def detectar_consulta(message: str) -> bool:
    """True se o texto pede uma consulta sobre dados do sistema (e não um gráfico)."""
    if re.search(r"\b(gr[aá]fico|dashboard)\b", message, re.IGNORECASE):
        return False
    return bool(_CONSULTA_RE.search(message) and _DADOS_RE.search(message))
```

```python
# backend/src/app/admin_tools/handler.py
"""Ponto de entrada das ferramentas do Admin para o orquestrador do chat."""

from collections.abc import AsyncIterator
from typing import Any

from app.admin_tools.consulta import executar_consulta, gerar_sql
from app.admin_tools.intencao import detectar_consulta
from app.models.chat import CardTabela
from app.services.safe_sql import SQLSecurityError, get_catalog_schema_prompt

LIMITE_LINHAS = 50


def _card_tabela(linhas: list[dict[str, Any]]) -> CardTabela:
    colunas = list(linhas[0].keys()) if linhas else []
    return CardTabela(
        titulo="Resultado da consulta",
        colunas=colunas,
        linhas=[[linha[c] for c in colunas] for linha in linhas],
        truncado=len(linhas) >= LIMITE_LINHAS,
    )


async def _consultar(message: str, local_client: Any, db_sessionmaker: Any):
    """Retorna (texto, card): o card é None quando a consulta não pôde ser feita."""
    async with db_sessionmaker() as session:
        sql = await gerar_sql(local_client, message, await get_catalog_schema_prompt(session))
        if sql is None:
            return "Não consegui montar uma consulta para esse pedido. Reformule, por favor.", None
        try:
            linhas = await executar_consulta(session, sql)
        except SQLSecurityError as exc:
            return f"Essa consulta não é permitida: {exc}", None
    if not linhas:
        return "A consulta não retornou nenhuma linha.", None
    return f"Encontrei {len(linhas)} linha(s).", _card_tabela(linhas)


async def processar_pedido_admin(
    message: str,
    *,
    is_admin: bool,
    local_client: Any,
    db_sessionmaker: Any,
    intent_router_provider: str,
) -> AsyncIterator[Any]:
    """Emite os eventos de uma ferramenta do Admin; não emite nada se o texto não é um pedido
    de ferramenta ou se o usuário não é Admin (o chat segue o fluxo normal)."""
    from app.router.orchestrator import (  # import tardio: evita ciclo com o orquestrador
        RouterDecision,
        TokenEvent,
        _emitir_chart_decision_base,
    )

    if not is_admin or db_sessionmaker is None or not detectar_consulta(message):
        return
    texto, card = await _consultar(message, local_client, db_sessionmaker)
    yield TokenEvent(text=texto)
    yield RouterDecision(
        **_emitir_chart_decision_base(intent_router_provider, None, None),
        resposta=texto,
        card=card,
    )
```

(Se `RouterDecision`/`TokenEvent` não forem importáveis desse jeito, usar os mesmos imports que `_emitir_eventos_chart` usa no orquestrador; a assinatura de `_emitir_chart_decision_base` está em `orchestrator.py`.)

Orquestrador — em `handle_message`, passar o handler novo antes do de gráfico:

```python
        partial(
            processar_pedido_admin,
            message,
            is_admin=is_admin,
            local_client=local_client,
            db_sessionmaker=db_sessionmaker,
            intent_router_provider=intent_router_provider,
        ),
        partial(_handle_chart_request, ...),   # já existente
```

Frontend: em `lib/types/chat.ts` adicionar

```ts
export interface ChatCardTabela {
  tipo: "tabela";
  titulo: string;
  colunas: string[];
  linhas: (string | number | null)[][];
  truncado?: boolean;
}
```

e incluí-lo em `ChatCard`. Criar `components/chat/cards/TabelaCard.tsx`:

```tsx
import type { ChatCardTabela } from "@/lib/types/chat";

export default function TabelaCard({ card }: { card: ChatCardTabela }) {
  return (
    <div className="mt-2 overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="w-full text-left text-xs">
        <thead className="bg-slate-50 text-slate-600">
          <tr>
            {card.colunas.map((c) => (
              <th key={c} scope="col" className="px-3 py-2 font-semibold">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {card.linhas.map((linha, i) => (
            <tr key={i}>
              {linha.map((valor, j) => (
                <td key={j} className="px-3 py-2 text-slate-800">
                  {valor === null ? "—" : String(valor)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {card.truncado && (
        <p className="px-3 py-2 text-xs text-slate-500">Mostrando as primeiras 50 linhas.</p>
      )}
    </div>
  );
}
```

e `case "tabela": return <TabelaCard card={card} />;` em `ChatCard.tsx`.

- [ ] **Step 8: Run to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_tools_consulta.py tests/test_admin_tools_handler.py tests/test_orchestrator.py tests/test_chat_chart_card.py -q` e `cd frontend && npx vitest run tests/components/TabelaCard.test.tsx && npx tsc --noEmit && npx eslint components/chat lib/types`
Expected: PASS.

- [ ] **Step 9: Docs + commit**

Marcar a etapa 1 no `docs/ROADMAP.md`; `docs/ARCHITECTURE.md`: decisão de 2026-11-01 (chat Admin lê com SELECT livre validado e `# MVP:` do timeout só em Postgres); `docs/FRONTEND.md`: card `tabela`.

```bash
git add backend/src/app/admin_tools backend/src/app/models/chat.py backend/src/app/router/orchestrator.py \
  backend/tests/test_admin_tools_*.py frontend docs
git commit -m "feat(chat-admin): consultar(sql) só de SELECT no chat do Admin, com card de tabela (R12, Fase 10/11)"
```

---

### Task 2: Proposta, confirmação e auditoria (migração 0031)

**Files:**
- Create: `backend/migrations/versions/0031_chat_admin_acoes.py`, `backend/src/app/admin_tools/propostas.py`, `backend/src/app/api/admin_chat_acoes.py`
- Modify: `backend/src/app/db/models.py`, `backend/src/app/models/chat.py`, `backend/src/app/main.py`
- Test: `backend/tests/test_admin_tools_propostas.py`, `backend/tests/test_admin_chat_acoes_api.py`
- Frontend: `frontend/lib/types/chat.ts`, `frontend/lib/api/adminChatAcoes.ts`, `frontend/components/chat/cards/AcaoPropostaCard.tsx`, `ChatCard.tsx`, `frontend/tests/components/AcaoPropostaCard.test.tsx`

**Interfaces:**
- Consumes: nada de outras tarefas além do pacote `app.admin_tools`.
- Produces:
  - `ChatAdminAcao` (tabela `chat_admin_acoes`): `id: UUID`, `admin_id: int`, `ferramenta: str`, `argumentos: dict`, `antes: dict | None`, `depois: dict | None`, `status: str` (`proposta|executada|cancelada|expirada`), `aviso: str | None`, `criado_em`, `expira_em`, `executado_em`.
  - `class Previa(BaseModel): titulo: str; antes: dict; depois: dict; aviso: str | None = None`.
  - `class Ferramenta(Protocol): nome: str; async preparar(session, args: dict) -> Previa; async executar(session, args: dict, *, admin_id: int) -> dict` (`executar` devolve o `depois` real; `admin_id` é o admin que confirmou).
  - `FERRAMENTAS: dict[str, Ferramenta]` em `ferramentas.py` (vazio nesta tarefa; as próximas registram).
  - `async criar_proposta(session, *, admin_id: int, ferramenta: str, argumentos: dict, agora: datetime | None = None) -> tuple[ChatAdminAcao, Previa]`
  - `async confirmar(session, acao_id: UUID, *, admin_id: int, agora: datetime | None = None) -> ChatAdminAcao`; levanta `PropostaInvalidaError` (inexistente, de outro admin, expirada, já resolvida).
  - `async cancelar(session, acao_id: UUID, *, admin_id: int) -> ChatAdminAcao`.
  - `CardAcaoProposta(tipo="acao_proposta", acao_id: str, titulo: str, antes: dict, depois: dict, aviso: str | None, expira_em: datetime)`.
  - `POST /api/admin/chat/acoes/{id}/confirmar` e `/cancelar` → `{status, depois}`.

- [ ] **Step 1: Write the failing tests (propostas)**

```python
# backend/tests/test_admin_tools_propostas.py
from datetime import UTC, datetime, timedelta

import pytest

from app.admin_tools import ferramentas
from app.admin_tools.ferramentas import Previa
from app.admin_tools.propostas import (
    PROPOSTA_TTL,
    PropostaInvalidaError,
    cancelar,
    confirmar,
    criar_proposta,
)


class _Fake:
    nome = "fake"

    def __init__(self):
        self.execucoes = 0

    async def preparar(self, session, args):
        return Previa(titulo="Fake", antes={"v": 1}, depois={"v": args["v"]})

    async def executar(self, session, args, *, admin_id):
        self.execucoes += 1
        return {"v": args["v"]}


@pytest.fixture
def fake(monkeypatch):
    f = _Fake()
    monkeypatch.setitem(ferramentas.FERRAMENTAS, "fake", f)
    return f


@pytest.mark.asyncio
async def test_criar_proposta_grava_previa_sem_executar(db_session, fake):
    acao, previa = await criar_proposta(db_session, admin_id=1, ferramenta="fake", argumentos={"v": 2})
    assert acao.status == "proposta" and acao.antes == {"v": 1} and acao.depois == {"v": 2}
    assert previa.titulo == "Fake" and fake.execucoes == 0


@pytest.mark.asyncio
async def test_confirmar_executa_uma_vez_e_registra(db_session, fake):
    acao, _ = await criar_proposta(db_session, admin_id=1, ferramenta="fake", argumentos={"v": 2})
    feita = await confirmar(db_session, acao.id, admin_id=1)
    assert feita.status == "executada" and feita.executado_em is not None and fake.execucoes == 1
    with pytest.raises(PropostaInvalidaError):
        await confirmar(db_session, acao.id, admin_id=1)  # reconfirmar não grava de novo
    assert fake.execucoes == 1


@pytest.mark.asyncio
async def test_confirmar_proposta_de_outro_admin_ou_expirada_falha(db_session, fake):
    acao, _ = await criar_proposta(db_session, admin_id=1, ferramenta="fake", argumentos={"v": 2})
    with pytest.raises(PropostaInvalidaError):
        await confirmar(db_session, acao.id, admin_id=2)
    depois = datetime.now(UTC) + PROPOSTA_TTL + timedelta(seconds=1)
    with pytest.raises(PropostaInvalidaError):
        await confirmar(db_session, acao.id, admin_id=1, agora=depois)
    assert fake.execucoes == 0
    await db_session.refresh(acao)
    assert acao.status == "expirada"


@pytest.mark.asyncio
async def test_cancelar_marca_cancelada_e_nao_executa(db_session, fake):
    acao, _ = await criar_proposta(db_session, admin_id=1, ferramenta="fake", argumentos={"v": 2})
    feita = await cancelar(db_session, acao.id, admin_id=1)
    assert feita.status == "cancelada" and fake.execucoes == 0


@pytest.mark.asyncio
async def test_ferramenta_desconhecida_levanta(db_session):
    with pytest.raises(PropostaInvalidaError):
        await criar_proposta(db_session, admin_id=1, ferramenta="nao_existe", argumentos={})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_tools_propostas.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement model, migration, registry and lifecycle**

`backend/src/app/db/models.py` (junto de `AgenteExecucao`; `JSON` já vem de `sqlalchemy`, importar se faltar):

```python
class ChatAdminAcao(Base):
    """Proposta/execução de uma ferramenta do Admin no chat (`app.admin_tools`): a trilha de
    auditoria de toda escrita feita pelo chat (antes → depois, quem, quando).

    # MVP: o `admin_id` é o id do cliente do token mock (`mock-token-<id>`); sem retenção.
    """

    __tablename__ = "chat_admin_acoes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    admin_id: Mapped[int] = mapped_column(Integer, index=True)
    ferramenta: Mapped[str] = mapped_column(String(50))
    argumentos: Mapped[dict] = mapped_column(JSON)
    antes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    depois: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    aviso: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="proposta", index=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    executado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

```python
# backend/migrations/versions/0031_chat_admin_acoes.py
"""chat_admin_acoes (propostas e auditoria das ferramentas do Admin no chat)

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_admin_acoes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("admin_id", sa.Integer(), nullable=False),
        sa.Column("ferramenta", sa.String(50), nullable=False),
        sa.Column("argumentos", sa.JSON(), nullable=False),
        sa.Column("antes", sa.JSON(), nullable=True),
        sa.Column("depois", sa.JSON(), nullable=True),
        sa.Column("aviso", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="proposta"),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executado_em", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_chat_admin_acoes_admin_id", "chat_admin_acoes", ["admin_id"])
    op.create_index("idx_chat_admin_acoes_status", "chat_admin_acoes", ["status"])


def downgrade() -> None:
    op.drop_index("idx_chat_admin_acoes_status", table_name="chat_admin_acoes")
    op.drop_index("idx_chat_admin_acoes_admin_id", table_name="chat_admin_acoes")
    op.drop_table("chat_admin_acoes")
```

```python
# backend/src/app/admin_tools/ferramentas.py
"""Registro das ferramentas de escrita do Admin no chat."""

from typing import Any, Protocol

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession


class Previa(BaseModel):
    titulo: str
    antes: dict[str, Any]
    depois: dict[str, Any]
    aviso: str | None = None


class Ferramenta(Protocol):
    nome: str

    async def preparar(self, session: AsyncSession, args: dict[str, Any]) -> Previa: ...

    async def executar(
        self, session: AsyncSession, args: dict[str, Any], *, admin_id: int
    ) -> dict[str, Any]: ...


# Preenchido pelas ferramentas (Tasks 3–5) ao final de cada módulo de ferramenta.
FERRAMENTAS: dict[str, Ferramenta] = {}
```

```python
# backend/src/app/admin_tools/propostas.py
"""Ciclo de vida de uma proposta: criar → confirmar/cancelar/expirar, com auditoria."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.admin_tools.ferramentas import FERRAMENTAS, Previa
from app.db.models import ChatAdminAcao

PROPOSTA_TTL = timedelta(minutes=10)


class PropostaInvalidaError(Exception):
    """Proposta inexistente, de outro admin, expirada ou já resolvida."""


def _agora(agora: datetime | None) -> datetime:
    return agora or datetime.now(UTC)


async def criar_proposta(
    session: AsyncSession,
    *,
    admin_id: int,
    ferramenta: str,
    argumentos: dict,
    agora: datetime | None = None,
) -> tuple[ChatAdminAcao, Previa]:
    """Valida via `preparar` e grava a proposta; nada é executado aqui."""
    impl = FERRAMENTAS.get(ferramenta)
    if impl is None:
        raise PropostaInvalidaError(f"Ferramenta desconhecida: {ferramenta}.")
    previa = await impl.preparar(session, argumentos)
    momento = _agora(agora)
    acao = ChatAdminAcao(
        admin_id=admin_id,
        ferramenta=ferramenta,
        argumentos=argumentos,
        antes=previa.antes,
        depois=previa.depois,
        aviso=previa.aviso,
        status="proposta",
        expira_em=momento + PROPOSTA_TTL,
    )
    session.add(acao)
    await session.commit()
    return acao, previa


async def _carregar_pendente(
    session: AsyncSession, acao_id: uuid.UUID, admin_id: int, agora: datetime
) -> ChatAdminAcao:
    acao = await session.get(ChatAdminAcao, acao_id)
    if acao is None or acao.admin_id != admin_id:
        raise PropostaInvalidaError("Proposta não encontrada.")
    if acao.status != "proposta":
        raise PropostaInvalidaError(f"Proposta já {acao.status}.")
    expira = acao.expira_em if acao.expira_em.tzinfo else acao.expira_em.replace(tzinfo=UTC)
    if agora > expira:
        acao.status = "expirada"
        await session.commit()
        raise PropostaInvalidaError("Proposta expirada; peça de novo.")
    return acao


async def confirmar(
    session: AsyncSession, acao_id: uuid.UUID, *, admin_id: int, agora: datetime | None = None
) -> ChatAdminAcao:
    """Revalida (`preparar` de novo) e executa na mesma transação do registro de auditoria."""
    momento = _agora(agora)
    acao = await _carregar_pendente(session, acao_id, admin_id, momento)
    impl = FERRAMENTAS[acao.ferramenta]
    await impl.preparar(session, acao.argumentos)
    acao.depois = await impl.executar(session, acao.argumentos, admin_id=admin_id)
    acao.status = "executada"
    acao.executado_em = momento
    await session.commit()
    return acao


async def cancelar(session: AsyncSession, acao_id: uuid.UUID, *, admin_id: int) -> ChatAdminAcao:
    acao = await _carregar_pendente(session, acao_id, admin_id, _agora(None))
    acao.status = "cancelada"
    await session.commit()
    return acao
```

(`impl.executar` NÃO faz `commit`: o `commit` acima grava a escrita da ferramenta e a auditoria juntas. Se `executar` levantar, nada é gravado e a proposta continua pendente.)

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_tools_propostas.py -v`
Expected: PASS (5 testes).

- [ ] **Step 5: Write the failing API tests**

```python
# backend/tests/test_admin_chat_acoes_api.py
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.admin_tools import ferramentas
from app.admin_tools.ferramentas import Previa
from app.admin_tools.propostas import criar_proposta
from app.api.admin_chat_acoes import router
from app.api.rag_dependencies import get_db_session


class _Fake:
    nome = "fake"

    async def preparar(self, session, args):
        return Previa(titulo="Fake", antes={}, depois={"v": 1})

    async def executar(self, session, args, *, admin_id):
        return {"v": 1}


@pytest.fixture
def client(db_session, monkeypatch):
    monkeypatch.setitem(ferramentas.FERRAMENTAS, "fake", _Fake())
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db_session] = lambda: db_session
    return TestClient(app)


@pytest.mark.asyncio
async def test_confirmar_sem_token_admin_retorna_403(client, db_session):
    acao, _ = await criar_proposta(db_session, admin_id=1, ferramenta="fake", argumentos={})
    assert client.post(f"/api/admin/chat/acoes/{acao.id}/confirmar").status_code == 403


@pytest.mark.asyncio
async def test_confirmar_executa_e_reconfirmar_retorna_409(client, db_session, admin_headers):
    acao, _ = await criar_proposta(db_session, admin_id=1, ferramenta="fake", argumentos={})
    # `admin_headers` cria o admin com id 1 no banco de teste.
    ok = client.post(f"/api/admin/chat/acoes/{acao.id}/confirmar", headers=admin_headers)
    assert ok.status_code == 200 and ok.json() == {"status": "executada", "depois": {"v": 1}}
    again = client.post(f"/api/admin/chat/acoes/{acao.id}/confirmar", headers=admin_headers)
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_cancelar(client, db_session, admin_headers):
    acao, _ = await criar_proposta(db_session, admin_id=1, ferramenta="fake", argumentos={})
    r = client.post(f"/api/admin/chat/acoes/{acao.id}/cancelar", headers=admin_headers)
    assert r.status_code == 200 and r.json()["status"] == "cancelada"
```

(Se o id do admin criado por `admin_headers` não for 1, usar o id real lido de `Cliente` no teste.)

- [ ] **Step 6: Run to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_chat_acoes_api.py -v`
Expected: FAIL (`ModuleNotFoundError: app.api.admin_chat_acoes`).

- [ ] **Step 7: Implement the API and register it**

```python
# backend/src/app/api/admin_chat_acoes.py
"""Confirmação/cancelamento das propostas de ferramenta do Admin no chat."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin_tools.propostas import PropostaInvalidaError, cancelar, confirmar
from app.api.admin_auth import require_admin
from app.api.auth import MOCK_TOKEN_PREFIX
from app.api.rag_dependencies import get_db_session

router = APIRouter(prefix="/api/admin/chat/acoes", tags=["admin-chat-acoes"])


def _admin_id(
    authorization: Annotated[str | None, Header()] = None,
    x_auth_token: Annotated[str | None, Header(alias="X-Auth-Token")] = None,
    token_param: Annotated[str | None, Query(alias="token")] = None,
) -> int:
    """Id do admin a partir do token (já validado por `require_admin`)."""
    token = (authorization or "").split()[-1] if authorization else (x_auth_token or token_param)
    return int((token or "").removeprefix(MOCK_TOKEN_PREFIX))


@router.post("/{acao_id}/confirmar", dependencies=[Depends(require_admin)])
async def post_confirmar(
    acao_id: uuid.UUID,
    admin_id: int = Depends(_admin_id),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        acao = await confirmar(session, acao_id, admin_id=admin_id)
    except PropostaInvalidaError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": acao.status, "depois": acao.depois}


@router.post("/{acao_id}/cancelar", dependencies=[Depends(require_admin)])
async def post_cancelar(
    acao_id: uuid.UUID,
    admin_id: int = Depends(_admin_id),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        acao = await cancelar(session, acao_id, admin_id=admin_id)
    except PropostaInvalidaError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": acao.status}
```

Em `backend/src/app/main.py`: `from app.api.admin_chat_acoes import router as admin_chat_acoes_router` e `app.include_router(admin_chat_acoes_router)` junto dos demais; em `test_main_app.py`, acrescentar a rota esperada se houver lista de rotas.

`models/chat.py`: `CardAcaoProposta` e inclusão na união:

```python
class CardAcaoProposta(BaseModel):
    """Prévia de uma escrita pedida pelo Admin, aguardando Confirmar/Cancelar."""

    tipo: Literal["acao_proposta"] = "acao_proposta"
    acao_id: str
    titulo: str
    antes: dict[str, Any]
    depois: dict[str, Any]
    aviso: str | None = None
    expira_em: datetime
```

- [ ] **Step 8: Run to verify it passes (inclui migração)**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_tools_propostas.py tests/test_admin_chat_acoes_api.py tests/test_main_app.py -q && .venv/bin/alembic upgrade head && .venv/bin/alembic current`
Expected: PASS; `0031 (head)`.

- [ ] **Step 9: Frontend (card + cliente) com teste primeiro**

```tsx
// frontend/tests/components/AcaoPropostaCard.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AcaoPropostaCard from "@/components/chat/cards/AcaoPropostaCard";
import { useAuthStore } from "@/lib/hooks/useAuthStore";

vi.mock("@/lib/api/adminChatAcoes", () => ({
  confirmarAcao: vi.fn().mockResolvedValue({ status: "executada", depois: { estoque: 35 } }),
  cancelarAcao: vi.fn().mockResolvedValue({ status: "cancelada" }),
}));
import { cancelarAcao, confirmarAcao } from "@/lib/api/adminChatAcoes";

const CARD = {
  tipo: "acao_proposta" as const,
  acao_id: "a-1",
  titulo: "Baixa de estoque",
  antes: { estoque: 40 },
  depois: { estoque: 35 },
  aviso: null,
  expira_em: "2026-11-01T12:00:00Z",
};

describe("AcaoPropostaCard", () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: { id: 1, nome: "Admin", email: "a@b.c", perfil: "Admin" },
      token: "mock-token-1",
    });
  });

  it("mostra antes e depois e confirma com o token do admin", async () => {
    const user = userEvent.setup();
    render(<AcaoPropostaCard card={CARD} />);
    expect(screen.getByText("Baixa de estoque")).toBeInTheDocument();
    expect(screen.getByText(/40/)).toBeInTheDocument();
    expect(screen.getByText(/35/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Confirmar" }));
    expect(confirmarAcao).toHaveBeenCalledWith("mock-token-1", "a-1");
    expect(await screen.findByText(/executada/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Confirmar" })).not.toBeInTheDocument();
  });

  it("cancelar chama a API e esconde os botões", async () => {
    const user = userEvent.setup();
    render(<AcaoPropostaCard card={CARD} />);
    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(cancelarAcao).toHaveBeenCalledWith("mock-token-1", "a-1");
    expect(await screen.findByText(/cancelada/i)).toBeInTheDocument();
  });
});
```

Em `frontend/lib/types/chat.ts` adicionar (e incluir na união `ChatCard`):

```ts
export interface ChatCardAcaoProposta {
  tipo: "acao_proposta";
  acao_id: string;
  titulo: string;
  antes: Record<string, unknown>;
  depois: Record<string, unknown>;
  aviso?: string | null;
  expira_em: string;
}
```

`frontend/lib/api/adminChatAcoes.ts`:

```ts
import { extrairDetalheDeErro } from "@/lib/api/errors";
import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";

const API_BASE_URL = getApiBaseUrl();

async function postarAcao(
  token: string,
  id: string,
  rota: "confirmar" | "cancelar",
): Promise<{ status: string; depois?: Record<string, unknown> }> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/admin/chat/acoes/${id}/${rota}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new Error("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }
  if (!response.ok) {
    throw new Error(
      (await extrairDetalheDeErro(response)) ?? "Não foi possível concluir a ação. Tente novamente.",
    );
  }
  return (await response.json()) as { status: string; depois?: Record<string, unknown> };
}

export const confirmarAcao = (token: string, id: string) => postarAcao(token, id, "confirmar");
export const cancelarAcao = (token: string, id: string) => postarAcao(token, id, "cancelar");
```

`frontend/components/chat/cards/AcaoPropostaCard.tsx`:

```tsx
"use client";

import { useState } from "react";

import { cancelarAcao, confirmarAcao } from "@/lib/api/adminChatAcoes";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import type { ChatCardAcaoProposta } from "@/lib/types/chat";

type Estado = "pendente" | "enviando" | "executada" | "cancelada" | "erro";

function Valores({ dados }: { dados: Record<string, unknown> }) {
  return (
    <ul className="space-y-0.5 text-xs text-slate-800">
      {Object.entries(dados).map(([chave, valor]) => (
        <li key={chave}>
          <span className="text-slate-500">{chave}:</span>{" "}
          {typeof valor === "object" ? JSON.stringify(valor) : String(valor)}
        </li>
      ))}
    </ul>
  );
}

export default function AcaoPropostaCard({ card }: { card: ChatCardAcaoProposta }) {
  const token = useAuthStore((s) => s.token);
  const [estado, setEstado] = useState<Estado>("pendente");
  const [erro, setErro] = useState<string | null>(null);

  async function agir(acao: typeof confirmarAcao, final: Estado) {
    if (!token) return;
    setEstado("enviando");
    try {
      await acao(token, card.acao_id);
      setEstado(final);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro inesperado.");
      setEstado("erro");
    }
  }

  const aberto = estado === "pendente" || estado === "enviando" || estado === "erro";
  return (
    <div className="mt-2 space-y-2 rounded-lg border border-amber-200 bg-amber-50 p-3">
      <p className="text-sm font-semibold text-slate-900">{card.titulo}</p>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase text-slate-500">Antes</p>
          <Valores dados={card.antes} />
        </div>
        <div>
          <p className="text-[11px] font-semibold uppercase text-slate-500">Depois</p>
          <Valores dados={card.depois} />
        </div>
      </div>
      {card.aviso && <p className="text-xs font-semibold text-amber-800">{card.aviso}</p>}
      {erro && <p className="text-xs text-red-700">{erro}</p>}
      {estado === "executada" && <p className="text-xs font-semibold text-green-700">Ação executada.</p>}
      {estado === "cancelada" && <p className="text-xs font-semibold text-slate-600">Ação cancelada.</p>}
      {aberto && (
        <div className="flex gap-2">
          <button
            type="button"
            disabled={estado === "enviando"}
            onClick={() => agir(confirmarAcao, "executada")}
            className="rounded-md bg-gray-900 px-3 py-1.5 text-xs text-white disabled:opacity-50"
          >
            Confirmar
          </button>
          <button
            type="button"
            disabled={estado === "enviando"}
            onClick={() => agir(cancelarAcao, "cancelada")}
            className="rounded-md px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-100 disabled:opacity-50"
          >
            Cancelar
          </button>
        </div>
      )}
    </div>
  );
}
```

E `case "acao_proposta": return <AcaoPropostaCard card={card} />;` em `components/chat/cards/ChatCard.tsx`.

Run: `cd frontend && npx vitest run tests/components/AcaoPropostaCard.test.tsx && npx tsc --noEmit && npx eslint components lib`
Expected: PASS.

- [ ] **Step 10: Docs + commit**

ROADMAP (etapa 2); ARCHITECTURE: tabela `chat_admin_acoes`, fluxo proposta→confirmação, `# MVP:` do admin_id do token mock; FRONTEND: endpoints `POST /api/admin/chat/acoes/{id}/confirmar|cancelar` e o card `acao_proposta`.

```bash
git add backend frontend docs
git commit -m "feat(chat-admin): proposta, confirmação e auditoria das escritas do Admin no chat (migração 0031; R12, Fase 10/11)"
```

---

### Task 3: Ferramentas de produto (incluir, alterar nome, alterar descrição) e roteamento da escrita

**Files:**
- Create: `backend/src/app/admin_tools/ferramentas_produto.py`, `backend/src/app/admin_tools/roteador.py`
- Modify: `backend/src/app/admin_tools/ferramentas.py` (importar o módulo ao final para registrar), `backend/src/app/admin_tools/intencao.py`, `backend/src/app/admin_tools/handler.py`
- Test: `backend/tests/test_admin_tools_produto.py`, `backend/tests/test_admin_tools_roteador.py`

**Interfaces:**
- Consumes: `Previa`, `FERRAMENTAS`, `criar_proposta` (Task 2); `criar_produto`, `atualizar_produto`, `listar_produtos`, `obter_produto` de `app.db.catalog`.
- Produces:
  - `class ProdutoAmbiguoError(PropostaInvalidaError)` com `.candidatos: list[tuple[int, str]]`.
  - `async resolver_produto(session, referencia: str | int) -> Produto`: id numérico ou nome (ilike); 0 resultados → `PropostaInvalidaError`; 2+ → `ProdutoAmbiguoError`.
  - Ferramentas registradas: `incluir_produto` (args `nome, descricao, preco, categoria`), `alterar_nome_produto` (`produto, novo_nome`), `alterar_descricao_produto` (`produto, nova_descricao`).
  - `detectar_escrita(message: str) -> bool`.
  - `async interpretar_escrita(llm_client, message: str) -> dict | None` → `{"ferramenta": str, "argumentos": dict}` ou `None`.
  - `PROMPT_FERRAMENTAS: str` (em `roteador.py`; registrar em `PROMPTS_E_INSTRUCOES_LLM.md`).

- [ ] **Step 1: Write the failing tests (produto)**

```python
# backend/tests/test_admin_tools_produto.py
from decimal import Decimal

import pytest

from app.admin_tools import ferramentas
from app.admin_tools import ferramentas_produto  # noqa: F401  (registra as ferramentas)
from app.admin_tools.ferramentas_produto import ProdutoAmbiguoError, resolver_produto
from app.admin_tools.propostas import PropostaInvalidaError, confirmar, criar_proposta
from app.db.catalog import criar_produto, obter_produto


async def _produto(session, nome, **kw):
    return await criar_produto(
        session, nome=nome, descricao=kw.get("descricao", "d"), preco=Decimal("10"), categoria="Geral"
    )


@pytest.mark.asyncio
async def test_resolver_produto_por_id_nome_e_ambiguidade(db_session):
    a = await _produto(db_session, "Controlador iDFace Max")
    await _produto(db_session, "Controlador iDFace Mini")
    assert (await resolver_produto(db_session, a.id)).id == a.id
    assert (await resolver_produto(db_session, "iDFace Max")).id == a.id
    with pytest.raises(ProdutoAmbiguoError) as exc:
        await resolver_produto(db_session, "iDFace")
    assert len(exc.value.candidatos) == 2
    with pytest.raises(PropostaInvalidaError):
        await resolver_produto(db_session, "inexistente")


@pytest.mark.asyncio
async def test_incluir_produto_so_grava_depois_de_confirmar(db_session):
    acao, previa = await criar_proposta(
        db_session,
        admin_id=1,
        ferramenta="incluir_produto",
        argumentos={"nome": "Novo", "descricao": "Desc", "preco": "99.90", "categoria": "CFTV"},
    )
    assert previa.depois["nome"] == "Novo"
    from app.db.catalog import listar_produtos

    assert await listar_produtos(db_session, termo="Novo") == []
    await confirmar(db_session, acao.id, admin_id=1)
    achados = await listar_produtos(db_session, termo="Novo")
    assert len(achados) == 1 and achados[0].preco == Decimal("99.90")


@pytest.mark.asyncio
async def test_alterar_nome_e_descricao_mostram_antes_e_depois(db_session):
    p = await _produto(db_session, "Antigo", descricao="velha")
    acao, previa = await criar_proposta(
        db_session,
        admin_id=1,
        ferramenta="alterar_nome_produto",
        argumentos={"produto": p.id, "novo_nome": "Moderno"},
    )
    assert previa.antes == {"nome": "Antigo"} and previa.depois == {"nome": "Moderno"}
    await confirmar(db_session, acao.id, admin_id=1)
    assert (await obter_produto(db_session, p.id)).nome == "Moderno"

    acao2, previa2 = await criar_proposta(
        db_session,
        admin_id=1,
        ferramenta="alterar_descricao_produto",
        argumentos={"produto": p.id, "nova_descricao": "nova"},
    )
    assert previa2.antes == {"descricao": "velha"}
    await confirmar(db_session, acao2.id, admin_id=1)
    assert (await obter_produto(db_session, p.id)).descricao == "nova"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "args",
    [{"nome": "", "descricao": "d", "preco": "1", "categoria": "x"}, {"nome": "n", "descricao": "d", "preco": "-1", "categoria": "x"}],
)
async def test_incluir_produto_rejeita_argumentos_invalidos(db_session, args):
    with pytest.raises(PropostaInvalidaError):
        await criar_proposta(db_session, admin_id=1, ferramenta="incluir_produto", argumentos=args)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_tools_produto.py -v`
Expected: FAIL (`ModuleNotFoundError: app.admin_tools.ferramentas_produto`).

- [ ] **Step 3: Implement `ferramentas_produto.py`**

```python
# backend/src/app/admin_tools/ferramentas_produto.py
"""Ferramentas de produto do Admin no chat: incluir, alterar nome, alterar descrição."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin_tools.ferramentas import FERRAMENTAS, Previa
from app.admin_tools.propostas import PropostaInvalidaError
from app.db.catalog import atualizar_produto, criar_produto, listar_produtos, obter_produto
from app.db.models import Produto


class ProdutoAmbiguoError(PropostaInvalidaError):
    def __init__(self, candidatos: list[tuple[int, str]]):
        self.candidatos = candidatos
        lista = "; ".join(f"{i}: {n}" for i, n in candidatos)
        super().__init__(f"Mais de um produto combina ({lista}). Informe o id.")


async def resolver_produto(session: AsyncSession, referencia: str | int) -> Produto:
    """Produto por id ou por nome; nunca escolhe sozinho entre vários."""
    if isinstance(referencia, int) or str(referencia).strip().isdigit():
        produto = await obter_produto(session, int(referencia))
        if produto is None:
            raise PropostaInvalidaError(f"Produto {referencia} não encontrado.")
        return produto
    achados = await listar_produtos(session, termo=str(referencia))
    if not achados:
        raise PropostaInvalidaError(f"Nenhum produto combina com '{referencia}'.")
    if len(achados) > 1:
        raise ProdutoAmbiguoError([(p.id, p.nome) for p in achados[:10]])
    return achados[0]


def _validar(modelo: type[BaseModel], args: dict[str, Any]) -> Any:
    try:
        return modelo(**args)
    except ValidationError as exc:
        campo = exc.errors()[0]["loc"][0] if exc.errors() else "argumentos"
        raise PropostaInvalidaError(f"Argumento inválido: {campo}.") from exc


class _Incluir(BaseModel):
    nome: str = Field(min_length=1)
    descricao: str = Field(min_length=1)
    preco: Decimal = Field(gt=0)
    categoria: str = Field(min_length=1)

    @field_validator("nome", "descricao", "categoria")
    @classmethod
    def _sem_espacos(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("vazio")
        return v.strip()


class _AlterarNome(BaseModel):
    produto: str | int
    novo_nome: str = Field(min_length=1)


class _AlterarDescricao(BaseModel):
    produto: str | int
    nova_descricao: str = Field(min_length=1)


class IncluirProduto:
    nome = "incluir_produto"

    async def preparar(self, session: AsyncSession, args: dict[str, Any]) -> Previa:
        dados = _validar(_Incluir, args)
        return Previa(
            titulo="Incluir produto",
            antes={},
            depois={"nome": dados.nome, "categoria": dados.categoria, "preco": str(dados.preco)},
        )

    async def executar(
        self, session: AsyncSession, args: dict[str, Any], *, admin_id: int
    ) -> dict[str, Any]:
        dados = _validar(_Incluir, args)
        produto = await criar_produto(
            session,
            nome=dados.nome,
            descricao=dados.descricao,
            preco=dados.preco,
            categoria=dados.categoria,
        )
        return {"produto_id": produto.id, "nome": produto.nome}


class _AlterarCampo:
    """Base das alterações de um único campo de texto do produto."""

    campo: str
    modelo: type[BaseModel]
    arg_novo: str
    titulo: str

    async def preparar(self, session: AsyncSession, args: dict[str, Any]) -> Previa:
        dados = _validar(self.modelo, args)
        produto = await resolver_produto(session, dados.produto)
        return Previa(
            titulo=f"{self.titulo}: {produto.nome}",
            antes={self.campo: getattr(produto, self.campo)},
            depois={self.campo: getattr(dados, self.arg_novo).strip()},
        )

    async def executar(
        self, session: AsyncSession, args: dict[str, Any], *, admin_id: int
    ) -> dict[str, Any]:
        dados = _validar(self.modelo, args)
        produto = await resolver_produto(session, dados.produto)
        novo = getattr(dados, self.arg_novo).strip()
        await atualizar_produto(session, produto.id, {self.campo: novo})
        return {self.campo: novo}


class AlterarNomeProduto(_AlterarCampo):
    nome = "alterar_nome_produto"
    campo, modelo, arg_novo, titulo = "nome", _AlterarNome, "novo_nome", "Alterar nome"


class AlterarDescricaoProduto(_AlterarCampo):
    nome = "alterar_descricao_produto"
    campo, modelo, arg_novo, titulo = (
        "descricao",
        _AlterarDescricao,
        "nova_descricao",
        "Alterar descrição",
    )


for _f in (IncluirProduto(), AlterarNomeProduto(), AlterarDescricaoProduto()):
    FERRAMENTAS[_f.nome] = _f
```

Observação: `criar_produto` e `atualizar_produto` fazem `commit` próprio; para a confirmação ser atômica com a auditoria, ajustar os dois a aceitar `commit: bool = True` (padrão mantém o comportamento dos endpoints) e as ferramentas passam `commit=False`. Cobrir com um teste que força erro em `executar` e verifica que o produto não ficou gravado.

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_tools_produto.py tests/test_catalog*.py tests/test_admin_products*.py -q`
Expected: PASS.

- [ ] **Step 5: Write the failing tests (roteador da escrita)**

```python
# backend/tests/test_admin_tools_roteador.py
import pytest

from app.admin_tools.intencao import detectar_escrita
from app.admin_tools.roteador import interpretar_escrita


@pytest.mark.parametrize(
    ("mensagem", "esperado"),
    [
        ("inclua o produto Câmera X na categoria CFTV por 199,90", True),
        ("altere o nome do produto 12 para Câmera Y", True),
        ("mude a descrição do iDFace Max", True),
        ("dê baixa de 5 unidades do produto 3 no CD Sul", True),
        ("cancele a venda 6f1e…", True),
        ("liste os produtos", False),
        ("qual o prazo de entrega?", False),
    ],
)
def test_detectar_escrita(mensagem, esperado):
    assert detectar_escrita(mensagem) is esperado


class _LLM:
    def __init__(self, texto):
        self.texto = texto

    async def generate(self, prompt):
        class _R:
            response = text = self.texto

        return _R()


@pytest.mark.asyncio
async def test_interpretar_escrita_extrai_ferramenta_e_argumentos():
    llm = _LLM('{"ferramenta": "alterar_nome_produto", "argumentos": {"produto": 12, "novo_nome": "Y"}}')
    assert await interpretar_escrita(llm, "altere o nome do produto 12 para Y") == {
        "ferramenta": "alterar_nome_produto",
        "argumentos": {"produto": 12, "novo_nome": "Y"},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resposta",
    ["texto livre", '{"ferramenta": "apagar_tudo", "argumentos": {}}', '{"argumentos": {}}'],
)
async def test_interpretar_escrita_ignora_resposta_fora_do_catalogo(resposta):
    assert await interpretar_escrita(_LLM(resposta), "x") is None
```

- [ ] **Step 6: Run to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_tools_roteador.py -v`
Expected: FAIL.

- [ ] **Step 7: Implement `detectar_escrita`, `interpretar_escrita` e o ramo de escrita do handler**

`intencao.py`:

```python
_ESCRITA_RE = re.compile(
    r"\b(inclu[ai]\w*|cadastr[ae]\w*|adicion[ae]\w*|alter[ae]\w*|mude\w*|renome[ie]\w*|atualiz[ae]\w*"
    r"|d[êe]\s+baixa|baixa\s+(?:de|no|do)|cancel[ae]\w*)\b",
    re.IGNORECASE,
)


def detectar_escrita(message: str) -> bool:
    """True se o texto pede uma mudança de dados (produto, estoque, venda)."""
    return bool(_ESCRITA_RE.search(message) and _DADOS_ESCRITA_RE.search(message))
```

com `_DADOS_ESCRITA_RE = re.compile(r"\b(produtos?|estoque|vendas?|pedidos?|descri[cç][aã]o|nome)\b", re.IGNORECASE)`.

```python
# backend/src/app/admin_tools/roteador.py
"""Interpreta, com o LLM local, qual ferramenta de escrita o Admin pediu."""

import json
import re
from typing import Any

from app.admin_tools.ferramentas import FERRAMENTAS

PROMPT_FERRAMENTAS = """Você traduz um pedido do administrador em UMA ação do sistema.
Ações disponíveis e seus argumentos:
- incluir_produto: nome, descricao, preco (número), categoria
- alterar_nome_produto: produto (id ou nome), novo_nome
- alterar_descricao_produto: produto (id ou nome), nova_descricao
- baixa_estoque: produto (id ou nome), cd (centro de distribuição), quantidade (inteiro)
- atualizar_venda: pedido_id (UUID), novo_status ("venda_concluida" ou "cancelada")
Responda APENAS com JSON: {{"ferramenta": "<ação>", "argumentos": {{...}}}}.
Se o pedido não corresponder a nenhuma ação, responda {{"ferramenta": null}}.
Não invente valores que o administrador não informou.

Pedido: {pedido}
"""


async def interpretar_escrita(llm_client: Any, message: str) -> dict[str, Any] | None:
    resposta = await llm_client.generate(PROMPT_FERRAMENTAS.format(pedido=message))
    bruto = getattr(resposta, "response", getattr(resposta, "text", str(resposta)))
    achado = re.search(r"\{.*\}", bruto, re.DOTALL)
    if not achado:
        return None
    try:
        dados = json.loads(achado.group(0))
    except json.JSONDecodeError:
        return None
    nome = dados.get("ferramenta")
    argumentos = dados.get("argumentos")
    if nome not in FERRAMENTAS or not isinstance(argumentos, dict):
        return None
    return {"ferramenta": nome, "argumentos": argumentos}
```

`handler.py`: adicionar o ramo de escrita (a função `processar_pedido_admin` passa a tentar `detectar_escrita` antes de `detectar_consulta`). Para identificar o admin, o orquestrador precisa do `admin_id`: acrescentar o parâmetro `admin_id: int | None` a `processar_pedido_admin` e ao `handle_message` (default `None`; `chat.py` o preenche com o id parseado de `payload.auth_token` ao lado de `is_admin`). Ramo novo:

```python
async def _propor_escrita(message, local_client, db_sessionmaker, admin_id):
    """Retorna (texto, card). Nada é gravado: só a proposta."""
    pedido = await interpretar_escrita(local_client, message)
    if pedido is None:
        return "Não entendi qual alteração você quer fazer. Descreva o produto/pedido e o novo valor.", None
    async with db_sessionmaker() as session:
        try:
            acao, previa = await criar_proposta(
                session, admin_id=admin_id, ferramenta=pedido["ferramenta"], argumentos=pedido["argumentos"]
            )
        except PropostaInvalidaError as exc:
            return str(exc), None
    card = CardAcaoProposta(
        acao_id=str(acao.id), titulo=previa.titulo, antes=previa.antes,
        depois=previa.depois, aviso=previa.aviso, expira_em=acao.expira_em,
    )
    return "Confira a alteração abaixo e confirme para aplicar.", card
```

Teste do handler (acrescentar a `test_admin_tools_handler.py`): admin pede "altere o nome do produto 1 para Y" com LLM falso → `RouterDecision.card.tipo == "acao_proposta"` e o nome do produto **não** mudou no banco; não-admin → nenhum evento; `admin_id=None` → nenhum evento.

- [ ] **Step 8: Run to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_tools_*.py tests/test_orchestrator.py tests/test_chat*.py -q`
Expected: PASS.

- [ ] **Step 9: Docs + commit**

`PROMPTS_E_INSTRUCOES_LLM.md`: entrada nova para `PROMPT_FERRAMENTAS` (e para o prompt de `consultar`, da Task 1); ROADMAP (etapa 3); ARCHITECTURE: catálogo de ferramentas e a regra "produto ambíguo nunca é adivinhado".

```bash
git add backend docs
git commit -m "feat(chat-admin): incluir produto e alterar nome/descrição pelo chat, com prévia e confirmação (R3, Fase 10/11)"
```

---

### Task 4: `baixa_estoque`

**Files:**
- Create: `backend/src/app/admin_tools/ferramentas_estoque.py`
- Modify: `backend/src/app/admin_tools/ferramentas.py` (importar para registrar), `backend/src/app/db/catalog.py` (função atômica)
- Test: `backend/tests/test_admin_tools_estoque.py`

**Interfaces:**
- Consumes: `resolver_produto` (Task 3), `Previa`, `FERRAMENTAS`, `criar_proposta`, `confirmar`.
- Produces: `async baixar_estoque_atomico(session, produto_id: int, cd: str, quantidade: int) -> int` em `db/catalog.py` (devolve o saldo novo; levanta `EstoqueInsuficienteError` se não há saldo; não faz commit); `async devolver_estoque(session, produto_id, cd, quantidade) -> None` (soma; cria a linha se não existir; sem commit) — usada pela Task 5; ferramenta `baixa_estoque` (args `produto, cd, quantidade`).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_admin_tools_estoque.py
from decimal import Decimal

import pytest

from app.admin_tools import ferramentas_estoque, ferramentas_produto  # noqa: F401
from app.admin_tools.propostas import PropostaInvalidaError, confirmar, criar_proposta
from app.db.catalog import (
    EstoqueInsuficienteError,
    atualizar_estoque,
    baixar_estoque_atomico,
    criar_produto,
    devolver_estoque,
    obter_produto,
)


async def _com_estoque(session, saldo=40):
    p = await criar_produto(
        session, nome="Leitor", descricao="d", preco=Decimal("10"), categoria="Geral"
    )
    await atualizar_estoque(session, p.id, "CD Sul", saldo)
    return p


async def _saldo(session, produto_id, cd="CD Sul"):
    session.expire_all()
    p = await obter_produto(session, produto_id)
    return next(e.quantidade for e in p.estoques if e.centro_distribuicao == cd)


@pytest.mark.asyncio
async def test_baixar_estoque_atomico_subtrai_e_recusa_saldo_insuficiente(db_session):
    p = await _com_estoque(db_session, 40)
    assert await baixar_estoque_atomico(db_session, p.id, "CD Sul", 5) == 35
    with pytest.raises(EstoqueInsuficienteError):
        await baixar_estoque_atomico(db_session, p.id, "CD Sul", 36)
    await db_session.commit()
    assert await _saldo(db_session, p.id) == 35


@pytest.mark.asyncio
async def test_devolver_estoque_soma_e_cria_linha_se_nao_existir(db_session):
    p = await _com_estoque(db_session, 10)
    await devolver_estoque(db_session, p.id, "CD Sul", 4)
    await devolver_estoque(db_session, p.id, "CD Norte", 3)
    await db_session.commit()
    assert await _saldo(db_session, p.id) == 14 and await _saldo(db_session, p.id, "CD Norte") == 3


@pytest.mark.asyncio
async def test_baixa_estoque_mostra_antes_depois_e_so_aplica_ao_confirmar(db_session):
    p = await _com_estoque(db_session, 40)
    acao, previa = await criar_proposta(
        db_session,
        admin_id=1,
        ferramenta="baixa_estoque",
        argumentos={"produto": p.id, "cd": "CD Sul", "quantidade": 5},
    )
    assert previa.antes == {"CD Sul": 40} and previa.depois == {"CD Sul": 35}
    assert await _saldo(db_session, p.id) == 40
    await confirmar(db_session, acao.id, admin_id=1)
    assert await _saldo(db_session, p.id) == 35


@pytest.mark.asyncio
@pytest.mark.parametrize("quantidade", [0, -3, "abc"])
async def test_baixa_estoque_rejeita_quantidade_invalida(db_session, quantidade):
    p = await _com_estoque(db_session, 40)
    with pytest.raises(PropostaInvalidaError):
        await criar_proposta(
            db_session,
            admin_id=1,
            ferramenta="baixa_estoque",
            argumentos={"produto": p.id, "cd": "CD Sul", "quantidade": quantidade},
        )


@pytest.mark.asyncio
async def test_baixa_maior_que_o_saldo_e_recusada_ja_na_previa(db_session):
    p = await _com_estoque(db_session, 3)
    with pytest.raises(PropostaInvalidaError, match="Estoque insuficiente"):
        await criar_proposta(
            db_session,
            admin_id=1,
            ferramenta="baixa_estoque",
            argumentos={"produto": p.id, "cd": "CD Sul", "quantidade": 5},
        )


@pytest.mark.asyncio
async def test_saldo_mudou_entre_a_previa_e_a_confirmacao_nao_deixa_negativo(db_session):
    p = await _com_estoque(db_session, 10)
    acao, _ = await criar_proposta(
        db_session,
        admin_id=1,
        ferramenta="baixa_estoque",
        argumentos={"produto": p.id, "cd": "CD Sul", "quantidade": 8},
    )
    await baixar_estoque_atomico(db_session, p.id, "CD Sul", 5)  # outra baixa concorrente
    await db_session.commit()
    with pytest.raises(PropostaInvalidaError):
        await confirmar(db_session, acao.id, admin_id=1)
    assert await _saldo(db_session, p.id) == 5
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_tools_estoque.py -v`
Expected: FAIL (`ImportError: baixar_estoque_atomico`).

- [ ] **Step 3: Implement**

`db/catalog.py` (após `atualizar_estoque`; `update` vem de `sqlalchemy`):

```python
async def baixar_estoque_atomico(
    session: AsyncSession, produto_id: int, centro_distribuicao: str, quantidade: int
) -> int:
    """Subtrai `quantidade` do CD em uma só instrução (`quantidade >= n` na cláusula WHERE),
    sem a corrida de ler-e-gravar. Devolve o saldo novo; não faz commit."""
    resultado = await session.execute(
        update(ProdutoEstoque)
        .where(
            ProdutoEstoque.produto_id == produto_id,
            ProdutoEstoque.centro_distribuicao == centro_distribuicao,
            ProdutoEstoque.quantidade >= quantidade,
        )
        .values(quantidade=ProdutoEstoque.quantidade - quantidade)
    )
    if resultado.rowcount == 0:
        raise EstoqueInsuficienteError(
            f"Estoque insuficiente em {centro_distribuicao} para dar baixa de {quantidade}."
        )
    saldo = await session.execute(
        select(ProdutoEstoque.quantidade).where(
            ProdutoEstoque.produto_id == produto_id,
            ProdutoEstoque.centro_distribuicao == centro_distribuicao,
        )
    )
    return int(saldo.scalar_one())


async def devolver_estoque(
    session: AsyncSession, produto_id: int, centro_distribuicao: str, quantidade: int
) -> None:
    """Soma `quantidade` ao CD (cria a linha se faltar); não faz commit."""
    resultado = await session.execute(
        update(ProdutoEstoque)
        .where(
            ProdutoEstoque.produto_id == produto_id,
            ProdutoEstoque.centro_distribuicao == centro_distribuicao,
        )
        .values(quantidade=ProdutoEstoque.quantidade + quantidade)
    )
    if resultado.rowcount == 0:
        session.add(
            ProdutoEstoque(
                produto_id=produto_id,
                centro_distribuicao=centro_distribuicao,
                quantidade=quantidade,
            )
        )
        await session.flush()
```

```python
# backend/src/app/admin_tools/ferramentas_estoque.py
"""Ferramenta de baixa de estoque do Admin no chat."""

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin_tools.ferramentas import FERRAMENTAS, Previa
from app.admin_tools.ferramentas_produto import _validar, resolver_produto
from app.admin_tools.propostas import PropostaInvalidaError
from app.db.catalog import EstoqueInsuficienteError, baixar_estoque_atomico


class _Baixa(BaseModel):
    produto: str | int
    cd: str = Field(min_length=1)
    quantidade: int = Field(gt=0)


def _saldo(produto: Any, cd: str) -> int | None:
    return next((e.quantidade for e in produto.estoques if e.centro_distribuicao == cd), None)


class BaixaEstoque:
    nome = "baixa_estoque"

    async def preparar(self, session: AsyncSession, args: dict[str, Any]) -> Previa:
        dados = _validar(_Baixa, args)
        produto = await resolver_produto(session, dados.produto)
        saldo = _saldo(produto, dados.cd)
        if saldo is None:
            raise PropostaInvalidaError(f"{produto.nome} não tem estoque em {dados.cd}.")
        if saldo < dados.quantidade:
            raise PropostaInvalidaError(
                f"Estoque insuficiente em {dados.cd}: saldo {saldo}, baixa pedida {dados.quantidade}."
            )
        return Previa(
            titulo=f"Baixa de estoque: {produto.nome}",
            antes={dados.cd: saldo},
            depois={dados.cd: saldo - dados.quantidade},
        )

    async def executar(
        self, session: AsyncSession, args: dict[str, Any], *, admin_id: int
    ) -> dict[str, Any]:
        dados = _validar(_Baixa, args)
        produto = await resolver_produto(session, dados.produto)
        try:
            novo = await baixar_estoque_atomico(session, produto.id, dados.cd, dados.quantidade)
        except EstoqueInsuficienteError as exc:
            raise PropostaInvalidaError(str(exc)) from exc
        return {dados.cd: novo}


FERRAMENTAS["baixa_estoque"] = BaixaEstoque()
```

(`confirmar` chama `preparar` antes de `executar`, então o caso "saldo mudou" já falha na revalidação; `baixar_estoque_atomico` é a segunda barreira contra corrida.)

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_tools_estoque.py tests/test_catalog*.py tests/test_orders*.py -q`
Expected: PASS.

- [ ] **Step 5: Docs + commit**

ROADMAP (etapa 4); ARCHITECTURE: nota de que a baixa/devolução do chat usa `UPDATE … WHERE quantidade >= n` (o `# MVP:` de `ProdutoEstoque` sobre concorrência continua valendo para `criar_pedido`).

```bash
git add backend docs
git commit -m "feat(chat-admin): baixa de estoque atômica pelo chat do Admin (R12, Fase 10/11)"
```

---

### Task 5: `atualizar_venda` (status, inclusive cancelar devolvendo ao estoque)

**Files:**
- Create: `backend/src/app/admin_tools/ferramentas_venda.py`
- Modify: `backend/src/app/admin_tools/ferramentas.py`, `backend/src/app/services/safe_sql.py` (nota semântica), `backend/src/app/db/models.py` (comentário do `Pedido.status`)
- Test: `backend/tests/test_admin_tools_venda.py`

**Interfaces:**
- Consumes: `Previa`, `FERRAMENTAS`, `_validar`, `PropostaInvalidaError`, `devolver_estoque` (Task 4), `obter_pedido`.
- Produces: ferramenta `atualizar_venda` (args `pedido_id: UUID`, `novo_status: "venda_concluida" | "cancelada"`); constante `TRANSICOES: dict[str, set[str]]`.

Tabela de transições (a única fonte de verdade; outros status entram aqui):

| De | Para |
|---|---|
| `reservado` | `venda_concluida`, `cancelada` |
| `pagamento_divergente` | `venda_concluida`, `cancelada` |
| `venda_concluida` | `cancelada` (prévia com aviso extra) |
| `cancelada` | (nenhum) |

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_admin_tools_venda.py
import uuid
from decimal import Decimal

import pytest

from app.admin_tools import ferramentas_estoque, ferramentas_produto, ferramentas_venda  # noqa: F401
from app.admin_tools.propostas import PropostaInvalidaError, confirmar, criar_proposta
from app.db.catalog import atualizar_estoque, criar_pedido, criar_produto, obter_pedido, obter_produto


async def _pedido_reservado(session, quantidade=3, saldo=10):
    p = await criar_produto(
        session, nome="Leitor", descricao="d", preco=Decimal("10"), categoria="Geral"
    )
    await atualizar_estoque(session, p.id, "CD Sul", saldo)
    pedido = await criar_pedido(session, [(p.id, quantidade, "CD Sul")], user_email="c@x.com")
    return p, pedido


async def _saldo(session, produto_id):
    session.expire_all()
    p = await obter_produto(session, produto_id)
    return next(e.quantidade for e in p.estoques if e.centro_distribuicao == "CD Sul")


@pytest.mark.asyncio
async def test_concluir_venda_preenche_conversao_e_nao_mexe_no_estoque(db_session):
    p, pedido = await _pedido_reservado(db_session, quantidade=3, saldo=10)
    assert await _saldo(db_session, p.id) == 7  # criar_pedido já reservou
    acao, previa = await criar_proposta(
        db_session,
        admin_id=1,
        ferramenta="atualizar_venda",
        argumentos={"pedido_id": str(pedido.id), "novo_status": "venda_concluida"},
    )
    assert previa.antes == {"status": "reservado"} and previa.depois == {"status": "venda_concluida"}
    await confirmar(db_session, acao.id, admin_id=1)
    db_session.expire_all()
    novo = await obter_pedido(db_session, pedido.id)
    assert novo.status == "venda_concluida" and novo.tipo_conversao == "chat_admin"
    assert novo.convertido_em is not None and novo.convertido_por == "admin:1"
    assert await _saldo(db_session, p.id) == 7


@pytest.mark.asyncio
async def test_cancelar_devolve_cada_item_ao_estoque_do_proprio_cd(db_session):
    p, pedido = await _pedido_reservado(db_session, quantidade=3, saldo=10)
    acao, previa = await criar_proposta(
        db_session,
        admin_id=1,
        ferramenta="atualizar_venda",
        argumentos={"pedido_id": str(pedido.id), "novo_status": "cancelada"},
    )
    assert previa.depois["estoque_devolvido"] == {"CD Sul": 3} or "CD Sul" in str(previa.depois)
    await confirmar(db_session, acao.id, admin_id=1)
    assert (await obter_pedido(db_session, pedido.id)).status == "cancelada"
    assert await _saldo(db_session, p.id) == 10


@pytest.mark.asyncio
async def test_cancelar_venda_concluida_avisa_na_previa(db_session):
    _, pedido = await _pedido_reservado(db_session)
    a, _ = await criar_proposta(
        db_session, admin_id=1, ferramenta="atualizar_venda",
        argumentos={"pedido_id": str(pedido.id), "novo_status": "venda_concluida"},
    )
    await confirmar(db_session, a.id, admin_id=1)
    _, previa = await criar_proposta(
        db_session, admin_id=1, ferramenta="atualizar_venda",
        argumentos={"pedido_id": str(pedido.id), "novo_status": "cancelada"},
    )
    assert previa.aviso and "concluída" in previa.aviso


@pytest.mark.asyncio
async def test_cancelada_e_terminal_e_status_invalido_ou_pedido_inexistente_falham(db_session):
    _, pedido = await _pedido_reservado(db_session)
    a, _ = await criar_proposta(
        db_session, admin_id=1, ferramenta="atualizar_venda",
        argumentos={"pedido_id": str(pedido.id), "novo_status": "cancelada"},
    )
    await confirmar(db_session, a.id, admin_id=1)
    with pytest.raises(PropostaInvalidaError):
        await criar_proposta(
            db_session, admin_id=1, ferramenta="atualizar_venda",
            argumentos={"pedido_id": str(pedido.id), "novo_status": "venda_concluida"},
        )
    for args in (
        {"pedido_id": str(pedido.id), "novo_status": "inventado"},
        {"pedido_id": str(uuid.uuid4()), "novo_status": "cancelada"},
        {"pedido_id": "nao-e-uuid", "novo_status": "cancelada"},
    ):
        with pytest.raises(PropostaInvalidaError):
            await criar_proposta(db_session, admin_id=1, ferramenta="atualizar_venda", argumentos=args)


@pytest.mark.asyncio
async def test_cancelar_duas_vezes_nao_devolve_estoque_duas_vezes(db_session):
    p, pedido = await _pedido_reservado(db_session, quantidade=3, saldo=10)
    args = {"pedido_id": str(pedido.id), "novo_status": "cancelada"}
    a1, _ = await criar_proposta(db_session, admin_id=1, ferramenta="atualizar_venda", argumentos=args)
    # Segunda proposta criada antes de a primeira ser confirmada:
    a2, _ = await criar_proposta(db_session, admin_id=1, ferramenta="atualizar_venda", argumentos=args)
    await confirmar(db_session, a1.id, admin_id=1)
    with pytest.raises(PropostaInvalidaError):
        await confirmar(db_session, a2.id, admin_id=1)  # revalidação: já está cancelada
    assert await _saldo(db_session, p.id) == 10
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_tools_venda.py -v`
Expected: FAIL (`ModuleNotFoundError: ferramentas_venda`).

- [ ] **Step 3: Implement**

```python
# backend/src/app/admin_tools/ferramentas_venda.py
"""Ferramenta `atualizar_venda`: muda o status de um pedido pelo chat do Admin."""

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin_tools.ferramentas import FERRAMENTAS, Previa
from app.admin_tools.ferramentas_produto import _validar
from app.admin_tools.propostas import PropostaInvalidaError
from app.db.catalog import devolver_estoque, obter_pedido
from app.db.models import Pedido

# Única fonte de verdade das transições. # MVP: sem estorno financeiro nem cancelamento parcial.
TRANSICOES: dict[str, set[str]] = {
    "reservado": {"venda_concluida", "cancelada"},
    "pagamento_divergente": {"venda_concluida", "cancelada"},
    "venda_concluida": {"cancelada"},
    "cancelada": set(),
}


class _AtualizarVenda(BaseModel):
    pedido_id: uuid.UUID
    novo_status: Literal["venda_concluida", "cancelada"]


async def _pedido_para_mudar(session: AsyncSession, args: dict[str, Any]) -> tuple[Pedido, str]:
    dados = _validar(_AtualizarVenda, args)
    pedido = await obter_pedido(session, dados.pedido_id)
    if pedido is None:
        raise PropostaInvalidaError("Pedido não encontrado.")
    if dados.novo_status not in TRANSICOES.get(pedido.status, set()):
        raise PropostaInvalidaError(
            f"Não é possível ir de '{pedido.status}' para '{dados.novo_status}'."
        )
    return pedido, dados.novo_status


def _devolucao(pedido: Pedido) -> dict[str, int]:
    soma: dict[str, int] = {}
    for item in pedido.itens:
        soma[item.centro_distribuicao] = soma.get(item.centro_distribuicao, 0) + item.quantidade
    return soma


class AtualizarVenda:
    nome = "atualizar_venda"

    async def preparar(self, session: AsyncSession, args: dict[str, Any]) -> Previa:
        pedido, novo = await _pedido_para_mudar(session, args)
        depois: dict[str, Any] = {"status": novo}
        aviso = None
        if novo == "cancelada":
            depois["estoque_devolvido"] = _devolucao(pedido)
            if pedido.status == "venda_concluida":
                aviso = "Esta venda já foi concluída; cancelar devolve os itens ao estoque."
        return Previa(
            titulo=f"Pedido {str(pedido.id)[:8]}: {pedido.status} → {novo}",
            antes={"status": pedido.status},
            depois=depois,
            aviso=aviso,
        )

    async def executar(
        self, session: AsyncSession, args: dict[str, Any], *, admin_id: int
    ) -> dict[str, Any]:
        pedido, novo = await _pedido_para_mudar(session, args)
        resultado: dict[str, Any] = {"status": novo}
        if novo == "cancelada":
            for item in pedido.itens:
                await devolver_estoque(
                    session, item.produto_id, item.centro_distribuicao, item.quantidade
                )
            resultado["estoque_devolvido"] = _devolucao(pedido)
        else:
            pedido.tipo_conversao = "chat_admin"
            pedido.convertido_em = datetime.now(UTC)
            pedido.convertido_por = f"admin:{admin_id}"
        pedido.status = novo
        return resultado


FERRAMENTAS["atualizar_venda"] = AtualizarVenda()
```

`safe_sql.py`: em `_SEMANTIC_NOTES["pedidos"]` acrescentar `'cancelada' (pedido cancelado; os itens voltaram ao estoque e NÃO contam como venda)` e na regra de vendas excluir `cancelada`; atualizar o teste correspondente de `test_safe_sql.py`. `db/models.py`: ajustar o comentário do `Pedido.status` (hoje diz que fica sempre `reservado`).

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_tools_*.py tests/test_admin_pedidos*.py tests/test_orders*.py tests/test_safe_sql.py -q`
Expected: PASS.

- [ ] **Step 5: Verificação ponta a ponta + docs + commit**

Com o backend e o frontend no ar: logar como admin, pedir no chat "liste os pedidos reservados" (card de tabela), "dê baixa de 1 unidade do produto N no CD X" (card com Confirmar), confirmar e conferir em `/admin/produtos`; "cancele o pedido <id>" e conferir o estoque devolvido. Rodar a suíte inteira dos arquivos tocados, ruff (check + format), tsc, eslint e vitest.

Docs finais: ARCHITECTURE (decisão de 2026-11-01 consolidada: ferramentas, tabela de transições, `cancelada`, auditoria, `# MVP:`s), FRONTEND, ROADMAP (etapa 5 e item geral), `PROMPTS_E_INSTRUCOES_LLM.md` (conferir que as duas entradas novas estão lá), `HOWTO_ADMINISTRADOR.md` (como pedir cada ação no chat e como confirmar).

```bash
git add backend frontend docs
git commit -m "feat(chat-admin): atualizar venda pelo chat, com status cancelada que devolve o estoque (R12, Fase 10/11)"
```

---

## Self-Review

- **Spec coverage:** `consultar(sql)` (Task 1, com `safe_sql`, limite de 50 linhas e tempo máximo); `incluir_produto`, `alterar_nome_produto`, `alterar_descricao_produto` (Task 3); `baixa_estoque` (Task 4); `atualizar_venda` com `cancelada` e devolução (Task 5); confirmação em toda escrita, auditoria `chat_admin_acoes` e migração 0031 (Task 2); ambiguidade nunca adivinhada (Task 3); só Admin (Tasks 1 e 3: `is_admin`; Task 2: `require_admin`); injeção só gera prévia (a gravação existe apenas no endpoint de confirmação). `consultar_estoque` da tabela do spec é coberta por `consultar(sql)` sobre `produto_estoque` (sem ferramenta própria, para não duplicar). Gráfico segue como está.
- **Placeholders:** nenhum; todos os passos de código trazem o código. Dois pontos dependem de inspeção no momento da execução e estão sinalizados no texto: o import de `RouterDecision`/`TokenEvent` no handler (Task 1) e o id do admin criado por `admin_headers` (Task 2).
- **Consistência de tipos:** `Previa`, `FERRAMENTAS`, `criar_proposta`, `confirmar`, `cancelar`, `PropostaInvalidaError` definidos na Task 2 e usados nas Tasks 3–5; `executar(..., *, admin_id)` é definido já na Task 2 e usado por todas as ferramentas; `_validar` e `resolver_produto` vêm da Task 3; `devolver_estoque` e `baixar_estoque_atomico` da Task 4.
- **Riscos conhecidos:** `RouterDecision`/`TokenEvent`/`_emitir_chart_decision_base` vivem em `orchestrator.py` (import tardio no handler para evitar ciclo); o `admin_id` precisa chegar ao `handle_message` a partir de `chat.py` (Task 3); `criar_produto`/`atualizar_produto` hoje fazem `commit` próprio (Task 3 pede o parâmetro `commit`).
