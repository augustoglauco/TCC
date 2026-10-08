# Ledger de Uso de IA — Item E (Painel) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconstruir o painel `/admin/metricas` sobre a tabela `ai_usage_events` como fonte única, estratificado por origem × ambiente × modelo, e migrar o último ponto de uso de IA que ainda ficava fora do ledger (o classificador do crawler).

**Architecture:** Um endpoint novo `GET /api/admin/metrics/ai-usage` faz duas consultas — um `GROUP BY origem, ambiente, modelo, operacao` que alimenta cinco visões por roll-up em Python, e uma seleção estreita por evento para o recorte diário (bucketado no fuso local do administrador, porque não há expressão SQL portável entre SQLite e PostgreSQL para isso). O roll-up vive num módulo puro sem FastAPI nem banco (`app/services/ai_usage_report.py`), testável direto. O endpoint antigo `/tokens-and-costs` e sua heurística de "é visão?" são removidos, e a página Next.js é reconstruída em cinco seções.

**Tech Stack:** Python 3.14 / FastAPI / SQLAlchemy 2 async / Pydantic v2 / pytest + pytest-asyncio (SQLite em memória); Next.js 15 (App Router) / React / TypeScript / Tailwind / vitest + React Testing Library.

**Spec:** `docs/superpowers/specs/2026-10-08-ledger-uso-ia-item-e-painel-design.md`

## Global Constraints

- **`None` nunca vira `0`.** No ledger `None` = "não capturado / não se aplica" e `0.0` = "zero conhecido (grátis)". É proibido `COALESCE(..., 0)`, `or 0`, `or 0.0` ou `int(x or 0)` em qualquer caminho de agregação de `tokens_entrada`, `tokens_saida` ou `custo_usd`. Decisão dos itens A/B/D; é a razão de existir do ledger.
- **Fuso local, não UTC.** Todo recorte de período e todo bucket diário usa `ZoneInfo(get_settings().agendamento_timezone)`. Achado da revisão de 2026-10-04: bucketar em UTC cortava o dia às 21h de Brasília.
- **Data mal formada → HTTP 400**, nunca cair silenciosamente no período default (achado da revisão de 2026-10-04).
- **Custo arredondado a 6 casas** na saída (`round(x, 6)`), como já faz `registrar_uso_ia`.
- **Sem SQL dialect-specific.** Testes rodam em `sqlite+aiosqlite:///:memory:` e produção em PostgreSQL; o projeto não tem nenhum SQL específico de dialeto hoje e este item não introduz o primeiro.
- **Comentário `# MVP: <limitação>`** em toda simplificação deliberada (regra 2 do `CLAUDE.md`).
- Backend: `cd backend && pytest`. Frontend: `cd frontend && npm test`.

---

### Task 1: Módulo de roll-up puro (`ai_usage_report`)

Produz os modelos de resposta e toda a lógica de agregação, sem FastAPI e sem banco — é a única parte com lógica sutil (a soma que respeita `None`) e por isso ganha testes diretos.

**Files:**
- Create: `backend/src/app/services/ai_usage_report.py`
- Test: `backend/tests/test_ai_usage_report.py`

**Interfaces:**
- Consumes: nada (módulo folha).
- Produces:
  - `LinhaAgregada` — dataclass frozen: `origem: str`, `ambiente: str`, `modelo: str`, `operacao: str`, `chamadas: int`, `tokens_entrada: int | None`, `tokens_saida: int | None`, `custo_usd: float | None`, `chamadas_sem_custo_medido: int`.
  - `EventoDiario` — dataclass frozen: `data: str` (`"YYYY-MM-DD"` já resolvido no fuso local por quem chama), `origem: str`, `tokens_entrada: int | None`, `tokens_saida: int | None`, `custo_usd: float | None`.
  - `BlocoMetricas`, `MetricasPorOrigem`, `MetricasPorAmbiente`, `MetricasPorModelo`, `MetricasPorOperacao`, `Atendimento`, `DiaUsoIa`, `AiUsageReport` — modelos Pydantic.
  - `montar_relatorio(*, period: str, linhas: Sequence[LinhaAgregada], eventos_diarios: Sequence[EventoDiario], chats_encerrados_total: int, chats_encerrados_por_dia: Mapping[str, int]) -> AiUsageReport`.

- [ ] **Step 1: Write the failing tests**

Crie `backend/tests/test_ai_usage_report.py`:

```python
"""Testes do roll-up puro do relatório de uso de IA (item E do ledger).

Sem banco e sem HTTP de propósito: a regra sutil deste item é a soma que
respeita `None` (não-medido) versus `0.0` (grátis conhecido), e ela é
testada direto na função, não através do endpoint.
"""

from app.services.ai_usage_report import (
    EventoDiario,
    LinhaAgregada,
    montar_relatorio,
)


def _linha(
    origem="chat",
    ambiente="externo",
    modelo="gpt-x",
    operacao="geracao_resposta",
    chamadas=1,
    tokens_entrada=100,
    tokens_saida=10,
    custo_usd=0.001,
    chamadas_sem_custo_medido=0,
) -> LinhaAgregada:
    return LinhaAgregada(
        origem=origem,
        ambiente=ambiente,
        modelo=modelo,
        operacao=operacao,
        chamadas=chamadas,
        tokens_entrada=tokens_entrada,
        tokens_saida=tokens_saida,
        custo_usd=custo_usd,
        chamadas_sem_custo_medido=chamadas_sem_custo_medido,
    )


def test_relatorio_vazio_nao_inventa_zeros_de_custo():
    rel = montar_relatorio(
        period="7d",
        linhas=[],
        eventos_diarios=[],
        chats_encerrados_total=0,
        chats_encerrados_por_dia={},
    )

    assert rel.period == "7d"
    assert rel.totais.chamadas == 0
    # Nada medido => `None`, não `0.0`: o painel precisa distinguir
    # "não houve chamada" de "houve chamada grátis".
    assert rel.totais.custo_usd is None
    assert rel.totais.tokens_entrada is None
    assert rel.por_origem == []
    assert rel.por_ambiente == []
    assert rel.por_modelo == []
    assert rel.por_operacao == []
    assert rel.diario == []
    assert rel.atendimento.chats_encerrados == 0


def test_totais_fecham_com_a_soma_por_origem():
    linhas = [
        _linha(origem="chat", chamadas=3, tokens_entrada=300, tokens_saida=30, custo_usd=0.003),
        _linha(origem="b2b", chamadas=2, tokens_entrada=200, tokens_saida=20, custo_usd=0.002),
        _linha(origem="admin", chamadas=1, tokens_entrada=100, tokens_saida=10, custo_usd=0.001),
    ]

    rel = montar_relatorio(
        period="30d",
        linhas=linhas,
        eventos_diarios=[],
        chats_encerrados_total=5,
        chats_encerrados_por_dia={},
    )

    assert rel.totais.chamadas == 6
    assert rel.totais.custo_usd == 0.006
    assert rel.totais.tokens_entrada == 600
    assert rel.totais.tokens_saida == 60

    por_origem = {b.origem: b for b in rel.por_origem}
    assert set(por_origem) == {"chat", "b2b", "admin"}
    assert por_origem["chat"].chamadas == 3
    assert sum(b.chamadas for b in rel.por_origem) == rel.totais.chamadas
    assert round(sum(b.custo_usd for b in rel.por_origem), 6) == rel.totais.custo_usd
    assert rel.atendimento.chats_encerrados == 5


def test_custo_todo_nao_medido_sai_none_e_conta_sem_custo_medido():
    linhas = [
        _linha(
            origem="chat",
            ambiente="interno",
            modelo="clip",
            operacao="identificacao_imagem_clip",
            chamadas=4,
            tokens_entrada=None,
            tokens_saida=None,
            custo_usd=None,
            chamadas_sem_custo_medido=4,
        )
    ]

    rel = montar_relatorio(
        period="7d",
        linhas=linhas,
        eventos_diarios=[],
        chats_encerrados_total=0,
        chats_encerrados_por_dia={},
    )

    assert rel.totais.custo_usd is None
    assert rel.totais.tokens_entrada is None
    assert rel.totais.chamadas == 4
    assert rel.totais.chamadas_sem_custo_medido == 4


def test_custo_parcialmente_medido_soma_so_o_medido_e_sinaliza_o_resto():
    linhas = [
        _linha(chamadas=2, custo_usd=0.002, tokens_entrada=200, tokens_saida=20),
        _linha(
            modelo="clip",
            ambiente="interno",
            operacao="identificacao_imagem_clip",
            chamadas=3,
            custo_usd=None,
            tokens_entrada=None,
            tokens_saida=None,
            chamadas_sem_custo_medido=3,
        ),
    ]

    rel = montar_relatorio(
        period="7d",
        linhas=linhas,
        eventos_diarios=[],
        chats_encerrados_total=0,
        chats_encerrados_por_dia={},
    )

    assert rel.totais.chamadas == 5
    assert rel.totais.custo_usd == 0.002
    assert rel.totais.chamadas_sem_custo_medido == 3


def test_custo_zero_conhecido_nao_e_confundido_com_nao_medido():
    linhas = [
        _linha(
            ambiente="interno",
            modelo="llama3.1:8b",
            custo_usd=0.0,
            chamadas=2,
            chamadas_sem_custo_medido=0,
        )
    ]

    rel = montar_relatorio(
        period="7d",
        linhas=linhas,
        eventos_diarios=[],
        chats_encerrados_total=0,
        chats_encerrados_por_dia={},
    )

    assert rel.totais.custo_usd == 0.0
    assert rel.totais.custo_usd is not None
    assert rel.totais.chamadas_sem_custo_medido == 0


def test_agrupamentos_usam_as_chaves_certas():
    linhas = [
        _linha(origem="chat", ambiente="interno", modelo="clip", operacao="identificacao_imagem_clip", custo_usd=0.0),
        _linha(origem="chat", ambiente="externo", modelo="gemma-vision", operacao="identificacao_imagem_visao_externa"),
        _linha(origem="admin", ambiente="externo", modelo="gemma-vision", operacao="extracao_catalogo_visao_externa"),
    ]

    rel = montar_relatorio(
        period="all",
        linhas=linhas,
        eventos_diarios=[],
        chats_encerrados_total=0,
        chats_encerrados_por_dia={},
    )

    assert {b.ambiente for b in rel.por_ambiente} == {"interno", "externo"}
    # `por_modelo` agrupa por (modelo, ambiente): o mesmo modelo externo
    # usado por duas origens é UMA linha.
    modelos = {(b.modelo, b.ambiente): b for b in rel.por_modelo}
    assert set(modelos) == {("clip", "interno"), ("gemma-vision", "externo")}
    assert modelos[("gemma-vision", "externo")].chamadas == 2
    # `por_operacao` agrupa por (operacao, origem, ambiente): é o nível que
    # separa visão interna de externa, que a heurística antiga misturava.
    assert len(rel.por_operacao) == 3


def test_diario_agrupa_por_dia_local_ordenado_do_mais_recente():
    eventos = [
        EventoDiario(data="2026-10-06", origem="chat", tokens_entrada=10, tokens_saida=1, custo_usd=0.001),
        EventoDiario(data="2026-10-08", origem="chat", tokens_entrada=20, tokens_saida=2, custo_usd=0.002),
        EventoDiario(data="2026-10-08", origem="admin", tokens_entrada=None, tokens_saida=None, custo_usd=None),
    ]

    rel = montar_relatorio(
        period="7d",
        linhas=[],
        eventos_diarios=eventos,
        chats_encerrados_total=3,
        chats_encerrados_por_dia={"2026-10-08": 2, "2026-10-06": 1},
    )

    assert [d.data for d in rel.diario] == ["2026-10-08", "2026-10-06"]

    hoje = rel.diario[0]
    assert hoje.chats_encerrados == 2
    assert hoje.totais.chamadas == 2
    assert hoje.totais.custo_usd == 0.002
    assert hoje.totais.chamadas_sem_custo_medido == 1
    assert {b.origem for b in hoje.por_origem} == {"chat", "admin"}

    ontem = rel.diario[1]
    assert ontem.chats_encerrados == 1
    assert ontem.totais.chamadas == 1


def test_diario_inclui_dia_com_chat_encerrado_e_nenhum_uso_de_ia():
    rel = montar_relatorio(
        period="7d",
        linhas=[],
        eventos_diarios=[],
        chats_encerrados_total=1,
        chats_encerrados_por_dia={"2026-10-07": 1},
    )

    assert [d.data for d in rel.diario] == ["2026-10-07"]
    assert rel.diario[0].chats_encerrados == 1
    assert rel.diario[0].totais.chamadas == 0
    assert rel.diario[0].totais.custo_usd is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_ai_usage_report.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.services.ai_usage_report'`

