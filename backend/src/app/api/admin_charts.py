"""Endpoints REST administrativos para gestão de Dashboards e Gráficos Dinâmicos."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_auth import require_admin
from app.api.rag_dependencies import get_db_session
from app.db.models import AdminChart
from app.services.safe_sql import SQLSecurityError, execute_readonly_sql

logger = logging.getLogger("assistente.admin_charts")

router = APIRouter(prefix="/api/admin/charts", tags=["Admin Charts"])


class AdminChartCreate(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=255)
    descricao: str | None = None
    tipo_grafico: str = Field(default="bar", description="bar, line, pie, area, donut")
    config_json: dict[str, Any] = Field(default_factory=dict)
    dados_json: list[dict[str, Any]] = Field(default_factory=list)
    sql_query: str | None = None
    fixado: bool = True
    ordem: int = 0


class AdminChartUpdate(BaseModel):
    titulo: str | None = None
    descricao: str | None = None
    tipo_grafico: str | None = None
    config_json: dict[str, Any] | None = None
    dados_json: list[dict[str, Any]] | None = None
    fixado: bool | None = None
    ordem: int | None = None


class AdminChartOut(BaseModel):
    id: str
    titulo: str
    descricao: str | None = None
    tipo_grafico: str
    config_json: dict[str, Any]
    dados_json: list[dict[str, Any]]
    sql_query: str | None = None
    fixado: bool
    ordem: int
    criado_por: str
    criado_em: datetime
    atualizado_em: datetime

    @classmethod
    def from_model(cls, m: AdminChart) -> AdminChartOut:
        return cls(
            id=str(m.id),
            titulo=m.titulo,
            descricao=m.descricao,
            tipo_grafico=m.tipo_grafico,
            config_json=m.config_json or {},
            dados_json=m.dados_json or [],
            sql_query=m.sql_query,
            fixado=m.fixado,
            ordem=m.ordem,
            criado_por=m.criado_por,
            criado_em=m.criado_em,
            atualizado_em=m.atualizado_em,
        )


@router.get("", response_model=list[AdminChartOut])
async def list_admin_charts(
    response: Response,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_admin),
) -> list[AdminChartOut]:
    """Retorna a lista de gráficos salvos no banco de dados."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    stmt = select(AdminChart).order_by(
        AdminChart.fixado.desc(), AdminChart.ordem.asc(), AdminChart.criado_em.desc()
    )
    res = await session.scalars(stmt)
    return [AdminChartOut.from_model(c) for c in res.all()]


@router.post("", response_model=AdminChartOut, status_code=status.HTTP_201_CREATED)
async def create_admin_chart(
    payload: AdminChartCreate,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_admin),
) -> AdminChartOut:
    """Cria e persiste um novo gráfico no painel do administrador."""
    chart = AdminChart(
        titulo=payload.titulo,
        descricao=payload.descricao,
        tipo_grafico=payload.tipo_grafico,
        config_json=payload.config_json,
        dados_json=payload.dados_json,
        sql_query=payload.sql_query,
        fixado=payload.fixado,
        ordem=payload.ordem,
        criado_por="admin",
    )
    session.add(chart)
    await session.commit()
    await session.refresh(chart)
    return AdminChartOut.from_model(chart)


@router.post("/{chart_id}/refresh", response_model=AdminChartOut)
async def refresh_admin_chart(
    chart_id: str,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_admin),
) -> AdminChartOut:
    """Re-executa a agregação de dados e atualiza o gráfico no banco de dados."""
    try:
        cid = uuid.UUID(chart_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="ID de gráfico inválido."
        )

    chart = await session.get(AdminChart, cid)
    if not chart:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gráfico não encontrado.")

    if chart.sql_query:
        if chart.sql_query.startswith("dynamic_sql:"):
            sql = chart.sql_query.removeprefix("dynamic_sql:").strip()
            try:
                dados_json = await execute_readonly_sql(session, sql)
                chart.dados_json = dados_json
                chart.atualizado_em = datetime.now(UTC)
                await session.commit()
                await session.refresh(chart)
            except SQLSecurityError as exc:
                await session.rollback()
                logger.error(
                    "sql_inseguro_ao_recalcular", extra={"chart_id": chart_id, "erro": str(exc)}
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"A consulta salva deste gráfico não é mais permitida: {exc}",
                ) from exc
            except Exception as exc:
                # Achado da revisão de 2026-10-04: sem o rollback aqui, o
                # commit anterior falho deixava a sessão em estado inválido
                # e esse `except` só devolvia dados obsoletos com 200 (nunca
                # avisando o chamador que o recálculo falhou).
                await session.rollback()
                logger.error(
                    "falha_ao_recalcular_dynamic_sql",
                    extra={"chart_id": chart_id, "erro": str(exc)},
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Não foi possível atualizar os dados deste gráfico agora. "
                    "Tente novamente.",
                ) from exc
        elif chart.sql_query == "dynamic_user_data":
            chart.atualizado_em = datetime.now(UTC)
            await session.commit()
            await session.refresh(chart)
        # Achado de 2026-10-06 (docs/ARCHITECTURE.md §5): removido o
        # terceiro caminho, que recalculava gráficos salvos com uma
        # `query_key` fixa de `chart_generator.execute_chart_aggregation`
        # (ex.: "vendas_por_categoria") — não existe mais gráfico gerado
        # dessa forma em uso, e gráfico novo só é criado via Text-to-SQL
        # (`sql_query` sempre vem com o prefixo `dynamic_sql:` ou é
        # `dynamic_user_data`). Qualquer `sql_query` que não caia nos dois
        # ramos acima simplesmente não é recalculado no refresh.

    return AdminChartOut.from_model(chart)


@router.put("/{chart_id}", response_model=AdminChartOut)
async def update_admin_chart(
    chart_id: str,
    payload: AdminChartUpdate,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_admin),
) -> AdminChartOut:
    """Atualiza propriedades de exibição do gráfico (título, descrição, fixado, ordem)."""
    try:
        cid = uuid.UUID(chart_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="ID de gráfico inválido."
        )

    chart = await session.get(AdminChart, cid)
    if not chart:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gráfico não encontrado.")

    if payload.titulo is not None:
        chart.titulo = payload.titulo
    if payload.descricao is not None:
        chart.descricao = payload.descricao
    if payload.tipo_grafico is not None:
        chart.tipo_grafico = payload.tipo_grafico
    if payload.config_json is not None:
        chart.config_json = payload.config_json
    if payload.dados_json is not None:
        chart.dados_json = payload.dados_json
    if payload.fixado is not None:
        chart.fixado = payload.fixado
    if payload.ordem is not None:
        chart.ordem = payload.ordem

    chart.atualizado_em = datetime.now(UTC)
    await session.commit()
    await session.refresh(chart)
    return AdminChartOut.from_model(chart)


@router.delete("/{chart_id}")
async def delete_admin_chart(
    chart_id: str,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_admin),
) -> dict[str, bool]:
    """Exclui permanentemente um gráfico do banco de dados."""
    try:
        cid = uuid.UUID(chart_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="ID de gráfico inválido."
        )

    chart = await session.get(AdminChart, cid)
    if not chart:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gráfico não encontrado.")

    await session.delete(chart)
    await session.commit()
    return {"ok": True}
