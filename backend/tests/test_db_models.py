from app.db.engine import create_db_engine, create_session_factory
from app.db.models import Base, ModelCharacteristics, TomEscalonamento


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


async def test_model_characteristics_tem_colunas_esperadas():
    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)

    async with factory() as session:
        registro = ModelCharacteristics(
            source="openrouter",
            tag="meta-llama/llama-2-7b-chat",
            is_multimodal=False,
            input_modalities=["text"],
            output_modalities=["text"],
            context_length=4096,
            parameter_size="7B",
            quantization="q4",
            pricing_prompt_per_1k=0.0007,
            pricing_completion_per_1k=0.0009,
            knowledge_cutoff="2023-08",
            raw_payload={"model": "llama-2-7b", "version": "1.0"},
        )
        session.add(registro)
        await session.commit()
        await session.refresh(registro)

        assert registro.id is not None
        assert registro.source == "openrouter"
        assert registro.tag == "meta-llama/llama-2-7b-chat"
        assert registro.is_multimodal is False
        assert registro.input_modalities == ["text"]
        assert registro.output_modalities == ["text"]
        assert registro.context_length == 4096
        assert registro.parameter_size == "7B"
        assert registro.quantization == "q4"
        assert registro.pricing_prompt_per_1k == 0.0007
        assert registro.pricing_completion_per_1k == 0.0009
        assert registro.knowledge_cutoff == "2023-08"
        assert registro.raw_payload == {"model": "llama-2-7b", "version": "1.0"}
        assert registro.fetched_at is not None

    await engine.dispose()
