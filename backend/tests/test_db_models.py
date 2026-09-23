from app.db.models import Base, TomEscalonamento
from app.db.engine import create_db_engine, create_session_factory


async def test_tom_escalonamento_tem_colunas_esperadas():
    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)

    async with factory() as session:
        registro = TomEscalonamento(
            conversation_id="conv-1",
            mensagem="preciso falar com um atendente AGORA",
            motivo="urgencia",
            confianca=0.9,
            provider_efetivo="heuristica_llm",
        )
        session.add(registro)
        await session.commit()
        await session.refresh(registro)

        assert registro.id is not None
        assert registro.conversation_id == "conv-1"
        assert registro.criado_em is not None

    await engine.dispose()