- [ ] **Step 3: Write the implementation**

Crie `backend/src/app/services/ai_usage_report.py`:

```python
"""Relatório de uso de IA para o painel `/admin/metricas` — roll-up puro
sobre as linhas já agregadas de `ai_usage_events` (item E do ledger, ver
docs/superpowers/specs/2026-10-08-ledger-uso-ia-item-e-painel-design.md).

Sem FastAPI e sem sessão de banco de propósito: a consulta mora no
endpoint (`app.api.admin_metrics`), a lógica de combinar grupos mora aqui e
é testada direto. A regra central é a soma que respeita `None`: no ledger
`None` significa "não capturado / não se aplica" e `0.0` significa "zero
conhecido (grátis)" — somar `None` como zero é exatamente o erro que o
painel antigo cometia e que este módulo existe para não repetir.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pydantic import BaseModel

ORIGENS_CONHECIDAS: tuple[str, ...] = ("chat", "b2b", "admin")
AMBIENTES_CONHECIDOS: tuple[str, ...] = ("interno", "externo")


@dataclass(frozen=True)
class LinhaAgregada:
    """Uma linha do `GROUP BY origem, ambiente, modelo, operacao`."""

    origem: str
    ambiente: str
    modelo: str
    operacao: str
    chamadas: int
    tokens_entrada: int | None
    tokens_saida: int | None
    custo_usd: float | None
    chamadas_sem_custo_medido: int


@dataclass(frozen=True)
class EventoDiario:
    """Um evento do ledger com o dia já resolvido no fuso local de quem
    chama — o bucket diário não é feito em SQL porque não existe expressão
    portável entre SQLite (testes) e PostgreSQL (produção) para truncar um
    timestamp num fuso arbitrário (ver spec §3.1)."""

    data: str
    origem: str
    tokens_entrada: int | None
    tokens_saida: int | None
    custo_usd: float | None


class BlocoMetricas(BaseModel):
    chamadas: int = 0
    tokens_entrada: int | None = None
    tokens_saida: int | None = None
    custo_usd: float | None = None
    chamadas_sem_custo_medido: int = 0


class MetricasPorOrigem(BlocoMetricas):
    origem: str


class MetricasPorAmbiente(BlocoMetricas):
    ambiente: str


class MetricasPorModelo(BlocoMetricas):
    modelo: str
    ambiente: str


class MetricasPorOperacao(BlocoMetricas):
    operacao: str
    origem: str
    ambiente: str


class Atendimento(BaseModel):
    """Volume de atendimento — NÃO vem do ledger, vem de `Conversa`. Fica
    em bloco próprio para não misturar semântica com uso de IA."""

    chats_encerrados: int = 0


class DiaUsoIa(BaseModel):
    data: str
    chats_encerrados: int = 0
    totais: BlocoMetricas
    por_origem: list[MetricasPorOrigem]


class AiUsageReport(BaseModel):
    period: str
    atendimento: Atendimento
    totais: BlocoMetricas
    por_origem: list[MetricasPorOrigem]
    por_ambiente: list[MetricasPorAmbiente]
    por_modelo: list[MetricasPorModelo]
    por_operacao: list[MetricasPorOperacao]
    diario: list[DiaUsoIa]


def _somar[T: (int, float)](a: T | None, b: T | None) -> T | None:
    """Soma preservando a semântica `None` = não-medido: `None + None` é
    `None` (continua não-medido), e `None + x` é `x` (não contamina o que
    foi medido com um zero fabricado)."""
    if a is None:
        return b
    if b is None:
        return a
    return a + b


class _Acumulador:
    def __init__(self) -> None:
        self.chamadas = 0
        self.tokens_entrada: int | None = None
        self.tokens_saida: int | None = None
        self.custo_usd: float | None = None
        self.chamadas_sem_custo_medido = 0

    def somar(
        self,
        *,
        chamadas: int,
        tokens_entrada: int | None,
        tokens_saida: int | None,
        custo_usd: float | None,
        chamadas_sem_custo_medido: int,
    ) -> None:
        self.chamadas += chamadas
        self.tokens_entrada = _somar(self.tokens_entrada, tokens_entrada)
        self.tokens_saida = _somar(self.tokens_saida, tokens_saida)
        self.custo_usd = _somar(self.custo_usd, custo_usd)
        self.chamadas_sem_custo_medido += chamadas_sem_custo_medido

    def como_dict(self) -> dict[str, object]:
        return {
            "chamadas": self.chamadas,
            "tokens_entrada": self.tokens_entrada,
            "tokens_saida": self.tokens_saida,
            "custo_usd": round(self.custo_usd, 6) if self.custo_usd is not None else None,
            "chamadas_sem_custo_medido": self.chamadas_sem_custo_medido,
        }


def _agrupar(
    linhas: Sequence[LinhaAgregada], campos: tuple[str, ...]
) -> dict[tuple[str, ...], _Acumulador]:
    grupos: dict[tuple[str, ...], _Acumulador] = {}
    for linha in linhas:
        chave = tuple(getattr(linha, campo) for campo in campos)
        acc = grupos.setdefault(chave, _Acumulador())
        acc.somar(
            chamadas=linha.chamadas,
            tokens_entrada=linha.tokens_entrada,
            tokens_saida=linha.tokens_saida,
            custo_usd=linha.custo_usd,
            chamadas_sem_custo_medido=linha.chamadas_sem_custo_medido,
        )
    return grupos


def _ordem_conhecida(valor: str, conhecidos: tuple[str, ...]) -> tuple[int, str]:
    """Ordena pelos valores conhecidos primeiro (chat, b2b, admin), e
    alfabeticamente o que aparecer de novo — o ledger é extensível por
    design, então uma origem nova não quebra a ordenação."""
    try:
        return (conhecidos.index(valor), "")
    except ValueError:
        return (len(conhecidos), valor)


def montar_relatorio(
    *,
    period: str,
    linhas: Sequence[LinhaAgregada],
    eventos_diarios: Sequence[EventoDiario],
    chats_encerrados_total: int,
    chats_encerrados_por_dia: Mapping[str, int],
) -> AiUsageReport:
    """Monta o relatório completo a partir das linhas agregadas (Q1) e dos
    eventos com dia local já resolvido (Q2)."""
    totais = _Acumulador()
    for linha in linhas:
        totais.somar(
            chamadas=linha.chamadas,
            tokens_entrada=linha.tokens_entrada,
            tokens_saida=linha.tokens_saida,
            custo_usd=linha.custo_usd,
            chamadas_sem_custo_medido=linha.chamadas_sem_custo_medido,
        )

    por_origem = [
        MetricasPorOrigem(origem=chave[0], **acc.como_dict())
        for chave, acc in sorted(
            _agrupar(linhas, ("origem",)).items(),
            key=lambda kv: _ordem_conhecida(kv[0][0], ORIGENS_CONHECIDAS),
        )
    ]
    por_ambiente = [
        MetricasPorAmbiente(ambiente=chave[0], **acc.como_dict())
        for chave, acc in sorted(
            _agrupar(linhas, ("ambiente",)).items(),
            key=lambda kv: _ordem_conhecida(kv[0][0], AMBIENTES_CONHECIDOS),
        )
    ]
    por_modelo = [
        MetricasPorModelo(modelo=chave[0], ambiente=chave[1], **acc.como_dict())
        for chave, acc in sorted(
            _agrupar(linhas, ("modelo", "ambiente")).items(),
            key=lambda kv: (-kv[1].chamadas, kv[0]),
        )
    ]
    por_operacao = [
        MetricasPorOperacao(
            operacao=chave[0], origem=chave[1], ambiente=chave[2], **acc.como_dict()
        )
        for chave, acc in sorted(
            _agrupar(linhas, ("operacao", "origem", "ambiente")).items(),
            key=lambda kv: (-kv[1].chamadas, kv[0]),
        )
    ]

    # Dias: união dos dias com uso de IA e dos dias com chat encerrado — um
    # dia sem nenhuma chamada de IA mas com conversa encerrada é uma linha
    # legítima do relatório.
    dias: dict[str, _Acumulador] = {}
    dias_por_origem: dict[str, dict[str, _Acumulador]] = {}
    for evento in eventos_diarios:
        acc_dia = dias.setdefault(evento.data, _Acumulador())
        sem_custo = 1 if evento.custo_usd is None else 0
        acc_dia.somar(
            chamadas=1,
            tokens_entrada=evento.tokens_entrada,
            tokens_saida=evento.tokens_saida,
            custo_usd=evento.custo_usd,
            chamadas_sem_custo_medido=sem_custo,
        )
        acc_origem = dias_por_origem.setdefault(evento.data, {}).setdefault(
            evento.origem, _Acumulador()
        )
        acc_origem.somar(
            chamadas=1,
            tokens_entrada=evento.tokens_entrada,
            tokens_saida=evento.tokens_saida,
            custo_usd=evento.custo_usd,
            chamadas_sem_custo_medido=sem_custo,
        )

    datas = set(dias) | set(chats_encerrados_por_dia)
    diario = [
        DiaUsoIa(
            data=data,
            chats_encerrados=chats_encerrados_por_dia.get(data, 0),
            totais=BlocoMetricas(**dias.get(data, _Acumulador()).como_dict()),
            por_origem=[
                MetricasPorOrigem(origem=origem, **acc.como_dict())
                for origem, acc in sorted(
                    dias_por_origem.get(data, {}).items(),
                    key=lambda kv: _ordem_conhecida(kv[0], ORIGENS_CONHECIDAS),
                )
            ],
        )
        for data in sorted(datas, reverse=True)
    ]

    return AiUsageReport(
        period=period,
        atendimento=Atendimento(chats_encerrados=chats_encerrados_total),
        totais=BlocoMetricas(**totais.como_dict()),
        por_origem=por_origem,
        por_ambiente=por_ambiente,
        por_modelo=por_modelo,
        por_operacao=por_operacao,
        diario=diario,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_ai_usage_report.py -v`
Expected: PASS (9 testes)

Se `_somar[T: (int, float)]` (sintaxe de generics de PEP 695) der problema no interpretador do projeto, troque a assinatura por `def _somar(a: float | None, b: float | None) -> float | None:` e mantenha o corpo — a semântica é a mesma; `int` é subtipo aceitável aqui.

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/services/ai_usage_report.py backend/tests/test_ai_usage_report.py
git commit -m "feat(telemetria): roll-up puro do relatorio de uso de IA (item E, Task 1)

Modelos de resposta e agregacao por origem/ambiente/modelo/operacao sobre
as linhas de ai_usage_events, sem FastAPI e sem banco. A regra central e a
soma que respeita None=nao-medido versus 0.0=gratis conhecido, testada
direto na funcao.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Endpoint `GET /api/admin/metrics/ai-usage` (e remoção do antigo)

