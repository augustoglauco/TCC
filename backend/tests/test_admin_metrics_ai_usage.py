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

from app.api.admin_metrics import _resolver_janela
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
    assert [d["data"] for d in data_7d["diario"]] == [ontem_22h_local.strftime("%Y-%m-%d")]


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


def test_resolver_janela_com_ambas_as_datas_usa_limites_do_dia_local():
    """Teste direto de `_resolver_janela` (revisão final de ponta a ponta,
    2026-10-09): com `start_date`/`end_date` setados, os limites devolvidos
    devem ser o início e o fim do DIA LOCAL correspondente, convertidos
    para UTC — não meia-noite/fim de dia em UTC."""
    local_tz = ZoneInfo(get_settings().agendamento_timezone)

    cutoff_start, cutoff_end = _resolver_janela("custom", "2026-03-10", "2026-03-12", local_tz)

    esperado_start = datetime(2026, 3, 10, 0, 0, 0, tzinfo=local_tz).astimezone(UTC)
    esperado_end = datetime(2026, 3, 12, 23, 59, 59, 999999, tzinfo=local_tz).astimezone(UTC)

    assert cutoff_start == esperado_start
    assert cutoff_end == esperado_end


@pytest.mark.asyncio
async def test_ai_usage_custom_date_filtra_janela_local_do_dia(
    metrics_client, admin_headers, db_session, local_tz
):
    """Regressão para a janela `start_date`/`end_date` (achado da revisão
    final de ponta a ponta, 2026-10-09): até aqui só havia cobertura para
    data mal formada (`400`); nada garantia que o filtro de fato
    restringia os eventos contados, então um `cutoff_start`/`cutoff_end`
    trocado, ou um `start_date` que silenciosamente não fosse aplicado,
    passaria a suíte inteira. Um evento antes da janela e um depois dela
    (além do que está dentro) cobre tanto a omissão do filtro quanto uma
    transposição dos limites."""
    dia_pedido = (datetime.now(local_tz) - timedelta(days=3)).date()
    inicio_do_dia = datetime(
        dia_pedido.year, dia_pedido.month, dia_pedido.day, 0, 0, 0, tzinfo=local_tz
    )
    antes_da_janela = inicio_do_dia - timedelta(hours=1)  # 23h do dia anterior, local
    dentro_da_janela = inicio_do_dia + timedelta(hours=12)
    depois_da_janela = inicio_do_dia + timedelta(days=1, hours=1)  # 01h do dia seguinte, local

    await _evento(db_session, criado_em=antes_da_janela.astimezone(UTC), custo_usd=0.001)
    await _evento(db_session, criado_em=dentro_da_janela.astimezone(UTC), custo_usd=0.002)
    await _evento(db_session, criado_em=depois_da_janela.astimezone(UTC), custo_usd=0.003)

    data_str = dia_pedido.isoformat()
    res = metrics_client.get(
        f"/api/admin/metrics/ai-usage?period=custom&start_date={data_str}&end_date={data_str}",
        headers=admin_headers,
    )

    assert res.status_code == 200
    data = res.json()
    assert data["totais"]["chamadas"] == 1
    assert data["totais"]["custo_usd"] == pytest.approx(0.002)


@pytest.mark.asyncio
async def test_endpoint_antigo_de_tokens_e_custos_nao_existe_mais(metrics_client, admin_headers):
    res = metrics_client.get("/api/admin/metrics/tokens-and-costs?period=7d", headers=admin_headers)
    assert res.status_code == 404
