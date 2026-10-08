# Especificação Arquitetural: Ledger Unificado de Uso de IA (Origem × Ambiente × Modelo) — Item A da Fundação

> **Data:** 08 de Outubro de 2026
> **Status:** Proposta de Arquitetura / Design Spec
> **Domínio:** Telemetria e Custos de IA (admin, cross-cutting)
> **Escopo desta spec:** só o item **A** do plano registrado em
> `docs/ROADMAP.md` ("Extra fora do MVP — Ledger Unificado de Uso de IA") —
> a tabela nova e a função central de registro, sem ainda conectar nenhum
> ponto de chamada real (isso é B/C/D, cada um com sua própria spec).

---

## 1. Contexto e Objetivo

O administrador reportou não conseguir identificar, no painel
`/admin/metricas`, o que foi efetivamente gasto em Visão Computacional
interna (CLIP local, grátis) x externa (OpenRouter, pago). Investigação
revelou um problema maior que uma correção pontual resolveria apenas pela
metade:

1. Hoje o uso de IA é rastreado em **dois esquemas diferentes**:
   `ConversaMensagem.metricas` (JSON por mensagem de chat,
   `app.memory.store`) e `IngestionCostEvent` (tabela própria da extração
   de catálogo/crawler, `app.services.ingestion_metrics`). Nenhum dos dois
   tem a dimensão "origem" (de onde a chamada partiu).
2. **Achado 1** — `vision_used` (`app.api.chat`) é setado
   incondicionalmente sempre que a resposta vem do fluxo de identificação
   de imagem, misturando acerto grátis do CLIP interno com chamada paga de
   visão externa dentro do mesmo total.
3. **Achado 2** — `app.services.comprovante_evaluator.ComprovanteEvaluator`
   chama visão (local ou OpenRouter) mas `ParecerComprovante` só carrega
   `prompt_tokens`/`completion_tokens`, nenhum campo de custo em USD. Essa
   mesma função já é chamada hoje pela ferramenta MCP B2B
   `converter_reserva_venda` — custo real gerado por um parceiro externo,
   não rastreado em lugar nenhum.
4. **Achado 3** — o classificador/monitor de tom via TypeSafe Jev
   (`OpenRouterClient._perguntar_systemone_jev`, usado por
   `classify_intent_jev`/`classify_tone_jev`) não captura **nenhuma**
   métrica de uso desde que foi implementado — nem contagem de chamada.

Decisão do usuário (brainstorming de 2026-10-08): em vez de remendar os
dois esquemas existentes achado a achado, construir uma tabela nova e
genérica — um ledger — com uma função central de registro chamada por
**todo** ponto de uso de IA do sistema (local ou externo, texto ou visão),
com estas dimensões exigidas:

- **`origem`** — de onde a chamada partiu: `"chat"`, `"b2b"`, `"admin"`, e
  outras que vierem a existir. Extensível por design (sem enum rígido no
  banco).
- **`ambiente`** — `"interno"` (modelo/engine local, sem custo de API) ou
  `"externo"` (API paga de terceiro).
- **`modelo`** — qual modelo ou estrutura foi usada: `"clip"`,
  `"gemma4:12b-it-q4_K_M"`, `"jev"`, nome do modelo externo, etc.
- **`tokens_entrada`/`tokens_saida`** — quando fizer sentido (CLIP não
  tem; um LLM tem).
- **`custo_usd`** — quando existir (CLIP e Ollama local são `0.0`
  conhecido, não "não aplicável"; falha ao capturar é a única razão
  legítima de ficar vazio).
- **`operacao`** — granularidade do "o que aconteceu" dentro da origem
  (ex.: `"identificacao_imagem_clip"` vs `"identificacao_imagem_visao_externa"`
  — a mesma origem/ambiente pode cobrir operações bem diferentes).

