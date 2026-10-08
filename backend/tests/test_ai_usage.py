"""Ledger unificado de uso de IA (origem × ambiente × modelo) —
`app.services.ai_usage` / `app.db.models.AiUsageEvent`. Ver
docs/superpowers/specs/2026-10-08-ledger-uso-ia-origem-ambiente-modelo-design.md.
"""

import logging

from sqlalchemy import select

from app.db.engine import create_db_engine, create_session_factory
from app.db.models import AiUsageEvent, Base
from app.services.ai_usage import registrar_uso_ia, set_global_sessionmaker


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


async def test_registrar_uso_ia_com_session_explicita_grava():
    engine, factory = await _engine_e_sessionmaker_vazios()
    try:
        async with factory() as session:
            evento = await registrar_uso_ia(
                origem="chat",
                ambiente="externo",
                modelo="gpt-4o-mini",
                operacao="geracao_texto",
                tokens_entrada=120,
                tokens_saida=40,
                custo_usd=0.0021,
                referencia_id="conv-123",
                session=session,
                commit=True,
            )
            assert evento is not None

        async with factory() as session:
            resultado = await session.execute(select(AiUsageEvent))
            salvos = resultado.scalars().all()
        assert len(salvos) == 1
        assert salvos[0].referencia_id == "conv-123"
        assert salvos[0].custo_usd == 0.0021
    finally:
        await engine.dispose()


async def test_registrar_uso_ia_com_session_factory_fire_and_forget_grava():
    engine, factory = await _engine_e_sessionmaker_vazios()
    try:
        evento = await registrar_uso_ia(
            origem="admin",
            ambiente="externo",
            modelo="gemini-2.5-flash",
            operacao="extracao_catalogo_visao",
            session_factory=factory,
        )
        assert evento is not None

        async with factory() as session:
            resultado = await session.execute(select(AiUsageEvent))
            salvos = resultado.scalars().all()
        assert len(salvos) == 1
        assert salvos[0].origem == "admin"
    finally:
        await engine.dispose()


async def test_registrar_uso_ia_sem_session_nem_factory_usa_fallback_global():
    engine, factory = await _engine_e_sessionmaker_vazios()
    try:
        set_global_sessionmaker(factory)
        try:
            evento = await registrar_uso_ia(
                origem="chat",
                ambiente="externo",
                modelo="jev",
                operacao="classificacao_jev",
            )
            assert evento is not None
        finally:
            set_global_sessionmaker(None)

        async with factory() as session:
            resultado = await session.execute(select(AiUsageEvent))
            salvos = resultado.scalars().all()
        assert len(salvos) == 1
        assert salvos[0].modelo == "jev"
    finally:
        await engine.dispose()


async def test_registrar_uso_ia_sem_nenhuma_sessao_disponivel_devolve_none_sem_lancar():
    set_global_sessionmaker(None)
    evento = await registrar_uso_ia(
        origem="chat",
        ambiente="interno",
        modelo="clip",
        operacao="identificacao_imagem_clip",
    )
    assert evento is None


async def test_registrar_uso_ia_com_factory_que_falha_devolve_none_e_loga(caplog):
    class _SessionFactoryQuebrada:
        def __call__(self):
            return self

        async def __aenter__(self):
            raise ConnectionError("sem banco nos testes")

        async def __aexit__(self, *exc_info):
            return False

    with caplog.at_level(logging.WARNING, logger="assistente.ai_usage"):
        evento = await registrar_uso_ia(
            origem="b2b",
            ambiente="externo",
            modelo="gpt-4o-mini",
            operacao="comprovante_visao",
            session_factory=_SessionFactoryQuebrada(),
        )

    assert evento is None
    assert any("Falha ao registrar AiUsageEvent" in r.message for r in caplog.records)
