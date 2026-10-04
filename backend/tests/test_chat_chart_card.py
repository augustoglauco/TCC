from unittest.mock import AsyncMock
import pytest
from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import AdminChart, Produto
from app.models.chat import CardGrafico, ChatCard, ChatDoneEventData
from app.router.orchestrator import RouterDecision, StatusEvent, TokenEvent, handle_message


def test_card_grafico_schema():
    card = CardGrafico(
        chart_id="123e4567-e89b-12d3-a456-426614174000",
        titulo="Vendas por Categoria",
        tipo_grafico="bar",
        config={"x_key": "categoria", "y_keys": ["total"]},
        dados=[{"categoria": "Ferramentas", "total": 100}],
        fixado=True,
    )
    assert card.tipo == "grafico"
    assert card.tipo_grafico == "bar"

    adapter = TypeAdapter(ChatCard)
    dumped = adapter.dump_python(card)
    assert dumped["tipo"] == "grafico"

    done = ChatDoneEventData(
        domain="vendas",
        backend_used="local",
        escalation_reason="nenhum",
        card=card,
    )
    assert done.card is not None
    assert done.card.tipo == "grafico"


@pytest.mark.asyncio
async def test_orchestrator_chart_generation_admin(db_session):
    p = Produto(nome="Produto Teste", descricao="Desc", preco=80.0, categoria="Ferramentas")
    db_session.add(p)
    await db_session.commit()

    # Wrap session in sessionmaker
    class _MockSessionMaker:
        def __call__(self):
            return db_session

    events = []
    async for ev in handle_message(
        message="Por favor, gere um gráfico de vendas por categoria",
        recent_messages=[],
        local_client=AsyncMock(),
        external_client=AsyncMock(),
        rag_client=AsyncMock(),
        complexity_strategy="heuristic",
        conversation_id="conv-chart-1",
        db_sessionmaker=_MockSessionMaker(),
        is_admin=True,
        user_email="admin@empresa.com",
    ):
        events.append(ev)

    token_events = [e for e in events if isinstance(e, TokenEvent)]
    assert len(token_events) > 0
    assert "gráfico" in token_events[0].text.lower() or "grafico" in token_events[0].text.lower()

    decisions = [e for e in events if isinstance(e, RouterDecision)]
    assert len(decisions) == 1
    assert decisions[0].card is not None
    assert decisions[0].card.tipo == "grafico"
    assert decisions[0].card.tipo_grafico == "bar"


@pytest.mark.asyncio
async def test_orchestrator_chart_generation_non_admin(db_session):
    events = []
    async for ev in handle_message(
        message="Gere um gráfico de vendas por categoria",
        recent_messages=[],
        local_client=AsyncMock(),
        external_client=AsyncMock(),
        rag_client=AsyncMock(),
        complexity_strategy="heuristic",
        conversation_id="conv-chart-2",
        is_admin=False,
    ):
        events.append(ev)

    token_events = [e for e in events if isinstance(e, TokenEvent)]
    assert any("administrador" in e.text.lower() for e in token_events)

    decisions = [e for e in events if isinstance(e, RouterDecision)]
    assert len(decisions) == 1
    assert decisions[0].card is None