Este item A entrega só a fundação: a tabela e a função de registro,
testadas isoladamente, **sem alterar nenhum comportamento observável** —
nenhum ponto de chamada real é conectado ainda (isso é explicitamente
escopo de B/C/D, cada um com spec e plano próprios, por já estarem
registrados como itens separados em `docs/ROADMAP.md`).

---

## 2. Decisão de Design: Reaproveitar o Padrão Já Aceito de `record_ingestion_cost`

Duas abordagens foram consideradas para como a função central lida com a
sessão de banco:

- **Função recebe uma sessão já aberta do chamador** — mais correto
  transacionalmente (o evento entra na mesma transação da operação
  principal), mas exigiria roteirizar `session` por várias funções que
  hoje não têm nenhuma sessão de banco em escopo (o classificador via Jev
  em `app.router.classifier`/`app.router.openrouter_client`,
  `identify_product_by_image` em `app.rag.image_identification`,
  `ComprovanteEvaluator`) — invasivo demais para o que este item precisa
  entregar.
- **Função abre sua própria sessão / cai num fallback global
  (ESCOLHIDA):** ao ler `app/services/ingestion_metrics.py` em busca de
  precedente, encontrado que `record_ingestion_cost` **já resolve
  exatamente este problema**, de um jeito já aceito neste código: aceita
  `session` (explícita, quando o chamador já tem uma aberta),
  `session_factory` (abre a própria sessão curta, fire-and-forget), ou cai
  num `_global_sessionmaker` configurado uma vez em `app.main` via
  `set_global_sessionmaker()` — para os chamadores que não têm nem
  `session` nem `session_factory` à mão. Em qualquer um dos três
  caminhos, falha vira só um `logger.warning`, nunca uma exceção
  propagada: telemetria é conveniência, nunca pode derrubar a chamada de
  IA real.

**Decisão: `registrar_uso_ia` espelha esse padrão exatamente** (mesmos
três modos de sessão, mesmo contrato de nunca lançar exceção), em vez de
inventar uma convenção nova. Isso também significa que B/C/D poderão
reaproveitar o mesmo `_global_sessionmaker` já configurado — ou configurar
o seu próprio, mantendo os dois serviços (`ingestion_metrics` e o novo)
independentes, mesmo padrão de duplicação pequena já presente no código
(este arquivo não importa um helper genérico de terceiros também).

---

## 3. Modelagem de Dados

### 3.1 Tabela `ai_usage_events` (nova, migração Alembic `0024`)

| Campo | Tipo | Nullable | Observação |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | não (PK) | `default=uuid.uuid4` |
| `origem` | `String(50)` | não | índice — `"chat"`, `"b2b"`, `"admin"`, futuros |
| `ambiente` | `String(20)` | não | `"interno"` ou `"externo"` |
| `modelo` | `String(100)` | não | `"clip"`, nome do modelo local/externo, `"jev"` |
| `operacao` | `String(100)` | não | índice — granularidade do que aconteceu |
| `tokens_entrada` | `Integer` | sim | sem default — `NULL` é "não capturado"; um valor conhecido pode ser `0` |
| `tokens_saida` | `Integer` | sim | sem default — mesma convenção de `tokens_entrada` |
| `custo_usd` | `Float` | sim | sem default — `NULL` é "não capturado"; `0.0` é um valor real conhecido (CLIP/local) |
| `referencia_id` | `String(500)` | sim | `conversation_id`/`pedido_id`/etc., para rastrear até a origem exata |
| `criado_em` | `DateTime(timezone=True)` | não | `server_default=func.now()`, índice |

Nota (correção pós-implementação, revisão final de item A, 2026-10-08):
`tokens_entrada`, `tokens_saida` e `custo_usd` são `NULL`able sem default,
não `default=0`/`0.0` como uma versão anterior desta decisão (na seção de
Global Constraints do plano, que não faz parte desta spec) havia
estabelecido para todos os campos numéricos. Isso satisfaz o §1 acima:
"falha ao capturar é a única razão legítima de ficar vazio" exige que
"não capturado" (`NULL`) seja distinguível de "capturado como zero"
(`0`/`0.0`, ex.: uma chamada local ao CLIP sem custo de API) — um default
numérico apagaria essa distinção. `origem`/`ambiente`/`modelo`/`operacao`/
`id`/`criado_em` não são afetados: nunca foram ambíguos.

