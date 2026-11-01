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
