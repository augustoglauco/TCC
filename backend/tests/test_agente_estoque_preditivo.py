"""Agente autônomo de previsão de estoque (R13) — gancho em `criar_pedido`,
regra de cobertura, anti-ruído, e-mail e a caixa de entrada administrativa.
Tudo sobre SQLite em memória; o SMTP é substituído por dublê."""

from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.agents import email as agente_email
from app.agents.estoque_preditivo import avaliar_estoque, cobertura_dias
from app.api.admin_mensagens import router as mensagens_router
from app.api.rag_dependencies import get_db_session
from app.config import get_settings
from app.db.catalog import atualizar_estoque, criar_pedido, criar_produto
from app.db.models import MensagemAgente


async def _produto(session, estoque: int, nome="Gerador GD-15"):
    p = await criar_produto(
        session, nome=nome, descricao="x", preco=Decimal("100.00"), categoria="geradores"
    )
    await atualizar_estoque(session, p.id, "CD-SP", estoque)
    return p


async def _mensagens(session):
    return (await session.scalars(select(MensagemAgente))).all()


def test_cobertura_sem_baixa_nao_tem_previsao():
    assert cobertura_dias(50, 0, 30) is None


def test_cobertura_em_dias():
    # 30 unidades em 30 dias = 1/dia; 5 em estoque => 5 dias.
    assert cobertura_dias(5, 30, 30) == Decimal(5)


async def test_reserva_que_deixa_menos_de_10_dias_gera_alerta(db_session):
    produto = await _produto(db_session, 40)
    # 30 unidades em uma reserva: sobram 10, taxa 1/dia => 10 dias (não alerta)
    await criar_pedido(db_session, [(produto.id, 30, "CD-SP")])
    assert await _mensagens(db_session) == []
    # +5: sobram 5, taxa 35/30 => ~4,3 dias => alerta
    await criar_pedido(db_session, [(produto.id, 5, "CD-SP")])

    [msg] = await _mensagens(db_session)
    assert msg.agente == "estoque_preditivo"
    assert msg.dados["produto_id"] == produto.id
    assert msg.dados["estoque_atual"] == 5
    assert msg.dados["cobertura_dias"] < 10
    assert msg.lida is False
    assert msg.email_status == "nao_configurado"


async def test_estoque_folgado_nao_alerta(db_session):
    produto = await _produto(db_session, 1000)
    await criar_pedido(db_session, [(produto.id, 5, "CD-SP")])
    assert await _mensagens(db_session) == []


async def test_alerta_nao_repete_em_24h(db_session):
    produto = await _produto(db_session, 10)
    await criar_pedido(db_session, [(produto.id, 8, "CD-SP")])
    await criar_pedido(db_session, [(produto.id, 1, "CD-SP")])
    await avaliar_estoque(db_session, [produto.id])
    assert len(await _mensagens(db_session)) == 1