Índices: `origem`, `operacao`, `criado_em` (mesmo padrão de
`idx_ingestion_cost_events_source_type`/`idx_ingestion_cost_events_criado_em`)
— são exatamente os três campos pelos quais o painel (item E, fora do
escopo desta spec) vai filtrar/agrupar.

**Modelo SQLAlchemy** (`backend/src/app/db/models.py`, mesmo estilo de
`IngestionCostEvent`, logo após ela):

```python
class AiUsageEvent(Base):
    """Ledger unificado de uso de IA — todo ponto do sistema que chama um
    modelo/engine (local ou externo, texto ou visão) registra um evento
    aqui. Substitui a necessidade de inferir origem/ambiente a partir de
    campos espalhados em ConversaMensagem.metricas/IngestionCostEvent.
    """

    __tablename__ = "ai_usage_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    origem: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    ambiente: Mapped[str] = mapped_column(String(20), nullable=False)
    modelo: Mapped[str] = mapped_column(String(100), nullable=False)
    operacao: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tokens_entrada: Mapped[int] = mapped_column(default=0)
    tokens_saida: Mapped[int] = mapped_column(default=0)
    custo_usd: Mapped[float] = mapped_column(default=0.0)
    referencia_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
```

### 3.2 Migração Alembic `0024_ai_usage_events.py`

Mesmo formato exato de `0020_ingestion_cost_events.py` (`op.create_table` +
`op.create_index` para `origem`, `operacao`, `criado_em`; `downgrade`
remove os índices e a tabela, na ordem inversa).

---

## 4. A Função Central: `registrar_uso_ia`

Novo módulo `backend/src/app/services/ai_usage.py` (paralelo a
`app.services.ingestion_metrics`, não dentro dele — são dois ledgers com
propósito distinto: este é cross-cutting por origem/ambiente/modelo, o
outro é específico de pipelines de ingestão de dados; `IngestionCostEvent`
**não é removida nem substituída** por este item — isso é uma decisão a
revisitar em D, quando a origem "admin" for conectada, não aqui).

```python
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import AiUsageEvent

logger = logging.getLogger("assistente.ai_usage")

_global_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def set_global_sessionmaker(sessionmaker: async_sessionmaker[AsyncSession] | None) -> None:
    """Configura o sessionmaker global usado quando nenhuma sessão/factory
    explícita é passada — chamado uma vez em app.main, mesmo padrão de
    app.services.ingestion_metrics.set_global_sessionmaker."""
    global _global_sessionmaker
    _global_sessionmaker = sessionmaker


async def registrar_uso_ia(
    *,
    origem: str,
    ambiente: str,
    modelo: str,
    operacao: str,
    tokens_entrada: int = 0,
    tokens_saida: int = 0,
    custo_usd: float = 0.0,
    referencia_id: str | None = None,
    session: AsyncSession | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    commit: bool = False,
) -> AiUsageEvent | None:
    """Registra um evento de uso de IA — chamado por todo ponto do sistema
    que usa um modelo/engine de IA, local ou externo, texto ou visão.
    Nunca lança exceção: falha de banco vira log e `None`, igual
    `record_ingestion_cost` — telemetria não pode derrubar a chamada real.
    """
    evento = AiUsageEvent(
        origem=origem,
        ambiente=ambiente,
        modelo=modelo,
        operacao=operacao,
        tokens_entrada=tokens_entrada,
        tokens_saida=tokens_saida,
        custo_usd=round(custo_usd, 6),
        referencia_id=referencia_id,
    )

    try:
        if session is not None:
            session.add(evento)
            await (session.commit() if commit else session.flush())
            return evento

        factory = session_factory or _global_sessionmaker
        if factory is not None:
            async with factory() as s:
                s.add(evento)
                await s.commit()
                return evento
    except Exception as exc:
        logger.warning(
            "Falha ao registrar AiUsageEvent (origem=%s, operacao=%s): %s",
            origem,
            operacao,
            exc,
        )
    return None
```