**Files:**
- Modify: `backend/src/app/api/admin_metrics.py` (reescrita quase total: remove `MetricSummary`, `DailyMetric`, `get_token_and_cost_metrics` e a heurística de visão; adiciona o endpoint novo e o helper de janela)
- Test: `backend/tests/test_admin_metrics_ai_usage.py` (criar)
- Delete: `backend/tests/test_admin_metrics_api.py`, `backend/tests/test_admin_metrics_vision.py`

**Interfaces:**
- Consumes: `app.services.ai_usage_report.{LinhaAgregada, EventoDiario, AiUsageReport, montar_relatorio}` (Task 1).
- Produces: `GET /api/admin/metrics/ai-usage` com o payload de `AiUsageReport`; `app.api.admin_metrics._resolver_janela(period: str, start_date: str | None, end_date: str | None, local_tz: ZoneInfo) -> tuple[datetime | None, datetime | None]` (consumido pelo próprio endpoint). `GET /api/admin/metrics/tokens-and-costs` deixa de existir.

- [ ] **Step 1: Write the failing tests**

Crie `backend/tests/test_admin_metrics_ai_usage.py`:

```python
"""Testes do endpoint `GET /api/admin/metrics/ai-usage` (item E do ledger).

Portam os casos de regressão que viviam em `test_admin_metrics_api.py` e
`test_admin_metrics_vision.py` (endpoint antigo, removido neste item): a
autenticação de admin, o recorte de período no fuso LOCAL e a separação
entre visão interna e externa — que agora é um fato do ledger
(`ambiente`/`operacao`) e não mais uma heurística de nome de modelo.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin_metrics import router as admin_metrics_router
from app.api.rag_dependencies import get_db_session
from app.config import get_settings
from app.db.models import AiUsageEvent, Conversa


class _SingleSessionMaker:
    def __init__(self, session) -> None:
        self._session = session
        self._lock = asyncio.Lock()

    def __call__(self):
        return self

    async def __aenter__(self):
        await self._lock.acquire()
        return self._session

    async def __aexit__(self, *exc_info) -> bool:
        self._lock.release()
        return False


@pytest.fixture
def metrics_client(db_session):
    app = FastAPI()
    app.include_router(admin_metrics_router)
    app.state.db_sessionmaker = _SingleSessionMaker(db_session)
    app.dependency_overrides[get_db_session] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def local_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().agendamento_timezone)


async def _evento(session, **kwargs) -> AiUsageEvent:
    padrao: dict = {
        "origem": "chat",
        "ambiente": "externo",
        "modelo": "gpt-x",
        "operacao": "geracao_resposta",
        "tokens_entrada": 100,
        "tokens_saida": 10,
        "custo_usd": 0.001,
        "criado_em": datetime.now(UTC),
    }
    padrao.update(kwargs)
    evento = AiUsageEvent(**padrao)
    session.add(evento)
    await session.commit()
    return evento


@pytest.mark.asyncio
async def test_ai_usage_requer_autenticacao_admin(metrics_client):
    assert metrics_client.get("/api/admin/metrics/ai-usage?period=7d").status_code == 403


@pytest.mark.asyncio
async def test_ai_usage_sem_dados(metrics_client, admin_headers):
    res = metrics_client.get("/api/admin/metrics/ai-usage?period=7d", headers=admin_headers)

    assert res.status_code == 200
    data = res.json()
    assert data["period"] == "7d"
    assert data["totais"]["chamadas"] == 0
    assert data["totais"]["custo_usd"] is None
    assert data["por_origem"] == []
    assert data["diario"] == []
    assert data["atendimento"]["chats_encerrados"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("campo", ["start_date", "end_date"])
async def test_ai_usage_data_malformada_retorna_400(metrics_client, admin_headers, campo):
    res = metrics_client.get(
        f"/api/admin/metrics/ai-usage?{campo}=not-a-date", headers=admin_headers
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_ai_usage_estratifica_por_origem_ambiente_modelo_e_operacao(
    metrics_client, admin_headers, db_session
):
    await _evento(
        db_session,
        origem="chat",
        ambiente="interno",
        modelo="clip",
        operacao="identificacao_imagem_clip",
        tokens_entrada=None,
        tokens_saida=None,
        custo_usd=0.0,
    )
    await _evento(
        db_session,
        origem="chat",
        ambiente="externo",
        modelo="gemma-vision",
        operacao="identificacao_imagem_visao_externa",
        tokens_entrada=800,
        tokens_saida=60,
        custo_usd=0.0025,
    )
    await _evento(
        db_session,
        origem="admin",
        ambiente="externo",
        modelo="gemma-vision",
        operacao="extracao_catalogo_visao_externa",
        tokens_entrada=1200,
        tokens_saida=90,
        custo_usd=0.004,
    )
    await _evento(
        db_session,
        origem="b2b",
        ambiente="interno",
        modelo="llama3.1:8b",
        operacao="comprovante_texto_llm",
        tokens_entrada=300,
        tokens_saida=30,
        custo_usd=0.0,
    )

    res = metrics_client.get("/api/admin/metrics/ai-usage?period=today", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()

    por_origem = {b["origem"]: b for b in data["por_origem"]}
    assert por_origem["chat"]["chamadas"] == 2
    assert por_origem["admin"]["chamadas"] == 1
    assert por_origem["b2b"]["chamadas"] == 1

    por_ambiente = {b["ambiente"]: b for b in data["por_ambiente"]}
    # A pergunta que originou o plano A→E: quanto foi grátis e quanto foi pago.
    assert por_ambiente["interno"]["custo_usd"] == 0.0
    assert por_ambiente["externo"]["custo_usd"] == 0.0065

    # Visão interna (CLIP) e externa são operações distintas — fato do
    # ledger, não heurística de nome de modelo.
    operacoes = {b["operacao"] for b in data["por_operacao"]}
    assert "identificacao_imagem_clip" in operacoes
    assert "identificacao_imagem_visao_externa" in operacoes

    modelos = {(b["modelo"], b["ambiente"]): b for b in data["por_modelo"]}
    assert modelos[("gemma-vision", "externo")]["chamadas"] == 2

    assert data["totais"]["chamadas"] == 4
    assert data["totais"]["custo_usd"] == 0.0065


@pytest.mark.asyncio
async def test_ai_usage_nao_transforma_custo_nao_medido_em_zero(
    metrics_client, admin_headers, db_session
):
    await _evento(
        db_session,
        origem="admin",
        ambiente="externo",
        modelo="gemma-vision",
        operacao="extracao_catalogo_visao_externa",
        tokens_entrada=None,
        tokens_saida=None,
        custo_usd=None,
    )

    res = metrics_client.get("/api/admin/metrics/ai-usage?period=today", headers=admin_headers)
    data = res.json()

    assert data["totais"]["custo_usd"] is None
    assert data["totais"]["tokens_entrada"] is None
    assert data["totais"]["chamadas"] == 1
    assert data["totais"]["chamadas_sem_custo_medido"] == 1


@pytest.mark.asyncio
async def test_ai_usage_period_today_usa_calendario_local_nao_utc(
    metrics_client, admin_headers, db_session, local_tz
):
    """Regressão do achado de 2026-10-04: um evento às 22h locais de ontem
    é 01h UTC de hoje; bucketar/filtrar em UTC o fazia aparecer em 'Hoje'."""
    agora_local = datetime.now(local_tz)
    ontem_22h_local = (agora_local - timedelta(days=1)).replace(
        hour=22, minute=0, second=0, microsecond=0
    )
    await _evento(db_session, criado_em=ontem_22h_local.astimezone(UTC), custo_usd=0.009)

    res = metrics_client.get("/api/admin/metrics/ai-usage?period=today", headers=admin_headers)
    data = res.json()
    assert data["totais"]["chamadas"] == 0

    res_7d = metrics_client.get("/api/admin/metrics/ai-usage?period=7d", headers=admin_headers)
    data_7d = res_7d.json()
    assert data_7d["totais"]["chamadas"] == 1
    assert [d["data"] for d in data_7d["diario"]] == [
        ontem_22h_local.strftime("%Y-%m-%d")
    ]


@pytest.mark.asyncio
async def test_ai_usage_diario_ordenado_do_mais_recente_e_com_chats_encerrados(
    metrics_client, admin_headers, db_session, local_tz
):
    agora_local = datetime.now(local_tz)
    anteontem_local = (agora_local - timedelta(days=2)).replace(hour=12, minute=0)

    await _evento(db_session, criado_em=agora_local.astimezone(UTC), custo_usd=0.002)
    await _evento(db_session, criado_em=anteontem_local.astimezone(UTC), custo_usd=0.001)

    conversa = Conversa(
        id="conv-ai-usage-1",
        status="encerrada",
        encerrada_em=agora_local.astimezone(UTC),
        motivo_encerramento="manual_usuario",
    )
    db_session.add(conversa)
    aberta = Conversa(id="conv-ai-usage-2", status="aberta")
    db_session.add(aberta)
    await db_session.commit()

    res = metrics_client.get("/api/admin/metrics/ai-usage?period=7d", headers=admin_headers)
    data = res.json()

    datas = [d["data"] for d in data["diario"]]
    assert datas == sorted(datas, reverse=True)
    assert datas[0] == agora_local.strftime("%Y-%m-%d")

    # Conversa aberta não conta: `chats_encerrados` é literalmente o que a
    # métrica mede.
    assert data["atendimento"]["chats_encerrados"] == 1
    assert data["diario"][0]["chats_encerrados"] == 1


@pytest.mark.asyncio
async def test_endpoint_antigo_de_tokens_e_custos_nao_existe_mais(metrics_client, admin_headers):
    res = metrics_client.get(
        "/api/admin/metrics/tokens-and-costs?period=7d", headers=admin_headers
    )
    assert res.status_code == 404
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_admin_metrics_ai_usage.py -v`
Expected: a maioria FAIL com `404` (o endpoint `ai-usage` não existe), e `test_endpoint_antigo_...` FAIL porque o antigo ainda responde `200`.

- [ ] **Step 3: Reescreva `app/api/admin_metrics.py`**

Substitua o conteúdo inteiro do arquivo por:

```python
"""Endpoint administrativo de uso de IA, estratificado por origem ×
ambiente × modelo, sobre o ledger unificado `ai_usage_events` (item E, ver
docs/superpowers/specs/2026-10-08-ledger-uso-ia-item-e-painel-design.md).

Substituiu `GET /api/admin/metrics/tokens-and-costs`, que lia dois esquemas
diferentes (`ConversaMensagem.metricas` e `IngestionCostEvent`) e inferia
"isto é visão?" por heurística de nome de modelo. A dimensão que faltava
(`origem`) e a separação interno/externo agora são fatos gravados pelo
ledger, então a heurística foi removida — não portada.
"""

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import verificar_admin_por_token
from app.api.rag_dependencies import get_db_session
from app.config import get_settings
from app.db.models import AiUsageEvent, Conversa
from app.services.ai_usage_report import (
    AiUsageReport,
    EventoDiario,
    LinhaAgregada,
    montar_relatorio,
)

logger = logging.getLogger("assistente.admin_metrics")

router = APIRouter(prefix="/api/admin/metrics", tags=["Admin Metricas"])

try:
    from app.api.admin_auth import require_admin
except ImportError:

    async def require_admin(
        session: AsyncSession = Depends(get_db_session),
        authorization: Annotated[str | None, Header()] = None,
        x_auth_token: Annotated[str | None, Header(alias="X-Auth-Token")] = None,
        token_param: Annotated[str | None, Query(alias="token")] = None,
    ) -> None:
        token: str | None = None
        if authorization:
            parts = authorization.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token = parts[1]
            elif len(parts) == 1:
                token = parts[0]
        elif x_auth_token:
            token = x_auth_token
        elif token_param:
            token = token_param

        if not token or not await verificar_admin_por_token(session, token):
            raise HTTPException(
                status_code=403,
                detail="Acesso restrito a administradores autenticados.",
            )


def _resolver_janela(
    period: str,
    start_date: str | None,
    end_date: str | None,
    local_tz: ZoneInfo,
) -> tuple[datetime | None, datetime | None]:
    """Converte o filtro do painel em limites UTC.

    "Hoje"/`start_date`/`end_date` são conceitos de calendário LOCAL do
    administrador, não UTC — bucketar em UTC fazia o filtro cortar o dia às
    21h (horário de Brasília) em vez da meia-noite local (achado da revisão
    de 2026-10-04). Reaproveita o fuso já configurado para o Agendamento
    (`agendamento_timezone`) em vez de introduzir uma config nova.

    Data mal formada é `400`, não um fallback silencioso para o período
    default — também achado de 2026-10-04: o administrador via um filtro
    aplicado que na verdade era outro, bem diferente.
    """
    cutoff_start: datetime | None = None
    cutoff_end: datetime | None = None

    if start_date:
        try:
            d = date.fromisoformat(start_date)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"start_date inválida ({start_date!r}); use o formato YYYY-MM-DD.",
            ) from exc
        cutoff_start = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=local_tz).astimezone(UTC)

    if end_date:
        try:
            d = date.fromisoformat(end_date)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"end_date inválida ({end_date!r}); use o formato YYYY-MM-DD.",
            ) from exc
        cutoff_end = datetime(
            d.year, d.month, d.day, 23, 59, 59, 999999, tzinfo=local_tz
        ).astimezone(UTC)

    if cutoff_start is None and cutoff_end is None:
        now_local = datetime.now(local_tz)
        if period == "today":
            cutoff_start = datetime(
                now_local.year, now_local.month, now_local.day, 0, 0, 0, tzinfo=local_tz
            ).astimezone(UTC)
        elif period == "7d":
            cutoff_start = now_local.astimezone(UTC) - timedelta(days=7)
        elif period == "30d":
            cutoff_start = now_local.astimezone(UTC) - timedelta(days=30)
        # period == "all" (ou desconhecido): sem corte.

    return cutoff_start, cutoff_end


def _dia_local(dt: datetime, local_tz: ZoneInfo) -> str:
    dt = dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    return dt.astimezone(local_tz).strftime("%Y-%m-%d")


@router.get("/ai-usage", response_model=AiUsageReport)
async def get_ai_usage_metrics(
    request: Request,
    period: str = Query("7d", description="Período: 'today', '7d', '30d' ou 'all'"),
    start_date: str | None = Query(None, description="Data inicial ISO YYYY-MM-DD"),
    end_date: str | None = Query(None, description="Data final ISO YYYY-MM-DD"),
    _: None = Depends(require_admin),
) -> AiUsageReport:
    """Uso de IA do período, estratificado por origem × ambiente × modelo ×
    operação, mais o recorte diário e o volume de chats encerrados."""
    session_factory = getattr(request.app.state, "db_sessionmaker", None)
    if not session_factory:
        raise HTTPException(status_code=503, detail="Banco de dados não configurado.")

    local_tz = ZoneInfo(get_settings().agendamento_timezone)
    cutoff_start, cutoff_end = _resolver_janela(period, start_date, end_date, local_tz)

    # Q1 — agregação cross-dimensional no banco. `SUM()` devolve NULL
    # quando TODOS os valores do grupo são NULL, que é exatamente a
    # semântica desejada ("não medido"); nenhum COALESCE aqui, de
    # propósito. `COUNT(coluna)` ignora NULLs, então
    # `COUNT(*) - COUNT(custo_usd)` é a contagem de chamadas sem custo
    # medido.
    stmt_agregado = select(
        AiUsageEvent.origem,
        AiUsageEvent.ambiente,
        AiUsageEvent.modelo,
        AiUsageEvent.operacao,
        func.count().label("chamadas"),
        func.sum(AiUsageEvent.tokens_entrada).label("tokens_entrada"),
        func.sum(AiUsageEvent.tokens_saida).label("tokens_saida"),
        func.sum(AiUsageEvent.custo_usd).label("custo_usd"),
        (func.count() - func.count(AiUsageEvent.custo_usd)).label("sem_custo"),
    ).group_by(
        AiUsageEvent.origem,
        AiUsageEvent.ambiente,
        AiUsageEvent.modelo,
        AiUsageEvent.operacao,
    )

    # Q2 — recorte diário. O bucket é o dia do calendário LOCAL do
    # administrador e não existe expressão portável entre SQLite (testes) e
    # PostgreSQL (produção) para truncar um timestamp num fuso arbitrário
    # (`date_trunc(... AT TIME ZONE ...)` é PostgreSQL, `date(x, '-3
    # hours')` é SQLite), e `CAST(criado_em AS DATE)` reintroduziria o bug
    # do dia cortado às 21h. Por isso só estas cinco colunas vêm do banco e
    # o agrupamento por dia é feito em Python — escolha deliberada, não
    # descuido (ver spec §3.1).
    stmt_eventos = select(
        AiUsageEvent.criado_em,
        AiUsageEvent.origem,
        AiUsageEvent.tokens_entrada,
        AiUsageEvent.tokens_saida,
        AiUsageEvent.custo_usd,
    )

    # Chats encerrados: KPI de volume de atendimento, não de uso de IA —
    # continua exigindo `status == "encerrada"` e bucketado por
    # `encerrada_em`, porque é literalmente isso que a métrica mede.
    stmt_closed = (
        select(Conversa.id, Conversa.encerrada_em)
        .where(Conversa.status == "encerrada")
        .where(Conversa.encerrada_em.is_not(None))
    )

    if cutoff_start is not None:
        stmt_agregado = stmt_agregado.where(AiUsageEvent.criado_em >= cutoff_start)
        stmt_eventos = stmt_eventos.where(AiUsageEvent.criado_em >= cutoff_start)
        stmt_closed = stmt_closed.where(Conversa.encerrada_em >= cutoff_start)
    if cutoff_end is not None:
        stmt_agregado = stmt_agregado.where(AiUsageEvent.criado_em <= cutoff_end)
        stmt_eventos = stmt_eventos.where(AiUsageEvent.criado_em <= cutoff_end)
        stmt_closed = stmt_closed.where(Conversa.encerrada_em <= cutoff_end)

    try:
        async with session_factory() as session:
            linhas_res = await session.execute(stmt_agregado)
            eventos_res = await session.execute(stmt_eventos)
            closed_res = await session.execute(stmt_closed)

            linhas = [
                LinhaAgregada(
                    origem=row.origem,
                    ambiente=row.ambiente,
                    modelo=row.modelo,
                    operacao=row.operacao,
                    chamadas=row.chamadas,
                    tokens_entrada=row.tokens_entrada,
                    tokens_saida=row.tokens_saida,
                    custo_usd=row.custo_usd,
                    chamadas_sem_custo_medido=row.sem_custo,
                )
                for row in linhas_res.all()
            ]
            eventos_diarios = [
                EventoDiario(
                    data=_dia_local(row.criado_em, local_tz),
                    origem=row.origem,
                    tokens_entrada=row.tokens_entrada,
                    tokens_saida=row.tokens_saida,
                    custo_usd=row.custo_usd,
                )
                for row in eventos_res.all()
            ]
            closed_rows = closed_res.all()
    except Exception as exc:
        logger.error("Erro ao consultar métricas de uso de IA no banco: %s", exc)
        raise HTTPException(status_code=503, detail="Erro ao consultar métricas.") from exc

    chats_por_dia: dict[str, set[str]] = {}
    todos_chats: set[str] = set()
    for conv_id, encerrada_em in closed_rows:
        todos_chats.add(conv_id)
        chats_por_dia.setdefault(_dia_local(encerrada_em, local_tz), set()).add(conv_id)

    return montar_relatorio(
        period=period,
        linhas=linhas,
        eventos_diarios=eventos_diarios,
        chats_encerrados_total=len(todos_chats),
        chats_encerrados_por_dia={dia: len(ids) for dia, ids in chats_por_dia.items()},
    )
```

- [ ] **Step 4: Remova os testes do endpoint antigo**

```bash
cd /home/augusto/Projetos/TCC
git rm backend/tests/test_admin_metrics_api.py backend/tests/test_admin_metrics_vision.py
```

Esses dois arquivos testavam exclusivamente `/tokens-and-costs`, incluindo a heurística de visão. Os casos que continuam valendo — autenticação, `400` em data inválida, calendário local, separação de visão interna × externa — foram portados para `test_admin_metrics_ai_usage.py` no Step 1; nada de cobertura real é perdido.

- [ ] **Step 5: Remova o teste do endpoint antigo em `test_ingestion_cost_metrics.py`**

Apague de `backend/tests/test_ingestion_cost_metrics.py` a função `test_admin_metrics_aggregates_ingestion_and_chat_costs` (e a fixture `test_client` junto com a classe `_SingleSessionMaker`, se nada mais no arquivo as usar) — ela exercita o endpoint que deixou de existir. **Não** apague `test_crawler_records_ingestion_cost_event` ainda; a Task 3 cuida dele.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_admin_metrics_ai_usage.py tests/test_ai_usage_report.py tests/test_ingestion_cost_metrics.py -v`
Expected: PASS

Run: `cd backend && pytest -q`
Expected: toda a suíte verde. Se algum teste de `app.main`/rotas falhar por referenciar `/tokens-and-costs`, ajuste-o para o endpoint novo.

- [ ] **Step 7: Commit**

```bash
git add -A backend
git commit -m "feat(telemetria): endpoint GET /api/admin/metrics/ai-usage sobre o ledger (item E, Task 2)

Duas consultas: um GROUP BY origem/ambiente/modelo/operacao que alimenta
cinco visoes por roll-up, e uma selecao estreita por evento para o recorte
diario (bucket em Python porque nao ha expressao SQL portavel entre SQLite
e PostgreSQL para truncar num fuso arbitrario).

Remove /tokens-and-costs, MetricSummary, DailyMetric e a heuristica de nome
de modelo para inferir visao. Os casos de regressao dos testes antigos
(auth, 400 em data invalida, calendario local, visao interna x externa)
foram portados para test_admin_metrics_ai_usage.py.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Migrar o classificador do crawler para o ledger

Último ponto de uso de IA fora do ledger. Sem isto, a "fonte única" do painel nasce sem o custo da classificação de páginas crawleadas.

**Files:**
- Modify: `backend/src/app/rag/crawler_classifier.py:60-82`
- Modify: `backend/src/app/api/crawler.py:136-138`
- Modify: `backend/src/app/db/models.py` (comentário marcando `IngestionCostEvent` como tabela morta)
- Test: `backend/tests/test_rag_crawler_classifier.py`
- Delete: `backend/tests/test_ingestion_cost_metrics.py`

**Interfaces:**
- Consumes: `app.services.ai_usage.registrar_uso_ia` (item A), `app.background_tasks.spawn_background_task`.
- Produces: eventos de ledger com `origem="admin"`, `operacao="classificacao_crawler"`. `classify_page` mantém a assinatura `(llm_client, text, source_identifier=None, session=None)`.

- [ ] **Step 1: Write the failing test**

Adicione ao fim de `backend/tests/test_rag_crawler_classifier.py`:

```python
@pytest.mark.asyncio
async def test_classify_page_registra_uso_no_ledger(monkeypatch):
    """O classificador do crawler foi o último ponto de uso de IA a entrar
    no ledger unificado (item E) — antes disso escrevia em
    `IngestionCostEvent`, que o painel deixou de ler."""
    registros: list[dict] = []

    async def _fake_registrar(**kwargs):
        registros.append(kwargs)
        return None

    monkeypatch.setattr("app.rag.crawler_classifier.registrar_uso_ia", _fake_registrar)

    llm = _MockLLM(
        '{"domain": "vendas", "confidence": 0.9}',
        prompt_tokens=500,
        completion_tokens=20,
        estimated_cost_usd=0.0008,
        model_name="gpt-x",
    )

    resultado = await classify_page(llm, "promoções", source_identifier="https://ex.com/p")

    assert resultado.domain == "vendas"
    assert len(registros) == 1
    assert registros[0]["origem"] == "admin"
    assert registros[0]["operacao"] == "classificacao_crawler"
    assert registros[0]["ambiente"] == "externo"
    assert registros[0]["modelo"] == "gpt-x"
    assert registros[0]["tokens_entrada"] == 500
    assert registros[0]["tokens_saida"] == 20
    assert registros[0]["custo_usd"] == 0.0008
    assert registros[0]["referencia_id"] == "https://ex.com/p"


@pytest.mark.asyncio
async def test_classify_page_sem_uso_reportado_registra_none_nao_zero(monkeypatch):
    """`None` = não capturado; nunca um zero fabricado (semântica do
    ledger, itens A/B/D)."""
    registros: list[dict] = []

    async def _fake_registrar(**kwargs):
        registros.append(kwargs)
        return None

    monkeypatch.setattr("app.rag.crawler_classifier.registrar_uso_ia", _fake_registrar)

    llm = _MockLLM('{"domain": "suporte", "confidence": 0.5}')
    await classify_page(llm, "texto")

    assert len(registros) == 1
    assert registros[0]["tokens_entrada"] is None
    assert registros[0]["custo_usd"] is None


@pytest.mark.asyncio
async def test_classify_page_sobrevive_a_falha_de_telemetria(monkeypatch):
    """Telemetria não derruba a classificação que ela registra."""

    async def _explode(**kwargs):
        raise RuntimeError("banco fora")

    monkeypatch.setattr("app.rag.crawler_classifier.registrar_uso_ia", _explode)

    llm = _MockLLM('{"domain": "vendas", "confidence": 0.8}')
    resultado = await classify_page(llm, "texto")

    assert resultado.domain == "vendas"
    assert resultado.confidence == 0.8
```

No topo do arquivo, garanta os imports e um mock de LLM que carregue os campos de uso. Se `_MockLLM` ainda não existir com esses atributos, use:

```python
import pytest

from app.rag.crawler_classifier import classify_page


class _MockLLM:
    def __init__(
        self,
        text: str,
        prompt_tokens=None,
        completion_tokens=None,
        estimated_cost_usd=None,
        model_name=None,
    ) -> None:
        self.text = text
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.estimated_cost_usd = estimated_cost_usd
        self.model_name = model_name
        self.model = model_name

    async def generate(self, prompt: str):
        return self
```

Ajuste os testes já existentes no arquivo para usar esse mock se eles tiverem um equivalente com outro nome — não duplique dois mocks de LLM no mesmo arquivo.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_rag_crawler_classifier.py -v`
Expected: FAIL — `monkeypatch.setattr` não encontra `registrar_uso_ia` em `app.rag.crawler_classifier` (`AttributeError`).

- [ ] **Step 3: Migre `classify_page`**

Em `backend/src/app/rag/crawler_classifier.py`, adicione aos imports do topo:

```python
from app.background_tasks import spawn_background_task
from app.services.ai_usage import registrar_uso_ia
```

E substitua o bloco de telemetria (hoje `# Telemetria e auditoria de custo do crawler` até o `except Exception: pass`) por:

```python
    # Telemetria de uso de IA no ledger unificado (item E, 2026-10-08).
    # Antes escrevia em `IngestionCostEvent` via `record_ingestion_cost`;
    # era o último ponto de uso de IA fora do ledger, e o painel
    # `/admin/metricas` passou a ler só `ai_usage_events`.
    # `None` = não capturado, nunca um zero fabricado (semântica dos itens
    # A/B/D) — por isso `getattr(..., None)` sem `or 0`.
    # MVP: `ambiente="externo"` fixo porque `app.api.crawler` sempre passa
    # `app.state.external_client`; se o crawler passar a aceitar modelo
    # local, isto precisa virar parâmetro.
    spawn_background_task(
        registrar_uso_ia(
            origem="admin",
            ambiente="externo",
            modelo=getattr(response, "model_name", None)
            or getattr(llm_client, "model", None)
            or "desconhecido",
            operacao="classificacao_crawler",
            tokens_entrada=getattr(response, "prompt_tokens", None),
            tokens_saida=getattr(response, "completion_tokens", None),
            custo_usd=getattr(response, "estimated_cost_usd", None),
            referencia_id=source_identifier,
            session=session,
            session_factory=None,
            commit=False,
        )
    )
```

Note que o `if (p_tok + c_tok > 0) or (c_tot > 0)` desaparece: o registro agora é incondicional, porque "chamou o LLM e não mediu nada" é um fato que o painel precisa mostrar (`chamadas_sem_custo_medido`), não um evento a esconder.

- [ ] **Step 4: Passe a URL da página como referência**

Em `backend/src/app/api/crawler.py:136`, troque:

```python
                    classification = await classify_page(
                        request.app.state.external_client, page.text
                    )
```

por:

```python
                    classification = await classify_page(
                        request.app.state.external_client,
                        page.text,
                        source_identifier=page.url,
                    )
```

O parâmetro já existia na assinatura e nunca era passado pelo caller, então o evento de ledger nascia sem referência; uma linha, e a linha do painel fica rastreável até a página classificada.

- [ ] **Step 5: Marque `IngestionCostEvent` como tabela morta**

Em `backend/src/app/db/models.py`, na docstring/comentário da classe `IngestionCostEvent` (linha ~525), adicione:

```python
    # MORTA desde 2026-10-08 (item E do ledger de uso de IA): nenhum
    # caminho de produção escreve nem lê esta tabela — a extração de
    # catálogo por visão migrou para `ai_usage_events` no item D e o
    # classificador do crawler no item E. A tabela, o modelo e a migração
    # permanecem no banco por decisão do dono do projeto (não vale uma
    # migração destrutiva); os dados históricos não foram migrados.
```

- [ ] **Step 6: Remova `test_ingestion_cost_metrics.py`**

```bash
cd /home/augusto/Projetos/TCC
git rm backend/tests/test_ingestion_cost_metrics.py
```

Depois da Task 2 (que removeu o teste do endpoint) e do Step 1 desta task (que recria a cobertura do crawler em cima do ledger), o arquivo não cobre mais nenhum caminho vivo. Se tiver sobrado ali algum teste que **não** seja do endpoint antigo nem do crawler, mova-o para o arquivo temático correspondente antes de apagar.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_rag_crawler_classifier.py -v`
Expected: PASS

Run: `cd backend && pytest -q`
Expected: toda a suíte verde.

- [ ] **Step 8: Commit**

```bash
git add -A backend
git commit -m "feat(telemetria): migra classificador do crawler para o ledger (item E, Task 3)

Era o ultimo ponto de uso de IA escrevendo em IngestionCostEvent; com o
painel lendo so ai_usage_events, o custo da classificacao de paginas
crawleadas desapareceria. Registro agora e incondicional (chamou o LLM e
nao mediu nada e um fato a mostrar, nao a esconder) e a URL da pagina vai
como referencia_id. IngestionCostEvent marcada como tabela morta.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Cliente de API e helpers de formatação no frontend

**Files:**
- Modify: `frontend/lib/api/metrics.ts` (reescrita: tipos novos + `fetchAiUsageMetrics`)
- Create: `frontend/lib/format/metricas.ts`
- Test: `frontend/tests/lib/formatMetricas.test.ts` (criar)

**Interfaces:**
- Consumes: payload de `AiUsageReport` (Task 2).
- Produces:
  - `frontend/lib/api/metrics.ts`: `BlocoMetricas`, `MetricasPorOrigem`, `MetricasPorAmbiente`, `MetricasPorModelo`, `MetricasPorOperacao`, `DiaUsoIa`, `AiUsageReport`, `GetMetricsParams`, `fetchAiUsageMetrics(token: string, params?: GetMetricsParams): Promise<AiUsageReport>`.
  - `frontend/lib/format/metricas.ts`: `formatarCusto(valor: number | null | undefined): string`, `formatarTokens(valor: number | null | undefined): string`, `NAO_MEDIDO: "—"`, `TITULO_NAO_MEDIDO: string`.

- [ ] **Step 1: Write the failing test**

Crie `frontend/tests/lib/formatMetricas.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import {
  formatarCusto,
  formatarTokens,
  NAO_MEDIDO,
} from "@/lib/format/metricas";

describe("formatarCusto", () => {
  it("mostra zero conhecido como valor monetário, não como traço", () => {
    // 0.0 no ledger significa "grátis" (CLIP, modelo local) — é um número
    // medido, não ausência de medição.
    expect(formatarCusto(0)).toBe("$0.0000");
  });

  it("mostra não-medido como traço, não como zero", () => {
    expect(formatarCusto(null)).toBe(NAO_MEDIDO);
    expect(formatarCusto(undefined)).toBe(NAO_MEDIDO);
  });

  it("formata custo com 4 casas", () => {
    expect(formatarCusto(0.00254)).toBe("$0.0025");
    expect(formatarCusto(1.5)).toBe("$1.5000");
  });
});

describe("formatarTokens", () => {
  it("distingue zero medido de não-medido", () => {
    expect(formatarTokens(0)).toBe("0");
    expect(formatarTokens(null)).toBe(NAO_MEDIDO);
  });

  it("usa separador de milhar pt-BR", () => {
    expect(formatarTokens(1234567)).toBe((1234567).toLocaleString("pt-BR"));
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test -- formatMetricas`
Expected: FAIL — módulo `@/lib/format/metricas` não encontrado.

- [ ] **Step 3: Crie os helpers**

Crie `frontend/lib/format/metricas.ts`:

```ts
/**
 * Formatação do painel de uso de IA (`/admin/metricas`).
 *
 * A distinção que importa: no ledger `null` significa "não medido" e `0`
 * significa "zero conhecido" (CLIP e modelo local são genuinamente
 * grátis). Um `—` e um `$0.0000` querem dizer coisas diferentes, e o
 * painel não os confunde — é a razão de existir do ledger chegando aos
 * olhos do administrador.
 */

export const NAO_MEDIDO = "—";
export const TITULO_NAO_MEDIDO = "Não medido — a chamada aconteceu, mas o custo/tokens não foram capturados";

export function formatarCusto(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return NAO_MEDIDO;
  return `$${valor.toFixed(4)}`;
}

export function formatarTokens(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return NAO_MEDIDO;
  return valor.toLocaleString("pt-BR");
}
```

- [ ] **Step 4: Reescreva o cliente de API**

Substitua todo o conteúdo de `frontend/lib/api/metrics.ts` por:

```ts
import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";

/**
 * Contrato de `GET /api/admin/metrics/ai-usage` (item E do ledger de uso
 * de IA). Substituiu `/tokens-and-costs`.
 *
 * `tokens_entrada`/`tokens_saida`/`custo_usd` são `number | null`: `null`
 * é "não medido", `0` é "grátis". Nunca normalize `null` para `0` aqui —
 * use os helpers de `@/lib/format/metricas` na renderização.
 */

export interface BlocoMetricas {
  chamadas: number;
  tokens_entrada: number | null;
  tokens_saida: number | null;
  custo_usd: number | null;
  chamadas_sem_custo_medido: number;
}

export interface MetricasPorOrigem extends BlocoMetricas {
  origem: string;
}

export interface MetricasPorAmbiente extends BlocoMetricas {
  ambiente: string;
}

export interface MetricasPorModelo extends BlocoMetricas {
  modelo: string;
  ambiente: string;
}

export interface MetricasPorOperacao extends BlocoMetricas {
  operacao: string;
  origem: string;
  ambiente: string;
}

export interface DiaUsoIa {
  data: string;
  chats_encerrados: number;
  totais: BlocoMetricas;
  por_origem: MetricasPorOrigem[];
}

export interface AiUsageReport {
  period: string;
  atendimento: { chats_encerrados: number };
  totais: BlocoMetricas;
  por_origem: MetricasPorOrigem[];
  por_ambiente: MetricasPorAmbiente[];
  por_modelo: MetricasPorModelo[];
  por_operacao: MetricasPorOperacao[];
  diario: DiaUsoIa[];
}

export interface GetMetricsParams {
  period?: "today" | "7d" | "30d" | "all" | "custom" | string;
  startDate?: string;
  endDate?: string;
}

export async function fetchAiUsageMetrics(
  token: string,
  params: GetMetricsParams = {}
): Promise<AiUsageReport> {
  const baseUrl = getApiBaseUrl();
  const query = new URLSearchParams();
  if (params.period) query.set("period", params.period);
  if (params.startDate) query.set("start_date", params.startDate);
  if (params.endDate) query.set("end_date", params.endDate);
  query.set("_t", Date.now().toString());

  const qs = query.toString();
  const url = `${baseUrl}/api/admin/metrics/ai-usage${qs ? `?${qs}` : ""}`;

  const response = await fetch(url, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-cache",
      Pragma: "no-cache",
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Falha ao obter métricas (${response.status})`);
  }

  return response.json();
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && npm test -- formatMetricas`
Expected: PASS

A página e seu teste ainda importam `fetchTokenCostMetrics`/`TokenCostMetricsResponse` e vão quebrar o typecheck neste ponto — é esperado; a Task 5 os reescreve. Não adicione um alias de compatibilidade para "não quebrar": o endpoint antigo não existe mais.

- [ ] **Step 6: Commit**

```bash
git add frontend/lib/api/metrics.ts frontend/lib/format/metricas.ts frontend/tests/lib/formatMetricas.test.ts
git commit -m "feat(metricas): cliente e helpers do painel de uso de IA (item E, Task 4)