async def test_falha_do_agente_nao_derruba_a_reserva(db_session, monkeypatch):
    produto = await _produto(db_session, 10)

    async def _explode(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.agents.estoque_preditivo.avaliar_estoque", _explode)
    pedido = await criar_pedido(db_session, [(produto.id, 2, "CD-SP")])
    assert pedido.status == "reservado"


async def test_email_enviado_quando_smtp_configurado(db_session, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "smtp.exemplo.test")
    monkeypatch.setattr(settings, "admin_alert_email", "admin@exemplo.test")
    enviados = []
    monkeypatch.setattr(
        agente_email, "_enviar_sync", lambda s, assunto, corpo: enviados.append(assunto)
    )
    produto = await _produto(db_session, 10)

    await criar_pedido(db_session, [(produto.id, 8, "CD-SP")])

    [msg] = await _mensagens(db_session)
    assert msg.email_status == "enviado"
    assert enviados == [msg.titulo]


async def test_falha_de_smtp_fica_registrada_e_nao_quebra(db_session, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "smtp.exemplo.test")
    monkeypatch.setattr(settings, "admin_alert_email", "admin@exemplo.test")

    def _falha(*_a):
        raise OSError("sem rede")

    monkeypatch.setattr(agente_email, "_enviar_sync", _falha)
    produto = await _produto(db_session, 10)

    await criar_pedido(db_session, [(produto.id, 8, "CD-SP")])

    [msg] = await _mensagens(db_session)
    assert msg.email_status == "falhou"


@pytest.fixture
def mensagens_client(db_session):
    app = FastAPI()
    app.include_router(mensagens_router)
    app.dependency_overrides[get_db_session] = lambda: db_session
    with TestClient(app) as c:
        yield c


async def test_api_requer_admin(mensagens_client):
    assert mensagens_client.get("/api/admin/agentes/mensagens").status_code == 403


async def test_api_lista_e_marca_como_lida(mensagens_client, admin_headers, db_session):
    produto = await _produto(db_session, 10)
    await criar_pedido(db_session, [(produto.id, 8, "CD-SP")])

    r = mensagens_client.get("/api/admin/agentes/mensagens", headers=admin_headers)
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["nao_lidas"] == 1
    mid = corpo["mensagens"][0]["id"]

    r = mensagens_client.post(f"/api/admin/agentes/mensagens/{mid}/lida", headers=admin_headers)
    assert r.status_code == 200 and r.json()["lida"] is True
    r = mensagens_client.get(
        "/api/admin/agentes/mensagens?apenas_nao_lidas=true", headers=admin_headers
    )
    assert r.json() == {"mensagens": [], "nao_lidas": 0}


async def test_api_marcar_inexistente_404(mensagens_client, admin_headers):
    r = mensagens_client.post(
        "/api/admin/agentes/mensagens/00000000-0000-0000-0000-000000000000/lida",
        headers=admin_headers,
    )
    assert r.status_code == 404


# --- modo IA e configuração (R13) -------------------------------------------


class _LLMFalso:
    def __init__(self, texto: str | None = None, erro: Exception | None = None):
        self.texto, self.erro, self.prompts = texto, erro, []

    async def generate(self, prompt: str):
        self.prompts.append(prompt)
        if self.erro:
            raise self.erro
        from app.router.llm_client import LLMResponse

        return LLMResponse(
            text=self.texto,
            prompt_tokens=10,
            completion_tokens=5,
            total_duration_ms=1.0,
            load_duration_ms=0.0,
            prompt_eval_duration_ms=0.0,
            eval_duration_ms=0.0,
            cost_prompt_usd=0.0,
            cost_completion_usd=0.0,
            estimated_cost_usd=0.0,
            model_name="modelo-falso",
        )


def _ligar_ia(llm: _LLMFalso):
    from app.agents.runtime import runtime

    runtime.estoque_modo = "ia"
    runtime.local_client = llm


_RESP_ALERTA = (
    '{"risco": "alto", "dias_ate_falta": 2, "reposicao_sugerida": 40, '
    '"alertar": true, "justificativa": "Baixa acelerou nos últimos dias."}'
)


async def test_modo_ia_usa_a_decisao_do_llm(db_session):
    llm = _LLMFalso(_RESP_ALERTA)
    _ligar_ia(llm)
    produto = await _produto(db_session, 10)

    await criar_pedido(db_session, [(produto.id, 8, "CD-SP")])

    [msg] = await _mensagens(db_session)
    assert msg.agente == "estoque_ia"
    assert msg.severidade == "critico"
    assert msg.dados["metodo"] == "ia"
    assert msg.dados["reposicao_sugerida"] == 40
    assert "Baixa acelerou" in msg.corpo
    assert "Gerador GD-15" in llm.prompts[0]


async def test_modo_ia_pode_decidir_nao_alertar(db_session):
    _ligar_ia(
        _LLMFalso(
            '{"risco": "baixo", "dias_ate_falta": null, "alertar": false, "reposicao_sugerida": 0}'
        )
    )
    produto = await _produto(db_session, 10)
    await criar_pedido(db_session, [(produto.id, 8, "CD-SP")])
    assert await _mensagens(db_session) == []


@pytest.mark.parametrize("llm", [_LLMFalso("isto não é json"), _LLMFalso(erro=TimeoutError())])
async def test_modo_ia_cai_na_regra_deterministica_se_o_llm_falha(db_session, llm):
    _ligar_ia(llm)
    produto = await _produto(db_session, 10)

    await criar_pedido(db_session, [(produto.id, 8, "CD-SP")])

    [msg] = await _mensagens(db_session)
    assert msg.agente == "estoque_preditivo"


async def test_modo_desativado_nao_avalia_nem_chama_llm(db_session):
    from app.agents.runtime import runtime

    llm = _LLMFalso(_RESP_ALERTA)
    _ligar_ia(llm)
    runtime.estoque_modo = "desativado"
    produto = await _produto(db_session, 10)

    await criar_pedido(db_session, [(produto.id, 8, "CD-SP")])

    assert await _mensagens(db_session) == []
    assert llm.prompts == []


async def test_sem_baixa_na_janela_nao_gasta_llm(db_session):
    llm = _LLMFalso(_RESP_ALERTA)
    _ligar_ia(llm)
    produto = await _produto(db_session, 3)
    await avaliar_estoque(db_session, [produto.id])
    assert llm.prompts == []


async def test_configuracao_persistente_via_runtime_settings(db_session, admin_headers):
    """O modo do agente passa pelo mesmo PUT/GET das outras configurações."""
    from app.agents.runtime import runtime
    from tests.test_runtime_settings_api import _build_default_app

    app, *_ = _build_default_app(db_session)
    with TestClient(app) as c:
        r = c.put(
            "/api/admin/runtime-settings",
            headers=admin_headers,
            json={"estoque_agent_mode": "ia", "estoque_agent_llm": "externo"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["estoque_agent_mode"] == "ia"
        assert r.json()["estoque_agent_llm"] == "externo"
    assert runtime.estoque_modo == "ia" and runtime.estoque_llm == "externo"


async def test_horizonte_por_produto_substitui_o_padrao(db_session):
    """Mesma baixa e mesmo estoque: com 3 dias de horizonte o produto está
    seguro; com o padrão global (10) ele alerta."""
    seguro = await _produto(db_session, 10, nome="Seguro")
    seguro.dias_alerta_estoque = 3
    longo = await _produto(db_session, 10, nome="Prazo longo")
    await db_session.commit()

    # 9 de 10 unidades: sobra 1, taxa 9/30 => ~3,3 dias de cobertura.
    await criar_pedido(db_session, [(seguro.id, 9, "CD-SP"), (longo.id, 9, "CD-SP")])

    msgs = await _mensagens(db_session)
    assert [m.dados["produto_id"] for m in msgs] == [longo.id]
    assert msgs[0].dados["horizonte_dias"] == 10


async def test_horizonte_do_produto_maior_que_o_padrao_alerta_antes(db_session):
    produto = await _produto(db_session, 10)
    produto.dias_alerta_estoque = 60
    await db_session.commit()

    # sobram 5, taxa 5/30 => 30 dias: < 60 (alerta) mas > 10 (não alertaria).
    await criar_pedido(db_session, [(produto.id, 5, "CD-SP")])

    [msg] = await _mensagens(db_session)
    assert msg.dados["horizonte_dias"] == 60
