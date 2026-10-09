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


def _somar(a: float | None, b: float | None) -> float | None:
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