Tipos de GET /api/admin/metrics/ai-usage com tokens/custo como number|null
e helpers que renderizam null como traco e 0 como \$0.0000 — a distincao
nao-medido x gratis chegando aos olhos do administrador.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Reconstrução da página `/admin/metricas`

**Files:**
- Create: `frontend/components/admin/metricas/CardMetrica.tsx`
- Create: `frontend/components/admin/metricas/SecaoPorOrigem.tsx`
- Create: `frontend/components/admin/metricas/SecaoPorAmbiente.tsx`
- Create: `frontend/components/admin/metricas/TabelaPorModelo.tsx`
- Create: `frontend/components/admin/metricas/TabelaPorOperacao.tsx`
- Create: `frontend/components/admin/metricas/TabelaDiaria.tsx`
- Modify: `frontend/app/admin/metricas/page.tsx` (preserva o shell; troca as seções de dados)
- Test: `frontend/tests/components/AdminMetricasPage.test.tsx` (reescrever)

**Interfaces:**
- Consumes: `fetchAiUsageMetrics`, `AiUsageReport` e os tipos de bloco (Task 4); `formatarCusto`, `formatarTokens`, `NAO_MEDIDO`, `TITULO_NAO_MEDIDO` (Task 4).
- Produces: a página renderizada; componentes com props explícitas (`bloco: BlocoMetricas`, `linhas: MetricasPorModelo[]`, etc.).