`app.main` (lifespan, junto da linha já existente que chama
`ingestion_metrics.set_global_sessionmaker`) ganha a linha equivalente:
`from app.services.ai_usage import set_global_sessionmaker as
set_global_sessionmaker_ai; set_global_sessionmaker_ai(app.state.db_sessionmaker)`
(nome do alias de import só para não colidir com o símbolo já importado de
`ingestion_metrics` no mesmo escopo).

---

## 5. Testes (item A, sem nenhum ponto de chamada real conectado ainda)

- `backend/tests/test_ai_usage.py` (novo, mesmo padrão de
  `tests/test_memory_store.py`): engine SQLite em memória, `Base.metadata.create_all`.
  - `registrar_uso_ia` com `session` explícita grava e o evento aparece
    numa query direta à tabela.
  - `registrar_uso_ia` com `session_factory` (sem `session`) também
    grava — fire-and-forget funciona.
  - `registrar_uso_ia` sem `session` nem `session_factory`, mas com
    `set_global_sessionmaker` configurado antes, grava via o fallback
    global.
  - `registrar_uso_ia` sem nenhum dos três (nem sessão, nem factory, nem
    global configurado) retorna `None` sem lançar exceção.
  - `registrar_uso_ia` com uma `session_factory` que lança
    `ConnectionError` ao abrir (mesmo padrão de teste de
    `test_image_api.py`'s `_SemBanco`) retorna `None`, loga, não propaga.
  - Valores default (`tokens_entrada=0`, `tokens_saida=0`, `custo_usd=0.0`)
    são persistidos corretamente quando omitidos pelo chamador.
- Migração testada subindo `alembic upgrade head` contra Postgres real de
  desenvolvimento (mesmo processo manual já usado para as migrações
  anteriores, ver `docs/TESTE_LOCAL.md`) — fora do que testes automatizados
  cobrem, mas necessário antes de B/C/D poderem gravar de verdade.

---

## 6. Fora de Escopo Desta Spec (itens B/C/D/E do roadmap)

- Conectar qualquer ponto de chamada real (`handle_message`, Jev,
  `identify_product_by_image`, `ComprovanteEvaluator`, MCP B2B, extração
  de catálogo, geração de gráficos) a `registrar_uso_ia` — item B/C/D.
- Qualquer mudança no painel `/admin/metricas` ou em
  `app/api/admin_metrics.py` — item E.
- Decidir se `IngestionCostEvent`/`total_vision_cost_usd` (em
  `MetricSummary`) são descontinuados em favor da tabela nova, mantidos em
  paralelo, ou usados como fonte de dados históricos pré-migração — essa
  decisão específica fica para quando a origem "admin" (D) e o painel (E)
  forem desenhados, não aqui.

---

## 7. Próximos Passos

1. Criar `AiUsageEvent` em `backend/src/app/db/models.py`.
2. Migração Alembic `0024_ai_usage_events.py`.
3. Criar `backend/src/app/services/ai_usage.py`
   (`registrar_uso_ia`/`set_global_sessionmaker`).
4. Chamar `set_global_sessionmaker` em `app.main` (lifespan).
5. Testes de `registrar_uso_ia` (os 6 casos da Seção 5).
6. Atualizar `docs/ARCHITECTURE.md` com a decisão desta spec (nova seção
   ou acréscimo à seção de telemetria existente) e marcar o item A como
   `[x]` em `docs/ROADMAP.md`.
