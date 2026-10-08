"""Ledger unificado de uso de IA (origem × ambiente × modelo) —
`app.services.ai_usage` / `app.db.models.AiUsageEvent`. Ver
docs/superpowers/specs/2026-10-08-ledger-uso-ia-origem-ambiente-modelo-design.md.
"""

from sqlalchemy import select

from app.db.engine import create_db_engine, create_session_factory
from app.db.models import AiUsageEvent, Base


async def _engine_e_sessionmaker_vazios():
    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, create_session_factory(engine)


async def test_ai_usage_event_grava_e_le_com_defaults_corretos():
    engine, factory = await _engine_e_sessionmaker_vazios()
    try:
        async with factory() as session:
            evento = AiUsageEvent(
                origem="chat",
                ambiente="interno",
                modelo="clip",
                operacao="identificacao_imagem_clip",
            )
            session.add(evento)
            await session.commit()

        async with factory() as session:
            resultado = await session.execute(select(AiUsageEvent))
            eventos = resultado.scalars().all()

        assert len(eventos) == 1
        salvo = eventos[0]
        assert salvo.origem == "chat"
        assert salvo.ambiente == "interno"
        assert salvo.modelo == "clip"
        assert salvo.operacao == "identificacao_imagem_clip"
        # Defaults: "não se aplica" é 0/0.0, nunca None.
        assert salvo.tokens_entrada == 0
        assert salvo.tokens_saida == 0
        assert salvo.custo_usd == 0.0
        assert salvo.referencia_id is None
        assert salvo.criado_em is not None
    finally:
        await engine.dispose()