**O que PRESERVAR da página atual** (não reescrever do zero): o gate de acesso (`Acesso Restrito ao Administrador`), o cabeçalho com título e botão de atualizar (`RefreshIcon`), o seletor de período, o `<input type="date">` com `handleDateChange`, o `ToastStack`/`useToast`, o `requestIdRef` que descarta respostas obsoletas (achado da revisão de 2026-10-04 — remover isso reintroduz o bug de uma resposta antiga sobrescrever a tela) e o `useEffect` de carregamento. Só o que vem **abaixo** dos filtros muda.

**O que REMOVER:** `preencherLinhasDetalhamento` (preenchia dias faltantes com um objeto de `DailyMetric` zerado — o backend agora devolve o dia sempre que houver uso de IA ou chat encerrado, e um dia inteiramente vazio não precisa de linha fabricada com zeros que mentem sobre `null`), os 4 cards antigos, a faixa consolidada e a tabela de detalhamento de 6 colunas.

- [ ] **Step 1: Write the failing test**

Substitua o conteúdo de `frontend/tests/components/AdminMetricasPage.test.tsx` por:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import AdminMetricasPage from "@/app/admin/metricas/page";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import * as metricsApi from "@/lib/api/metrics";

function bloco(over: Partial<metricsApi.BlocoMetricas> = {}): metricsApi.BlocoMetricas {
  return {
    chamadas: 1,
    tokens_entrada: 100,
    tokens_saida: 10,
    custo_usd: 0.001,
    chamadas_sem_custo_medido: 0,
    ...over,
  };
}

const mockResponse: metricsApi.AiUsageReport = {
  period: "7d",
  atendimento: { chats_encerrados: 12 },
  totais: bloco({ chamadas: 7, custo_usd: 0.0065, tokens_entrada: 2400, tokens_saida: 190, chamadas_sem_custo_medido: 1 }),
  por_origem: [
    { origem: "chat", ...bloco({ chamadas: 4, custo_usd: 0.0025 }) },
    { origem: "b2b", ...bloco({ chamadas: 1, custo_usd: 0.0 }) },
    { origem: "admin", ...bloco({ chamadas: 2, custo_usd: 0.004 }) },
  ],
  por_ambiente: [
    { ambiente: "interno", ...bloco({ chamadas: 3, custo_usd: 0.0, tokens_entrada: null, tokens_saida: null }) },
    { ambiente: "externo", ...bloco({ chamadas: 4, custo_usd: 0.0065 }) },
  ],
  por_modelo: [
    { modelo: "gemma-vision", ambiente: "externo", ...bloco({ chamadas: 2, custo_usd: 0.0065 }) },
    { modelo: "clip", ambiente: "interno", ...bloco({ chamadas: 2, custo_usd: 0.0, tokens_entrada: null, tokens_saida: null }) },
    { modelo: "gpt-desconhecido", ambiente: "externo", ...bloco({ chamadas: 1, custo_usd: null, chamadas_sem_custo_medido: 1 }) },
  ],
  por_operacao: [
    { operacao: "identificacao_imagem_clip", origem: "chat", ambiente: "interno", ...bloco({ chamadas: 2, custo_usd: 0.0 }) },
    { operacao: "identificacao_imagem_visao_externa", origem: "chat", ambiente: "externo", ...bloco({ chamadas: 1, custo_usd: 0.0025 }) },
    { operacao: "classificacao_crawler", origem: "admin", ambiente: "externo", ...bloco({ chamadas: 2, custo_usd: 0.004 }) },
  ],
  diario: [
    {
      data: "2026-10-08",
      chats_encerrados: 7,
      totais: bloco({ chamadas: 5, custo_usd: 0.005 }),
      por_origem: [{ origem: "chat", ...bloco({ chamadas: 5, custo_usd: 0.005 }) }],
    },
    {
      data: "2026-10-07",
      chats_encerrados: 5,
      totais: bloco({ chamadas: 2, custo_usd: 0.0015 }),
      por_origem: [{ origem: "admin", ...bloco({ chamadas: 2, custo_usd: 0.0015 }) }],
    },
  ],
};

function logarComoAdmin() {
  useAuthStore.setState({
    user: { id: 1, nome: "Admin Teste", email: "admin@example.com", perfil: "Admin" },
    token: "mock-token",
  });
}

describe("AdminMetricasPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({ user: null, token: null });
  });

  it("renderiza aviso de acesso restrito se o usuário não for Administrador", () => {
    useAuthStore.setState({
      user: { id: 2, nome: "João Cliente", email: "joao@example.com", perfil: "Cliente" },
      token: "mock-token",
    });

    render(<AdminMetricasPage />);
    expect(screen.getByText("Acesso Restrito ao Administrador")).toBeInTheDocument();
  });

  it("renderiza as cinco seções do painel de uso de IA", async () => {
    logarComoAdmin();
    vi.spyOn(metricsApi, "fetchAiUsageMetrics").mockResolvedValue(mockResponse);

    render(<AdminMetricasPage />);

    await waitFor(() => {
      expect(screen.getByText(/Por Origem/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/Por Ambiente/i)).toBeInTheDocument();
    expect(screen.getByText(/Por Modelo/i)).toBeInTheDocument();
    expect(screen.getByText(/Por Operação/i)).toBeInTheDocument();
    expect(screen.getByText(/Detalhamento Diário/i)).toBeInTheDocument();
  });

  it("mostra custo não medido como traço e grátis como $0.0000", async () => {
    logarComoAdmin();
    vi.spyOn(metricsApi, "fetchAiUsageMetrics").mockResolvedValue(mockResponse);

    render(<AdminMetricasPage />);

    // `clip` (interno) tem custo 0.0 medido => $0.0000
    await waitFor(() => {
      expect(screen.getByTestId("custo-modelo-clip-interno")).toHaveTextContent("$0.0000");
    });
    // `gpt-desconhecido` tem custo null => traço, não "$0.0000"
    expect(screen.getByTestId("custo-modelo-gpt-desconhecido-externo")).toHaveTextContent("—");
  });

  it("mostra tokens não medidos como traço", async () => {
    logarComoAdmin();
    vi.spyOn(metricsApi, "fetchAiUsageMetrics").mockResolvedValue(mockResponse);

    render(<AdminMetricasPage />);

    await waitFor(() => {
      expect(screen.getByTestId("tokens-entrada-ambiente-interno")).toHaveTextContent("—");
    });
  });

  it("exibe as origens, operações e o volume de chats encerrados", async () => {
    logarComoAdmin();
    vi.spyOn(metricsApi, "fetchAiUsageMetrics").mockResolvedValue(mockResponse);

    render(<AdminMetricasPage />);

    await waitFor(() => {
      expect(screen.getByTestId("custo-origem-chat")).toHaveTextContent("$0.0025");
    });
    expect(screen.getByTestId("custo-origem-admin")).toHaveTextContent("$0.0040");
    expect(screen.getByText("classificacao_crawler")).toBeInTheDocument();
    expect(screen.getByTestId("chats-encerrados")).toHaveTextContent("12");
  });

  it("sinaliza quantas chamadas ficaram sem custo medido", async () => {
    logarComoAdmin();
    vi.spyOn(metricsApi, "fetchAiUsageMetrics").mockResolvedValue(mockResponse);

    render(<AdminMetricasPage />);

    await waitFor(() => {
      expect(screen.getByTestId("sem-custo-medido")).toHaveTextContent("1");
    });
  });

  it("mostra mensagem de erro quando a requisição falha", async () => {
    logarComoAdmin();
    vi.spyOn(metricsApi, "fetchAiUsageMetrics").mockRejectedValue(new Error("Falha ao obter métricas (503)"));

    render(<AdminMetricasPage />);

    await waitFor(() => {
      expect(screen.getByText(/Falha ao obter métricas/i)).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test -- AdminMetricasPage`
Expected: FAIL — a página ainda chama `fetchTokenCostMetrics` e não tem as seções novas.

- [ ] **Step 3: Crie o card reutilizável**

Crie `frontend/components/admin/metricas/CardMetrica.tsx`:

```tsx
import { BlocoMetricas } from "@/lib/api/metrics";
import {
  formatarCusto,
  formatarTokens,
  TITULO_NAO_MEDIDO,
} from "@/lib/format/metricas";

interface CardMetricaProps {
  titulo: string;
  subtitulo?: string;
  bloco: BlocoMetricas;
  /** Prefixo dos `data-testid` das células (ex.: "origem-chat"). */
  testIdPrefixo: string;
  destaque?: boolean;
}

export function CardMetrica({
  titulo,
  subtitulo,
  bloco,
  testIdPrefixo,
  destaque = false,
}: CardMetricaProps) {
  const custoNaoMedido = bloco.custo_usd === null;
  return (
    <div
      className={`rounded-2xl border p-4 shadow-xs ${
        destaque ? "border-blue-200 bg-blue-50/60" : "border-slate-200 bg-white"
      }`}
    >
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {titulo}
      </div>
      {subtitulo ? <div className="text-[11px] text-slate-400">{subtitulo}</div> : null}
      <div
        className="mt-2 text-2xl font-bold text-slate-900"
        data-testid={`custo-${testIdPrefixo}`}
        title={custoNaoMedido ? TITULO_NAO_MEDIDO : undefined}
      >
        {formatarCusto(bloco.custo_usd)}
      </div>
      <dl className="mt-3 space-y-1 text-xs text-slate-600">
        <div className="flex justify-between gap-2">
          <dt>Chamadas</dt>
          <dd data-testid={`chamadas-${testIdPrefixo}`} className="font-semibold">
            {bloco.chamadas.toLocaleString("pt-BR")}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Tokens entrada</dt>
          <dd data-testid={`tokens-entrada-${testIdPrefixo}`} className="font-semibold">
            {formatarTokens(bloco.tokens_entrada)}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Tokens saída</dt>
          <dd data-testid={`tokens-saida-${testIdPrefixo}`} className="font-semibold">
            {formatarTokens(bloco.tokens_saida)}
          </dd>
        </div>
        {bloco.chamadas_sem_custo_medido > 0 ? (
          <div className="flex justify-between gap-2 text-amber-700">
            <dt title={TITULO_NAO_MEDIDO}>Sem custo medido</dt>
            <dd data-testid={`sem-custo-${testIdPrefixo}`} className="font-semibold">
              {bloco.chamadas_sem_custo_medido}
            </dd>
          </div>
        ) : null}
      </dl>
    </div>
  );
}
```

- [ ] **Step 4: Crie as seções de cards**

Crie `frontend/components/admin/metricas/SecaoPorOrigem.tsx`:

```tsx
import { MetricasPorOrigem } from "@/lib/api/metrics";
import { CardMetrica } from "./CardMetrica";

const ROTULOS: Record<string, { titulo: string; subtitulo: string }> = {
  chat: { titulo: "Chat", subtitulo: "Atendimento ao cliente no site" },
  b2b: { titulo: "B2B", subtitulo: "MCP provido a parceiros" },
  admin: { titulo: "Admin", subtitulo: "Ingestão, catálogo e gráficos" },
};

export function SecaoPorOrigem({ linhas }: { linhas: MetricasPorOrigem[] }) {
  return (
    <section className="space-y-3">
      <h2 className="text-base font-bold text-slate-900">
        Por Origem{" "}
        <span className="font-normal text-slate-500">— de onde partiu a chamada de IA</span>
      </h2>
      {linhas.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum uso de IA registrado no período.</p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {linhas.map((linha) => (
            <CardMetrica
              key={linha.origem}
              titulo={ROTULOS[linha.origem]?.titulo ?? linha.origem}
              subtitulo={ROTULOS[linha.origem]?.subtitulo}
              bloco={linha}
              testIdPrefixo={`origem-${linha.origem}`}
            />
          ))}
        </div>
      )}
    </section>
  );
}
```

Crie `frontend/components/admin/metricas/SecaoPorAmbiente.tsx`:

```tsx
import { BlocoMetricas, MetricasPorAmbiente } from "@/lib/api/metrics";
import { CardMetrica } from "./CardMetrica";

const ROTULOS: Record<string, { titulo: string; subtitulo: string }> = {
  interno: { titulo: "Interno", subtitulo: "GPU local / CLIP — sem custo de API" },
  externo: { titulo: "Externo", subtitulo: "API paga (OpenRouter, visão externa)" },
};

interface Props {
  linhas: MetricasPorAmbiente[];
  totais: BlocoMetricas;
}

export function SecaoPorAmbiente({ linhas, totais }: Props) {
  return (
    <section className="space-y-3">
      <h2 className="text-base font-bold text-slate-900">
        Por Ambiente{" "}
        <span className="font-normal text-slate-500">— quanto foi grátis e quanto foi pago</span>
      </h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {linhas.map((linha) => (
          <CardMetrica
            key={linha.ambiente}
            titulo={ROTULOS[linha.ambiente]?.titulo ?? linha.ambiente}
            subtitulo={ROTULOS[linha.ambiente]?.subtitulo}
            bloco={linha}
            testIdPrefixo={`ambiente-${linha.ambiente}`}
          />
        ))}
        <CardMetrica
          titulo="Consolidado"
          subtitulo="Todas as origens e ambientes"
          bloco={totais}
          testIdPrefixo="total"
          destaque
        />
      </div>
    </section>
  );
}
```

- [ ] **Step 5: Crie as tabelas**

Crie `frontend/components/admin/metricas/TabelaPorModelo.tsx`:

```tsx
import { MetricasPorModelo } from "@/lib/api/metrics";
import {
  formatarCusto,
  formatarTokens,
  TITULO_NAO_MEDIDO,
} from "@/lib/format/metricas";

export function TabelaPorModelo({ linhas }: { linhas: MetricasPorModelo[] }) {
  return (
    <section className="space-y-3">
      <h2 className="text-base font-bold text-slate-900">
        Por Modelo{" "}
        <span className="font-normal text-slate-500">— qual modelo/engine custou o quê</span>
      </h2>
      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-xs">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-3 py-2 text-left">Modelo</th>
              <th className="px-3 py-2 text-left">Ambiente</th>
              <th className="px-3 py-2 text-right">Chamadas</th>
              <th className="px-3 py-2 text-right">Tokens entrada</th>
              <th className="px-3 py-2 text-right">Tokens saída</th>
              <th className="px-3 py-2 text-right">Custo</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {linhas.length === 0 ? (
              <tr>
                <td className="px-3 py-4 text-slate-500" colSpan={6}>
                  Nenhum uso de IA registrado no período.
                </td>
              </tr>
            ) : (
              linhas.map((linha) => {
                const id = `${linha.modelo}-${linha.ambiente}`;
                return (
                  <tr key={id}>
                    <td className="px-3 py-2 font-medium text-slate-900">{linha.modelo}</td>
                    <td className="px-3 py-2 text-slate-600">{linha.ambiente}</td>
                    <td className="px-3 py-2 text-right">{linha.chamadas.toLocaleString("pt-BR")}</td>
                    <td className="px-3 py-2 text-right">{formatarTokens(linha.tokens_entrada)}</td>
                    <td className="px-3 py-2 text-right">{formatarTokens(linha.tokens_saida)}</td>
                    <td
                      className="px-3 py-2 text-right font-semibold"
                      data-testid={`custo-modelo-${id}`}
                      title={linha.custo_usd === null ? TITULO_NAO_MEDIDO : undefined}
                    >
                      {formatarCusto(linha.custo_usd)}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
```

Crie `frontend/components/admin/metricas/TabelaPorOperacao.tsx` com a mesma estrutura, mudando o cabeçalho, as colunas e os `data-testid`:

```tsx
import { MetricasPorOperacao } from "@/lib/api/metrics";
import {
  formatarCusto,
  formatarTokens,
  TITULO_NAO_MEDIDO,
} from "@/lib/format/metricas";

export function TabelaPorOperacao({ linhas }: { linhas: MetricasPorOperacao[] }) {
  return (
    <section className="space-y-3">
      <h2 className="text-base font-bold text-slate-900">
        Por Operação{" "}
        <span className="font-normal text-slate-500">
          — o nível que separa visão interna de visão externa
        </span>
      </h2>
      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-xs">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-3 py-2 text-left">Operação</th>
              <th className="px-3 py-2 text-left">Origem</th>
              <th className="px-3 py-2 text-left">Ambiente</th>
              <th className="px-3 py-2 text-right">Chamadas</th>
              <th className="px-3 py-2 text-right">Tokens</th>
              <th className="px-3 py-2 text-right">Custo</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {linhas.length === 0 ? (
              <tr>
                <td className="px-3 py-4 text-slate-500" colSpan={6}>
                  Nenhum uso de IA registrado no período.
                </td>
              </tr>
            ) : (
              linhas.map((linha) => {
                const id = `${linha.operacao}-${linha.origem}-${linha.ambiente}`;
                return (
                  <tr key={id}>
                    <td className="px-3 py-2 font-medium text-slate-900">{linha.operacao}</td>
                    <td className="px-3 py-2 text-slate-600">{linha.origem}</td>
                    <td className="px-3 py-2 text-slate-600">{linha.ambiente}</td>
                    <td className="px-3 py-2 text-right">{linha.chamadas.toLocaleString("pt-BR")}</td>
                    <td className="px-3 py-2 text-right">{formatarTokens(linha.tokens_entrada)}</td>
                    <td
                      className="px-3 py-2 text-right font-semibold"
                      data-testid={`custo-operacao-${id}`}
                      title={linha.custo_usd === null ? TITULO_NAO_MEDIDO : undefined}
                    >
                      {formatarCusto(linha.custo_usd)}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
```

Crie `frontend/components/admin/metricas/TabelaDiaria.tsx`:

```tsx
import { DiaUsoIa } from "@/lib/api/metrics";
import { formatarCusto, TITULO_NAO_MEDIDO } from "@/lib/format/metricas";

function formatarDataPtBr(isoDate: string): string {
  const [ano, mes, dia] = isoDate.split("-");
  return ano && mes && dia ? `${dia}/${mes}/${ano}` : isoDate;
}

const ORIGENS = ["chat", "b2b", "admin"] as const;

export function TabelaDiaria({ dias }: { dias: DiaUsoIa[] }) {
  return (
    <section className="space-y-3">
      <h2 className="text-base font-bold text-slate-900">
        Detalhamento Diário{" "}
        <span className="font-normal text-slate-500">— no fuso local do administrador</span>
      </h2>
      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-xs">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-3 py-2 text-left">Data</th>
              <th className="px-3 py-2 text-right">Chats encerrados</th>
              <th className="px-3 py-2 text-right">Chamadas</th>
              {ORIGENS.map((origem) => (
                <th key={origem} className="px-3 py-2 text-right">
                  {origem}
                </th>
              ))}
              <th className="px-3 py-2 text-right">Custo total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {dias.length === 0 ? (
              <tr>
                <td className="px-3 py-4 text-slate-500" colSpan={7}>
                  Nenhum registro no período.
                </td>
              </tr>
            ) : (
              dias.map((dia) => {
                const porOrigem = new Map(dia.por_origem.map((b) => [b.origem, b]));
                return (
                  <tr key={dia.data}>
                    <td className="px-3 py-2 font-medium text-slate-900">
                      {formatarDataPtBr(dia.data)}
                    </td>
                    <td className="px-3 py-2 text-right">{dia.chats_encerrados}</td>
                    <td className="px-3 py-2 text-right">{dia.totais.chamadas}</td>
                    {ORIGENS.map((origem) => (
                      <td
                        key={origem}
                        className="px-3 py-2 text-right"
                        data-testid={`custo-dia-${dia.data}-${origem}`}
                      >
                        {porOrigem.has(origem)
                          ? formatarCusto(porOrigem.get(origem)!.custo_usd)
                          : "—"}
                      </td>
                    ))}
                    <td
                      className="px-3 py-2 text-right font-semibold"
                      data-testid={`custo-dia-${dia.data}-total`}
                      title={dia.totais.custo_usd === null ? TITULO_NAO_MEDIDO : undefined}
                    >
                      {formatarCusto(dia.totais.custo_usd)}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
```

- [ ] **Step 6: Reconstrua a página**

Em `frontend/app/admin/metricas/page.tsx`:

1. Troque os imports de `@/lib/api/metrics` por:

```tsx
import { fetchAiUsageMetrics, AiUsageReport, GetMetricsParams } from "@/lib/api/metrics";
import { SecaoPorOrigem } from "@/components/admin/metricas/SecaoPorOrigem";
import { SecaoPorAmbiente } from "@/components/admin/metricas/SecaoPorAmbiente";
import { TabelaPorModelo } from "@/components/admin/metricas/TabelaPorModelo";
import { TabelaPorOperacao } from "@/components/admin/metricas/TabelaPorOperacao";
import { TabelaDiaria } from "@/components/admin/metricas/TabelaDiaria";
```

2. Apague as funções `preencherLinhasDetalhamento` e `obterDiaSemanaPtBr` e a `formatarDataPtBr` do topo (a tabela diária traz a sua).
3. Troque o tipo do estado: `const [data, setData] = useState<AiUsageReport | null>(null);`
4. Em `carregarMetricas`, troque `fetchTokenCostMetrics(token, params)` por `fetchAiUsageMetrics(token, params)`. **Mantenha** `requestIdRef`, o `startTime`/delay de 400ms do refresh manual, o `showToast` e o tratamento de erro exatamente como estão.
5. Substitua tudo o que vem **depois** do bloco de filtros (os 4 cards, a faixa consolidada e a tabela de detalhamento) por:

```tsx
        {error ? (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        ) : null}

        <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-sm text-slate-600">
          <span>
            Chats encerrados no período:{" "}
            <strong data-testid="chats-encerrados" className="text-slate-900">
              {data?.atendimento.chats_encerrados ?? 0}
            </strong>
          </span>
          {data && data.totais.chamadas_sem_custo_medido > 0 ? (
            <span className="text-amber-700">
              Chamadas sem custo medido:{" "}
              <strong data-testid="sem-custo-medido">
                {data.totais.chamadas_sem_custo_medido}
              </strong>
            </span>
          ) : null}
        </div>

        {data ? (
          <div className="space-y-6">
            <SecaoPorOrigem linhas={data.por_origem} />
            <SecaoPorAmbiente linhas={data.por_ambiente} totais={data.totais} />
            <TabelaPorModelo linhas={data.por_modelo} />
            <TabelaPorOperacao linhas={data.por_operacao} />
            <TabelaDiaria dias={data.diario} />
          </div>
        ) : null}
```

6. Remova qualquer variável que ficou sem uso (`summary`, `daily`, `rawDaily`, `selectedDate` se de fato não for mais usado pelo seletor — confira antes de apagar; o `<input type="date">` depende dele).

- [ ] **Step 7: Run the tests and typecheck**

Run: `cd frontend && npm test -- AdminMetricasPage formatMetricas`
Expected: PASS

Run: `cd frontend && npx tsc --noEmit`
Expected: sem erros. Qualquer resíduo de `TokenCostMetricsResponse`/`DailyMetric`/`fetchTokenCostMetrics` aparece aqui — remova o resíduo, não reintroduza o tipo.

Run: `cd frontend && npm run lint`
Expected: sem erros novos.

- [ ] **Step 8: Commit**

```bash
git add -A frontend
git commit -m "feat(metricas): reconstroi /admin/metricas sobre o ledger de uso de IA (item E, Task 5)

Cinco secoes — por origem, por ambiente (gratis x pago), por modelo, por
operacao e diaria — em componentes proprios sob components/admin/metricas.
Preserva o shell da pagina (gate de admin, filtros de periodo, toast e o
guard de resposta obsoleta de 2026-10-04). Remove os 4 cards antigos e o
preenchimento de dias com zeros fabricados.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Documentação e fechamento do item

**Files:**
- Modify: `docs/ROADMAP.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/FRONTEND.md`
- Modify: `docs/Manuais/HOWTO_ADMINISTRADOR.md`
- Verify (sem alteração esperada): `docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md`

**Interfaces:**
- Consumes: o estado final das Tasks 1–5.
- Produces: documentação refletindo o estado atual (regras 5, 6, 9 e 11 do `CLAUDE.md`).

- [ ] **Step 1: Rode a suíte inteira antes de documentar**

Run: `cd backend && pytest -q`
Run: `cd frontend && npm test`
Expected: tudo verde. Documentar um estado que não passa é documentar ficção — pare e corrija antes de seguir.

- [ ] **Step 2: `docs/ROADMAP.md`**

Marque o item E como concluído (`- [x] **E — Painel.**`) e acrescente ao texto dele:

```markdown
      Fechamento (2026-10-08): `GET /api/admin/metrics/ai-usage` substituiu
      `/tokens-and-costs`, que foi removido junto com a heurística de nome
      de modelo que inferia "isto é visão?". O painel passou a ter cinco
      seções (origem, ambiente, modelo, operação, diária) e distingue na
      tela custo `null` (não medido, `—`) de `0.0` (grátis, `$0.0000`).
      Descoberta durante o design e corrigida neste item: o classificador
      do crawler (`app.rag.crawler_classifier.classify_page`) era o último
      ponto de uso de IA ainda escrevendo em `IngestionCostEvent` e foi
      migrado para o ledger (`origem="admin"`,
      `operacao="classificacao_crawler"`). Histórico pré-ledger descartado
      sem backfill e `IngestionCostEvent` mantida como tabela morta — ambas
      decisões do dono do projeto. Com isto o plano A→E está completo: todo
      uso de IA do sistema é registrado num só lugar.
```

- [ ] **Step 3: `docs/ARCHITECTURE.md`**

Na seção que descreve o "Relatório Analítico Consolidado" (procure por `tokens-and-costs`, ~linha 1457), substitua a descrição do endpoint antigo por:

```markdown
   - **Painel de Uso de IA:** o endpoint `GET /api/admin/metrics/ai-usage`
     agrega a tabela `ai_usage_events` (ledger unificado, item A) por
     origem × ambiente × modelo × operação, com filtros de período
     (`today`, `7d`, `30d`, `all` ou `start_date`+`end_date`) no calendário
     local do administrador, e alimenta o painel `/admin/metricas`. Duas
     consultas: um `GROUP BY` das quatro dimensões, de onde cinco visões
     são derivadas por roll-up (`app.services.ai_usage_report`), e uma
     seleção estreita por evento para o recorte diário — o bucket diário é
     feito em Python porque não existe expressão SQL portável entre SQLite
     (testes) e PostgreSQL (produção) para truncar um timestamp num fuso
     arbitrário. Substituiu `GET /api/admin/metrics/tokens-and-costs`
     (removido em 2026-10-08), que lia dois esquemas diferentes
     (`ConversaMensagem.metricas` e `IngestionCostEvent`) e inferia visão
     computacional por heurística de nome de modelo.
```

E acrescente, logo após a nota existente sobre o item D (procure por `record_ingestion_cost`, ~linha 870):

```markdown
Fechamento do ledger (item E, 2026-10-08): o painel `/admin/metricas`
passou a ler **somente** `ai_usage_events`. Decisões do dono do projeto:
(1) substituir o painel antigo em vez de mantê-lo em paralelo; (2) descartar
o histórico pré-ledger sem backfill — inferir `origem`/`operacao` dos dados
antigos exigiria exatamente a heurística que o ledger veio eliminar, e os
números que importam para a avaliação experimental (Fase 10) serão gerados
em cima do ledger; (3) manter a tabela `IngestionCostEvent` no banco sem
leitor nem escritor, marcada como morta no modelo, em vez de uma migração
destrutiva. O classificador do crawler
(`app.rag.crawler_classifier.classify_page`), último ponto de uso de IA
fora do ledger, foi migrado neste item. A distinção `custo_usd`/`tokens`
`None` (não capturado) × `0.0` (grátis conhecido) é preservada da tabela
até a tela: `—` versus `$0.0000`, mais um contador
`chamadas_sem_custo_medido` por grupo, que é como o painel expõe — em vez
de esconder atrás de um zero — o gap conhecido de estimativa de uso em
`OpenRouterClient.describe_image`.
```

- [ ] **Step 4: `docs/FRONTEND.md`**

Atualize o contrato de API da página `/admin/metricas`: endpoint
`GET /api/admin/metrics/ai-usage`, o payload de `AiUsageReport` (§2.3 da
spec), e a regra de renderização `null` → `—` / `0` → `$0.0000` via
`@/lib/format/metricas`. Liste os componentes novos em
`frontend/components/admin/metricas/`.

- [ ] **Step 5: `docs/Manuais/HOWTO_ADMINISTRADOR.md`**

Reescreva a parte que descreve a tela de métricas: as cinco seções, o que
cada uma responde, e — explicitamente, porque é a dúvida que o
administrador vai ter — que `—` significa "a chamada aconteceu mas o
custo/tokens não foram capturados" e `$0.0000` significa "medido e
gratuito" (CLIP, modelo local na GPU). Mencione que o campo "Chamadas sem
custo medido" aparece só quando é maior que zero.

- [ ] **Step 6: Verifique `docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md`**

Run: `grep -n -i "crawler" docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md`

Este item **não altera nenhum prompt** — a migração do crawler mexe só na
telemetria, não no texto enviado ao LLM. Confirme que o prompt de
`crawler_classifier` já está mapeado; se estiver, não mude nada (regra 11
só exige atualização quando o prompt muda ou nasce). Se **não** estiver
mapeado, adicione a entrada: é um prompt existente ausente do documento,
que a própria regra 11 classifica como bug a corrigir.

- [ ] **Step 7: Confirme que nenhuma referência órfã sobrou**

Run: `grep -rn "tokens-and-costs\|fetchTokenCostMetrics\|MetricSummary\|DailyMetric" --include=*.py --include=*.ts --include=*.tsx --include=*.md . | grep -v node_modules | grep -v '\.next' | grep -v docs/superpowers/plans | grep -v docs/superpowers/specs`

Expected: nenhum resultado. Ocorrências em `docs/superpowers/plans/` e
`docs/superpowers/specs/` são registros históricos de planos já executados
e **devem** ficar como estão.

- [ ] **Step 8: Commit**

```bash
git add -A docs
git commit -m "docs: fecha o item E do ledger de uso de IA (painel) — plano A-E completo

ROADMAP (item E marcado), ARCHITECTURE (endpoint novo, as tres decisoes do
dono do projeto, semantica None x 0.0 preservada ate a tela), FRONTEND
(contrato e componentes) e HOWTO_ADMINISTRADOR (as cinco secoes e o que o
traco significa).

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Verificação Final (antes de considerar o item concluído)

- [ ] `cd backend && pytest -q` — verde
- [ ] `cd frontend && npm test` — verde
- [ ] `cd frontend && npx tsc --noEmit` — sem erros
- [ ] `cd frontend && npm run lint` — sem erros novos
- [ ] Checklist de `docs/CONVENTIONS.md` ("Checklist antes de cada commit")
- [ ] `/code-review` sobre o diff completo do item (regra do skill `proximo-passo`); achados `high`/`critical` são bloqueantes
- [ ] Teste manual com dados reais via `./testar.sh` (`docs/TESTE_LOCAL.md`) — vale a pena aqui porque o painel só mostra o que o ledger tem, e a conferência de que os números batem com o uso real do chat/admin não é algo que teste de unidade cubra
